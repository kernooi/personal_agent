"""Offline Chrome identity, semantic DOM and worker-boundary regression tests."""

import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.browser_worker import (
    READ_VIDEO,
    READ_VIDEO_ID,
    READ_VIDEO_TITLE,
    ChromeSession,
    netflix_results,
    public_browser_destination,
    safe_worker_error,
    youtube_results,
    youtube_state,
)
from jarvis.chrome_identity import (
    ChromeIdentity,
    create_registration,
    load_registration,
    validate_profile,
)
from jarvis.domain import AdmissionRejected
from jarvis.media_data import MediaArguments, MediaError, WorkerRequest, text_hash


class Locator:
    def __init__(self, values):
        self.values = values

    @property
    def first(self):
        return self.nth(0)

    def nth(self, i):
        return Locator(self.values[i : i + 1])

    def count(self):
        return len(self.values)

    def locator(self, selector):
        item = self.values[0]
        return Locator(item.get(selector, []))

    def get_attribute(self, name):
        return self.values[0].get(name)

    def inner_text(self, **kwargs):
        return self.values[0].get("text", "")


class Page:
    def __init__(self, rows=None, error="", video=None):
        self.rows = rows or []
        self.error, self.video = error, video
        self.scripts = []
        self.url = "https://www.youtube.com/results?search_query=synthetic"

    def locator(self, selector):
        if selector == "#player-error-message-container":
            return Locator([{"text": self.error}] if self.error else [])
        return Locator(self.rows)

    def evaluate(self, script):
        self.scripts.append(script)
        assert script == READ_VIDEO
        return self.video

    def is_closed(self):
        return False


def row(identity, title="Synthetic", href=None):
    return {
        "a#video-title": [{"href": href or "/watch?v=" + identity, "title": title}],
        "ytd-channel-name": [{"text": "Synthetic creator"}],
        "ytd-thumbnail-overlay-time-status-renderer": [{"text": "03:00"}],
    }


def test_youtube_extraction_bounded_deduplicates_and_rejects_unsafe_urls():
    page = Page(
        [
            row("dQw4w9WgXcQ"),
            row("dQw4w9WgXcQ"),
            row("bad", href="http://localhost"),
            row("bad", href="https://evil.test/watch?v=aaaaaaaaaaa"),
            *[row(str(i).zfill(11)) for i in range(10)],
        ]
    )
    results = youtube_results(page, 3)
    assert len(results) == 3
    assert [r.item_id for r in results] == ["dQw4w9WgXcQ", "00000000000", "00000000001"]
    assert len({r.reference for r in results}) == 3
    assert all(r.url.startswith("https://www.youtube.com/watch?v=") for r in results)


def test_youtube_changed_layout_does_not_fabricate_results():
    assert youtube_results(Page(), 5) == []


def test_youtube_runtime_refs_remain_for_same_result_but_not_new_items():
    old = youtube_results(Page([row("dQw4w9WgXcQ")]), 5)
    fresh = youtube_results(Page([row("dQw4w9WgXcQ"), row("aaaaaaaaaaa")]), 5, old)
    assert old[0].reference == fresh[0].reference
    assert fresh[1].reference != old[0].reference


@pytest.mark.parametrize(
    "video,expected",
    [
        (None, "unknown"),
        (
            {"ad": True, "paused": False, "ready": 4, "time": 10, "ended": False, "error": False},
            "ad",
        ),
        (
            {"ad": False, "paused": False, "ready": 1, "time": 0, "ended": False, "error": False},
            "loading",
        ),
        (
            {"ad": False, "paused": False, "ready": 4, "time": 10, "ended": False, "error": False},
            "playing",
        ),
        (
            {"ad": False, "paused": True, "ready": 4, "time": 10, "ended": False, "error": False},
            "paused",
        ),
        (
            {"ad": False, "paused": False, "ready": 4, "time": 10, "ended": False, "error": True},
            "error",
        ),
    ],
)
def test_youtube_player_observations_distinguish_partial_states(video, expected):
    page = Page(video=video)
    assert youtube_state(page) == expected
    assert page.scripts == [READ_VIDEO]


@pytest.mark.parametrize(
    "text,state",
    [
        ("Sign in to watch", "login_required"),
        ("Age verification", "age_restricted"),
        ("Not available in your country", "region_restricted"),
        ("Service unavailable", "error"),
    ],
)
def test_youtube_service_error_states_are_not_playback(text, state):
    assert youtube_state(Page(error=text)) == state


def test_netflix_title_extraction_never_returns_playback_urls():
    page = Page(
        [
            {"href": "/title/1234", "aria-label": "Synthetic title"},
            {"href": "/watch/1234", "aria-label": "Playback is excluded"},
            {"href": "https://localhost/title/999", "aria-label": "Unsafe"},
        ]
    )
    results = netflix_results(page, 5)
    assert len(results) == 1
    assert results[0].item_id == "1234"
    assert results[0].url == "https://www.netflix.com/title/1234"


def identity():
    return ChromeIdentity(
        executable="C:/Program Files/Google/Chrome/Application/chrome.exe",
        sha256="a" * 64,
        version="154.0.0.0",
        product="Google Chrome",
        signer="O=Google LLC,",
    )


def test_private_profile_rejects_normal_chrome_and_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    expected = tmp_path / "local/Jarvis/browser/chrome"
    assert validate_profile(expected, tmp_path / "repo") == expected.absolute()
    with pytest.raises(MediaError):
        validate_profile(tmp_path / "local/Google/Chrome/User Data", tmp_path / "repo")
    with pytest.raises(MediaError):
        validate_profile(expected, tmp_path)


def test_registration_pins_identity_and_preserves_existing_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr("jarvis.chrome_identity.discover_chrome", identity)
    path = tmp_path / "local/Jarvis/chrome-registration.json"
    pinned = create_registration(path, tmp_path / "repo")
    assert load_registration(path) == pinned
    with pytest.raises(MediaError, match="EXISTING_REGISTRATION"):
        create_registration(path, tmp_path / "repo")
    monkeypatch.setattr(
        "jarvis.chrome_identity.discover_chrome",
        lambda: identity().model_copy(update={"sha256": "b" * 64}),
    )
    with pytest.raises(MediaError, match="IDENTITY_CHANGED"):
        load_registration(path)


def test_existing_profile_data_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr("jarvis.chrome_identity.discover_chrome", identity)
    root = tmp_path / "local/Jarvis/browser/chrome"
    root.mkdir(parents=True)
    marker = root / "existing_sensitive_marker"
    marker.write_text("synthetic credential material")
    with pytest.raises(MediaError, match="EXISTING_PROFILE_PRESERVED"):
        create_registration(tmp_path / "local/Jarvis/registration.json", tmp_path / "repo")
    assert marker.read_text() == "synthetic credential material"


def test_browser_download_cancel_and_no_open_or_execution():
    session = ChromeSession(Path("synthetic"), Path("synthetic"))
    called = []
    session.download(SimpleNamespace(cancel=lambda: called.append("cancel")))
    assert called == ["cancel"]
    assert session.blocked_downloads == 1


def test_worker_session_generation_before_launch_and_snapshot_has_no_effect():
    session = ChromeSession(Path("synthetic"), Path("synthetic"), clock=lambda: 1000.0)
    session.launch = lambda: pytest.fail("Unexpected Chrome launch")
    args = MediaArguments(service="youtube", operation="current", session_ref="browser_" + "a" * 32)
    snapshot = session.handle(
        WorkerRequest(request_id="a" * 32, command="snapshot", arguments=args, deadline=1200.0)
    )
    assert snapshot.state == "ready"
    assert session.context is None
    stale = MediaArguments(
        service="youtube",
        operation="search",
        generation=1,
        query_hash=text_hash("cats"),
        session_ref=args.session_ref,
    )
    with pytest.raises(MediaError, match="STALE_NAVIGATION"):
        session.handle(
            WorkerRequest(
                request_id="b" * 32,
                command="execute",
                arguments=stale,
                query="cats",
                deadline=1200.0,
            )
        )


def test_worker_changed_session_and_expired_request_never_launch():
    session = ChromeSession(Path("synthetic"), Path("synthetic"), clock=lambda: 1000.0)
    session.session_ref = "browser_" + "a" * 32
    args = MediaArguments(service="youtube", operation="current", session_ref="browser_" + "b" * 32)
    with pytest.raises(MediaError, match="SESSION_CHANGED"):
        session.handle(
            WorkerRequest(request_id="a" * 32, command="execute", arguments=args, deadline=1200.0)
        )
    with pytest.raises(MediaError, match="DEADLINE"):
        session.handle(
            WorkerRequest(request_id="b" * 32, command="execute", arguments=args, deadline=999.0)
        )


def test_browser_private_dns_in_mixed_answer_set_is_rejected():
    def resolver(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))
            for ip in ["8.8.8.8", "127.0.0.1"]
        ]

    with pytest.raises(MediaError):
        public_browser_destination("https://www.youtube.com/", resolver)


def test_closed_owned_page_is_not_replaced_with_personal_chrome():
    session = ChromeSession(Path("synthetic"), Path("synthetic"), clock=lambda: 1000.0)
    session.pages["youtube"] = SimpleNamespace(is_closed=lambda: True)
    args = MediaArguments(service="youtube", operation="current", session_ref="browser_" + "a" * 32)
    with pytest.raises(MediaError, match="PAGE_CLOSED"):
        session.observe(args)


@pytest.mark.parametrize(
    "service,host,allowed",
    [
        ("youtube", "www.youtube.com", True),
        ("youtube", "accounts.google.com", True),
        ("youtube", "www.netflix.com", False),
        ("netflix", "www.netflix.com", True),
        ("netflix", "accounts.google.com", False),
        ("netflix", "example.com", False),
    ],
)
def test_navigation_is_bound_to_owned_service(monkeypatch, service, host, allowed):
    monkeypatch.setattr("jarvis.browser_worker.public_browser_destination", lambda url: None)
    session = ChromeSession(Path("synthetic"), Path("synthetic"))
    page = SimpleNamespace()
    frame = SimpleNamespace(page=page)
    page.main_frame = frame
    session.pages[service] = page
    delivered = []
    route = SimpleNamespace(
        request=SimpleNamespace(
            url=f"https://{host}/", frame=frame, is_navigation_request=lambda: True
        ),
        continue_=lambda: delivered.append("continue"),
        abort=lambda: delivered.append("abort"),
    )
    session.route(route)
    assert delivered == ["continue" if allowed else "abort"]


def test_launch_uses_installed_chrome_and_exclusive_private_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    root = tmp_path / "local/Jarvis/browser/chrome"
    root.mkdir(parents=True)
    monkeypatch.setattr("jarvis.browser_worker.load_registration", lambda path: identity())
    calls = []
    context = SimpleNamespace(
        pages=[SimpleNamespace(url="about:blank")],
        set_default_timeout=lambda timeout: None,
        set_default_navigation_timeout=lambda timeout: None,
        add_init_script=lambda script: None,
        route=lambda pattern, callback: None,
        on=lambda event, callback: None,
        close=lambda: None,
    )
    runtime = SimpleNamespace(
        chromium=SimpleNamespace(
            launch_persistent_context=lambda path, **options: (
                calls.append((path, options)) or context
            )
        ),
        stop=lambda: None,
    )
    session = ChromeSession(Path("synthetic"), tmp_path / "repo", factory=lambda: runtime)
    try:
        session.launch()
        path, options = calls[0]
        assert Path(path) == root
        assert options["executable_path"] == identity().executable
        assert options["channel"] == "chrome"
        assert options["chromium_sandbox"] is True
        assert options["accept_downloads"] is False
        assert options["service_workers"] == "block"
        assert not any("remote-debugging-port" in arg for arg in options["args"])
        other = ChromeSession(Path("synthetic"), tmp_path / "repo", factory=lambda: runtime)
        with pytest.raises(AdmissionRejected, match="lease is busy"):
            other.launch()
        assert len(calls) == 1
    finally:
        session.close()


def test_external_multiline_labels_are_inert_normalized_data():
    rows = [row("dQw4w9WgXcQ", title="Public\nvideo")]
    rows[0]["ytd-channel-name"] = [{"text": "Public\ncreator"}]
    result = youtube_results(Page(rows), 5)[0]
    assert result.title == "Public video"
    assert result.creator == "Public creator"


@pytest.mark.parametrize(
    "error,expected",
    [
        (MediaError("STALE_RESULT_REFERENCE"), "STALE_RESULT_REFERENCE"),
        (TimeoutError("synthetic private URL"), "BROWSER_LOCATOR_OR_NAVIGATION_TIMEOUT"),
        (
            ValueError("strict mode violation: synthetic private DOM"),
            "BROWSER_AMBIGUOUS_SEMANTIC_LOCATOR",
        ),
        (ValueError("net::ERR_FAILED https://private.invalid/"), "BROWSER_NAVIGATION_FAILED"),
        (ValueError("synthetic secret material"), "BROWSER_OPERATION_FAILED"),
    ],
)
def test_worker_error_classification_never_returns_raw_details(error, expected):
    assert safe_worker_error(error) == expected


@pytest.mark.parametrize("player_id", ["dQw4w9WgXcQ", "aaaaaaaaaaa"])
def test_player_identity_is_observed_independently_of_watch_url(player_id):
    class ObservedPage:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        def is_closed(self):
            return False

        def locator(self, selector):
            return Locator([])

        def get_by_text(self, text, **kwargs):
            return Locator([])

        def evaluate(self, script):
            return {
                READ_VIDEO_ID: player_id,
                READ_VIDEO_TITLE: "Observed public title",
                READ_VIDEO: {
                    "paused": True,
                    "ready": 4,
                    "time": 1,
                    "ended": False,
                    "error": False,
                    "ad": False,
                },
            }[script]

    session = ChromeSession(Path("synthetic"), Path("synthetic"), clock=lambda: 1000.0)
    session.pages["youtube"] = ObservedPage()
    args = MediaArguments(service="youtube", operation="current", session_ref="browser_" + "a" * 32)
    observation = session.observe(args)
    assert observation.item_id == (player_id if player_id == "dQw4w9WgXcQ" else "")
    assert observation.state == ("paused" if player_id == "dQw4w9WgXcQ" else "unknown")
    assert observation.title == "Observed public title"
