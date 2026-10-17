"""Private two-model handoff; no actual screen, network or desktop effects."""

import json

import httpx
import pytest

from jarvis.bootstrap import ManualClock, build
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import State
from jarvis.models import FakeProvider, ModelReply, OllamaProfile, Profile
from jarvis.screen_answer import LocalScreenAnswer, parse
from jarvis.screen_data import Interpretation, ScreenConfig
from jarvis.screen_fake import FakeCapture, FakeIndicator, FakeVision
from jarvis.screen_tools import attach


class ChatProvider(FakeProvider):
    def __init__(self, clock):
        super().__init__(clock)
        self.requests = []
        self.transform = lambda data: data
        self.after = lambda: None

    def generate(self, request, cancel):
        self.requests.append(request)
        self.calls += 1
        if request.decision_boundary == "screen-answer-v1":
            data = self.transform(
                {
                    "kind": "screen_answer",
                    "observation_id": request.schema["properties"]["observation_id"]["const"],
                    "text": "You're looking at a synthetic test application.",
                    "evidence_ids": ["v0"],
                }
            )
        else:
            data = {"kind": "say", "text": "Four."}
        self.after()
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        return ModelReply(
            request.request_id,
            request.task_id,
            request.revision,
            raw,
            request.profile.model_identity,
        )


@pytest.fixture
def handoff(tmp_path):
    clock = ManualClock()
    provider = ChatProvider(clock)
    broker = build(
        tmp_path / "journal",
        Profile(
            profile_name="fixture",
            model_identity="fixture:chat",
            reply='{"kind":"say","text":"Fixture"}',
        ),
        clock,
        provider=provider,
    )
    capture, vision, indicator = FakeCapture(clock), FakeVision(), FakeIndicator()
    screen = attach(
        broker,
        ScreenConfig(
            enabled=True, vision_model="fixture:vision", default_capture_scope="foreground_window"
        ),
        capture=capture,
        vision=vision,
        indicator=indicator,
    )
    yield broker, screen, capture, vision, indicator, provider, clock
    screen.close()
    broker.store.close()
    broker.provider.close()


def test_bound_observation_natural_text_and_no_action_authority(handoff):
    broker, screen, capture, vision, _, provider, _ = handoff
    assert isinstance(screen.answerer, LocalScreenAnswer)
    result = Conversation(broker).submit("What am I looking at?")
    assert result.state == State.SUCCEEDED
    assert conversational_text(result) == "You're looking at a synthetic test application."
    assert capture.calls == vision.calls == provider.calls == 1
    request = provider.requests[0]
    assert request.profile.model_identity == "fixture:chat"
    assert request.messages[-1].text == "What am I looking at?"
    assert request.messages[1].role == "untrusted_data"
    assert screen.answer_status == "generated" and len(screen.dialogue) == 1
    assert broker.desktop.execution_calls == 0 and broker.last_reply is None
    assert {r[0] for r in broker.store.db.execute("SELECT capability FROM actions")} == {
        "screen.observe"
    }


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b"bad",
        b"x" * 32769,
        b'{"kind":"screen_answer","kind":"say"}',
        b'{"text":NaN}',
        b'{"kind":"propose_action","action":{"capability":"apps.open"}}',
    ],
    ids=["empty", "array", "bad", "oversized", "duplicate", "nonfinite", "action"],
)
def test_whole_boundary_rejects_invalid_and_action_responses(raw):
    with pytest.raises(ValueError):
        parse(raw)


@pytest.mark.parametrize(
    "change",
    [
        {"observation_id": "older"},
        {"evidence_ids": ["invented"]},
        {"evidence_ids": []},
        {"approved": True},
        {"text": " "},
        {"text": "I clicked the button."},
        {"text": "I have uploaded it."},
        {"kind": "propose_action"},
    ],
)
def test_unbound_and_privileged_output_falls_back_without_logging_private_data(handoff, change):
    broker, screen, _, vision, _, provider, _ = handoff
    vision.result = Interpretation(description="PRIVATE_OBSERVATION")
    provider.transform = lambda data: {**data, **change}
    result = screen.submit("Read my screen")
    assert result.state == State.SUCCEEDED  # Capture is independently verified.
    assert conversational_text(result).startswith("From the captured image: PRIVATE_OBSERVATION")
    assert "couldn't finish the explanation" in conversational_text(result)
    assert screen.answer_status.startswith("fallback/")
    dump = "\n".join(broker.store.db.iterdump())
    assert "PRIVATE_OBSERVATION" not in dump and "Read my screen" not in dump
    assert '"code":"INVALID_ANSWER"' in dump
    assert broker.desktop.execution_calls == 0 and provider.calls == 1


@pytest.mark.parametrize("phase", ["cancel", "indicator", "target", "profile", "expiry"])
def test_invalidation_during_handoff_prevents_publication(handoff, phase):
    broker, screen, capture, _, indicator, provider, clock = handoff
    if phase == "cancel":
        provider.after = lambda: setattr(broker, "cancel_requested", lambda: True)
    elif phase == "indicator":
        provider.after = lambda: setattr(indicator, "alive", False)
    elif phase == "target":
        provider.after = lambda: setattr(capture, "changed", True)
    elif phase == "profile":
        provider.after = lambda: setattr(
            broker, "profile", broker.profile.model_copy(update={"profile_name": "changed"})
        )
    else:
        provider.after = lambda: clock.advance(200)
    result = screen.submit("Read my screen")
    assert result.state != State.SUCCEEDED
    assert screen.observation is None and not screen.dialogue
    assert "synthetic test application" not in conversational_text(result)
    assert capture.calls == provider.calls == 1


def test_short_answer_timeout_preserves_observation_and_accurate_age(handoff):
    _, screen, _, _, _, provider, clock = handoff
    provider.after = lambda: clock.advance(31)
    result = screen.submit("Read my screen")
    assert result.state == State.SUCCEEDED
    assert "captured 31 seconds ago" in conversational_text(result)
    assert "couldn't finish the explanation" in conversational_text(result)
    assert provider.calls == 1


def test_uncertainty_and_unreadable_warnings_survive_chat(handoff):
    _, screen, _, vision, _, _, _ = handoff
    vision.result = Interpretation(
        description="A game may be open.",
        uncertainty=["The game title is uncertain."],
        unreadable_regions=["tiny title"],
    )
    text = conversational_text(screen.submit("Read my screen"))
    assert "The game title is uncertain." in text and "tiny title" in text


def test_private_context_is_bounded_and_never_enters_general_chat_or_journal(handoff):
    broker, screen, capture, vision, _, provider, _ = handoff
    vision.result = Interpretation(description="PRIVATE_VISUAL_CANARY")
    provider.transform = lambda data: {**data, "text": "PRIVATE_DERIVED_CANARY"}
    chat = Conversation(broker)
    chat.submit("Read my screen")
    chat.submit("Tell me more about it")
    assert chat.history == [] and capture.calls == 2
    data = json.loads(provider.requests[-1].messages[1].text)
    assert data["recent_context"]["screen"][0]["answer"] == "PRIVATE_DERIVED_CANARY"
    for _ in range(3):
        chat.submit("Read my screen")
    assert len(screen.dialogue) == 2
    chat.submit("What is two plus two?")
    assert not screen.dialogue
    assert "PRIVATE_" not in repr(provider.requests[-1].messages)
    assert "PRIVATE_" not in repr(chat.history)
    assert "PRIVATE_" not in "\n".join(broker.store.db.iterdump())
    screen.clear()
    assert not screen.dialogue and screen.observation is None


def test_expired_or_other_target_context_is_not_shared(handoff):
    _, screen, capture, _, _, provider, clock = handoff
    screen.submit("Read my screen")
    clock.advance(31)
    assert not screen.has_dialogue()
    screen.submit("Read my screen")
    capture.target = capture.target.model_copy(update={"identity": "e" * 64})
    screen.submit("Read my screen")
    data = json.loads(provider.requests[-1].messages[1].text)
    assert data["recent_context"]["screen"] == []


def test_duplicate_delivery_does_not_repeat_models_or_capture(handoff):
    _, screen, capture, vision, _, provider, _ = handoff
    first = screen.submit("Read my screen", "delivery")
    again = screen.submit("Read my screen", "delivery")
    assert conversational_text(first) == conversational_text(again)
    assert capture.calls == vision.calls == provider.calls == 1


def test_disabled_handoff_and_wordle_remain_deterministic(handoff):
    _, screen, _, _, _, provider, _ = handoff
    screen.config = screen.config.model_copy(update={"chat_answer_enabled": False})
    assert screen.submit("Read my screen").state == State.SUCCEEDED and provider.calls == 0
    screen.config = screen.config.model_copy(update={"chat_answer_enabled": True})
    assert "cannot reliably read" in conversational_text(screen.submit("Help me solve Wordle"))
    assert provider.calls == 0


def test_combined_application_conversation_uses_same_private_handoff(handoff):
    from jarvis.application_tools import ApplicationConversation
    from jarvis.models import Message

    broker, screen, _, _, _, provider, _ = handoff
    chat = ApplicationConversation(broker, object())
    chat.original.history = [Message("owner", "Explain things simply.")]
    result = chat.submit("Read my screen")
    assert result.state == State.SUCCEEDED and screen.answer_status == "generated"
    data = json.loads(provider.requests[0].messages[1].text)
    assert data["recent_context"]["conversation"][0]["text"] == "Explain things simply."
    assert len(chat.original.history) == 1


def test_context_budget_stops_handoff_before_any_text_model_call(handoff):
    broker, screen, _, _, _, provider, _ = handoff
    broker.profile = broker.profile.model_copy(update={"context_bytes": 1024})
    result = screen.submit("Read my screen")
    assert result.state == State.SUCCEEDED
    assert screen.answer_status == "fallback/CONTEXT_LIMIT" and provider.calls == 0


def test_primary_transport_uses_text_only_fixed_loopback_and_no_tools(handoff):
    broker, screen, _, _, _, _, clock = handoff
    from jarvis.ollama import OllamaProvider

    seen = []

    def handler(request):
        assert str(request.url).startswith("http://127.0.0.1:11434/")
        payload = json.loads(request.content) if request.content else {}
        if request.url.path == "/api/version":
            data = {"version": "synthetic"}
        elif request.url.path == "/api/tags":
            data = {"models": [{"name": "fixture:chat", "digest": "d" * 64}]}
        elif request.url.path == "/api/show":
            data = {"capabilities": ["completion"], "model_info": {}}
        else:
            seen.append(payload)
            answer = {
                "kind": "screen_answer",
                "observation_id": payload["format"]["properties"]["observation_id"]["const"],
                "text": "A test application is visible.",
                "evidence_ids": ["v0"],
            }
            data = {
                "model": "fixture:chat",
                "done": True,
                "message": {"role": "assistant", "content": json.dumps(answer)},
            }
        return httpx.Response(200, json=data)

    broker.profile = OllamaProfile(
        provider="ollama",
        network_mode="local_model_only",
        profile_name="synthetic",
        model_identity="fixture:chat",
        cloud_disabled_verified=True,
        cloud_disabled_evidence="synthetic fixture",
        provider_options={"think": False, "keep_alive": "0"},
    )
    broker.provider = OllamaProvider(clock, httpx.MockTransport(handler))
    assert screen.submit("Read my screen").state == State.SUCCEEDED
    assert screen.answer_status == "generated" and len(seen) == 1
    assert seen[0]["model"] == "fixture:chat" and "tools" not in seen[0]
    assert "images" not in repr(seen[0]["messages"]) and seen[0]["think"] is False
    assert seen[0]["messages"][-1]["content"] == "Read my screen"
    assert "UNTRUSTED DATA" in seen[0]["messages"][1]["content"]
    assert broker.desktop.execution_calls == 0
