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

    def _deliver(self, line: str) -> bool:
        command = line.strip().casefold()
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
    reader = TerminalInput(stream, output)
    conversation.broker.cancel_requested = reader.cancel.is_set
    output("Type /stop during inference; /quit to exit. Actions are SIMULATED.")
    output("You> ")
    reader.thread.start()
    try:
        while not reader.exit.is_set():
            try:
                generation, text = reader.lines.get(timeout=0.05)
            except queue.Empty:
                if reader.closed.is_set():
                    break
                continue
            if not text.strip():
                continue
            if not reader.begin(generation):
                continue
            try:
                result = conversation.submit(text)
                message = conversational_text(result)
                if result.decision_kind not in {"say", "clarify", "unsupported"} and (
                    message.startswith("SIMULATED: ")
                ):
                    message = "[SIMULATED] " + message.removeprefix("SIMULATED: ")
                output(f"JARVIS: {message}")
            except Denied as exc:
                output(f"SIMULATED: request rejected: {exc}")
            output("You> ")
    except KeyboardInterrupt:
        reader.cancel.set()
        output("SIMULATED: interrupted; any admitted effect remains journaled.")
    finally:
        reader.close()
