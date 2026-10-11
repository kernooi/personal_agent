"""Spotify-only Windows media sessions. No keys, browser, network or app launching."""

import asyncio
import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from jarvis.browser_transport import BrowserWorkerProvider
from jarvis.domain import AdmissionRejected
from jarvis.media_data import MediaError, MediaObservation, WorkerRequest, parse_record

# Exact source identifiers, never substring/title/current-player matching.
# SourceAppUserModelId is OS-reported identity, not an anti-malware attestation.
SPOTIFY_IDS = frozenset({"Spotify.exe", "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"})
OPERATIONS = frozenset({"current", "play", "pause", "resume", "next", "previous"})


def select_spotify(sessions):
    if len(sessions) > 64:
        raise MediaError("WINDOWS_MEDIA_SESSION_LIMIT")
    matches = [s for s in sessions if s.source_app_user_model_id in SPOTIFY_IDS]
    if len(matches) != 1:
        raise MediaError("SPOTIFY_SESSION_MISSING" if not matches else "SPOTIFY_SESSIONS_AMBIGUOUS")
    return matches[0]


@dataclass(frozen=True)
class Snapshot:
    session: object
    source: str
    item_id: str
    title: str
    artist: str
    state: str
    controls: frozenset[str]


class WinRTBackend:
    def __init__(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

        self.manager_type = GlobalSystemMediaTransportControlsSessionManager
        self.manager = None
        self.identity_salt = uuid4().bytes

    async def snapshot(self):
        if self.manager is None:
            self.manager = await self.manager_type.request_async()
        session = select_spotify(list(self.manager.get_sessions()))
        properties = await session.try_get_media_properties_async()
        info = session.get_playback_info()
        title, artist = properties.title[:240], properties.artist[:160]
        # No unique catalog ID is exposed by GSMTC. Bind the observed metadata;
        # identical tracks/metadata cannot be distinguished by this interface.
        identity = hashlib.sha256(
            json.dumps(
                [
                    properties.title,
                    properties.artist,
                    properties.album_title,
                    properties.track_number,
                ]
            ).encode()
            + self.identity_salt
        ).hexdigest()
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus,
        )

        status = GlobalSystemMediaTransportControlsSessionPlaybackStatus
        state = (
            "playing"
            if info.playback_status == status.PLAYING
            else "paused"
            if info.playback_status == status.PAUSED
            else "unknown"
        )
        controls = info.controls
        enabled = frozenset(
            op
            for op, supported in {
                "play": controls.is_play_enabled,
                "resume": controls.is_play_enabled,
                "pause": controls.is_pause_enabled,
                "next": controls.is_next_enabled,
                "previous": controls.is_previous_enabled,
            }.items()
            if supported
        )
        return Snapshot(
            session, session.source_app_user_model_id, identity, title, artist, state, enabled
        )

    async def deliver(self, session, operation):
        method = {
            "play": session.try_play_async,
            "resume": session.try_play_async,
            "pause": session.try_pause_async,
            "next": session.try_skip_next_async,
            "previous": session.try_skip_previous_async,
        }[operation]
        return await method()


class WindowsMediaSession:
    def __init__(self, backend, clock=time.time):
        self.backend, self.clock = backend, clock
        self.generation = 0
        self.session_ref = None
        self.device_ref = "device_" + uuid4().hex
        self.selected = None
        self.expected = None
        self.admitted = False

    async def handle(self, request, cancelled=lambda: False):
        self.admitted = False
        args = request.arguments

        def gate():
            if cancelled() or self.clock() >= request.deadline:
                raise MediaError("WINDOWS_MEDIA_ADMISSION_STOPPED")

        gate()
        if (
            args.service != "spotify"
            or args.backend != "windows"
            or args.operation not in OPERATIONS
        ):
            raise MediaError("WINDOWS_MEDIA_OPERATION_UNSUPPORTED")
        if self.session_ref not in {None, args.session_ref}:
            raise MediaError("WINDOWS_MEDIA_SESSION_CHANGED")
        self.session_ref = args.session_ref
        before = await self.backend.snapshot()
        gate()
        if before.source not in SPOTIFY_IDS:
            raise MediaError("WINDOWS_MEDIA_WRONG_APP")
        if not before.title or before.state == "unknown":
            raise MediaError("SPOTIFY_PLAYBACK_STATE_UNAVAILABLE")
        if request.command == "execute":
            if args.generation != self.generation:
                raise MediaError("WINDOWS_MEDIA_STALE_GENERATION")
            if args.operation != "current":
                if self.selected and (
                    before.session != self.selected.session
                    or before.item_id != self.selected.item_id
                ):
                    raise MediaError("SPOTIFY_CHANGED_INSPECT_CURRENT")
                if args.operation not in before.controls:
                    raise MediaError("SPOTIFY_CONTROL_UNAVAILABLE")
                # Re-read immediately before admission; no global media keys.
                fresh = await self.backend.snapshot()
                if (
                    fresh.session != before.session
                    or fresh.source != before.source
                    or fresh.item_id != before.item_id
                    or fresh.state != before.state
                    or args.operation not in fresh.controls
                ):
                    raise MediaError("SPOTIFY_USER_TAKEOVER")
                gate()
                self.admitted = True
                if not await self.backend.deliver(fresh.session, args.operation):
                    raise MediaError("SPOTIFY_COMMAND_NOT_ACCEPTED")
                # A successful Try* is only an acknowledgement. Poll state, bounded
                # by the same deadline; never deliver again.
                while True:
                    observed = await self.backend.snapshot()
                    same = observed.session == before.session
                    verified = same and (
                        observed.item_id != before.item_id
                        if args.operation in {"next", "previous"}
                        else observed.item_id == before.item_id
                        and observed.state == ("paused" if args.operation == "pause" else "playing")
                    )
                    if verified:
                        break
                    gate()
                    await asyncio.sleep(0.05)
                before = observed
            self.selected = before
            self.expected = before
            self.generation += 1
        else:
            if (
                not self.expected
                or before.session != self.expected.session
                or before.item_id != self.expected.item_id
            ):
                raise MediaError("SPOTIFY_POSTCONDITION_CHANGED")
        return MediaObservation(
            session_ref=args.session_ref,
            service="spotify",
            generation=self.generation,
            observed_at=float(self.clock()),
            state=before.state,
            item_id=before.item_id,
            title=before.title,
            creator=before.artist,
            device_ref=self.device_ref,
        )


class WindowsMediaProvider(BrowserWorkerProvider):
    spotify_ready = True

    def __init__(self, clock, config, stop):
        # Avoid API credential reads and Chrome registration entirely.
        self.clock, self.config, self.stop = clock, config, stop
        import queue
        from pathlib import Path

        self.repository = Path.cwd().resolve()
        self.process = None
        self.replies = queue.Queue(maxsize=2)
        self.lock = threading.Lock()
        self.dead = False

    def start(self):
        if self.dead:
            raise MediaError("WINDOWS_MEDIA_WORKER_RESTART_REQUIRED")
        if self.process is None:
            self.launch([sys.executable, "-m", "jarvis.windows_media"])


class MediaProviders:
    real = True

    def __init__(self, browser, native, stop):
        self.browser, self.native, self._stop = browser, native, stop
        self.spotify_ready = True

    @property
    def stop(self):
        return self._stop

    @stop.setter
    def stop(self, value):
        self._stop = value
        for provider in (self.browser, self.native):
            if provider:
                provider.stop = value

    def call(self, request, cancel):
        provider = self.native if request.arguments.service == "spotify" else self.browser
        if provider is None:
            raise AdmissionRejected("This media service has no explicitly enabled real adapter")
        return provider.call(request, cancel)

    def close(self):
        for provider in (self.browser, self.native):
            if provider:
                provider.close()


def main():
    if os.name != "nt":
        return
    session = WindowsMediaSession(WinRTBackend())
    loop = asyncio.new_event_loop()
    seen = set()
    lease = None
    try:
        while raw := sys.stdin.buffer.readline(8194):
            if len(raw) > 8192 or not raw.endswith(b"\n"):
                break
            session.admitted = False
            request_id = ""
            try:
                request = parse_record(raw, WorkerRequest)
                request_id = request.request_id
                if request_id in seen or len(seen) >= 512:
                    raise MediaError("WINDOWS_MEDIA_DUPLICATE_OR_BUDGET")
                seen.add(request_id)
                if request.command == "execute" and request.arguments.operation != "current":
                    from pathlib import Path

                    from jarvis.notepad import DesktopLease

                    if lease is not None:
                        raise MediaError("WINDOWS_MEDIA_PENDING_VERIFICATION")
                    lease = DesktopLease(
                        Path(os.environ["LOCALAPPDATA"]) / "Jarvis/desktop-lease.lock"
                    )
                    lease.__enter__()
                observation = loop.run_until_complete(
                    asyncio.wait_for(
                        session.handle(request),
                        timeout=max(0.001, request.deadline - time.time()),
                    )
                )
                response = {
                    "version": 1,
                    "request_id": request_id,
                    "admitted": session.admitted,
                    "observation": observation.model_dump(),
                    "error": "",
                }
                if request.command != "execute" and lease:
                    lease.__exit__(None, None, None)
                    lease = None
            except Exception as exc:
                if lease and lease.stream and not lease.stream.closed:
                    lease.__exit__(None, None, None)
                lease = None
                response = {
                    "version": 1,
                    "request_id": request_id,
                    "admitted": session.admitted,
                    "observation": None,
                    "error": exc.code
                    if isinstance(exc, MediaError)
                    else "WINDOWS_MEDIA_NATIVE_FAILURE",
                }
            sys.stdout.buffer.write(json.dumps(response).encode() + b"\n")
            sys.stdout.buffer.flush()
    finally:
        if lease and lease.stream and not lease.stream.closed:
            lease.__exit__(None, None, None)
        loop.close()


if __name__ == "__main__":
    main()
