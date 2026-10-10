"""Regressions for the operator's transcript, without desktop effects."""

import json

import pytest

from jarvis.bootstrap import ManualClock, build
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import State, UserRequest
from jarvis.models import Profile


@pytest.fixture
def broker(tmp_path):
    profile = Profile(
        profile_name="truth-fixture",
        model_identity="scripted",
        prompt_version="planner-m2-v10",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    value = build(tmp_path / "journal.sqlite", profile, ManualClock())
    value.desktop.transport.add()
    ref = value.desktop.inventory()[0]["window_ref"]
    value.desktop.select(ref)
    yield value
    value.store.close()
    value.provider.close()


def reply(broker, decision):
    broker.profile = broker.profile.model_copy(update={"reply": json.dumps(decision)})


def focus(broker):
    reply(
        broker,
        {
            "kind": "propose_action",
            "action": {
                "capability": "windows.focus",
                "arguments": {"window_ref": broker.desktop.selected_ref},
            },
        },
    )


@pytest.mark.parametrize(
    "text",
    [
        "I've brought the Notepad window to the front.",
        "I've brought the Notepad window to the front again.",
        "I closed Notepad.",
        "The selected Notepad window is in the foreground.",
        "The window has been closed.",
        "Your text editor is now focused.",
    ],
)
def test_model_prose_cannot_claim_an_effect(broker, text):
    reply(broker, {"kind": "say", "text": text})
    result = Conversation(broker).submit("the only one that is open now")
    assert "haven't performed" in conversational_text(result)
    assert broker.desktop.execution_calls == 0
    assert result.state == State.ANSWERED


@pytest.mark.parametrize(
    "text",
    [
        "bring the text editor to the front",
        "bring it to the front again",
    ],
)
def test_reported_phrases_reach_verified_focus(broker, text):
    focus(broker)
    result = Conversation(broker).submit(text)
    assert result.state == State.SUCCEEDED
    assert broker.desktop.execution_calls == 1
    assert broker.desktop.observation_calls == 1


def test_clarification_is_bound_to_selected_window_and_previous_effect(broker):
    conversation = Conversation(broker)
    reply(broker, {"kind": "clarify", "question": "Which window?"})
    assert conversation.submit("bring a window to the front").state == State.WAITING_INPUT
    focus(broker)
    assert conversation.submit("the only one that is open now").state == State.SUCCEEDED
    assert broker.desktop.execution_calls == 1


@pytest.mark.parametrize("change", ["second-window", "gone", "intervening-turn"])
def test_clarification_cannot_guess_or_survive_changed_context(broker, change):
    conversation = Conversation(broker)
    reply(broker, {"kind": "clarify", "question": "Which window?"})
    conversation.submit("bring a window to the front")
    if change == "second-window":
        broker.desktop.transport.add()
    elif change == "gone":
        broker.desktop.transport.records.clear()
    else:
        reply(broker, {"kind": "say", "text": "Hello"})
        conversation.submit("Hello")
    reply(broker, {"kind": "say", "text": "I've brought the window to the front."})
    result = conversation.submit("the only one that is open now")
    assert broker.desktop.execution_calls == 0
    assert "haven't performed" in conversational_text(result)


def test_unknown_outcome_stays_blocked_and_identifies_review(broker):
    broker.desktop.blocked_unknown = True
    broker.desktop.review_task_id = "uncertain-task"
    focus(broker)
    result = broker.converse(UserRequest("blocked", "demo-session", "Focus Notepad"))
    assert result.state == State.WAITING_INPUT
    assert "/review uncertain-task manually-handled" in result.message
    assert broker.desktop.execution_calls == 0
