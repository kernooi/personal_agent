"""Responsive presentation host inside the existing capture-indicator process."""

import json
import queue
import sys
import threading
import time

from jarvis.companion import Animation
from jarvis.companion_windows import Overlay, system_reduced_motion


class Host:
    def __init__(self, root, config, label):
        self.root, self.config, self.label = root, config, label
        self.messages = queue.Queue(maxsize=32)
        self.closing = None
        self.frames, self.render_seconds = 0, 0.0
        self.started = time.monotonic()
        self.next_frame = self.started
        self.overlay = None
        self.error = None
        reduced = config.reduced_motion == "always" or (
            config.reduced_motion == "system" and system_reduced_motion()
        )
        self.animation = Animation(config, reduced=reduced)
        try:
            if config.enabled:
                self.overlay = Overlay(config)
        except (OSError, ValueError):
            self.error = "COMPANION_UNAVAILABLE"
        self.previous_pose = None
        threading.Thread(target=self.read, daemon=True).start()
        root.after(16, self.tick)

    def read(self):
        try:
            while True:
                line = sys.stdin.buffer.readline(8193)
                if not line:
                    self.shutdown_watchdog()
                    self.messages.put_nowait({"event": "shutdown"})
                    return
                if len(line) > 8192:
                    raise ValueError("Oversized UI message")
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("Invalid UI message")
                if value.get("event") == "shutdown":
                    self.shutdown_watchdog()
                self.messages.put_nowait(value)
        except (ValueError, queue.Full):
            # Parent liveness gates stop capture even when its inference is busy.
            import os

            os._exit(2)

    @staticmethod
    def shutdown_watchdog():
        # The venv launcher and the UI can be different processes on Windows.
        # Even a stuck native event loop must not leave its owned overlay behind.
        def expire():
            import os

            time.sleep(1.25)
            os._exit(0)  # This indicator process only; never a desktop target.

        threading.Thread(target=expire, daemon=True).start()

    def metadata(self):
        import ctypes as C
        from ctypes import wintypes as W

        user = C.WinDLL("user32")
        user.GetForegroundWindow.restype = W.HWND
        user.GetAncestor.argtypes, user.GetAncestor.restype = [W.HWND, W.UINT], W.HWND
        root_handle = user.GetAncestor(self.root.winfo_id(), 2)
        user.GetWindowLongPtrW.argtypes, user.GetWindowLongPtrW.restype = (
            [W.HWND, C.c_int],
            C.c_ssize_t,
        )
        return {
            "frames": self.frames,
            "render_seconds": self.render_seconds,
            "state": self.animation.state,
            "companion_error": self.error,
            "excluded": bool(self.overlay and self.overlay.excluded),
            "hwnd": int(self.overlay.hwnd) if self.overlay else None,
            "position": [self.overlay.x, self.overlay.y, self.overlay.edge]
            if self.overlay
            else None,
            "dpi": self.overlay.dpi if self.overlay else None,
            "reduced_motion": self.animation.reduced,
            "foreground_is_indicator": user.GetForegroundWindow() == root_handle,
            "foreground_is_orb": bool(
                self.overlay and user.GetForegroundWindow() == self.overlay.hwnd
            ),
            "indicator_noactivate": bool(user.GetWindowLongPtrW(root_handle, -20) & 0x08000000),
            "elapsed_seconds": time.monotonic() - self.started,
        }

    def tick(self):
        now = time.monotonic()
        for _ in range(32):
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            event = message.get("event")
            if event == "shutdown":
                self.closing = now + 0.95
                continue
            sequence = message.get("sequence")
            if type(sequence) is not int or not 0 <= sequence < 2**53:
                continue
            if event == "probe":
                print(json.dumps({"ack": sequence, **self.metadata()}), flush=True)
                continue
            task, bounds = message.get("task"), message.get("bounds")
            if (
                not isinstance(task, str)
                or len(task) > 80
                or not isinstance(bounds, list)
                or len(bounds) != 4
                or any(type(v) is not int for v in bounds)
            ):
                continue
            accepted = self.animation.event(
                event, task, sequence, now, watching=message.get("watching") is True
            )
            if accepted:
                text = {
                    "capturing": "Reading screen",
                    "analyzing": "Thinking locally",
                    "watching": "Watch active · between samples",
                    "completed": "Screen analysis complete",
                    "error": "Screen observation failed",
                    "cancelled": "Screen observation stopped",
                }.get(self.animation.state, "Screen access active")
                self.label.configure(text="JARVIS SCREEN ACCESS\n" + text + " · Close to stop")
                if self.overlay:
                    try:
                        self.overlay.move(bounds)
                        self.root.update_idletasks()
                        import ctypes as C
                        from ctypes import wintypes as W

                        user = self.overlay.user
                        user.GetAncestor.argtypes, user.GetAncestor.restype = (
                            [W.HWND, W.UINT],
                            W.HWND,
                        )
                        handle = user.GetAncestor(self.root.winfo_id(), 2)
                        user.SetWindowPos.argtypes = [
                            W.HWND,
                            W.HWND,
                            C.c_int,
                            C.c_int,
                            C.c_int,
                            C.c_int,
                            W.UINT,
                        ]
                        user.SetWindowPos(
                            handle,
                            None,
                            max(
                                self.overlay.work[0],
                                self.overlay.x + self.overlay.edge - self.root.winfo_reqwidth(),
                            ),
                            max(
                                self.overlay.work[1],
                                self.overlay.y - self.root.winfo_reqheight() - 12,
                            ),
                            0,
                            0,
                            0x15,
                        )
                        # Synchronous draw before acknowledgement: on unsupported
                        # systems CAPTURING hides only the orb, never this indicator.
                        self.overlay.show(self.animation.pose(now))
                    except (OSError, ValueError):
                        self.overlay.close()
                        self.overlay = None
                        self.error = "COMPANION_UNAVAILABLE"
            print(json.dumps({"ack": sequence, **self.metadata()}), flush=True)
        pose = self.animation.pose(now)
        if self.overlay and (not self.animation.reduced or pose != self.previous_pose):
            start = time.perf_counter()
            try:
                self.overlay.show(pose)
                if pose.opacity:
                    self.frames += 1
            except OSError:
                self.overlay.close()
                self.overlay = None
                self.error = "COMPANION_UNAVAILABLE"
            self.render_seconds += time.perf_counter() - start
        self.previous_pose = pose
        if self.closing and (pose.opacity == 0 or now >= self.closing):
            self.close()
            self.root.destroy()
            return
        self.next_frame = max(self.next_frame + 1 / 60, time.monotonic())
        self.root.after(max(1, round((self.next_frame - time.monotonic()) * 1000)), self.tick)

    def close(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None
