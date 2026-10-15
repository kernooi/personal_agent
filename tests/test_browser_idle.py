"""The browser services callbacks while awaiting input; no real browser is started."""

import queue
import threading
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.browser_worker import ChromeSession, worker_records


def test_pipe_wait_pumps_events_on_owner_thread_and_preserves_frame_order():
    chunks = queue.Queue()
    owner = threading.get_ident()
    reads, pumps = [], []

    class Stream:
        def readline(self, size):
            reads.append((threading.get_ident(), size))
            return chunks.get(timeout=2)

    def idle():
        pumps.append(threading.get_ident())
        # Simulate the browser's route callback completing independently of a
        # new owner request. Its completion then allows the next frame to arrive.
        if len(pumps) == 1:
            chunks.put(b"first\n")
            chunks.put(b"second\n")
            chunks.put(b"")

    assert list(worker_records(Stream(), idle)) == [b"first\n", b"second\n"]
    assert pumps and all(thread == owner for thread in pumps)
    assert reads and all(thread != owner and size == 8194 for thread, size in reads)


@pytest.mark.parametrize("raw", [b"missing newline", b"x" * 8193 + b"\n"])
def test_invalid_frame_ends_without_dispatch_or_unbounded_buffer(raw):
    assert list(worker_records(BytesIO(raw), lambda: None)) == []


def test_idle_does_not_launch_browser_or_release_pending_verification_lease():
    session = ChromeSession(Path("synthetic"), Path("synthetic"), clock=lambda: 1000.0)
    session.launch = lambda: pytest.fail("Idle launched a browser")
    session.pump_idle()
    lease = object()
    session.desktop_lease = lease
    pumped = []
    session.pages["youtube"] = SimpleNamespace(
        is_closed=lambda: False,
        wait_for_timeout=lambda duration: pumped.append((duration, session.active_deadline)),
    )
    session.pump_idle()
    assert pumped == [(50, 1030.0)]
    assert session.context is None and not session.admitted
    assert session.desktop_lease is lease
    assert session.active_deadline is None


def test_manual_page_close_is_tolerated_during_idle_without_reopening():
    session = ChromeSession(Path("synthetic"), Path("synthetic"))
    closed = []

    def wait(duration):
        closed.append(True)
        raise RuntimeError("Synthetic target closed")

    session.pages["youtube"] = SimpleNamespace(
        is_closed=lambda: bool(closed), wait_for_timeout=wait
    )
    session.pump_idle()
    session.pump_idle()
    assert closed == [True] and session.context is None and not session.admitted


def test_other_idle_failure_is_not_hidden():
    session = ChromeSession(Path("synthetic"), Path("synthetic"))
    session.pages["youtube"] = SimpleNamespace(
        is_closed=lambda: False,
        wait_for_timeout=lambda _: (_ for _ in ()).throw(RuntimeError("Synthetic driver failure")),
    )
    with pytest.raises(RuntimeError, match="driver failure"):
        session.pump_idle()
    assert session.active_deadline is None
