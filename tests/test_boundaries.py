from dataclasses import replace
from pathlib import Path

import pytest

from jarvis.bootstrap import ManualClock, build, load_profile
from jarvis.domain import Approval, Denied, Proposal, Scope, SimulatedCrash, State, UserRequest
from jarvis.policy import authorize
from jarvis.tools import digest

ROOT = Path(__file__).resolve().parents[1]
REQUEST = UserRequest("request-1", "demo-session", "Open my registered text editor.")


@pytest.fixture
def broker(tmp_path):
    instance = build(
        tmp_path / "journal.sqlite", load_profile(ROOT / "config/defaults.toml"), ManualClock()
    )
    yield instance
    instance.provider.close()
    instance.store.close()


def task_id(broker):
    return broker.store.db.execute("SELECT task_id FROM tasks").fetchone()[0]


@pytest.mark.parametrize("field", ["request_id", "task_id", "revision"])
def test_mismatched_reply_identity(broker, field):
    generate = broker.provider.generate
    broker.provider.generate = lambda request, cancel: replace(
        generate(request, cancel), **{field: 99 if field == "revision" else "obsolete"}
    )
    assert broker.submit(REQUEST).state == State.FAILED
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0


def test_profile_switch_applies_next_task(broker):
    old = broker.profile
    other = load_profile(ROOT / "config/examples/fake-alternate.toml")
    broker.provider.before_reply = lambda: setattr(
        broker, "profile", other.model_copy(update={"max_output_bytes": 1})
    )
    assert broker.submit(REQUEST).state == State.SUCCEEDED
    stored = broker.store.db.execute("SELECT profile_json FROM tasks").fetchone()[0]
    assert old.model_identity in stored and other.model_identity not in stored
    assert "reply" not in stored
    assert broker.submit(replace(REQUEST, request_key="next-task")).state == State.FAILED
    assert broker.desktop.execution_calls == 1


def test_adapter_error_after_effect_does_not_claim_zero_execution(broker):
    def error():
        raise Denied("Unexpected error after mutation")

    broker.desktop.after_effect = error
    result = broker.submit(REQUEST)
    assert result.state == State.NEEDS_REVIEW and "unknown" in result.message
    assert broker.desktop.effect_count == 1


@pytest.mark.parametrize("offset", [-1, 100])
def test_stale_or_future_observation_rejected(broker, offset):
    observe = broker.desktop.observe
    broker.desktop.observe = lambda a: replace(observe(a), observed_at=broker.clock.now() + offset)
    assert broker.submit(REQUEST).state == State.NEEDS_REVIEW


def test_duplicate_action_admission_rejected(broker):
    task, _ = broker.store.accept("direct", Scope("demo-session", "text_editor"), "f", 1030)
    broker.store.transition(task.task_id, State.PLANNING)
    broker.store.transition(task.task_id, State.READY)
    action = broker.registry.prepare(
        broker.store.get(task.task_id), Proposal("apps.open", "text_editor"), broker.grant
    )
    action_id = broker.store.intent(action, broker.grant.grant_id)
    broker.store.admit(action_id, action, None)
    with pytest.raises(Denied):
        broker.store.admit(action_id, action, None)
    assert broker.store.db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0


def test_reprepared_target_invalidates_approval(broker):
    task, _ = broker.store.accept("direct", Scope("demo-session", "text_editor"), "f", 1030)
    action = broker.registry.prepare(task, Proposal("apps.open", "text_editor"), broker.grant)
    approval = Approval(
        "consent", action.digest, action.revision, action.session, action.expires_at
    )
    app = broker.registry.apps["text_editor"]
    broker.registry.apps["text_editor"] = replace(app, identity="fake:editor:v2")
    changed = broker.registry.prepare(task, Proposal("apps.open", "text_editor"), broker.grant)
    broker.registry.validate(changed)
    assert digest(changed) != action.digest
    with pytest.raises(Denied):
        authorize(task, changed, broker.grant, approval, broker.clock.now())
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0


def test_approval_expires_after_intent(broker):
    broker.approve = lambda a: Approval(
        "consent", a.digest, a.revision, a.session, broker.clock.now() + 1
    )
    broker.before_admission = lambda: broker.clock.advance(2)
    assert broker.submit(REQUEST).state == State.FAILED
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0
    assert broker.store.db.execute("SELECT count(*) FROM consumed_approvals").fetchone()[0] == 0


def test_corrupt_recovery_record_is_unknown(broker):
    broker.desktop.crash = "after_effect"
    with pytest.raises(SimulatedCrash):
        broker.submit(REQUEST)
    with broker.store.db:
        broker.store.db.execute("UPDATE actions SET prepared_json='{}'")
    result = broker.recover()[0]
    assert result.state == State.NEEDS_REVIEW and "Invalid stored action" in result.message
    assert broker.desktop.execution_calls == 1


def test_verified_journal_reopen_does_not_replay(tmp_path):
    path = tmp_path / "verified.sqlite"
    profile = load_profile(ROOT / "config/defaults.toml")
    first = build(path, profile, ManualClock())
    result = first.submit(REQUEST)
    first.store.close()
    first.provider.close()
    second = build(path, profile, ManualClock())
    try:
        assert second.recover() == []
        assert second.submit(REQUEST) == result
        assert second.desktop.execution_calls == second.desktop.effect_count == 0
        assert second.provider.calls == 0
    finally:
        second.store.close()
        second.provider.close()


def test_storage_durability_and_foreign_keys(broker):
    assert broker.store.db.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert broker.store.db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert broker.store.db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_cancel_acknowledgment_is_idempotent(broker):
    broker.provider.before_reply = lambda: [broker.store.cancel(task_id(broker)) for _ in range(2)]
    assert broker.submit(REQUEST).state == State.CANCELLED
    assert broker.store.get(task_id(broker)).revision == 2
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0


def test_waiting_input_can_be_cancelled(broker):
    broker.profile = broker.profile.model_copy(
        update={"reply": '{"kind":"clarify","question":"Which editor?"}'}
    )
    result = broker.submit(REQUEST)
    assert result.state == State.WAITING_INPUT
    broker.store.cancel(result.task_id)
    assert broker.store.result(result.task_id).state == State.CANCELLED
    assert broker.desktop.execution_calls == broker.desktop.effect_count == 0
