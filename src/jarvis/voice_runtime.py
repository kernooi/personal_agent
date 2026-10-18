"""One bounded owned audio job at a time, cancellable without blocking Tk."""

import json
import os
import queue
import subprocess
import sys
import threading
import time

from jarvis.models import reject_constant, unique_object

MICROPHONE_START_SECONDS = 8


class AudioJobs:
    def __init__(self, root, *, popen=subprocess.Popen):
        self.root, self.popen = str(root), popen
        self.events = queue.Queue(maxsize=32)
        self.cancelled, self.finish_recording = threading.Event(), threading.Event()
        self.active = False
        self.generation = 0
        self.closed = False

    def post(self, generation, event):
        try:
            self.events.put_nowait((generation, event))
        except queue.Full:
            self.cancelled.set()

    def start(self, operation, config, text="", *, app_names=()):
        if self.active or self.closed:
            raise ValueError("Voice is still stopping. Please wait.")
        if operation not in {"inspect", "listen", "wake", "speak"}:
            raise ValueError("Unsupported audio operation")
        self.generation += 1
        generation = self.generation
        self.active = True
        self.cancelled.clear()
        self.finish_recording.clear()
        request = {"operation": operation, "root": self.root, "config": config.model_dump()}
        if operation in {"wake", "listen"} and config.app_name_hints and app_names:
            request["app_names"] = list(app_names)
        if operation == "speak":
            request["text"] = text
        threading.Thread(target=self.run, args=(generation, request, config), daemon=True).start()
        return generation

    def run(self, generation, request, config):
        process = None
        reader = None
        replies = queue.Queue(maxsize=32)
        final = False
        try:
            if self.cancelled.is_set():
                return
            process = self.popen(
                [sys.executable, "-m", "jarvis.voice_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            def read():
                try:
                    while True:
                        line = process.stdout.readline(32769)
                        if not line:
                            break
                        if len(line) > 32768 or not line.endswith(b"\n"):
                            raise ValueError("Invalid audio event")
                        event = json.loads(
                            line, object_pairs_hook=unique_object, parse_constant=reject_constant
                        )
                        replies.put(event, timeout=0.25)
                except (ValueError, OSError, queue.Full):
                    self.cancelled.set()
                finally:
                    process.stdout.close()

            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            process.stdin.write(json.dumps(request).encode() + b"\n")
            process.stdin.flush()
            operation = request["operation"]
            opening_until = (
                time.monotonic() + MICROPHONE_START_SECONDS
                if operation in {"listen", "wake"}
                else None
            )
            until = time.monotonic() + (
                config.recording_seconds + config.transcription_seconds + 10
                if operation == "listen"
                else config.wake_session_seconds
                + config.wake_followup_seconds
                + config.recording_seconds
                + config.transcription_seconds
                + config.wake_silence_seconds
                + 10
                + 20
                if operation == "wake"
                else config.speech_seconds + 10
                if operation == "speak"
                else 15
            )
            finish_sent, cancel_sent, stopping_until = False, False, None
            checking_until = None
            while True:
                if self.cancelled.is_set() and not cancel_sent:
                    process.stdin.write(b"cancel\n")
                    process.stdin.flush()
                    cancel_sent = True
                    stopping_until = time.monotonic() + 0.6
                if stopping_until and time.monotonic() >= stopping_until:
                    break
                if opening_until and time.monotonic() >= opening_until:
                    self.post(generation, {"kind": "error", "code": "MICROPHONE_START_TIMEOUT"})
                    final = True
                    break
                if checking_until and time.monotonic() >= checking_until:
                    self.post(generation, {"kind": "error", "code": "VOICE_TIMEOUT"})
                    final = True
                    break
                if self.finish_recording.is_set() and not finish_sent and operation == "listen":
                    process.stdin.write(b"finish\n")
                    process.stdin.flush()
                    finish_sent = True
                if time.monotonic() >= until:
                    self.post(generation, {"kind": "error", "code": "VOICE_TIMEOUT"})
                    break
                try:
                    event = replies.get(timeout=0.025)
                except queue.Empty:
                    if process.poll() is not None and not reader.is_alive():
                        break
                    continue
                if not isinstance(event, dict) or event.get("kind") not in {
                    "devices",
                    "stage",
                    "transcript",
                    "done",
                    "error",
                    "opening",
                    "level",
                    "wake_ready",
                    "wake_status",
                    "wake_level",
                }:
                    raise ValueError("Invalid audio event")
                if event["kind"] in {"devices", "transcript", "done", "error"}:
                    final = True
                if operation == "wake" and event["kind"] == "opening":
                    checking_until = None
                    if opening_until is None:
                        opening_until = time.monotonic() + MICROPHONE_START_SECONDS
                if (
                    operation == "wake"
                    and event["kind"] == "stage"
                    and event.get("state") == "WAKE_CHECKING"
                ):
                    checking_until = time.monotonic() + config.transcription_seconds
                if (
                    operation == "wake"
                    and event["kind"] == "stage"
                    and event.get("state") == "WAKE_ACKNOWLEDGING"
                ):
                    checking_until = time.monotonic() + min(config.speech_seconds, 10) + 1
                if (
                    event["kind"] == "stage"
                    and event.get("state") == "TRANSCRIBING"
                    and operation in {"listen", "wake"}
                ):
                    checking_until = time.monotonic() + config.transcription_seconds
                if event["kind"] == "stage" and event.get("state") in {
                    "LISTENING",
                    "WAKE_LISTENING",
                }:
                    opening_until = None
                    checking_until = None
                if not self.cancelled.is_set():
                    self.post(generation, event)
            if not final and not self.cancelled.is_set():
                self.post(generation, {"kind": "error", "code": "VOICE_WORKER_ENDED"})
        except (OSError, ValueError):
            if not self.cancelled.is_set():
                self.post(generation, {"kind": "error", "code": "VOICE_WORKER_FAILED"})
        finally:
            if process is not None:
                # EOF tells the owned worker to release devices and activates its
                # exit watchdog, including when the venv launcher has a child.
                try:
                    process.stdin.close()
                except OSError:
                    pass  # The worker may already have closed its request pipe.
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.terminate()  # Only this owned worker, never a desktop target.
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                if reader is not None:
                    reader.join(timeout=0.3)
                if reader is None or not reader.is_alive():
                    process.stdout.close()
            self.active = False
            self.post(generation, {"kind": "finished"})

    def cancel(self):
        self.cancelled.set()

    def finish(self):
        self.finish_recording.set()

    def close(self):
        self.closed = True
        self.cancel()
