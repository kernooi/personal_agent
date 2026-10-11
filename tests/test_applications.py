"""Application broker gates with names obtained from arbitrary synthetic catalogs."""

import json
from dataclasses import replace

import pytest

from jarvis.application_data import ApplicationsConfig, owner_intent, parse_choice
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.application_tools import attach
from jarvis.bootstrap import ManualClock, build
from jarvis.domain import Scope, State, TaskResult
from jarvis.models import ModelReply, Profile


class SchemaProvider:
    def __init__(self, hook=lambda: None):
        self.hook = hook
        self.mutate = lambda d: d
        self.calls = 0

    def generate(self, request, cancel):
        self.calls += 1
        self.hook()
        values = {
            key: value["const"]
            for key, value in request.schema["properties"].items()
            if "const" in value
        }
        values["kind"] = "application_choice"
        values = self.mutate(values)
        return ModelReply(
            request.request_id,
            request.task_id,
            request.revision,
            json.dumps(values).encode(),
            request.profile.model_identity,
        )

    def close(self):
        pass


@pytest.fixture
def setup(tmp_path):
    profile = Profile(
        profile_name="app-fixture",
        model_identity="scripted",
        prompt_version="planner-m2-v10",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    platform = FakeApplicationPlatform()
    app = platform.add_app("Unlisted Test Application 872")
    broker = build(tmp_path / "apps.sqlite", profile, ManualClock(), provider=SchemaProvider())
    conversation = attach(broker, ApplicationsConfig(enabled=True), platform=platform)
    yield broker, conversation, platform, app
    broker.store.close()


def test_catalog_driven_open_minimize_focus_close(setup):
    broker, chat, platform, app = setup
    assert chat.submit("Could you please open " + app.name + "?").state == State.SUCCEEDED
    assert len(platform.windows) == 1
    assert chat.submit("minimize it").state == State.SUCCEEDED
    assert platform.windows[0]["minimized"]
    assert chat.submit("bring it to the front").state == State.SUCCEEDED
    assert (
        not platform.windows[0]["minimized"] and platform.foreground == platform.windows[0]["hwnd"]
    )
    result = chat.submit("close it")
    assert result.state == State.SUCCEEDED and platform.windows == []
    assert broker.store.result(result.task_id).state == State.SUCCEEDED


@pytest.mark.parametrize(
    "hook", ["cancel", "revoke", "revision", "takeover", "identity", "stop", "dialog", "host"]
)
def test_late_admission_zero_effect(setup, hook):
    broker, chat, platform, app = setup
    assert chat.submit("open " + app.name).state == State.SUCCEEDED

    def mutate():
        task = broker.store.db.execute(
            "SELECT task_id FROM tasks WHERE state='RUNNING'"
        ).fetchone()[0]
        if hook == "cancel":
            broker.store.cancel(task)
        elif hook == "revoke":
            broker.revoke_grant()
        elif hook == "revision":
            broker.store.db.execute("UPDATE tasks SET revision=revision+1 WHERE task_id=?", (task,))
            broker.store.db.commit()
        elif hook == "takeover":
            platform.input_tick += 1
        elif hook == "identity":
            platform.windows[0]["created"] += 1
        elif hook == "dialog":
            platform.windows[0]["owned_dialog"] = True
        elif hook == "host":
            platform.windows[0]["frame_host"] = {"pid": 999, "created": 100}
        else:
            chat.desktop.stop.set()
            broker.cancel_requested = chat.desktop.stop.is_set

    platform.before_effect = mutate
    assert chat.submit("minimize it").state != State.SUCCEEDED
    assert platform.calls == ["open"] and not platform.windows[0]["minimized"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("app_id", "app_" + "0" * 32),
        ("capability", "windows.close"),
        ("window_ref", "win_" + "0" * 32),
        ("approved", True),
    ],
)
def test_model_cannot_change_target_or_effect(setup, field, value):
    broker, chat, platform, app = setup
    broker.provider.mutate = lambda d: {**d, field: value}
    assert chat.submit("open " + app.name).state == State.FAILED
    assert not platform.calls


def test_ambiguous_name_multiple_windows_and_unknown_target(setup):
    broker, chat, platform, app = setup
    another = platform.add_app("Another Test Application 872")
    chat.desktop.load_catalog()
    assert chat.submit("open Application 872").state == State.WAITING_INPUT
    assert chat.submit("open nonexistent app").state == State.WAITING_INPUT
    platform.add_window(app)
    platform.add_window(app)
    assert chat.submit("focus " + app.name).state == State.WAITING_INPUT
    assert not platform.calls and another.app_id != app.app_id


def test_close_preserves_other_windows_and_blocks_protected_dirty(setup):
    broker, chat, platform, app = setup
    row = platform.add_window(app)
    row["protected"] = True
    row["close_safe"] = False
    ref = chat.desktop.inventory()[0]["window_ref"]
    chat.desktop.select(ref)
    with pytest.raises(ValueError):
        chat.control("/app-confirm-close")
    assert chat.submit("close " + app.name).state == State.WAITING_INPUT
    row["close_safe"] = True
    chat.control("/app-confirm-close")
    other = platform.add_window(app)
    assert chat.submit("close it").state == State.SUCCEEDED
    assert platform.windows == [other]


def test_verification_failure_and_unknown_nonreplay(setup):
    broker, chat, platform, app = setup
    platform.apply = False
    assert chat.submit("open " + app.name).state == State.NEEDS_REVIEW
    platform.apply = True
    assert chat.submit("open " + app.name).state == State.WAITING_INPUT
    assert platform.calls == ["open"]


def test_missing_permission(setup):
    broker, chat, platform, app = setup
    broker.grant = replace(broker.grant, apps=frozenset({"notepad"}))
    assert chat.submit("open " + app.name).state == State.FAILED
    assert not platform.calls


@pytest.mark.parametrize(
    "text",
    [
        "do not open Something",
        "what does minimize Something mean?",
        "explain how to close Something",
    ],
)
def test_prose_and_negation_are_not_commands(text):
    assert owner_intent(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "open Something and close it",
        "open C:\\evil.exe",
        "open https://example.com",
        "open Something --delete",
    ],
)
def test_no_paths_arguments_or_chained_effects(text):
    assert owner_intent(text)[0] == "unsupported"


def test_duplicate_key_and_extra_fields_rejected():
    with pytest.raises(ValueError):
        parse_choice(b'{"kind":"application_choice","kind":"application_choice"}')


def test_duplicate_request_never_replays_after_window_changes(setup):
    broker, chat, platform, app = setup
    result = chat.submit("open " + app.name, "delivery-1")
    platform.windows.clear()
    assert chat.submit("open " + app.name, "delivery-1").task_id == result.task_id
    assert platform.calls == ["open"]
    with pytest.raises(ValueError):
        chat.submit("minimize " + app.name, "delivery-1")


def test_owner_close_request_replaces_expired_optional_review(setup):
    broker, chat, platform, app = setup
    chat.submit("open " + app.name)
    chat.control("/app-confirm-close")
    broker.clock.advance(61)
    assert chat.submit("close it").state == State.SUCCEEDED
    assert platform.calls == ["open", "close"]


def test_unknown_recovery_requires_manual_review_without_replay(setup):
    broker, chat, platform, app = setup
    platform.apply = False
    result = chat.submit("open " + app.name)
    assert result.state == State.NEEDS_REVIEW
    broker.recover()
    assert broker.desktop.blocked_unknown
    chat.control("/app-review " + result.task_id + " manually-handled")
    assert not broker.desktop.blocked_unknown
    assert platform.calls == ["open"]


def test_simulated_action_remains_clearly_labelled(setup):
    _, chat, _, app = setup
    assert chat.submit("open " + app.name).message.startswith("[SIMULATED]")


def test_existing_service_route_is_not_shadowed_by_unknown_app(setup, monkeypatch):
    broker, chat, _, _ = setup
    forwarded = []
    monkeypatch.setattr(
        broker.registry.underlying,
        "scope_for",
        lambda session, text: Scope(session, "media", "open", ""),
    )
    monkeypatch.setattr(
        chat.original,
        "submit",
        lambda text, key: forwarded.append(text) or TaskResult("fixture", State.ANSWERED, "ok"),
    )
    assert chat.submit("open YouTube").state == State.ANSWERED
    assert forwarded == ["open YouTube"]


def test_close_requires_handle_absence_even_when_inventory_loses_metadata(setup):
    _, chat, platform, app = setup
    chat.submit("open " + app.name)
    chat.control("/app-confirm-close")
    platform.apply = False
    original_call = platform.call

    def call(operation, payload=None, gate=None):
        if operation == "inventory" and platform.calls[-1:] == ["close"]:
            return []
        return original_call(operation, payload, gate)

    platform.call = call
    assert chat.submit("close it").state != State.SUCCEEDED
    assert len(platform.windows) == 1
    assert not chat.desktop.close_confirmed


def test_delivered_crash_never_replays(setup):
    _, chat, platform, app = setup
    platform.crash = True
    assert chat.submit("open " + app.name).state == State.NEEDS_REVIEW
    assert len(platform.windows) == 1
    platform.crash = False
    assert chat.submit("open " + app.name).state == State.WAITING_INPUT
    assert platform.calls == ["open"]
    assert chat.submit("open my text editor").state == State.WAITING_INPUT


@pytest.mark.parametrize(
    "change", [None, "input", "transient-input", "identity", "multiple", "missing", "stop"]
)
def test_delivered_open_input_change_requires_stable_exact_readonly_reobservation(setup, change):
    broker, chat, platform, app = setup
    platform.after_effect = lambda: setattr(platform, "input_tick", platform.input_tick + 1)
    original = platform.call
    observations = []

    def call(operation, payload=None, gate=None):
        if operation == "inventory" and platform.calls:
            observations.append(operation)
            if len(observations) == 2:
                if change == "identity":
                    platform.windows[0]["created"] += 1
                elif change == "multiple":
                    platform.add_window(app)
                elif change == "missing":
                    platform.windows.clear()
                elif change == "stop":
                    chat.desktop.stop.set()
        result = original(operation, payload, gate)
        if change == "input" and operation == "inspect" and len(observations) >= 2:
            platform.input_tick += 1
        if change == "transient-input" and operation == "inspect" and len(observations) == 2:
            platform.input_tick += 1
        return result

    platform.call = call
    result = chat.submit("open " + app.name)
    assert platform.calls == ["open"]  # Read-only reconciliation never replays.
    if change not in (None, "transient-input"):
        assert result.state == State.NEEDS_REVIEW
        assert chat.desktop.blocked_unknown
    else:
        assert result.state == State.SUCCEEDED
        assert not chat.desktop.blocked_unknown
        assert broker.store.result(result.task_id).state == State.SUCCEEDED
        raw = broker.store.db.execute("SELECT evidence_json FROM attempts").fetchone()[0]
        evidence = json.loads(raw)
        assert json.loads(evidence["observed_identity"])["reobserved_after_input_change"] is True


def test_slow_cold_launch_observes_past_four_seconds_without_relaunch(setup, monkeypatch):
    from jarvis import application_tools

    _, chat, platform, app = setup
    chat.desktop.real = True
    original = platform.call
    polls = []
    ticks = iter(range(100))
    monkeypatch.setattr(application_tools.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(application_tools.time, "sleep", lambda _: None)

    def call(operation, payload=None, gate=None):
        if operation == "inventory" and platform.calls:
            polls.append(True)
            if len(polls) <= 6:
                return []
        return original(operation, payload, gate)

    platform.call = call
    assert chat.submit("open " + app.name).state == State.SUCCEEDED
    assert len(polls) == 7
    assert platform.calls == ["open"]


def test_multiple_windows_accept_natural_number_and_preserve_other_window(setup):
    _, chat, platform, app = setup
    first = platform.add_window(app)
    second = platform.add_window(app)
    result = chat.submit("close " + app.name)
    assert result.state == State.WAITING_INPUT and "Reply with its number" in result.message
    assert not platform.calls
    assert chat.submit("the second one").state == State.SUCCEEDED
    assert platform.windows == [first] and second not in platform.windows


def test_disappeared_clarification_window_is_not_substituted(setup):
    _, chat, platform, app = setup
    first = platform.add_window(app)
    second = platform.add_window(app)
    chat.submit("close " + app.name)
    platform.windows.remove(second)
    assert chat.submit("second").state == State.WAITING_INPUT
    assert platform.windows == [first] and not platform.calls


def test_runtime_proof_requires_exact_launch_hash_and_os_package_or_publisher():
    from jarvis.application_data import valid_runtime_proof

    target = {
        "exe_sha256": "a" * 64,
        "app": {"launch_id": "Fixture!App", "package": "Fixture_package", "kind": "package"},
    }
    observed = {
        "exe_sha256": "b" * 64,
        "package": "Fixture_package",
        "association": {
            "method": "os-application-id",
            "launch_id": "Fixture!App",
            "launch_sha256": "a" * 64,
            "runtime_sha256": "b" * 64,
            "package": "Fixture_package",
        },
    }
    assert valid_runtime_proof(observed, target)
    for key in ["launch_id", "launch_sha256", "runtime_sha256", "package", "method"]:
        forged = {**observed, "association": {**observed["association"], key: "wrong"}}
        assert not valid_runtime_proof(forged, target)
    assert not valid_runtime_proof({**observed, "association": None}, target)
    target["app"].update(kind="exe", package="")
    observed.update(
        package="",
        association={
            **observed["association"],
            "method": "signed-versioned-runtime",
            "publisher_sha256": "c" * 64,
        },
    )
    assert valid_runtime_proof(observed, target)
    observed["association"]["publisher_sha256"] = ""
    assert not valid_runtime_proof(observed, target)


def test_sole_unselected_window_closes_without_reference_or_confirmation(setup):
    _, chat, platform, app = setup
    platform.add_window(app)
    assert chat.submit("close " + app.name).state == State.SUCCEEDED
    assert platform.windows == [] and platform.calls == ["close"]


@pytest.mark.parametrize("command", ["close", "focus", "minimize"])
def test_bare_operation_uses_only_clear_selected_application(setup, command):
    _, chat, platform, app = setup
    assert chat.submit(command).state == State.WAITING_INPUT
    assert platform.calls == []
    chat.submit("open " + app.name)
    assert chat.submit(command).state == State.SUCCEEDED
    assert platform.calls[-1] == command


@pytest.mark.parametrize("proof", [False, True])
def test_hidden_close_requires_fresh_exact_window_identity(setup, proof):
    from jarvis.application_tools import identity

    _, chat, platform, app = setup
    chat.submit("open " + app.name)
    expected = identity(platform.windows[0])
    platform.apply = False
    original = platform.call

    def call(operation, payload=None, gate=None):
        if operation == "absence":
            return {"present": True, "visible": False, "identity": expected if proof else {}}
        return original(operation, payload, gate)

    platform.call = call
    result = chat.submit("close it")
    assert (result.state == State.SUCCEEDED) == proof
