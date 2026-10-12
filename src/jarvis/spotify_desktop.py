"""Spotify-specific accessibility search/selection with independent native playback checks."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from jarvis.media_data import MediaError, MediaObservation, WorkerRequest, parse_record
from jarvis.spotify_accessibility import normalized
from jarvis.windows_media import (
    SPOTIFY_IDS,
    WindowsMediaProvider,
    WindowsMediaSession,
    WinRTBackend,
)


class SpotifyDesktopSession:
    def __init__(self, ui, playback, clock=time.time, sleep=asyncio.sleep):
        self.ui, self.playback, self.clock, self.sleep = ui, playback, clock, sleep
        self.basic = WindowsMediaSession(playback, clock)
        self.generation = 0
        self.session_ref = None
        self.admitted = False
        self.results = []
        self.selected = None
        self.expected_playback = None
        self.observation = None

    def observation_for(self, args, state, snapshot=None):
        return MediaObservation(
            session_ref=args.session_ref,
            service="spotify",
            generation=self.generation,
            observed_at=float(self.clock()),
            state=state,
            item_id=self.selected.item_id
            if self.selected
            else snapshot.item_id
            if snapshot
            else "",
            title=self.selected.title if self.selected else snapshot.title if snapshot else "",
            creator=self.selected.creator if self.selected else snapshot.artist if snapshot else "",
            device_ref=self.basic.device_ref,
            results=self.results if state == "results" else [],
        )

    async def handle(self, request, cancelled=lambda: False):
        self.admitted = False
        args = request.arguments

        def gate():
            if cancelled() or self.clock() >= request.deadline:
                raise MediaError("SPOTIFY_DESKTOP_STOPPED_OR_EXPIRED")

        gate()
        if (
            args.service != "spotify"
            or args.backend != "desktop"
            or args.operation in {"login", "devices"}
        ):
            raise MediaError("SPOTIFY_DESKTOP_OPERATION_UNSUPPORTED")
        if self.session_ref not in {None, args.session_ref}:
            raise MediaError("SPOTIFY_DESKTOP_SESSION_CHANGED")
        self.session_ref = args.session_ref
        if request.command == "execute" and args.generation != self.generation:
            raise MediaError("SPOTIFY_DESKTOP_STALE_GENERATION")

        if args.operation == "search":
            if request.command == "execute":
                self.selected = self.expected_playback = None
                self.basic.selected = None
                self.ui.root()
                gate()
                try:
                    await self.ui.search(request.query, args.search_kind, gate)
                finally:
                    self.admitted = self.ui.admitted
                # Observe only after a settling interval, then independently compare
                # another current result read. Never repeat Value/Invoke delivery.
                await self.sleep(0.75)
                last = None
                while True:
                    gate()
                    try:
                        records = self.ui.results(request.result_limit)
                    except MediaError as exc:
                        if exc.code != "SPOTIFY_RESULTS_LOADING":
                            raise
                        last = None
                        await self.sleep(0.2)
                        continue
                    if records == last:
                        break
                    last = records
                    await self.sleep(0.2)
                self.results = self.ui.bind(records)
                self.generation += 1
            else:
                fresh = self.ui.results(request.result_limit)
                bound = list(self.ui.bindings.values())
                if fresh != bound:
                    raise MediaError("SPOTIFY_SEARCH_POSTCONDITION_CHANGED")
            self.observation = self.observation_for(args, "results")
            return self.observation

        if args.operation == "open":
            item = next((r for r in self.results if r.reference == args.reference), None)
            if item is None:
                raise MediaError("SPOTIFY_RESULT_REFERENCE_EXPIRED")
            self.ui.selected(args.reference)
            if request.command == "execute":
                self.selected = item
                self.generation += 1
            elif self.selected != item:
                raise MediaError("SPOTIFY_SELECTION_CHANGED")
            # Selection pins a current retrieved result. It does not start playback.
            self.observation = self.observation_for(args, "opened")
            return self.observation

        if args.operation == "play" and self.selected is not None and request.command == "execute":
            if args.reference != self.selected.reference:
                raise MediaError("SPOTIFY_SELECTION_CHANGED")
            self.ui.selected(args.reference)
            self.ui.playback_control(args.reference)
            gate()
            try:
                self.ui.play(args.reference, gate)
            finally:
                self.admitted = self.ui.admitted
            while True:
                gate()
                snapshot = await self.playback.snapshot()
                if self.matches_playback(snapshot, require_context=True):
                    break
                await self.sleep(0.1)
            self.expected_playback = snapshot
            self.basic.selected = snapshot
            self.generation += 1
            self.observation = self.observation_for(args, "playing", snapshot)
            return self.observation

        if request.command != "execute" and self.selected is not None:
            snapshot = await self.playback.snapshot()
            if (
                self.expected_playback is None
                or snapshot.session != self.expected_playback.session
                or snapshot.item_id != self.expected_playback.item_id
                or snapshot.state != self.observation.state
                or not self.matches_playback(snapshot, require_context=snapshot.state == "playing")
            ):
                raise MediaError("SPOTIFY_PLAYBACK_POSTCONDITION_CHANGED")
            return self.observation_for(args, snapshot.state, snapshot)

        if request.command == "execute" and args.operation in {"current", "next", "previous"}:
            self.selected = None
        self.basic.generation = self.generation
        adapted = request.model_copy(
            update={
                "arguments": args.model_copy(update={"backend": "windows", "search_kind": "track"})
            }
        )
        try:
            observed = await self.basic.handle(adapted, cancelled)
        finally:
            self.admitted = self.basic.admitted
        self.generation = self.basic.generation
        self.expected_playback = self.basic.expected
        self.observation = self.observation_for(args, observed.state, self.basic.expected)
        return self.observation

    def matches_playback(self, snapshot, *, require_context):
        item = self.selected
        if not item or snapshot.source not in SPOTIFY_IDS or not snapshot.title:
            return False
        if require_context and snapshot.state != "playing":
            return False
        if item.content_type == "track":
            return (
                normalized(snapshot.title) == normalized(item.title)
                and (bool(item.creator) and normalized(snapshot.artist) == normalized(item.creator))
                and (not require_context or self.ui.context_playing(item.reference))
            )
        return item.content_type == "playlist" and (
            self.ui.context_playing(item.reference) if require_context else True
        )


class SpotifyDesktopProvider(WindowsMediaProvider):
    def start(self):
        if self.dead:
            raise MediaError("SPOTIFY_DESKTOP_WORKER_RESTART_REQUIRED")
        if self.process is None:
            self.launch([sys.executable, "-m", "jarvis.spotify_desktop"])


def main():
    if os.name != "nt":
        return
    sys.coinit_flags = 0
    from jarvis.notepad import DesktopLease
    from jarvis.spotify_accessibility import SpotifyAccessibility

    session = None
    loop = asyncio.new_event_loop()
    seen = set()
    lease = None
    try:
        while raw := sys.stdin.buffer.readline(8194):
            if len(raw) > 8192 or not raw.endswith(b"\n"):
                break
            request_id = ""
            if session:
                session.admitted = False
            try:
                request = parse_record(raw, WorkerRequest)
                request_id = request.request_id
                if request_id in seen or len(seen) >= 512:
                    raise MediaError("SPOTIFY_DESKTOP_DUPLICATE_OR_BUDGET")
                seen.add(request_id)
                if session is None:
                    session = SpotifyDesktopSession(SpotifyAccessibility(), WinRTBackend())
                if request.command == "execute" and request.arguments.operation not in {
                    "current",
                    "open",
                }:
                    if lease is not None:
                        raise MediaError("SPOTIFY_DESKTOP_PENDING_VERIFICATION")
                    lease = DesktopLease(
                        Path(os.environ["LOCALAPPDATA"]) / "Jarvis/desktop-lease.lock"
                    )
                    lease.__enter__()
                observation = loop.run_until_complete(
                    asyncio.wait_for(
                        session.handle(request), timeout=max(0.001, request.deadline - time.time())
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
                if lease:
                    lease.__exit__(None, None, None)
                    lease = None
                response = {
                    "version": 1,
                    "request_id": request_id,
                    "admitted": bool(session and session.admitted),
                    "observation": None,
                    "error": exc.code
                    if isinstance(exc, MediaError)
                    else "SPOTIFY_DESKTOP_NATIVE_FAILURE",
                }
            sys.stdout.buffer.write(json.dumps(response).encode() + b"\n")
            sys.stdout.buffer.flush()
    finally:
        if lease:
            lease.__exit__(None, None, None)
        loop.close()


if __name__ == "__main__":
    main()
