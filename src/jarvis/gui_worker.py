"""Frame the existing CLI's presentation as JSON over parent-owned pipes."""

import json
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout

from jarvis import cli, terminal


class EventWriter:
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()

    def emit(self, kind, text=""):
        record = json.dumps({"version": 1, "kind": kind, "text": text}, ensure_ascii=False)
        with self.lock:
            self.stream.write(record + "\n")
            self.stream.flush()

    def output(self, text):
        # One complete callback becomes one event. Model text cannot forge framing.
        if text == "You> ":
            self.emit("ready")
        elif text.startswith("JARVIS: "):
            self.emit("reply", text.removeprefix("JARVIS: "))
        elif text:
            self.emit("diagnostic", text)


class DiagnosticStream:
    def __init__(self, writer):
        self.writer = writer
        self.buffer = ""
        self.lock = threading.Lock()

    def write(self, text):
        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if line.strip():
                    self.writer.emit("diagnostic", line)
        return len(text)

    def flush(self):
        with self.lock:
            if self.buffer.strip():
                self.writer.emit("diagnostic", self.buffer)
            self.buffer = ""


def main():
    writer = EventWriter(sys.stdout)
    if len(sys.argv) < 2 or sys.argv[1] != "chat":
        writer.emit("diagnostic", "Desktop chat supports the chat command only.")
        return 2
    original = terminal.chat_loop

    def framed_loop(conversation, stream):
        return original(conversation, stream, output=writer.output)

    terminal.chat_loop = framed_loop
    diagnostics = DiagnosticStream(writer)
    try:
        with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
            cli.main()
    finally:
        terminal.chat_loop = original
        diagnostics.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
