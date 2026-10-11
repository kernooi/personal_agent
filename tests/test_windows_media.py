"""Offline native-session safety and broker regression tests."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_media import ChoiceProvider

from jarvis.bootstrap import ManualClock, build, load_profile
from jarvis.domain import State, UserRequest
from jarvis.media_data import MediaArguments, MediaConfig, MediaError, WorkerRequest, canonical
from jarvis.media_fake import FakeBrowserProvider
from jarvis.windows_media import Snapshot, WindowsMediaSession, select_spotify


def test_only_exact_spotify_source_selected():
    other = SimpleNamespace(source_app_user_model_id="Chrome.exe")
    spoof = SimpleNamespace(source_app_user_model_id="MySpotify.exe")
    spotify = SimpleNamespace(source_app_user_model_id="Spotify.exe")
    assert select_spotify([other, spoof, spotify]) is spotify
    with pytest.raises(MediaError, match="MISSING"):
        select_spotify([other, spoof])
    with pytest.raises(MediaError, match="AMBIGUOUS"):
        select_spotify([spotify, spotify])


def test_historical_api_scope_preserved_and_windows_bound():
    args = request().arguments.model_copy(update={"backend": "api"})
    original = json.dumps(
        args.model_dump(exclude={"backend"}), sort_keys=True, separators=(",", ":")
    )
    assert canonical(MediaArguments.model_validate_json(original)) == original
    windows = canonical(args.model_copy(update={"backend": "windows"}))
    assert json.loads(windows)["backend"] == "windows"
    assert windows != original


def test_global_stop_cancels_before_model_or_adapter(tmp_path):
    root = Path(__file__).resolve().parents[1]
    clock = ManualClock()
    fake, model = FakeBrowserProvider(clock), ChoiceProvider()
    broker = build(
        tmp_path / "stopped.sqlite",
        load_profile(root / "config/defaults.toml"),
        clock,
        provider=model,
        media_config=MediaConfig(enabled=True, spotify=True, spotify_backend="windows"),
        browser_provider=fake,
    )
    try:
        broker.cancel_requested = lambda: True
        result = broker.converse(UserRequest("stop", broker.grant.session, "Pause Spotify"))
        assert result.state == State.CANCELLED
        assert not model.requests and not fake.calls and broker.media.execution_calls == 0
    finally:
        broker.store.close()


class Backend:
    def __init__(self):
        self.state = Snapshot(
            object(),
            "Spotify.exe",
            "a" * 64,
            "Synthetic",
            "Test",
            "playing",
            frozenset({"play", "pause", "resume", "next", "previous"}),
        )
        self.calls = []
        self.reads = 0
        self.hook = lambda: None
        self.accept = True

    async def snapshot(self):
        self.reads += 1
        self.hook()
        return self.state

    async def deliver(self, session, operation):
        assert session == self.state.session
        self.calls.append(operation)
        if self.accept:
            self.state = replace(
                self.state,
                state="paused" if operation == "pause" else "playing",
                item_id="b" * 64 if operation in {"next", "previous"} else self.state.item_id,
            )
        return self.accept


def request(operation="pause", command="execute", generation=0):
    return WorkerRequest(
        request_id=uuid4().hex,
        command=command,
        arguments=MediaArguments(
            service="spotify",
            operation=operation,
            backend="windows",
            session_ref="browser_" + "1" * 32,
            generation=generation,
        ),
        deadline=120.0,
    )


@pytest.mark.parametrize("operation", ["play", "pause", "resume", "next", "previous", "current"])
def test_independent_native_verification(operation):
    backend = Backend()
    session = WindowsMediaSession(backend, clock=lambda: 100)
    action = request(operation)
    executed = asyncio.run(session.handle(action))
    observed = asyncio.run(session.handle(action.model_copy(update={"command": "observe"})))
    assert observed == executed
    assert backend.calls == ([] if operation == "current" else [operation])
    assert backend.reads >= 2


def test_stop_between_snapshot_and_delivery():
    backend = Backend()
    stopped = False

    def stop():
        nonlocal stopped
        if backend.reads == 2:
            stopped = True

    backend.hook = stop
    session = WindowsMediaSession(backend, clock=lambda: 100)
    with pytest.raises(MediaError):
        asyncio.run(session.handle(request(), lambda: stopped))
    assert not backend.calls and not session.admitted


@pytest.mark.parametrize("change", ["session", "item_id", "state", "controls"])
def test_takeover_rejects_delivery(change):
    backend = Backend()

    def mutate():
        if backend.reads == 2:
            values = {
                "session": object(),
                "item_id": "b" * 64,
                "state": "paused",
                "controls": frozenset(),
            }
            backend.state = replace(backend.state, **{change: values[change]})

    backend.hook = mutate
    session = WindowsMediaSession(backend, clock=lambda: 100)
    with pytest.raises(MediaError):
        asyncio.run(session.handle(request()))
    assert backend.calls == []


def test_rejected_command_is_not_success_or_replayed():
    backend = Backend()
    backend.accept = False
    session = WindowsMediaSession(backend, clock=lambda: 100)
    with pytest.raises(MediaError, match="NOT_ACCEPTED"):
        asyncio.run(session.handle(request()))
    assert backend.calls == ["pause"] and session.admitted


def test_postcondition_drift_rejected():
    backend = Backend()
    session = WindowsMediaSession(backend, clock=lambda: 100)
    action = request()
    asyncio.run(session.handle(action))
    backend.state = replace(backend.state, item_id="c" * 64)
    with pytest.raises(MediaError, match="POSTCONDITION"):
        asyncio.run(session.handle(action.model_copy(update={"command": "observe"})))
    assert backend.calls == ["pause"]


def test_stale_generation_no_delivery():
    backend = Backend()
    session = WindowsMediaSession(backend, clock=lambda: 100)
    with pytest.raises(MediaError, match="STALE"):
        asyncio.run(session.handle(request(generation=3)))
    assert not backend.calls


def test_native_frozen_corpus_through_broker(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "tests/fixtures/m4-windows-media-corpus-v1.json").read_text())[
        "cases"
    ]
    for case in cases:
        clock = ManualClock()
        fake = FakeBrowserProvider(clock)
        broker = build(
            tmp_path / (case["id"] + ".sqlite"),
            load_profile(root / "config/defaults.toml"),
            clock,
            provider=ChoiceProvider(),
            media_config=MediaConfig(enabled=True, spotify=True, spotify_backend="windows"),
            browser_provider=fake,
        )
        try:
            result = broker.converse(UserRequest(case["id"], broker.grant.session, case["text"]))
            assert broker.last_decision.kind == case["kind"]
            if case["kind"] == "propose_action":
                assert result.state == State.SUCCEEDED
                assert fake.execution_count == 1
            else:
                assert fake.execution_count == 0
            assert broker.desktop.execution_calls == 0
        finally:
            broker.store.close()
