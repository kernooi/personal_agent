"""Offline Spotify-specific search/playback boundaries; never operate the installed app."""

import asyncio
import hashlib
import json
import socket
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_media import ChoiceProvider

from jarvis.application_data import ApplicationsConfig
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.application_tools import attach
from jarvis.bootstrap import ManualClock, build
from jarvis.conversation import conversational_text
from jarvis.domain import AdmissionRejected, State
from jarvis.media_data import (
    MediaArguments,
    MediaConfig,
    MediaError,
    MediaItem,
    WorkerRequest,
    safe_media_query,
)
from jarvis.media_evaluation import SPOTIFY_DESKTOP_CORPUS, seed
from jarvis.media_fake import FakeBrowserProvider
from jarvis.models import Profile
from jarvis.spotify_accessibility import (
    content_identity,
    filter_route_matches,
    native_song_record,
    owner_identity,
    search_matches,
    search_uri,
)
from jarvis.spotify_desktop import SpotifyDesktopSession
from jarvis.spotify_flow import SpotifyFlow
from jarvis.windows_media import Snapshot


def test_explicit_artist_or_playlist_owner_cannot_be_satisfied_by_title_words():
    flow = SpotifyFlow(None)
    query = "playlist Deep Focus by Spotify"
    assert flow.matches_item(query, SimpleNamespace(title="Deep Focus", creator="Spotify"))
    assert not flow.matches_item(
        query, SimpleNamespace(title="Deep Focus by Spotify", creator="Other owner")
    )
    assert not flow.matches_item(query, SimpleNamespace(title="Deep Focus", creator=""))
    assert not flow.matches_item(
        query, SimpleNamespace(title="(copy of) Deep Focus by Spotify", creator="Other owner")
    )
    assert not flow.matches_item(
        "Never Gonna Give You Up by Rick Astley",
        SimpleNamespace(title="Never Gonna Give You Up by Rick Astley", creator="Karaoke artist"),
    )


def test_playlist_owner_link_is_validated_separately_from_content():
    assert owner_identity("https://xpui.app.spotify.com/user/spotify") == "spotify"
    assert owner_identity("https://open.spotify.com/user/another-owner") == "another-owner"
    assert owner_identity("https://xpui.app.spotify.com.evil.test/user/spotify") is None
    assert owner_identity("https://xpui.app.spotify.com/user/spotify?token=x") is None
    assert owner_identity("https://xpui.app.spotify.com/user/../spotify") is None


def test_filter_route_must_belong_to_the_new_exact_query():
    query = "Deep Focus by Spotify"
    assert filter_route_matches(
        "https://xpui.app.spotify.com/search/Deep%20Focus%20by%20Spotify/playlists",
        query,
        "playlist",
    )
    assert filter_route_matches(
        "https://xpui.app.spotify.com/search/Deep%2BFocus%2Bby%2BSpotify/playlists",
        query,
        "playlist",
    )
    assert not filter_route_matches(
        "https://xpui.app.spotify.com/search/Old%20query/playlists", query, "playlist"
    )
    assert not filter_route_matches(
        "https://xpui.app.spotify.com/search/Deep%20Focus%20by%20Spotify/tracks", query, "playlist"
    )
    assert not filter_route_matches(
        "https://127.0.0.1/search/Deep%20Focus%20by%20Spotify/playlists", query, "playlist"
    )
    assert not filter_route_matches(
        "https://xpui.app.spotify.com/search/Deep%20Focus%20by%20Spotify/playlists?private=1",
        query,
        "playlist",
    )


def test_search_commit_is_exact_form_scoped_and_rejects_changed_query():
    from jarvis.spotify_accessibility import SpotifyAccessibility

    field = SimpleNamespace()
    button = SimpleNamespace(CurrentControlType=50000)
    form = SimpleNamespace(
        children={(30005, "What do you want to play?"): [field], (30005, "Search"): [button]}
    )
    root = SimpleNamespace(children={(30101, "search"): [form]})
    ui = SpotifyAccessibility.__new__(SpotifyAccessibility)
    ui.root = lambda: root
    ui.uia = SimpleNamespace(CreatePropertyCondition=lambda p, v: (p, v))
    ui.nodes = lambda node, condition: node.children.get(condition, [])
    ui.search_field = lambda node: (field, SimpleNamespace(CurrentValue="Deep Focus"))
    sent = []
    ui.invoke = lambda target, gate: sent.append(target)
    ui.commit_search("Deep Focus", lambda: None)
    assert sent == [button]
    with pytest.raises(MediaError, match="SPOTIFY_SEARCH_FORM_CHANGED"):
        ui.commit_search("Another query", lambda: None)
    form.children[(30005, "Search")].append(button)
    with pytest.raises(MediaError, match="SPOTIFY_SEARCH_SUBMIT_UNAVAILABLE"):
        ui.commit_search("Deep Focus", lambda: None)
    assert sent == [button]


def test_native_row_identity_is_not_a_catalog_id_and_survives_play_pause():
    args = ("Rick Astley", ["a" * 22], (1, 2, 3))
    play = native_song_record("Play Never Gonna Give You Up by Rick Astley", *args)
    pause = native_song_record("Pause Never Gonna Give You Up by Rick Astley", *args)
    assert play == pause
    assert play["id"].startswith("native_") and play["uri"] == ""
    assert native_song_record("Play Other song by Rick Astley", *args)["id"] != play["id"]
    assert (
        native_song_record("Play Never Gonna Give You Up by Rick Astley", *args[:2], (1, 2, 4))[
            "id"
        ]
        != play["id"]
    )
    with pytest.raises(MediaError):
        native_song_record("Play Never Gonna Give You Up by Someone Else", *args)
    with pytest.raises(MediaError):
        native_song_record(
            "Play Never Gonna Give You Up by Rick Astley", "Rick Astley", [], (1, 2, 3)
        )


def test_native_client_link_has_exact_https_origin_and_catalog_shape():
    assert content_identity("https://xpui.app.spotify.com/artist/" + "a" * 22) == (
        "artist",
        "a" * 22,
    )
    assert content_identity("https://xpui.app.spotify.com.evil.test/artist/" + "a" * 22) is None


@pytest.mark.parametrize("catalog_link", [False, True])
def test_accessibility_row_layouts_bind_exact_play_and_reject_replaced_rows(catalog_link):
    from jarvis.spotify_accessibility import SpotifyAccessibility

    row = SimpleNamespace(CurrentIsOffscreen=False, GetRuntimeId=lambda: (1, 2, 3))
    title, creator = "Test song", "Test artist"
    button = SimpleNamespace(
        CurrentName="Play " + title + ("" if catalog_link else " by " + creator),
        CurrentIsOffscreen=False,
    )
    artist = SimpleNamespace(
        CurrentName=creator, link="https://xpui.app.spotify.com/artist/" + "a" * 22
    )
    links = [artist]
    if catalog_link:
        links.append(
            SimpleNamespace(
                CurrentName=title, link="https://xpui.app.spotify.com/track/" + "b" * 22
            )
        )
    row.children = {(30003, 50000): [button], (30003, 50005): links}
    main = SimpleNamespace(children={(30101, "row"): [row]})
    ui = SpotifyAccessibility.__new__(SpotifyAccessibility)
    ui.query, ui.kind, ui.bindings = "Test query", "track", {}
    ui.root = lambda: main
    ui.main = lambda root: root
    ui.search_field = lambda root: (None, SimpleNamespace(CurrentValue=ui.query))
    ui.uia = SimpleNamespace(CreatePropertyCondition=lambda prop, value: (prop, value))
    ui.nodes = lambda node, condition: node.children.get(condition, [])
    ui.uri = lambda node: node.link
    item = ui.bind(ui.results(5))[0]
    assert item.title == title and item.creator == creator
    assert item.item_id == "b" * 22 if catalog_link else item.item_id.startswith("native_")
    assert ui.playback_control(item.reference) is button
    button.CurrentName = button.CurrentName.replace("Play ", "Pause ", 1)
    assert ui.context_playing(item.reference)
    button.CurrentName = "Pause"
    row.children[(30003, 50000)].append(
        SimpleNamespace(CurrentName="More options for " + title + " by " + creator)
    )
    assert ui.context_playing(item.reference)
    assert ui.results(5)[0]["id"] == item.item_id
    if catalog_link:
        button.CurrentName = "Play"
        row.children[(30003, 50000)] = [button]
        assert ui.results(5)[0]["id"] == item.item_id
        assert ui.playback_control(item.reference) is button
    else:
        row.children[(30003, 50000)][1].CurrentName = "More options for " + title
        assert ui.results(5)[0]["id"] == item.item_id
    row.GetRuntimeId = lambda: (1, 2, 4)
    with pytest.raises(MediaError, match="SPOTIFY_RESULT_CHANGED"):
        ui.playback_control(item.reference, playing=True)


def test_search_readback_accepts_only_exact_client_space_representation():
    query = "Never Gonna Give You Up"
    assert search_matches(query, query)
    assert search_matches("Never+Gonna+Give+You+Up", query)
    assert not search_matches("Never Gonna Give Up", query)
    assert not search_matches("never+gonna+give+you+up", query)
    assert not search_matches("Never%20Gonna%20Give%20You%20Up", query)
    assert search_matches("A+B+C", "A+B C")


def test_search_uses_package_targeted_winrt_overload(monkeypatch):
    from jarvis.spotify_accessibility import SpotifyAccessibility

    calls = []

    async def launch(uri, options):
        calls.append((uri, options.target_application_package_family_name))
        return False

    monkeypatch.setitem(
        sys.modules,
        "winrt.windows.foundation",
        SimpleNamespace(Uri=lambda value: value),
    )
    monkeypatch.setitem(
        sys.modules,
        "winrt.windows.system",
        SimpleNamespace(
            Launcher=SimpleNamespace(launch_uri_with_options_async=launch),
            LauncherOptions=SimpleNamespace,
        ),
    )
    ui = SpotifyAccessibility.__new__(SpotifyAccessibility)
    ui.root = lambda: None
    with pytest.raises(MediaError, match="SPOTIFY_SEARCH_NAVIGATION_UNAVAILABLE"):
        asyncio.run(ui.search("Never Gonna Give You Up", "track", lambda: None))
    assert calls == [
        (
            "spotify:search:Never+Gonna+Give+You+Up",
            "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
        )
    ]
    assert ui.admitted


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network in offline test"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Process in offline test"))
    clock = ManualClock()
    fake, model = FakeBrowserProvider(clock), ChoiceProvider()
    profile = Profile(
        profile_name="spotify-desktop-fixture",
        model_identity="scripted",
        prompt_version="planner-m2-v10",
        decision_version="decision-m2-v1",
        reply='{"kind":"say","text":"Hello"}',
    )
    broker = build(
        tmp_path / "j.sqlite",
        profile,
        clock,
        provider=model,
        media_config=MediaConfig(enabled=True, spotify=True, spotify_backend="desktop"),
        browser_provider=fake,
    )
    chat = attach(broker, ApplicationsConfig(enabled=True), platform=FakeApplicationPlatform())
    yield broker, chat, fake, model
    broker.media.close()
    broker.store.close()


@pytest.mark.parametrize(
    ("code", "hint"),
    [
        ("SPOTIFY_WINDOW_MINIMIZED", "Restore its main window"),
        ("SPOTIFY_OPEN_ONE_VISIBLE_WINDOW", "Open Spotify"),
        ("SPOTIFY_WINDOW_UNAVAILABLE", "dialog"),
        ("unexpected private diagnostic", "couldn't accept this request"),
    ],
)
def test_native_pre_effect_rejection_is_actionable_and_never_simulated(
    setup, monkeypatch, code, hint
):
    broker, chat, fake, _ = setup
    broker.media.real = True  # Presentation flag only; process/network tools remain forbidden.

    def rejected(request, cancel):
        raise AdmissionRejected(code)

    monkeypatch.setattr(fake, "call", rejected)
    result = chat.submit("Play playlist Synthetic Playlist on Spotify")
    text = conversational_text(result)
    assert result.state == State.FAILED and not result.simulated
    assert hint in text and "SIMULATED" not in text and "gate" not in text
    assert "unexpected private diagnostic" not in text
    assert fake.execution_count == 0 and not broker.media.pending_reviews(broker.store)
    assert broker.store.db.execute("SELECT status FROM attempts").fetchone()[0] == "FAILED"


@pytest.mark.parametrize(
    "case", json.loads(SPOTIFY_DESKTOP_CORPUS.read_bytes())["cases"], ids=lambda c: c["id"]
)
def test_frozen_desktop_corpus_with_all_conversation_controllers(setup, case):
    broker, chat, fake, model = setup
    seed(broker, fake, case)
    result = chat.submit(case["text"])
    for followup in case.get("followups", []):
        result = chat.submit(followup)
    assert broker.last_decision.kind == case["kind"]
    if case["kind"] == "propose_action":
        assert result.state == State.SUCCEEDED, conversational_text(result)
        assert broker.media.pending["arguments"].operation == case["operation"]
        assert fake.execution_count == case.get("calls", 1)
    else:
        assert fake.execution_count == 0
    assert broker.applications.desktop.execution_calls == 0
    assert broker.desktop.original.execution_calls == 0


def test_autoplay_receipt_does_not_repeat_search_selection_or_play(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    chat.submit("Play relaxing music on Spotify", "play")
    one = chat.submit("Play relaxing music on Spotify", "play")
    again = chat.submit("Play relaxing music on Spotify", "play")
    assert one == again and fake.execution_count == 3


def test_explicit_search_choice_receipt_survives_pending_consumption(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    chat.submit("Search Spotify for relaxing music", "search")
    one = chat.submit("1", "choose")
    again = chat.submit("1", "choose")
    assert one == again and fake.execution_count == 2


@pytest.mark.parametrize("query", ["Avid", "playlist Fav Jpop"])
def test_play_request_selects_first_ranked_result_without_showing_list(setup, query):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    fake.catalog = [
        ("a" * 22, "First ranked match", "First creator"),
        ("b" * 22, query.removeprefix("playlist "), "Another creator"),
    ]
    result = chat.submit("Play " + query + " on Spotify", "play-first")
    assert result.state == State.SUCCEEDED
    assert broker.media.pending["arguments"].operation == "play"
    assert fake.execution_count == 3
    assert broker.media.observation.item_id == "a" * 22
    assert "I found:" not in conversational_text(result)
    assert "Choose" not in conversational_text(result)
    assert chat.original.spotify.pending is None
    again = chat.submit("Play " + query + " on Spotify", "play-first")
    assert again == result and fake.execution_count == 3


def test_explicit_search_displays_results_without_playback(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    result = chat.submit("Search Spotify for relaxing music")
    assert fake.execution_count == 1
    assert broker.media.pending["arguments"].operation == "search"
    assert "I found:" in conversational_text(result)


def test_first_result_preference_never_substitutes_an_explicit_creator(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    fake.catalog = [("a" * 22, "Avid", "Different artist")]
    result = chat.submit("Play Avid by Requested Artist on Spotify")
    assert fake.execution_count == 1
    assert broker.media.pending["arguments"].operation == "search"
    assert "nothing was played" in conversational_text(result)
    assert "I found:" not in conversational_text(result)


def test_autoplay_does_not_continue_after_cancelled_search(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    stopped = []
    broker.cancel_requested = lambda: bool(stopped)
    fake.after_execute = lambda: stopped.append(True)
    result = chat.submit("Play relaxing music on Spotify")
    assert result.state != State.SUCCEEDED
    assert fake.execution_count == 1


def test_autoplay_with_no_results_never_selects_or_plays(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    fake.catalog = []
    result = chat.submit("Play relaxing music on Spotify")
    assert fake.execution_count == 1
    assert broker.media.pending["arguments"].operation == "search"
    assert "No matching results" in conversational_text(result)


@pytest.mark.parametrize(
    "title",
    [
        "Never Gonna Give You Up",
        "Please Please Me",
        "The The",
        "Don't Stop Me Now",
        "Save Your Tears",
    ],
)
def test_literal_title_is_preserved_in_music_query(setup, title):
    broker, chat, fake, model = setup
    assert safe_media_query(title) == title
    chat.submit("Search Spotify for " + title)
    assert broker.media.pending["query"] == title


def test_selected_catalog_identity_cannot_be_replaced_by_execution_reply(setup):
    broker, chat, fake, _ = setup
    seed(broker, fake, {})
    original = fake.call

    def wrong(request, cancel):
        result = original(request, cancel)
        if request.arguments.operation == "play":
            return result.model_copy(update={"item_id": "c" * 22})
        return result

    fake.call = wrong
    result = chat.submit("Play Never Gonna Give You Up on Spotify")
    assert result.state != State.SUCCEEDED


@pytest.mark.parametrize(
    "value",
    [
        "http://open.spotify.com/track/" + "a" * 22,
        "https://open.spotify.com.evil.test/track/" + "a" * 22,
        "https://localhost/playlist/" + "a" * 22,
        "https://open.spotify.com/playlist/" + "a" * 22 + "?token=secret",
        "https://user:secret@open.spotify.com/track/" + "a" * 22,
        "https://open.spotify.com:8443/playlist/" + "a" * 22,
        "file:///private.txt",
        "https://open.spotify.com/track/short",
    ],
)
def test_native_result_uri_rejected(value):
    assert content_identity(value) is None


def test_only_exact_catalog_result_links():
    assert content_identity("https://open.spotify.com/playlist/" + "a" * 22) == (
        "playlist",
        "a" * 22,
    )
    assert content_identity("https://open.spotify.com/intl-en/track/" + "b" * 22) == (
        "track",
        "b" * 22,
    )


def test_search_navigation_uri_has_a_fixed_scheme_and_encoded_query():
    from urllib.parse import unquote_plus

    query = "Never Gonna Give You Up by Rick Astley"
    uri = search_uri(query)
    assert uri.startswith("spotify:search:")
    assert " " not in uri
    assert search_uri("Song: A+B & C") == "spotify:search:Song%3A+A%2BB+%26+C"
    assert unquote_plus(uri.removeprefix("spotify:search:")) == query
    with pytest.raises(ValueError):
        search_uri("file:///private/secret.txt")


class UI:
    def __init__(self, playback, kind="track"):
        self.playback = playback
        self.kind = kind
        self.bindings = {}
        self.admitted = False
        self.changed = False
        self.playing_context = False
        self.deliveries = []
        self.records = [
            {
                "id": "a" * 22,
                "title": "Test playlist" if kind == "playlist" else "Test song",
                "creator": "Test owner" if kind == "playlist" else "Test artist",
                "kind": kind,
            }
        ]

    def root(self):
        return None

    def begin_search(self):
        self.bindings = {}
        return self.root()

    async def search(self, query, kind, gate):
        gate()
        self.admitted = True
        self.deliveries.append("search")

    def results(self, limit):
        if self.changed:
            raise MediaError("SPOTIFY_RESULT_CHANGED")
        return self.records

    def bind(self, records):
        self.bindings = {"media_" + "a" * 32: records[0]}
        return [
            MediaItem(
                reference=ref,
                item_id=r["id"],
                title=r["title"],
                creator=r["creator"],
                content_type=r["kind"],
            )
            for ref, r in self.bindings.items()
        ]

    def selected(self, reference):
        self.results(5)
        if reference not in self.bindings:
            raise MediaError("SPOTIFY_RESULT_CHANGED")
        return self.bindings[reference]

    def playback_control(self, reference):
        self.selected(reference)

    def play(self, reference, gate):
        gate()
        self.admitted = True
        self.deliveries.append("play")
        self.playback.state = replace(
            self.playback.state,
            title="Playlist song" if self.kind == "playlist" else "Test song",
            artist="Actual artist" if self.kind == "playlist" else "Test artist",
            state="playing",
        )
        self.playing_context = True

    def context_playing(self, reference):
        return self.playing_context and not self.changed


class Playback:
    def __init__(self):
        self.state = Snapshot(
            "native-session",
            "Spotify.exe",
            "native-id",
            "Earlier song",
            "Earlier artist",
            "paused",
            frozenset({"play", "pause", "resume", "next", "previous"}),
        )
        self.deliveries = []

    async def snapshot(self):
        return self.state

    async def deliver(self, session, operation):
        self.deliveries.append(operation)
        self.state = replace(self.state, state="paused" if operation == "pause" else "playing")
        return True


def request(session, operation, command="execute", kind="track", reference=""):
    return WorkerRequest(
        request_id=uuid4().hex,
        command=command,
        deadline=1100.0,
        query="Test query" if command == "execute" and operation == "search" else "",
        arguments=MediaArguments(
            service="spotify",
            backend="desktop",
            operation=operation,
            search_kind=kind,
            query_hash=hashlib.sha256(b"Test query").hexdigest() if operation == "search" else "",
            session_ref="browser_" + "a" * 32,
            generation=session.generation,
            reference=reference,
        ),
    )


def native_fixture(kind):
    clock = ManualClock()
    playback = Playback()
    ui = UI(playback, kind)

    async def sleep(seconds):
        clock.advance(seconds)

    return SpotifyDesktopSession(ui, playback, clock.now, sleep), ui, playback


@pytest.mark.parametrize("kind", ["track", "playlist"])
def test_native_semantic_workflow_and_independent_observation(kind):
    session, ui, playback = native_fixture(kind)
    search = asyncio.run(session.handle(request(session, "search", kind=kind)))
    asyncio.run(session.handle(request(session, "search", "observe", kind)))
    ref = search.results[0].reference
    selected = asyncio.run(session.handle(request(session, "open", kind=kind, reference=ref)))
    assert ui.deliveries == ["search"] and selected.state == "opened"
    playing = asyncio.run(session.handle(request(session, "play", kind=kind, reference=ref)))
    observed = asyncio.run(session.handle(request(session, "play", "observe", kind, ref)))
    assert observed.item_id == playing.item_id == "a" * 22 and observed.state == "playing"
    asyncio.run(session.handle(request(session, "pause", kind=kind, reference=ref)))
    assert (
        asyncio.run(session.handle(request(session, "pause", "observe", kind, ref))).state
        == "paused"
    )
    asyncio.run(session.handle(request(session, "resume", kind=kind, reference=ref)))
    assert (
        asyncio.run(session.handle(request(session, "resume", "observe", kind, ref))).state
        == "playing"
    )
    assert ui.deliveries == ["search", "play"] and playback.deliveries == ["pause", "resume"]


@pytest.mark.parametrize(
    "change",
    [
        "cancel",
        "stale",
        "wrong-track",
        "lost-playlist-context",
        "lost-track-context",
        "other-player",
    ],
)
def test_native_denial_or_unknown_never_claims_verified_playback(change):
    kind = "playlist" if change == "lost-playlist-context" else "track"
    session, ui, playback = native_fixture(kind)
    search = asyncio.run(session.handle(request(session, "search", kind=kind)))
    ref = search.results[0].reference
    asyncio.run(session.handle(request(session, "open", kind=kind, reference=ref)))
    if change == "stale":
        ui.changed = True
    elif change in {"wrong-track", "other-player", "lost-playlist-context", "lost-track-context"}:
        original = ui.play

        def wrong(ref, gate):
            original(ref, gate)
            if change == "wrong-track":
                playback.state = replace(playback.state, title="Wrong song")
            if change == "other-player":
                playback.state = replace(playback.state, source="Chrome.exe")
            if change in {"lost-playlist-context", "lost-track-context"}:
                ui.playing_context = False

        ui.play = wrong
    with pytest.raises(MediaError):
        asyncio.run(
            session.handle(
                request(session, "play", kind=kind, reference=ref), lambda: change == "cancel"
            )
        )
    if change in {"cancel", "stale"}:
        assert ui.deliveries == ["search"]
    else:
        assert ui.deliveries == ["search", "play"]  # One uncertain delivery; no replay.
