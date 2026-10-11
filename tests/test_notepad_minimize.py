"""Minimize stays within the selected registered window and broker admission."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from jarvis.action_language import unverified_completion
from jarvis.bootstrap import ManualClock, build
from jarvis.domain import State, UserRequest
from jarvis.models import Profile
from jarvis.notepad_intent_v2 import interpret


@pytest.fixture
def broker(tmp_path):
    profile = Profile(
        profile_name="minimize-fixture",
        model_identity="scripted",
        prompt_version="planner-m2-v10",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    value = build(tmp_path / "journal.sqlite", profile, ManualClock())
    yield value
    value.store.close()
    value.provider.close()


def submit(broker, text, effect="minimize", key=None):
    ref = broker.desktop.selected_ref
    broker.profile = broker.profile.model_copy(
        update={
            "reply": json.dumps(
                {
                    "kind": "propose_action",
                    "action": {"capability": "windows." + effect, "arguments": {"window_ref": ref}},
                }
            )
        }
    )
    return broker.converse(UserRequest(key or text, "demo-session", text))


def select(broker):
    record = broker.desktop.transport.add(empty=False, tabs=2)
    record["modified"] = True
    ref = broker.desktop.inventory()[0]["window_ref"]
    broker.desktop.select(ref)
    return record


@pytest.mark.parametrize(
    "text",
    [
        "Minimize Notepad.",
        "minimize it",
        "Could you please minimise my text editor?",
        "minimize that window",
    ],
)
def test_minimize_dirty_selected_window_and_restore(broker, text):
    record = select(broker)
    other = broker.desktop.transport.add()
    snapshot = deepcopy(other)
    result = submit(broker, text)
    assert result.state == State.SUCCEEDED
    assert "minimized" in result.message
    assert record["minimized"] is True
    assert other == snapshot and len(broker.desktop.transport.records) == 2
    assert not broker.desktop.confirmed
    assert submit(broker, "bring it to the front", "focus").state == State.SUCCEEDED
    assert record["minimized"] is False
    assert broker.desktop.transport.focus == record["hwnd"]
    assert broker.store.result(result.task_id).state == State.SUCCEEDED


@pytest.mark.parametrize("change", ["cancel", "revoke", "takeover", "identity", "dialog", "stop"])
def test_late_admission_blocks_minimize(broker, change):
    record = select(broker)

    def mutate():
        if change == "cancel":
            task = broker.store.db.execute(
                "SELECT task_id FROM tasks WHERE state='RUNNING'"
            ).fetchone()[0]
            broker.store.cancel(task)
        elif change == "revoke":
            broker.revoke_grant()
        elif change == "takeover":
            broker.desktop.transport.input_tick += 1
        elif change == "identity":
            record["created"] += 1
        elif change == "dialog":
            record["owned_dialog"] = True
        else:
            broker.desktop.stop.set()
            broker.cancel_requested = broker.desktop.stop.is_set

    broker.desktop.transport.before_effect = mutate
    assert submit(broker, "minimize notepad").state != State.SUCCEEDED
    assert not broker.desktop.transport.calls and not record["minimized"]


@pytest.mark.parametrize("field", ["owned_dialog", "enabled"])
def test_modal_or_disabled_target_never_minimized(broker, field):
    record = select(broker)
    record[field] = field == "owned_dialog"
    assert submit(broker, "minimize notepad").state == State.WAITING_INPUT
    assert not broker.desktop.transport.calls


def test_minimize_missing_permission_is_rejected(broker):
    select(broker)
    broker.grant = replace(broker.grant, effects=frozenset({"open", "focus", "close"}))
    assert submit(broker, "minimize notepad").state == State.FAILED
    assert not broker.desktop.transport.calls


def test_minimize_requires_observed_postcondition(broker):
    record = select(broker)
    broker.desktop.transport.apply = False
    result = submit(broker, "minimize notepad")
    assert result.state != State.SUCCEEDED and not record["minimized"]
    assert "is minimized" not in result.message


def test_unknown_minimize_never_replayed(broker):
    select(broker)
    broker.desktop.transport.crash = True
    assert submit(broker, "minimize notepad").state == State.NEEDS_REVIEW
    broker.desktop.transport.crash = False
    assert submit(broker, "minimize notepad", key="again").state == State.WAITING_INPUT
    assert broker.desktop.transport.calls == ["minimize"]


@pytest.mark.parametrize(
    "text",
    [
        "do not minimize notepad",
        "minimize notepad and close it",
        "what does minimize notepad mean?",
        "minimize every app",
    ],
)
def test_words_do_not_authorize_effect(broker, text):
    select(broker)
    assert submit(broker, text).state != State.SUCCEEDED
    assert not broker.desktop.transport.calls


def test_other_app_remains_unregistered():
    assert interpret("minimize spotify").target == "unregistered"
    assert interpret("minimize notepad").effect == "minimize"


@pytest.mark.parametrize(
    "text", ["I've minimized Notepad", "Notepad is minimized", "The selected window was minimised"]
)
def test_prose_is_not_minimize_evidence(text):
    assert unverified_completion(text)


def test_historical_profile_cannot_grant_unevaluated_minimize(broker, tmp_path):
    from jarvis.bootstrap import build

    profile = broker.profile.model_copy(update={"prompt_version": "planner-m2-v1"})
    prior = build(tmp_path / "legacy.sqlite", profile, broker.clock)
    try:
        assert "minimize" not in prior.grant.effects
    finally:
        prior.store.close()
        prior.provider.close()
