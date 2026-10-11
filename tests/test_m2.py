"""M2 broker regressions use synthetic windows only; never native/Ollama calls."""

import json
from dataclasses import replace

import pytest

from jarvis.bootstrap import ManualClock, build
from jarvis.domain import Approval, Handoff, State, UserRequest
from jarvis.models import Profile, parse_decision


@pytest.fixture
def broker(tmp_path):
    profile = Profile(
        profile_name="m2-fixture",
        model_identity="scripted-m2",
        prompt_version="planner-m2-v1",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    value = build(tmp_path / "m2.sqlite", profile, ManualClock())
    yield value
    value.store.close()
    value.provider.close()


def submit(broker, text, capability="apps.open", ref="", key=None):
    args = {"app_id": "notepad"} if capability == "apps.open" else {"window_ref": ref}
    broker.profile = broker.profile.model_copy(
        update={
            "reply": json.dumps(
                {"kind": "propose_action", "action": {"capability": capability, "arguments": args}}
            )
        }
    )
    return broker.converse(UserRequest(key or text, "demo-session", text))


def opened(broker):
    assert submit(broker, "Open Notepad.").state == State.SUCCEEDED
    ref = broker.desktop.selected_ref
    broker.desktop.select(ref, confirm_disposable=True)
    return ref


def test_real_gate_requires_explicit_consent_and_registration(broker, tmp_path):
    with pytest.raises(ValueError, match="Real mode requires"):
        build(tmp_path / "other.sqlite", broker.profile, real=True)
    assert not broker.desktop.real and broker.desktop.transport.calls == []


def test_open_focus_close_and_independent_evidence(broker):
    ref = opened(broker)
    assert (
        submit(broker, "Bring that Notepad window to the front.", "windows.focus", ref).state
        == State.SUCCEEDED
    )
    assert broker.desktop.transport.focus == broker.desktop.windows[ref]["hwnd"]
    closed = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert closed.state == State.SUCCEEDED and not broker.desktop.transport.records
    assert broker.desktop.transport.calls == ["open", "focus", "close"]
    assert broker.desktop.observation_calls == 3
    proof = json.loads(
        broker.store.db.execute(
            "SELECT evidence_json FROM attempts p JOIN actions a ON p.action_id=a.action_id "
            "WHERE a.task_id=?",
            (closed.task_id,),
        ).fetchone()[0]
    )
    assert json.loads(proof["observed_identity"])["present"] is False
    broker.store.result(closed.task_id)  # Durable close evidence is validated independently.


@pytest.mark.parametrize(
    "change", ["empty", "tabs", "unknown", "dialog", "modified", "modified_unknown"]
)
def test_close_handoff_before_effect_for_unsafe_window(broker, change):
    ref = opened(broker)
    record = broker.desktop.transport.records[0]
    if change == "empty":
        record["empty"] = False
    elif change == "tabs":
        record["tab_ids"].append([99])
    elif change == "unknown":
        record["empty"] = None
    elif change == "dialog":
        record["owned_dialog"] = True
    elif change == "modified":
        record["modified"] = True
    elif change == "modified_unknown":
        record["modified"] = None
    else:
        broker.desktop.confirmed.clear()
    result = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert result.state == State.WAITING_INPUT
    assert "no close was sent" in result.message
    assert broker.desktop.transport.calls == ["open"]
    assert broker.store.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1


def test_two_window_scope_preserves_other_window(broker):
    ref = opened(broker)
    unrelated = broker.desktop.transport.add(empty=False, tabs=2)
    result = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert result.state == State.SUCCEEDED
    assert broker.desktop.transport.records == [unrelated]


def test_existing_selected_window_reused_without_launch(broker):
    ref = opened(broker)
    result = submit(broker, "Open Notepad.", key="second-intent")
    assert result.state == State.SUCCEEDED and broker.desktop.selected_ref == ref
    assert broker.desktop.transport.calls == ["open"]


def test_duplicate_delivery_does_not_launch_twice(broker):
    result = submit(broker, "Open Notepad.", key="delivery")
    again = submit(broker, "Open Notepad.", key="delivery")
    assert again.task_id == result.task_id and broker.desktop.transport.calls == ["open"]


@pytest.mark.parametrize("operation", ["windows.focus", "windows.close"])
def test_unknown_window_ref_and_ambiguous_request_cannot_dispatch(broker, operation):
    ref = opened(broker)
    wrong = "win_" + "0" * 32
    result = submit(
        broker,
        "Close that Notepad window." if operation.endswith("close") else "Focus Notepad.",
        operation,
        wrong,
    )
    assert result.state != State.SUCCEEDED and broker.desktop.transport.calls == ["open"]
    assert ref != wrong


@pytest.mark.parametrize(
    "payload",
    [
        {"app_id": "notepad", "path": "evil.exe"},
        {"app_id": "other_editor"},
        {"app_id": "notepad", "pid": 10},
        {"app_id": "notepad", "approved": True},
    ],
)
def test_strict_m2_arguments_reject_paths_handles_and_grants(payload):
    raw = json.dumps(
        {"kind": "propose_action", "action": {"capability": "apps.open", "arguments": payload}}
    ).encode()
    with pytest.raises(ValueError):
        parse_decision(raw, "decision-m2-v1")


def test_m1_parser_cannot_accept_m2_window_capabilities():
    raw = (
        b'{"kind":"propose_action","action":{"capability":"windows.close",'
        b'"arguments":{"window_ref":"win_00000000000000000000000000000000"}}}'
    )
    with pytest.raises(ValueError):
        parse_decision(raw)


@pytest.mark.parametrize("hook", ["cancel", "revoke", "revision", "takeover", "tab_change", "stop"])
def test_late_admission_revalidation_prevents_close(broker, hook):
    ref = opened(broker)

    def mutate():
        task_id = broker.store.db.execute(
            "SELECT task_id FROM tasks WHERE state='RUNNING'"
        ).fetchone()[0]
        if hook == "cancel":
            broker.store.cancel(task_id)
        elif hook == "revoke":
            broker.revoke_grant()
        elif hook == "revision":
            broker.store.db.execute(
                "UPDATE tasks SET revision=revision+1 WHERE task_id=?", (task_id,)
            )
            broker.store.db.commit()
        elif hook == "takeover":
            broker.desktop.transport.input_tick += 1
        elif hook == "tab_change":
            broker.desktop.transport.records[0]["tab_ids"].append([99])
        else:
            broker.desktop.stop.set()
            broker.cancel_requested = broker.desktop.stop.is_set

    broker.desktop.transport.before_effect = mutate
    result = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert result.state != State.SUCCEEDED
    assert broker.desktop.transport.calls == ["open"] and broker.desktop.transport.records


def test_focus_denial_and_confirmation_dialog_are_truthful(broker):
    ref = opened(broker)
    broker.desktop.transport.apply = False
    result = submit(broker, "Focus Notepad.", "windows.focus", ref)
    assert result.state == State.FAILED
    broker.desktop.transport.apply = True
    broker.desktop.transport.dialog = True
    result = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert result.state != State.SUCCEEDED and broker.desktop.transport.records
    assert not any(
        "saved" in event[0] for event in broker.store.db.execute("SELECT message FROM tasks")
    )


def test_unknown_effect_is_not_replayed(broker):
    broker.desktop.transport.crash = True
    result = submit(broker, "Open Notepad.")
    assert result.state == State.NEEDS_REVIEW
    broker.desktop.transport.crash = False
    again = submit(broker, "Open Notepad.", key="new-intent")
    assert again.state == State.WAITING_INPUT
    broker.recover()
    assert broker.desktop.transport.calls == ["open"]


def test_exact_approval_tampering_and_consumption(broker):
    broker.approve = lambda action: Approval(
        "approval-1", "wrong-digest", action.revision, action.session, action.expires_at
    )
    assert submit(broker, "Open Notepad.").state == State.FAILED
    assert not broker.desktop.transport.calls
    broker.approve = lambda action: Approval(
        "approval-1", action.digest, action.revision, action.session, action.expires_at
    )
    assert submit(broker, "Open Notepad.", key="new").state == State.SUCCEEDED
    ref = broker.desktop.selected_ref
    assert submit(broker, "Focus Notepad.", "windows.focus", ref).state == State.FAILED
    assert broker.desktop.transport.calls == ["open"]


def test_unregistered_request_cannot_widen_scope(broker):
    assert submit(broker, "Open my browser.").state == State.WAITING_INPUT
    assert not broker.desktop.transport.calls


def test_expired_grant_and_changed_prepared_target(broker):
    broker.grant = replace(broker.grant, expires_at=broker.clock.now() - 1)
    assert submit(broker, "Open Notepad.").state == State.FAILED
    assert not broker.desktop.transport.calls


def test_selection_requires_known_empty_disposable_state(broker):
    broker.desktop.transport.add(empty=None)
    ref = broker.desktop.inventory()[0]["window_ref"]
    with pytest.raises(Handoff):
        broker.desktop.select(ref, confirm_disposable=True)
    assert ref not in broker.desktop.confirmed


def test_user_takeover_during_verification_is_unknown_without_replay(broker):
    broker.desktop.transport.after_effect = lambda: setattr(
        broker.desktop.transport, "input_tick", 2
    )
    result = submit(broker, "Open Notepad.")
    assert result.state == State.NEEDS_REVIEW
    assert broker.desktop.blocked_unknown
    assert broker.desktop.transport.calls == ["open"]


def test_recovery_latches_unknown_after_restart(broker, tmp_path):
    broker.desktop.transport.crash = True
    assert submit(broker, "Open Notepad.").state == State.NEEDS_REVIEW
    reopened = build(tmp_path / "m2.sqlite", broker.profile, broker.clock)
    try:
        reopened.recover()
        assert reopened.desktop.blocked_unknown
        assert (
            submit(reopened, "Open Notepad.", key="new-after-restart").state == State.WAITING_INPUT
        )
        assert not reopened.desktop.transport.calls
    finally:
        reopened.store.close()
        reopened.provider.close()


def test_lease_covers_native_effect_and_independent_observation(broker):
    class Lease:
        active = False

        def __enter__(self):
            self.active = True

        def __exit__(self, *args):
            self.active = False

    lease = Lease()
    broker.desktop.lease = lease
    original = broker.desktop.transport.call
    trace = []

    def call(operation, *args):
        trace.append((operation, lease.active))
        return original(operation, *args)

    broker.desktop.transport.call = call
    assert submit(broker, "Open Notepad.").state == State.SUCCEEDED
    assert trace[-3:] == [("inventory", True), ("inspect", True), ("activity", True)]
    assert not lease.active and not broker.desktop.lease_held


def test_clean_notepad_close_uses_owner_request_without_disposable_confirmation(broker):
    ref = opened(broker)
    broker.desktop.confirmed.clear()
    result = submit(broker, "Close that Notepad window.", "windows.close", ref)
    assert result.state == State.SUCCEEDED
    assert broker.desktop.transport.records == []
    assert broker.desktop.transport.calls == ["open", "close"]
