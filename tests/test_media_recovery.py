"""Media failures retain reasons, exact targets and zero-replay boundaries."""

import json
from types import SimpleNamespace

import pytest
from test_media import ChoiceProvider

from jarvis.application_tools import IDENTITY_KEYS
from jarvis.bootstrap import ManualClock, build
from jarvis.conversation import Conversation, conversational_text
from jarvis.currency_provider import FixtureProvider
from jarvis.domain import AdmissionRejected, State
from jarvis.media_data import MediaConfig, MediaError
from jarvis.media_fake import FakeBrowserProvider
from jarvis.media_tools import MediaAdapter
from jarvis.models import Profile
from jarvis.public_data import PublicConfig
from jarvis.spotify_accessibility import SpotifyAccessibility


def test_new_search_rebinds_reopened_window_but_never_retargets_mid_operation():
    ui = object.__new__(SpotifyAccessibility)
    first = dict.fromkeys(IDENTITY_KEYS, "first")
    first.update(hwnd=1, pid=10)
    second = {**first, "hwnd": 2, "pid": 20}
    current = [first]
    ui.app, ui.config, ui.window, ui.query = object(), object(), None, ""
    ui.bindings = {}
    ui.native = SimpleNamespace(
        inventory=lambda *a: current,
        activity=lambda: None,
        has_dialog=lambda *a: False,
        user=SimpleNamespace(IsIconic=lambda h: False, IsWindowEnabled=lambda h: True),
    )
    ui.uia = SimpleNamespace(ElementFromHandle=lambda h: h)
    assert ui.root() == 1
    ui.query, ui.bindings = "Old query", {"old-reference": object()}
    current[:] = [second]
    with pytest.raises(MediaError, match="SPOTIFY_WINDOW_CHANGED"):
        ui.root()
    assert ui.begin_search() == 2
    assert ui.query == "" and ui.bindings == {}
    current[:] = [first]
    with pytest.raises(MediaError, match="SPOTIFY_WINDOW_CHANGED"):
        ui.root()


@pytest.mark.parametrize(
    "code,phrase",
    [
        ("SPOTIFY_WINDOW_CHANGED", "window changed"),
        ("USER_TAKEOVER_REOBSERVE_REQUIRED", "browser was used manually"),
        ("STALE_NAVIGATION_GENERATION", "page changed"),
        ("DESKTOP_INTERACTION_BUSY", "Another JARVIS operation"),
    ],
)
def test_rejection_reason_is_presented_and_journaled_without_delivery(tmp_path, code, phrase):
    clock = ManualClock()
    fake = FakeBrowserProvider(clock)
    original = fake.call

    def reject(request, cancel):
        if request.command == "execute":
            raise AdmissionRejected(code)
        return original(request, cancel)

    fake.call = reject
    broker = build(
        tmp_path / "j.sqlite",
        Profile(
            profile_name="synthetic-media",
            model_identity="synthetic",
            reply='{"kind":"say","text":"Synthetic."}',
        ),
        clock=clock,
        provider=ChoiceProvider(),
        media_config=MediaConfig(enabled=True),
        browser_provider=fake,
    )
    try:
        result = Conversation(broker).submit("Search YouTube for synthetic video")
        assert result.state == State.FAILED
        assert phrase in conversational_text(result)
        assert fake.execution_count == 0
        row = broker.store.db.execute(
            "SELECT redacted_payload_json FROM events WHERE kind='media_admission_rejected'"
        ).fetchone()
        assert json.loads(row[0]) == {"code": code}
    finally:
        broker.store.close()


@pytest.mark.parametrize("phase", ["execute", "observe"])
def test_uncertain_search_keeps_reason_and_never_replays(tmp_path, phase):
    clock = ManualClock()
    fake = FakeBrowserProvider(clock)
    original = fake.call

    def fail(request, cancel):
        if request.command == phase:
            if phase == "execute":
                original(request, cancel)
            raise MediaError("SPOTIFY_SEARCH_CONTROL_UNAVAILABLE")
        return original(request, cancel)

    fake.call = fail
    broker = build(
        tmp_path / "j.sqlite",
        Profile(
            profile_name="synthetic-media",
            model_identity="synthetic",
            reply='{"kind":"say","text":"Synthetic."}',
        ),
        clock=clock,
        provider=ChoiceProvider(),
        media_config=MediaConfig(enabled=True),
        browser_provider=fake,
    )
    try:
        chat = Conversation(broker)
        result = chat.submit("Search YouTube for synthetic video", "first")
        assert result.state == State.NEEDS_REVIEW
        row = broker.store.db.execute(
            "SELECT redacted_payload_json FROM events WHERE kind='media_execution_error'"
        ).fetchone()
        assert json.loads(row[0]) == {
            "code": "SPOTIFY_SEARCH_CONTROL_UNAVAILABLE",
            "stage": phase,
        }
        assert fake.execution_count == 1
        chat.submit("Search YouTube for another video", "second")
        assert fake.execution_count == 1
    finally:
        broker.store.close()


def test_diagnostics_never_record_arbitrary_exception_text():
    adapter = object.__new__(MediaAdapter)
    for error in (RuntimeError("PRIVATE TITLE OR URL"), MediaError("PRIVATE_VALUE")):
        assert adapter.diagnostic_error_code(error) == "MEDIA_EXECUTION_FAILED"
        assert adapter.admission_error_code(error) == "MEDIA_ADMISSION_REJECTED"


def test_combined_chat_uses_each_services_generation_and_selected_content(tmp_path):
    clock = ManualClock()
    fake = FakeBrowserProvider(clock)
    broker = build(
        tmp_path / "combined.sqlite",
        Profile(
            profile_name="synthetic-media",
            model_identity="synthetic",
            reply='{"kind":"say","text":"Synthetic."}',
        ),
        clock=clock,
        provider=ChoiceProvider(),
        public_config=PublicConfig(mode="fixture"),
        currency_provider=FixtureProvider(lambda base, quote: b"unused"),
        media_config=MediaConfig(enabled=True, spotify=True, spotify_backend="desktop"),
        browser_provider=fake,
    )
    try:
        chat = Conversation(broker)
        fake.catalog = [("a" * 22, "Avid", "Test artist")]
        assert chat.submit("play avid on spotify").state == State.SUCCEEDED
        assert broker.media.observation.state == "playing"
        # Make Spotify's counter exceed the next browser search counter.
        chat.submit("Pause Spotify")
        chat.submit("Resume Spotify")
        fake.catalog = [("dQw4w9WgXcQ", "Never Gonna Give You Up", "Rick Astley")]
        assert chat.submit("Play Never Gonna Give You Up on YouTube").state == State.SUCCEEDED
        assert broker.media.observation.state == "playing"
        assert broker.media.observation.service == "youtube"
        assert chat.submit("Pause Spotify").state == State.SUCCEEDED
        assert broker.media.observation.state == "paused"
        assert chat.submit("Pause YouTube").state == State.SUCCEEDED
        assert broker.media.observation.state == "paused"
    finally:
        broker.store.close()
