"""Trusted Playwright worker: installed Chrome and two reviewed service adapters only."""

import argparse
import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from uuid import uuid4

from jarvis.chrome_identity import load_registration, private_browser_root, validate_profile
from jarvis.media_data import (
    MediaError,
    MediaItem,
    MediaObservation,
    WorkerRequest,
    item_id,
    media_url,
    parse_record,
)
from jarvis.public_transport import public_address

# Purpose-specific trusted scripts. No strings from the model become scripts.
# The first tracks genuine user input; the second observes player state only.
USER_ACTIVITY = """(() => {
  window.__jarvisInput = 0;
  for (const event of ['pointerdown', 'keydown', 'wheel', 'touchstart']) {
    document.addEventListener(event, e => {if (e.isTrusted) window.__jarvisInput++;}, true);
  }
})()"""
READ_INPUT = "() => window.__jarvisInput || 0"
READ_VIDEO = """() => {
 const v = document.querySelector('video');
 return v ? {paused:v.paused, ready:v.readyState, time:v.currentTime, ended:v.ended,
 error:!!v.error, ad:!!document.querySelector('#movie_player.ad-showing')} : null;
}"""
READ_VIDEO_ID = """() => {
 const player = document.getElementById('movie_player');
 const data = player && typeof player.getVideoData === 'function' ? player.getVideoData() : null;
 return data && typeof data.video_id === 'string' ? data.video_id : '';
}"""
TITLE_SELECTOR = "ytd-watch-metadata h1:visible"
READ_VIDEO_TITLE = """() => {
 const player = document.getElementById('movie_player');
 const data = player && typeof player.getVideoData === 'function' ? player.getVideoData() : null;
 return data && typeof data.title === 'string' ? data.title : '';
}"""
WAIT_VIDEO_METADATA = """() => {
 const player = document.getElementById('movie_player');
 const data = player && typeof player.getVideoData === 'function' ? player.getVideoData() : null;
 return !!(data && data.video_id && data.title);
}"""


def safe_worker_error(exc):
    if isinstance(exc, MediaError):
        return exc.code
    # Classify trusted library failures without returning URLs, DOM or raw exceptions.
    if type(exc).__name__ == "TimeoutError":
        return "BROWSER_LOCATOR_OR_NAVIGATION_TIMEOUT"
    if type(exc).__name__ == "ValidationError":
        return "BROWSER_INVALID_EXTERNAL_METADATA"
    if "strict mode violation" in str(exc).casefold():
        return "BROWSER_AMBIGUOUS_SEMANTIC_LOCATOR"
    if "net::err_" in str(exc).casefold():
        return "BROWSER_NAVIGATION_FAILED"
    return "BROWSER_OPERATION_FAILED"


def public_browser_destination(url, resolver=socket.getaddrinfo):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise MediaError("BROWSER_DESTINATION_REJECTED")
    answers = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    for answer in answers:
        try:
            public_address(answer[4][0])
        except ValueError as exc:
            raise MediaError("BROWSER_PRIVATE_DESTINATION_REJECTED") from exc
    if not answers:
        raise MediaError("BROWSER_DNS_FAILED")


def youtube_results(page, limit, existing=None):
    """Reviewed YouTube custom elements and video links; never arbitrary selectors."""
    results, seen = [], set()
    rows = page.locator("ytd-video-renderer")
    for ordinal in range(min(rows.count(), 20)):
        row = rows.nth(ordinal)
        link = row.locator("a#video-title").first
        href = link.get_attribute("href")
        if not href:
            continue
        try:
            identity = item_id("youtube", urljoin("https://www.youtube.com", href).split("&")[0])
        except ValueError:
            continue
        if identity in seen:
            continue
        seen.add(identity)
        title = " ".join((link.get_attribute("title") or link.inner_text()).split())[:240]
        channel = row.locator("ytd-channel-name").first
        creator = " ".join(channel.inner_text().split())[:160] if channel.count() else ""
        duration = row.locator("ytd-thumbnail-overlay-time-status-renderer").first
        duration_text = " ".join(duration.inner_text().split())[:32] if duration.count() else ""
        ref = next(
            (r.reference for r in existing or [] if r.item_id == identity), "media_" + uuid4().hex
        )
        results.append(
            MediaItem(
                reference=ref,
                item_id=identity,
                title=title,
                creator=creator,
                duration=duration_text,
                url=f"https://www.youtube.com/watch?v={identity}",
            )
        )
        if len(results) == limit:
            break
    return results


def youtube_state(page):
    text = (
        page.locator("#player-error-message-container").inner_text(timeout=1000)
        if page.locator("#player-error-message-container").count()
        else ""
    )
    value = text.casefold()
    if "age" in value:
        return "age_restricted"
    if "country" in value or "region" in value:
        return "region_restricted"
    if "sign in" in value:
        return "login_required"
    if text.strip():
        return "error"
    state = page.evaluate(READ_VIDEO)
    if not state:
        return "unknown"
    if state["ad"]:
        return "ad"
    if state["error"] or state["ended"]:
        return "error"
    if state["ready"] < 3:
        return "loading"
    return "paused" if state["paused"] else "playing"


def netflix_results(page, limit, existing=None):
    results, seen = [], set()
    # Reviewed Netflix title links; no card clicks, no playback controls.
    links = page.locator("a[href^='/title/']")
    for ordinal in range(min(links.count(), 30)):
        link = links.nth(ordinal)
        href = link.get_attribute("href")
        try:
            identity = item_id(
                "netflix", urljoin("https://www.netflix.com", href or "").split("?")[0]
            )
        except ValueError:
            continue
        if identity in seen:
            continue
        title = (
            link.get_attribute("aria-label") or link.get_attribute("title") or link.inner_text()
        ).strip()[:240]
        if not title:
            image = link.locator("img[alt]").first
            title = image.get_attribute("alt")[:240] if image.count() else ""
        if not title:
            continue
        seen.add(identity)
        ref = next(
            (r.reference for r in existing or [] if r.item_id == identity), "media_" + uuid4().hex
        )
        results.append(
            MediaItem(
                reference=ref,
                item_id=identity,
                title=title,
                url=f"https://www.netflix.com/title/{identity}",
            )
        )
        if len(results) == limit:
            break
    return results


class ChromeSession:
    def __init__(self, registration, repository, *, factory=None, clock=time.time):
        self.registration, self.repository = registration, repository
        self.factory, self.clock = factory, clock
        self.runtime = None
        self.context = None
        self.pages = {}
        self.session_ref = None
        self.generation = 0
        self.expected_activity = {}
        self.results = {}
        self.selected = {}
        self.blocked_downloads = 0
        self.blocked_destination = False
        self.admitted = False
        self.lock = None
        self.desktop_lease = None
        self.limit = 5
        self.last_request_at = clock()
        self.active_deadline = None
        self.spotify = None

    def launch(self):
        identity = load_registration(self.registration)
        root = validate_profile(private_browser_root(), self.repository)
        from jarvis.notepad import DesktopLease

        lease = DesktopLease(root.parent / "chrome-profile-lease.lock")
        lease.__enter__()
        self.lock = lease
        if self.factory is None:
            from playwright.sync_api import sync_playwright

            self.runtime = sync_playwright().start()
        else:
            self.runtime = self.factory()
        # No CDP attachment, ports, bundled Chromium, extensions or personal tabs.
        self.context = self.runtime.chromium.launch_persistent_context(
            str(root),
            executable_path=identity.executable,
            channel="chrome",
            headless=False,
            accept_downloads=False,
            no_viewport=True,
            locale="en-US",
            chromium_sandbox=True,
            service_workers="block",
            timeout=15000,
            args=[
                "--disable-extensions",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        self.context.set_default_timeout(3000)
        self.context.set_default_navigation_timeout(12000)
        self.context.add_init_script(USER_ACTIVITY)
        self.context.route("**/*", self.route)
        # A fresh managed context has only its launch page. Never enumerate personal contexts.
        initial = self.context.pages
        if len(initial) > 1 or any(p.url != "about:blank" for p in initial):
            raise MediaError("RESTORED_TABS_REQUIRE_MANUAL_REVIEW")
        self.context.on("page", self.new_page)

    def acquire_lease(self):
        if self.desktop_lease is not None:
            raise MediaError("UNVERIFIED_BROWSER_STEP_PENDING")
        from jarvis.notepad import DesktopLease

        lease = DesktopLease(private_browser_root().parents[1] / "desktop-lease.lock")
        lease.__enter__()
        self.desktop_lease = lease

    def release_lease(self):
        if self.desktop_lease is not None:
            self.desktop_lease.__exit__(None, None, None)
            self.desktop_lease = None

    def new_page(self, page):
        # Explicit service tabs are added to self.pages immediately by the worker.
        page.on("download", self.download)
        page.on("filechooser", lambda chooser: chooser.set_files([]))

    def download(self, download):
        self.blocked_downloads += 1
        download.cancel()

    def route(self, route):
        try:
            request = route.request
            public_browser_destination(request.url)
            if request.is_navigation_request() and request.frame == request.frame.page.main_frame:
                service = next(
                    (name for name, page in self.pages.items() if page == request.frame.page), None
                )
                hosts = {
                    "youtube": {"www.youtube.com", "accounts.google.com"},
                    "netflix": {"www.netflix.com"},
                }.get(service, set())
                if urlsplit(request.url).hostname not in hosts:
                    raise MediaError("UNEXPECTED_TOP_LEVEL_ORIGIN")
                if request.frame.page not in self.pages.values():
                    raise MediaError("UNOWNED_POPUP_REJECTED")
            route.continue_()
        except OSError:
            # Failed DNS for an optional public resource is unavailable content,
            # not evidence of a private destination. It is still never fetched.
            if route.request.is_navigation_request():
                self.blocked_destination = True
                self.blocked_reason = "BROWSER_DNS_FAILED"
            route.abort()
        except ValueError as exc:
            self.blocked_destination = True
            self.blocked_reason = safe_worker_error(exc)
            route.abort()

    def page_for(self, service):
        if service not in self.pages:
            if len(self.pages) >= 2:
                raise MediaError("BROWSER_TAB_BUDGET")
            # Reuse only the initial blank page of this newly launched context.
            blank = next(
                (
                    p
                    for p in self.context.pages
                    if p.url == "about:blank" and p not in self.pages.values()
                ),
                None,
            )
            page = blank or self.context.new_page()
            self.pages[service] = page
            self.new_page(page)

            def navigated(frame):
                if frame == page.main_frame:
                    self.generation += 1

            page.on("framenavigated", navigated)
        return self.pages[service]

    def observe(self, args):
        page = self.pages.get(args.service)
        if page is None:
            return MediaObservation(
                session_ref=args.session_ref,
                service=args.service,
                generation=self.generation,
                observed_at=float(self.clock()),
                state="ready",
            )
        if page.is_closed():
            raise MediaError("JARVIS_PAGE_CLOSED")
        host = urlsplit(page.url).hostname
        if host == "accounts.google.com" and args.service == "youtube":
            state, identity, title = "login_required", "", ""
        else:
            media_url(args.service, page.url)
            identity, title, state = "", "", "ready"
            if args.service == "youtube":
                if (
                    page.locator("form[action*='consent']").count()
                    or page.get_by_text("Before you continue to YouTube", exact=False).count()
                ):
                    state = "challenge"
                elif urlsplit(page.url).path == "/results":
                    state = "results"
                elif urlsplit(page.url).path == "/watch":
                    expected_identity = item_id("youtube", page.url)
                    identity = page.evaluate(READ_VIDEO_ID)
                    if identity != expected_identity:
                        identity = ""
                    title = (
                        " ".join(page.locator(TITLE_SELECTOR).first.inner_text().split())[:240]
                        if page.locator(TITLE_SELECTOR).count()
                        else " ".join(page.evaluate(READ_VIDEO_TITLE).split())[:240]
                    )
                    state = youtube_state(page)
                    if not identity:
                        state = "unknown"
            elif args.service == "netflix":
                if (
                    urlsplit(page.url).path.startswith(("/login", "/signup"))
                    or page.locator("input[type='password']").count()
                ):
                    state = "login_required"
                elif urlsplit(page.url).path == "/search":
                    state = "results"
                elif urlsplit(page.url).path.startswith("/title/"):
                    identity = item_id("netflix", page.url)
                    heading = page.locator("h1").first
                    title = heading.inner_text().strip()[:240] if heading.count() else ""
                    state = "opened" if title else "unknown"
        authenticated = False if state == "login_required" else None
        if args.service == "netflix" and state != "login_required":
            authenticated = True if page.locator("a[href='/SignOut']").count() else None
        results = self.results.get(args.service, [])
        if state == "results":
            live = (
                youtube_results(page, self.limit, results)
                if args.service == "youtube"
                else netflix_results(page, self.limit, results)
            )
            if [(r.item_id, r.title) for r in live] != [(r.item_id, r.title) for r in results]:
                state = "unknown"
            results = live
        return MediaObservation(
            session_ref=args.session_ref,
            service=args.service,
            generation=self.generation,
            observed_at=float(self.clock()),
            state=state,
            item_id=identity,
            title=title,
            results=results if state == "results" else [],
            authenticated=authenticated,
            downloads_blocked=self.blocked_downloads,
        )

    def handle(self, request):
        self.admitted = False
        self.last_request_at = self.clock()
        self.active_deadline = min(request.deadline, self.clock() + 30)
        args = request.arguments
        self.limit = request.result_limit
        if self.clock() >= request.deadline:
            raise MediaError("WORKER_DEADLINE")
        if args.service == "spotify":
            from jarvis.spotify_api import SpotifyAPI

            if self.spotify is None:
                self.spotify = SpotifyAPI()
            try:
                return self.spotify.handle(request)
            finally:
                self.admitted = self.spotify.admitted
        if self.session_ref not in {None, args.session_ref}:
            raise MediaError("WORKER_SESSION_CHANGED")
        self.session_ref = args.session_ref
        if request.command != "execute":
            return self.observe(args)
        if args.operation == "current":
            # Explicit read-only reobservation can refresh after manual navigation/input.
            observed = self.observe(args)
            page = self.pages.get(args.service)
            if page:
                self.expected_activity[args.service] = page.evaluate(READ_INPUT)
            return observed
        if args.generation != self.generation:
            raise MediaError("STALE_NAVIGATION_GENERATION")
        page = self.pages.get(args.service)
        if page and page.evaluate(READ_INPUT) != self.expected_activity.get(args.service, 0):
            # A fresh current-state request is a read-only reobservation handoff.
            if args.operation != "current":
                raise MediaError("USER_TAKEOVER_REOBSERVE_REQUIRED")
        if args.operation == "open":
            items = self.results.get(args.service, [])
            selected = next((item for item in items if item.reference == args.reference), None)
            if selected is None:
                raise MediaError("STALE_RESULT_REFERENCE")
            live = (
                youtube_results(page, self.limit, items)
                if args.service == "youtube"
                else netflix_results(page, self.limit, items)
            )
            if [(i.item_id, i.title) for i in live] != [(i.item_id, i.title) for i in items]:
                raise MediaError("RESULTS_CHANGED_RESEARCH_REQUIRED")
        if args.operation in {"play", "pause", "resume"}:
            selected = self.selected.get(args.service)
            if not selected or args.reference != selected.reference:
                raise MediaError("STALE_MEDIA_REFERENCE")
            before = self.observe(args)
            if before.item_id != selected.item_id or before.state not in {"playing", "paused"}:
                # Ads/challenges are observed but never clicked through.
                return before
        if self.clock() >= request.deadline:
            raise MediaError("WORKER_DEADLINE")
        self.acquire_lease()
        if self.clock() >= request.deadline:
            self.release_lease()
            raise MediaError("WORKER_DEADLINE")
        self.admitted = True
        if self.context is None:
            self.launch()
        page = self.page_for(args.service)
        self.blocked_destination = False
        self.blocked_reason = "BROWSER_NETWORK_POLICY_BLOCKED"
        if args.operation == "search":
            url = (
                "https://www.youtube.com/results?" + urlencode({"search_query": request.query})
                if args.service == "youtube"
                else "https://www.netflix.com/search?" + urlencode({"q": request.query})
            )
            page.goto(url, wait_until="domcontentloaded")
            if args.service == "youtube":
                page.locator("ytd-video-renderer, #message").first.wait_for(timeout=7000)
                self.results[args.service] = youtube_results(page, self.limit)
            else:
                if self.observe(args).state != "login_required":
                    page.locator("a[href^='/title/'], .noResults").first.wait_for(timeout=7000)
                    self.results[args.service] = netflix_results(page, self.limit)
        elif args.operation == "login":
            page.goto(
                "https://www.youtube.com/"
                if args.service == "youtube"
                else "https://www.netflix.com/login",
                wait_until="domcontentloaded",
            )
        elif args.operation == "open":
            page.goto(selected.url, wait_until="domcontentloaded")
            self.selected[args.service] = selected
            if args.service == "youtube":
                page.locator("video, #player-error-message-container").first.wait_for(timeout=7000)
                if page.locator("#player-error-message-container").count() == 0:
                    page.wait_for_function(WAIT_VIDEO_METADATA, timeout=5000)
        elif args.operation in {"play", "pause", "resume"}:
            desired = "paused" if args.operation == "pause" else "playing"
            if before.state != desired:
                button = page.locator("#movie_player").get_by_role(
                    "button", name=re.compile(r"^Pause" if desired == "paused" else r"^Play")
                )
                button.click(timeout=3000)
        elif args.operation != "current":
            raise MediaError("UNSUPPORTED_SEMANTIC_OPERATION")
        self.expected_activity[args.service] = page.evaluate(READ_INPUT)
        self.generation += 1
        if self.blocked_destination:
            raise MediaError(self.blocked_reason)
        return self.observe(args)

    def close(self):
        # Only the context launched with this dedicated profile; ordinary Chrome is never attached.
        try:
            if self.context:
                self.context.close()
        finally:
            self.release_lease()
            if self.runtime:
                self.runtime.stop()
            if self.lock:
                self.lock.__exit__(None, None, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    session = ChromeSession(args.registration, args.repository)
    finished = threading.Event()

    def watchdog():
        while not finished.wait(0.05):
            if session.active_deadline is not None and time.time() >= session.active_deadline:
                # Contain this owned worker if a browser/DNS call blocks or parent disappears.
                # Chrome effects already sent remain uncertain; no restart/replay.
                os._exit(74)

    threading.Thread(target=watchdog, daemon=True).start()
    seen = {}
    try:
        while raw := sys.stdin.buffer.readline(8194):
            if len(raw) > 8192 or not raw.endswith(b"\n"):
                break
            request_id = ""
            try:
                request = parse_record(raw, WorkerRequest)
                request_id = request.request_id
                if request_id in seen:
                    saved, response = seen[request_id]
                    if saved != request.model_dump_json():
                        raise MediaError("DUPLICATE_WORKER_ID_CHANGED")
                else:
                    observation = session.handle(request)
                    if request.command in {"observe", "snapshot"}:
                        session.release_lease()
                    response = {
                        "version": 1,
                        "request_id": request_id,
                        "admitted": session.admitted,
                        "observation": observation.model_dump(),
                        "error": "",
                    }
                    seen[request_id] = (request.model_dump_json(), response)
                    if len(seen) > 128:
                        raise MediaError("WORKER_REQUEST_BUDGET")
            except Exception as exc:
                session.release_lease()
                response = {
                    "version": 1,
                    "request_id": request_id,
                    "admitted": session.admitted,
                    "observation": None,
                    "error": safe_worker_error(exc),
                }
            sys.stdout.buffer.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
            sys.stdout.buffer.flush()
            session.active_deadline = None
    finally:
        finished.set()
        session.close()


if __name__ == "__main__":
    main()
