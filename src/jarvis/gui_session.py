"""Desktop presentation transport. All effects stay inside the existing CLI broker."""

import json
import os
import queue
import subprocess
import threading

MAX_EVENT = 262144


def unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate desktop event field")
    return result


def parse_event(raw):
    if len(raw.encode("utf-8")) > MAX_EVENT:
        raise ValueError("Oversized desktop event")
    event = json.loads(raw, object_pairs_hook=unique_fields)
    if (
        not isinstance(event, dict)
        or set(event) != {"version", "kind", "text"}
        or type(event["version"]) is not int
        or event["version"] != 1
        or not isinstance(event["kind"], str)
        or event["kind"] not in {"ready", "reply", "diagnostic"}
        or not isinstance(event["text"], str)
        or (event["kind"] == "ready" and event["text"])
    ):
        raise ValueError("Invalid desktop event")
    return event


def request_line(text):
    # TerminalInput consumes one bounded request per line; never inject extra commands.
    line = " ".join(text.splitlines()).strip()
    if not line:
        raise ValueError("Write a message first.")
    if len(line) > 4096:
        raise ValueError("Please keep your message under 4,097 characters.")
    return line + "\n"


class ChatSession:
    def __init__(self, command_factory, repository, *, popen=subprocess.Popen, prepare=None):
        self.command_factory, self.repository, self.popen = command_factory, repository, popen
        self.process = None
        self.events = queue.Queue(maxsize=256)
        self.closing = threading.Event()
        self.startup_done = threading.Event()
        self.write_lock = threading.Lock()
        self.prepare = prepare

    def start(self, *, real=False):
        try:
            self._start(real=real)
        finally:
            self.startup_done.set()

    def _start(self, *, real=False):
        if self.closing.is_set():
            return
        command = list(self.command_factory(real=real))
        if command[1:4] != ["-m", "jarvis", "chat"]:
            raise ValueError("Expected the trusted JARVIS chat launcher.")
        if self.prepare:

            def notify(text, *, warning=False, diagnostic=False):
                self._post(
                    {
                        "kind": "reply" if warning else "diagnostic" if diagnostic else "progress",
                        "text": text,
                    }
                )

            self.prepare(command, notify, self.closing)
            if self.closing.is_set():
                return
        command[2] = "jarvis.gui_worker"
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        self.process = self.popen(
            command,
            cwd=self.repository,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        threading.Thread(target=self._read, daemon=True).start()
        if self.closing.is_set():
            self.close()

    def _post(self, event):
        while not self.closing.is_set():
            try:
                self.events.put(event, timeout=0.1)
                return
            except queue.Full:
                continue

    def _read(self):
        try:
            # Keep draining after close so a final long reply cannot block cleanup.
            while True:
                raw = self.process.stdout.readline(MAX_EVENT + 1)
                if not raw:
                    break
                try:
                    if not raw.endswith("\n"):
                        raise ValueError("Incomplete desktop event")
                    self._post(parse_event(raw))
                except (ValueError, TypeError):
                    self._post(
                        {"kind": "diagnostic", "text": "The chat connection returned invalid data."}
                    )
                    self.send("/stop")
                    self.send("/quit")
                    break
        except (OSError, ValueError):
            self._post({"kind": "diagnostic", "text": "The chat connection closed."})
        finally:
            self._post({"kind": "closed", "text": ""})

    def send(self, text):
        line = request_line(text)
        with self.write_lock:
            if self.process is None or self.process.poll() is not None:
                raise ValueError("Start a chat session first.")
            try:
                self.process.stdin.write(line)
                self.process.stdin.flush()
            except OSError as exc:
                raise ValueError("The chat connection closed.") from exc

    def close(self):
        # Cooperative shutdown only: acknowledge stop and quit through existing input.
        # Do not terminate apps, workers or the broker during an admitted effect.
        self.closing.set()
        try:
            self.send("/stop")
            self.send("/quit")
        except ValueError:
            pass

        def reap():
            if self.process is None:
                return
            self.process.wait()
            for stream in (self.process.stdin, self.process.stdout):
                if stream and not stream.closed:
                    stream.close()

        threading.Thread(target=reap, daemon=True).start()
