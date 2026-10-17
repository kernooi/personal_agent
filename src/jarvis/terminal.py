"""Read the user's own terminal while inference waits; no desktop input automation."""

import os
import queue
import select
import sys
import threading
from collections.abc import Callable
from typing import TextIO

from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import Denied


class TerminalInput:
    def __init__(self, stream: TextIO, notice: Callable[[str], None]):
        self.stream = stream
        self.notice = notice
        self.lines: queue.Queue[tuple[int, str]] = queue.Queue(maxsize=16)
        self.lock = threading.Lock()
        self.generation = 0
        self.cancel = threading.Event()
        self.exit = threading.Event()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.screen_stop = lambda: None

    def _deliver(self, line: str) -> bool:
        command = line.strip().casefold()
        if command in {"/screen-stop", "/screen-revoke", "stop watching", "stop screen watching"}:
            self.screen_stop()
        if command in {"stop", "/stop", "/cancel"}:
            with self.lock:
                self.generation += 1
                self.cancel.set()
            self.notice("SIMULATED: stop acknowledged; no new admissions; no rollback promised.")
            return True
        if command in {"quit", "exit", "/quit", "/exit"}:
            with self.lock:
                self.generation += 1
                self.cancel.set()
                self.exit.set()
            return False
        try:
            with self.lock:
                self.lines.put_nowait((self.generation, line))
        except queue.Full:
            self.notice("SIMULATED: input queue full; request discarded.")
        return True

    def begin(self, generation: int) -> bool:
        with self.lock:
            if self.exit.is_set() or generation != self.generation:
                return False
            self.cancel.clear()
            return True

    def _read(self):
        try:
            if self.stream.isatty() and os.name == "nt":
                import msvcrt

                buffer = ""
                overflow = False
                while not self.closed.is_set():
                    if not msvcrt.kbhit():
                        self.closed.wait(0.05)
                        continue
                    char = msvcrt.getwch()
                    if char == "\x03":
                        self._deliver("/stop")
                    elif char in ("\x00", "\xe0"):
                        msvcrt.getwch()
                    elif char == "\r":
                        self.notice("")
                        if overflow:
                            self.notice("SIMULATED: input too long; entire request discarded.")
                        elif not self._deliver(buffer):
                            break
                        buffer = ""
                        overflow = False
                    elif char == "\b":
                        if buffer:
                            buffer = buffer[:-1]
                            sys.stdout.write("\b \b")
                            sys.stdout.flush()
                    elif char.isprintable():
                        if len(buffer) >= 4096:
                            overflow = True
                        else:
                            buffer += char
                            sys.stdout.write(char)
                            sys.stdout.flush()
            else:
                while not self.closed.is_set():
                    if self.stream.isatty() and not select.select([self.stream], [], [], 0.05)[0]:
                        continue
                    line = self.stream.readline(4097)
                    if len(line.rstrip("\r\n")) > 4096:
                        while line and not line.endswith("\n") and not self.closed.is_set():
                            line = self.stream.readline(4097)
                        self.notice("SIMULATED: input too long; entire request discarded.")
                        continue
                    if not line or not self._deliver(line.rstrip("\r\n")):
                        break
        finally:
            self.closed.set()

    def close(self):
        self.closed.set()
        self.thread.join(timeout=1)


def chat_loop(conversation: Conversation, stream: TextIO, output: Callable[[str], None] = print):
    def notice(text):
        output("JARVIS: " + text.removeprefix("SIMULATED: ") if text else "")

    def prompt():
        if output is print:
            output("You> ", end="", flush=True)
        else:
            output("You> ")

    reader = TerminalInput(stream, notice)
    screen = getattr(conversation.broker, "screen", None)
    if screen:
        screen.notice = lambda text: output("Screen: " + text)
        reader.screen_stop = screen.stop_requested.set
    desktop_stop = getattr(conversation.broker.desktop, "stop", threading.Event())
    media = conversation.broker.media
    conversation.broker.cancel_requested = lambda: (
        reader.cancel.is_set()
        or desktop_stop.is_set()
        or (media is not None and getattr(media.provider, "stop", desktop_stop).is_set())
    )
    mode = "WINDOWS" if getattr(conversation.broker.desktop, "real", False) else "SIMULATED"
    execution_label = (
        f"Notepad={mode}; media=real, Spotify={media.config.spotify_backend}."
        if media is not None and media.real
        else f"Actions use {mode} mode."
    )
    applications = getattr(conversation.broker, "applications", None)
    if applications is not None:
        application_mode = "WINDOWS" if applications.desktop.real else "SIMULATED"
        execution_label += f" Applications={application_mode}."
    output(f"Type /stop during inference; /quit to exit. {execution_label}")
    prompt()
    reader.thread.start()
    try:
        while not reader.exit.is_set():
            try:
                generation, text = reader.lines.get(timeout=0.05)
            except queue.Empty:
                if screen:
                    screen.poll()
                if reader.closed.is_set():
                    break
                continue
            if not text.strip():
                continue
            if not reader.begin(generation):
                continue
            try:
                if screen and text.startswith("/screen-"):
                    output("JARVIS: " + screen.control(text))
                    prompt()
                    continue
                applications = getattr(conversation.broker, "applications", None)
                if applications is not None and text.startswith("/"):
                    reply = applications.control(text)
                    if reply is not None:
                        output("JARVIS: " + reply)
                        prompt()
                        continue
                currency = conversation.broker.currency
                web = conversation.broker.web
                media = conversation.broker.media
                if media is not None and text.startswith("/"):
                    reply = media.control(text, conversation.broker.store)
                    if reply is not None:
                        output("JARVIS: " + reply)
                        prompt()
                        continue
                if web is not None and text.startswith("/"):
                    reply = web.control(text)
                    if reply is not None:
                        output("JARVIS: " + reply)
                        prompt()
                        continue
                    if text == "/web-refresh":
                        text = "refresh my research"
                if currency is not None and text in {"/cache", "/cache-clear"}:
                    if text == "/cache-clear":
                        currency.cache.clear()
                        output("JARVIS: Public quote cache cleared.")
                    else:
                        import json

                        output(
                            "JARVIS: Public quote cache: " + json.dumps(currency.cache.inspect())
                        )
                    prompt()
                    continue
                if currency is not None and text == "/refresh-rate":
                    text = "refresh that rate"
                if hasattr(conversation.broker.desktop, "inventory") and text.startswith("/"):
                    desktop = conversation.broker.desktop
                    if text == "/windows":
                        for window in desktop.inventory():
                            output(f"JARVIS: {window}")
                    elif text == "/confirm-empty":
                        if not desktop.selected_ref:
                            raise Denied(
                                "Select a test Notepad window first with /windows and /select."
                            )
                        desktop.select(desktop.selected_ref, confirm_disposable=True)
                        output(
                            "JARVIS: Confirmed the selected empty disposable test window. "
                            "You can now ask me to close it; safety will be checked again."
                        )
                    elif text == "/clear":
                        if output is print and stream.isatty():
                            output("\x1b[2J\x1b[H", end="", flush=True)
                        output(
                            "JARVIS: Chat display cleared. "
                            "The selected Notepad window is unchanged."
                        )
                    elif text.startswith("/select "):
                        parts = text.split()
                        if len(parts) not in {2, 3} or (
                            len(parts) == 3 and parts[2] != "empty-disposable"
                        ):
                            raise Denied("Use /select <window_ref> [empty-disposable]")
                        desktop.select(parts[1], confirm_disposable=len(parts) == 3)
                        output(
                            "JARVIS: Selected Notepad window. "
                            "Close safety will be rechecked at dispatch."
                        )
                    elif text.startswith("/review "):
                        parts = text.split()
                        if len(parts) != 3 or parts[2] != "manually-handled":
                            raise Denied(
                                "Use /review <task_id> manually-handled "
                                "after inspecting the outcome"
                            )
                        store = conversation.broker.store
                        task = store.get(parts[1])
                        if task.state != "NEEDS_REVIEW":
                            raise Denied("Task does not require outcome review")
                        with store.db:
                            store.event(task.task_id, "manual_review_acknowledged")
                        unresolved = store.db.execute(
                            "SELECT a.task_id FROM actions a WHERE a.state='UNKNOWN' "
                            "AND a.capability NOT IN "
                            "('currency.quote','web.research','media.control') "
                            "AND NOT EXISTS "
                            "(SELECT 1 FROM events e WHERE e.task_id=a.task_id "
                            "AND e.kind='manual_review_acknowledged')"
                        ).fetchone()
                        desktop.blocked_unknown = unresolved is not None
                        output(
                            "JARVIS: Manual review recorded. The old action will never be replayed."
                        )
                    else:
                        output(
                            "JARVIS: Enter commands on their own line: /windows, "
                            "/select <reference> [empty-disposable], /confirm-empty, "
                            "/clear, /stop, /quit. Send Notepad requests on a separate line."
                        )
                    prompt()
                    continue
                result = conversation.submit(text)
                message = conversational_text(result)
                if result.decision_kind not in {"say", "clarify", "unsupported"} and (
                    message.startswith("SIMULATED: ")
                ):
                    message = "[SIMULATED] " + message.removeprefix("SIMULATED: ")
                output(f"JARVIS: {message}")
            except Denied as exc:
                output(f"JARVIS: Request paused: {exc}")
            prompt()
    except KeyboardInterrupt:
        reader.cancel.set()
        output("JARVIS: Interrupted; any admitted effect remains journaled.")
    finally:
        if screen:
            screen.close()
        reader.close()
