"""Controller-owned media request fields, independent of sentence templates.

This reads explicit owner verbs/service/title fields. It never selects a result,
supplies a URL, or executes an action. A later model proposal still uses the broker.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NamedMediaRequest:
    service: str
    goal: str
    query: str


def request_body(text):
    value = " ".join(text.strip().rstrip(".!?").split())
    for _ in range(3):
        value = re.sub(r"(?i)^(?:hey\s+)?jarvis[, ]+", "", value)
        value = re.sub(r"(?i)^(?:can|could|would|will) you\s+(?:please\s+)?", "", value)
        value = re.sub(r"(?i)^(?:i(?:'d| would) like|i want) (?:you to |to )", "", value)
        value = re.sub(r"(?i)^please\s+", "", value)
        value = re.sub(r"(?i)^let me\s+", "", value)
    return re.sub(r"(?i),?\s+please$", "", value)


def capability_question(text):
    return bool(
        re.match(
            r"(?i)^(?:can|could|are)\s+you\s+(?:control|support|use|access|operate|manage|able|capable)\b"
            r"|^(?:what (?:can you do|are your capabilities)|do you (?:support|have))\b",
            text.strip(),
        )
    )


def public_research_request(text):
    value = request_body(text)
    return bool(
        re.match(r"(?i)^(?:search|find|look|browse)\b", value)
        and re.search(r"(?i)\b(?:web|online|internet|sources|information|documentation)\b", value)
    )


def named_media_request(text, *, default_service=None):
    value = request_body(text)
    if public_research_request(text):
        return None
    # Negation, explanatory/quoted instructions and unrelated chains never become
    # authority. These are operation ceilings, rather than exact sentence matches.
    if re.search(
        r"(?i)^(?:do not|don't|never|how|why|explain|tell me|imagine|suppose|if)\b"
        r"|[;`]|\b(?:but don't|but do not|without playing|password|javascript|"
        r"ignore (?:the |your )?rules)\b",
        value,
    ):
        return None
    operation = re.match(
        r"(?i)^(play|put on|listen to|watch|show me|open|find|search|look for)\b\s*(.*)", value
    )
    if not operation:
        return None
    verb, query = operation[1].casefold(), operation[2].strip()
    services = {s.casefold() for s in re.findall(r"(?i)\b(youtube|spotify|netflix)\b", query)}
    if len(services) > 1:
        return None
    service = next(iter(services), default_service)
    if service not in {"spotify", "youtube"}:
        return None
    goal = (
        "search"
        if verb in {"find", "search", "look for"}
        else "open"
        if verb in {"open", "show me"}
        else "play"
    )
    # A service is a field: it can precede or follow the title, with or without
    # a preposition. Preserve artist/owner text, including 'by Spotify'.
    query = re.sub(rf"(?i)^(?:(?:on|in)\s+)?{service}\b\s*(?:for\s+)?", "", query)
    query = re.sub(rf"(?i)(?<!by)\s+(?:(?:on|in|using|with)\s+)?{service}$", "", query)
    query = re.sub(r"(?i)^(?:for|up)\s+", "", query)
    if goal == "open" and re.fullmatch(r"(?i)(?:the |my )?(?:app|application|window|home)?", query):
        return None
    chain = re.search(r"(?i)\s+(?:and|then)\s+(?:play|watch|open)(?: it| the video)?$", query)
    if chain and goal == "search":
        goal = "play" if re.search(r"(?i)\b(?:play|watch)\b", chain[0]) else "open"
        query = query[: chain.start()].strip()
    elif re.search(r"(?i)^and\s+play\s+", query) and verb in {"search", "open"}:
        goal, query = "play", re.sub(r"(?i)^and\s+play\s+", "", query)
    if re.search(
        r"(?i)\b(?:and|then)\s+(?:open|play|pause|resume|search|find|close|buy|delete)\b", query
    ):
        return None
    query = re.sub(r"(?i)^(?:a |the |my )?(?:song|track|video) (?:called |named )?", "", query)
    query = re.sub(r"(?i)^videos? (?:from|by|of)\s+", "", query)
    query = re.sub(r"(?i)^(?:my |the |a )?playlist (?:called |named )?", "playlist ", query)
    if re.fullmatch(
        r"(?i)(?:|it|this|that|music|spotify|youtube|a song|a playlist|playlist|the song|"
        r"the playlist|the video|(?:the )?(?:first|second|third|[1-5]) (?:result|video))",
        query,
    ):
        return None
    return NamedMediaRequest(service, goal, query)
