"""Bounded owner-requested YouTube workflow; every effect uses the existing broker."""

import re
from dataclasses import replace
from uuid import uuid4

from jarvis.domain import Denied, State, TaskResult
from jarvis.media_tools import owner_operation


def named_request(text):
    value = text.strip().rstrip(".!?")
    value = re.sub(r"(?i)^(?:please |(?:can|could|would) you (?:please )?)", "", value)
    services = {s.casefold() for s in re.findall(r"(?i)\b(youtube|spotify|netflix)\b", value)}
    if services != {"youtube"} or re.search(
        r"(?i)\b(?:do not|don't|how (?:do|can)|explain|like|subscribe|comment|upload|download|"
        r"buy|rent|password|javascript|click|type)\b",
        value,
    ):
        return None
    patterns = [
        ("play", r"search (?:on )?youtube and play (.+)"),
        ("play", r"(?:search|find) (?:on )?youtube for (.+?) (?:and|then) play(?: it| the video)?"),
        ("play", r"play (.+?) (?:on|in) youtube"),
        ("open", r"open (?:videos? (?:from|by|of) )?(.+?) (?:on|in) youtube"),
    ]
    for goal, pattern in patterns:
        match = re.fullmatch(pattern, value, re.I)
        if not match:
            continue
        query = match[1].strip()
        if re.fullmatch(
            r"(?i)(?:it|this|that|the video|"
            r"(?:the )?(?:first|second|third|[1-5]) (?:result|video))",
            query,
        ):
            return None
        if re.search(
            r"(?i)\b(?:and|then)\s+(?:open|play|pause|resume|search|find|close|buy)\b|;", query
        ):
            return None
        return goal, query
    return None


class YouTubeFlow:
    service = "youtube"
    service_name = "YouTube"
    noun = "video"
    named_request = staticmethod(named_request)

    def matching_words(self, query):
        return set(re.findall(r"\w+", query.casefold()))

    def matches_item(self, query, item):
        words = self.matching_words(query)
        return bool(words) and words <= set(
            re.findall(r"\w+", (item.title + " " + item.creator).casefold())
        )

    def __init__(self, conversation):
        self.chat = conversation
        self.pending = None
        self.receipts = {}

    def submit(self, text, request_key=None):
        adapter = self.chat.broker.media
        if adapter is None:
            return self.chat._submit_single(text, request_key)
        key = request_key or str(uuid4())
        if key in self.receipts:
            previous_text, previous_result = self.receipts[key]
            if text != previous_text:
                raise Denied("Request identity reused with different content")
            return previous_result
        original_text = text
        named = self.named_request(text)
        pending = self.pending
        if named:
            self.pending = None
            goal, query = named
            before = adapter.generation
            deadline = self.chat.broker.clock.now() + self.chat.broker.profile.task_seconds
            result = self.chat._submit_single(
                "Search " + self.service_name + " for " + query, key + "/search"
            )
            if (
                result.state == State.SUCCEEDED
                and adapter.observation is not None
                and adapter.observation.state == "results"
                and adapter.generation > before
                and adapter.results
                and self.chat.broker.clock.now() < deadline
            ):
                self.pending = (
                    goal,
                    adapter.generation,
                    adapter.session_ref,
                    adapter.owner_session,
                    deadline,
                )
                matches = [
                    i for i, item in enumerate(adapter.results, 1) if self.matches_item(query, item)
                ]
                if len(matches) == 1 and goal != "search":
                    self.pending = None
                    result = self._open_and_play(
                        "Open the " + str(matches[0]) + " result", key, goal, deadline
                    )
                elif goal == "play":
                    message = result.display_message or result.message
                    result = replace(
                        result,
                        display_message=message.removesuffix("Which one should I open?")
                        + f"Which {self.noun} should I play? Choose its number.",
                    )
        elif pending and owner_operation(text) == "open":
            self.pending = None
            goal, generation, session, owner, deadline = pending
            if (
                adapter.generation == generation
                and adapter.session_ref == session
                and adapter.owner_session == owner == self.chat.broker.grant.session
                and adapter.service == self.service
                and self.chat.broker.clock.now() < deadline
            ):
                selection = text.strip().casefold().rstrip(".!?")
                if re.fullmatch(r"[1-5]", selection):
                    text = "Open the " + selection + " result"
                result = self._open_and_play(text, key, goal, deadline)
                if result.state == State.WAITING_INPUT:
                    self.pending = pending
            else:
                result = TaskResult(
                    "",
                    State.WAITING_INPUT,
                    f"The {self.service_name} results changed or the request expired. "
                    f"Search again before choosing a {self.noun}.",
                    decision_kind="clarify",
                )
        else:
            self.pending = None
            result = self.chat._submit_single(text, key)
        self.receipts[key] = (original_text, result)
        while len(self.receipts) > 16:
            del self.receipts[next(iter(self.receipts))]
        return result

    def _open_and_play(self, text, key, goal, deadline):
        result = self.chat._submit_single(text, key + "/open")
        adapter = self.chat.broker.media
        if result.state != State.SUCCEEDED or goal != "play":
            return result
        if adapter.observation is None or adapter.observation.state == "ad":
            return result
        if self.chat.broker.clock.now() >= deadline:
            return replace(
                result,
                display_message=f"The {self.noun} was selected; the playback request expired. "
                "Ask me to play it when ready.",
            )
        # Separate scoped model proposal, journal, single-use approval, stop and
        # verification for play; this orchestration never dispatches an effect.
        played = self.chat._submit_single("Play it on " + self.service_name, key + "/play")
        if played.state != State.SUCCEEDED:
            played = replace(
                played,
                display_message=f"The {self.noun} was selected, but "
                + (played.display_message or played.message).removeprefix("SIMULATED: "),
            )
        return played
