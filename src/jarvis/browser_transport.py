"""Supervised persistent worker using parent-owned pipes, bounded JSON and no shell."""

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from pydantic import Field

from jarvis.domain import AdmissionRejected
from jarvis.media_data import MediaError, MediaObservation, parse_record
from jarvis.models import StrictRecord


class WorkerReply(StrictRecord):
    version: int = Field(ge=1, le=1)
    request_id: str
    admitted: bool
    observation: MediaObservation | None = None
    error: str = Field(default="", max_length=80, pattern=r"^[A-Z0-9_]*$")


class BrowserWorkerProvider:
    real = True
    spotify_ready = False

    def __init__(self, clock, registration, config, stop, repository=None):
        self.clock, self.registration, self.config, self.stop = (
            clock,
            Path(registration),
            config,
            stop,
        )
        self.repository = Path(repository or Path.cwd()).resolve()
        self.process = None
        self.replies = queue.Queue(maxsize=2)
        self.lock = threading.Lock()
        self.dead = False
        from jarvis.spotify_api import credential_ready

        self.spotify_ready = config.spotify and credential_ready()

    def start(self):
        if self.dead:
            raise MediaError("BROWSER_WORKER_REQUIRES_MANUAL_RESTART")
        if self.process is not None:
            return
        from jarvis.chrome_identity import load_registration, private_browser_root, validate_profile

        load_registration(self.registration)
        validate_profile(private_browser_root(), self.repository)
        self.launch(
            [
                sys.executable,
                "-m",
                "jarvis.browser_worker",
                "--registration",
                str(self.registration),
                "--repository",
                str(self.repository),
            ]
        )

    def launch(self, command):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            cwd=str(self.repository),
        )

        def read():
            try:
                while True:
                    raw = self.process.stdout.readline(32770)
                    if not raw or len(raw) > 32768 or not raw.endswith(b"\n"):
                        self.replies.put(None)
                        break
                    self.replies.put(raw)
            except (OSError, ValueError):
                try:
                    self.replies.put_nowait(None)
                except queue.Full:
                    pass

        threading.Thread(target=read, daemon=True).start()

    def call(self, request, cancel):
        if not self.lock.acquire(blocking=False):
            raise AdmissionRejected("Browser worker busy")
        try:
            if cancel() or self.stop.is_set() or self.clock.now() >= request.deadline:
                raise AdmissionRejected("Browser admission stopped")
            self.start()
            raw = request.model_dump_json().encode() + b"\n"
            if len(raw) > 8192:
                raise AdmissionRejected("Browser request too large")
            self.process.stdin.write(raw)
            self.process.stdin.flush()
            while self.clock.now() < request.deadline:
                if cancel() or self.stop.is_set():
                    # Do not promise cancellation rolls back the worker's already sent effect.
                    self.abort()
                    raise MediaError("BROWSER_CANCELLED_AFTER_DELIVERY")
                try:
                    raw = self.replies.get(timeout=0.02)
                except queue.Empty:
                    if self.process.poll() is not None:
                        self.dead = True
                        raise MediaError("BROWSER_WORKER_CRASH") from None
                    continue
                if raw is None:
                    self.dead = True
                    raise MediaError("BROWSER_WORKER_CLOSED")
                reply = parse_record(raw, WorkerReply)
                if reply.request_id != request.request_id or reply.version != 1:
                    self.abort()
                    raise MediaError("OBSOLETE_BROWSER_REPLY")
                if reply.error:
                    if not reply.admitted:
                        raise AdmissionRejected(reply.error)
                    raise MediaError(reply.error)
                if reply.observation is None:
                    raise MediaError("BROWSER_OBSERVATION_MISSING")
                return reply.observation
            self.abort()
            raise MediaError("BROWSER_WORKER_TIMEOUT")
        finally:
            self.lock.release()

    def abort(self):
        self.dead = True
        if self.process and self.process.poll() is None:
            # Only the owned Python worker is terminated; no Chrome or personal app kill.
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)

    def close(self):
        if not self.process:
            return
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.abort()
        for stream in (self.process.stdout, self.process.stdin):
            if stream and not stream.closed:
                stream.close()
