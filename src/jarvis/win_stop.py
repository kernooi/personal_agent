"""Registered global stop hotkey. No keyboard hook or ordinary-key capture."""

import ctypes as C
import queue
import threading
from ctypes import wintypes as W

from jarvis.domain import Handoff


class StopHotkey:
    def __init__(self, stop, notice=print):
        self.stop = stop
        self.notice = notice
        self.closed = threading.Event()
        self.ready = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        user = C.WinDLL("user32", use_last_error=True)
        user.RegisterHotKey.argtypes = [W.HWND, C.c_int, W.UINT, W.UINT]
        user.UnregisterHotKey.argtypes = [W.HWND, C.c_int]
        user.PeekMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
        # Ctrl+Alt+Shift+F10, MOD_NOREPEAT. Conflict fails closed, never remapped silently.
        registered = bool(user.RegisterHotKey(None, 0x4A52, 0x4007, 0x79))
        self.ready.put(registered)
        if not registered:
            return
        try:
            message = W.MSG()
            while not self.closed.is_set():
                while user.PeekMessageW(C.byref(message), None, 0, 0, 1):
                    if message.message == 0x0312 and message.wParam == 0x4A52:
                        self.stop.set()
                        self.notice(
                            "JARVIS: Stop acknowledged. New actions are blocked; "
                            "already delivered effects may remain."
                        )
                self.closed.wait(0.02)
        finally:
            user.UnregisterHotKey(None, 0x4A52)

    def __enter__(self):
        self.thread.start()
        try:
            registered = self.ready.get(timeout=2)
        except queue.Empty as exc:
            self.closed.set()
            raise Handoff("Stop hotkey startup timed out; real mode is disabled") from exc
        if not registered:
            raise Handoff("Ctrl+Alt+Shift+F10 conflicts with another hotkey; real mode is disabled")
        return self

    def __exit__(self, *_):
        self.closed.set()
        self.thread.join(timeout=2)
