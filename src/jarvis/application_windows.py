"""Bounded parent-owned Windows worker transport. No runtime shell commands."""

import json
import queue
import subprocess
import sys
import threading
import time
from uuid import uuid4

from jarvis.domain import AdmissionRejected, Handoff
from jarvis.models import reject_constant, unique_object


class WindowsApplicationPlatform:
    def __init__(self, config, stop):
        self.config, self.stop = config, stop

    def call(self, operation, payload=None, gate=None):
        request_id = uuid4().hex
        request = {
            "version": 1,
            "request_id": request_id,
            "deadline": time.time() + self.config.operation_seconds,
            "operation": operation,
            "config": self.config.model_dump(),
            "payload": payload or {},
        }
        raw = (json.dumps(request) + "\n").encode()
        if len(raw) > 1048576:
            raise ValueError("Application envelope limit")
        process = subprocess.Popen(
            [sys.executable, "-m", "jarvis.application_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            creationflags=0x08000000,
        )
        messages = queue.Queue(maxsize=4)

        def read():
            try:
                while raw := process.stdout.readline(1048577):
                    if len(raw) > 1048576:
                        raise ValueError("Application result limit")
                    reply = json.loads(
                        raw, object_pairs_hook=unique_object, parse_constant=reject_constant
                    )
                    if (
                        set(reply) != {"version", "request_id", "stage", "data"}
                        or reply["version"] != 1
                        or reply["request_id"] != request_id
                    ):
                        raise ValueError("Worker reply identity")
                    messages.put_nowait(reply)
            except Exception:
                try:
                    messages.put_nowait({"stage": "error", "data": {}})
                except queue.Full:
                    pass

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        committed = False
        try:
            process.stdin.write(raw)
            process.stdin.flush()
            while time.time() < request["deadline"]:
                if self.stop.is_set() and gate:
                    if not committed:
                        raise AdmissionRejected("Stopped before application effect")
                    raise RuntimeError("Stopped after possible application effect")
                try:
                    reply = messages.get(timeout=0.025)
                except queue.Empty:
                    continue
                stage = reply["stage"]
                if stage == "ready":
                    if gate is None or committed:
                        raise RuntimeError("Invalid application admission")
                    gate()
                    if self.stop.is_set():
                        raise AdmissionRejected("Stopped at application admission")
                    committed = True
                    process.stdin.write(
                        (
                            json.dumps({"version": 1, "request_id": request_id, "commit": True})
                            + "\n"
                        ).encode()
                    )
                    process.stdin.flush()
                elif stage == "result":
                    if gate and not committed:
                        raise AdmissionRejected("No committed application effect")
                    return reply["data"]
                elif stage == "rejected" or (stage == "error" and gate and not committed):
                    raise AdmissionRejected("Application preparation changed; zero delivery")
                else:
                    if gate is None:
                        raise Handoff(
                            "Application discovery or inspection is unavailable; no effect sent"
                        )
                    raise RuntimeError("Application outcome unavailable")
            if gate and not committed:
                raise AdmissionRejected("Application timed out before admission")
            if gate is None:
                raise Handoff("Application inspection timed out; no effect sent")
            raise RuntimeError("Application worker deadline exceeded")
        finally:
            # Only this supervised automation worker is terminated, never an app.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()
            reader.join(timeout=1)
