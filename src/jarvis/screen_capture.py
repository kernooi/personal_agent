"""Bounded capture worker IPC. No screenshot files, shell, or arbitrary regions."""

import base64
import json
import queue
import subprocess
import sys
import threading
import time
from uuid import uuid4

from jarvis.domain import Denied
from jarvis.models import reject_constant, unique_object
from jarvis.screen_data import Frame, Target


class WindowsCapture:
    def __init__(self, config):
        self.config = config
        self.generation = 0
        self.last_error = None

    def call(self, operation, target=None, cancel=lambda: False, indicator_pid=0):
        self.last_error = None
        if cancel():
            raise Denied("CAPTURE_CANCELLED")
        request = {
            "version": 1,
            "id": uuid4().hex,
            "operation": operation,
            "config": self.config.model_dump(),
            "target": target.model_dump(mode="json") if target else None,
            "indicator_pid": indicator_pid,
        }
        worker = subprocess.Popen(
            [sys.executable, "-m", "jarvis.screen_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        replies = queue.Queue(maxsize=1)

        def read():
            try:
                raw = worker.stdout.readline(self.config.max_image_bytes * 2 + 1)
                data = json.loads(
                    raw, object_pairs_hook=unique_object, parse_constant=reject_constant
                )
                replies.put_nowait(data)
            except (ValueError, OSError):
                replies.put_nowait(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            if cancel():
                raise Denied("CAPTURE_CANCELLED")
            worker.stdin.write((json.dumps(request) + "\n").encode())
            worker.stdin.flush()
            deadline = time.monotonic() + self.config.capture_seconds
            while time.monotonic() < deadline:
                if cancel():
                    raise Denied("CAPTURE_CANCELLED")
                try:
                    result = replies.get(timeout=0.025)
                except queue.Empty:
                    continue
                if not isinstance(result, dict) or set(result) != {"id", "result", "error"}:
                    raise Denied("CAPTURE_WORKER_FAILED")
                if result["id"] != request["id"]:
                    raise Denied("CAPTURE_WORKER_IDENTITY")
                if result["error"]:
                    # Only a fixed native code is returned; no titles/exception text.
                    self.last_error = result["error"]
                    raise Denied(result["error"])
                return result["result"]
            raise Denied("CAPTURE_TIMEOUT")
        finally:
            if worker.poll() is None:
                worker.terminate()  # Only our worker, never the observed application.
            worker.wait(timeout=2)
            worker.stdin.close()
            worker.stdout.close()
            reader.join(timeout=1)

    def inventory(self, cancel=lambda: False):
        result = self.call("inventory", cancel=cancel)
        return [Target.model_validate_json(json.dumps(item)) for item in result]

    def foreground(self, cancel=lambda: False):
        return Target.model_validate_json(json.dumps(self.call("foreground", cancel=cancel)))

    def validate(self, target, cancel=lambda: False):
        self.call("validate", target, cancel)

    def capture(self, target, cancel, indicator_pid=0):
        result = self.call("capture", target, cancel, indicator_pid)
        self.generation += 1
        result["png"] = base64.b64decode(result["png"], validate=True)
        result["generation"] = self.generation
        result["bounds"] = tuple(result["bounds"])
        frame = Frame.model_validate(result, strict=True)
        if frame.target_identity != target.identity:
            raise Denied("CAPTURE_TARGET_CHANGED")
        return frame


class CaptureIndicator:
    """Separate visible process stays responsive during synchronous inference."""

    def __init__(self, companion=None):
        from jarvis.companion import CompanionConfig

        self.process = None
        self.companion = companion or CompanionConfig()
        self.sequence = 0
        self.replies = queue.Queue(maxsize=32)

    def start(self):
        if self.process and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "jarvis.screen_indicator",
                "--companion-config",
                json.dumps(self.companion.model_dump()),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        process = self.process
        ready = queue.Queue(maxsize=1)
        threading.Thread(target=lambda: ready.put(process.stdout.readline(32)), daemon=True).start()
        try:
            if ready.get(timeout=5).strip() != b"VISIBLE":
                raise Denied("CAPTURE_INDICATOR_UNAVAILABLE")
        except (queue.Empty, Denied) as exc:
            self.close()
            raise Denied("CAPTURE_INDICATOR_UNAVAILABLE") from exc

        def read_events():
            try:
                for line in iter(lambda: process.stdout.readline(8193), b""):
                    self.replies.put_nowait(json.loads(line))
            except (ValueError, OSError, queue.Full):
                pass

        threading.Thread(target=read_events, daemon=True).start()

    def update(self, event, task="", bounds=(0, 0, 1, 1), *, watching=False):
        if not self.alive:
            return None
        self.sequence += 1
        message = {
            "event": event,
            "task": task,
            "bounds": list(bounds),
            "sequence": self.sequence,
            "watching": watching,
        }
        try:
            self.process.stdin.write((json.dumps(message) + "\n").encode())
            self.process.stdin.flush()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                reply = self.replies.get(timeout=max(0.001, deadline - time.monotonic()))
                if reply.get("ack") == self.sequence:
                    return reply
        except (OSError, ValueError, queue.Empty):
            pass
        raise Denied("CAPTURE_INDICATOR_UNAVAILABLE")

    @property
    def alive(self):
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self):
        return self.process.pid if self.alive else 0

    def close(self):
        if self.process:
            if self.alive:
                try:
                    self.process.stdin.write(b'{"event":"shutdown"}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=1.5)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
                if self.process.poll() is None:
                    self.process.terminate()
            self.process.wait(timeout=2)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
