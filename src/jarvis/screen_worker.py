"""Disposable Win32 visible-pixel capture; no window rendering or hidden content."""

import base64
import ctypes as C
import hashlib
import json
import struct
import sys
import time
import zlib
from ctypes import wintypes as W
from pathlib import Path
from uuid import uuid4

from jarvis.domain import Denied
from jarvis.screen_data import ScreenConfig, Target
from jarvis.storage import encode


def png_bgra(data, width, height):
    """Lossless, original-resolution encoding. No unreadable automatic downscale."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        row = data[y * width * 4 : (y + 1) * width * 4]
        rgb = bytearray(width * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        rows.extend(rgb)

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 3))
        + chunk(b"IEND", b"")
    )


def covered_by_displays(bounds, displays):
    """Exact rectangle coverage, including negative origins and monitor gaps."""
    left, top, right, bottom = bounds
    edges = sorted(
        {left, right} | {max(left, min(right, x)) for rect in displays for x in (rect[0], rect[2])}
    )
    for first, last in zip(edges, edges[1:], strict=False):
        intervals = sorted(
            (max(top, rect[1]), min(bottom, rect[3]))
            for rect in displays
            if rect[0] <= first and rect[2] >= last and rect[1] < bottom and rect[3] > top
        )
        end = top
        for start, stop in intervals:
            if start > end:
                return False
            end = max(end, stop)
        if end < bottom:
            return False
    return right > left and bottom > top


class CaptureNative:
    def __init__(self, config):
        from jarvis.win_native import Native

        self.config = config
        self.native = Native()
        self.user, self.kernel = self.native.user, self.native.kernel
        # Thread-local per-monitor-v2 DPI awareness; no global machine settings.
        self.user.SetThreadDpiAwarenessContext.argtypes = [C.c_void_p]
        self.user.SetThreadDpiAwarenessContext.restype = C.c_void_p
        if not self.user.SetThreadDpiAwarenessContext(C.c_void_p(-4)):
            raise Denied("DPI_UNAVAILABLE")
        self.user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        self.user.GetWindowDisplayAffinity.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        self.user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
        self.user.GetDpiForWindow.argtypes = [W.HWND]
        self.user.GetDC.argtypes = [W.HWND]
        self.user.GetDC.restype = W.HDC
        self.user.ReleaseDC.argtypes = [W.HWND, W.HDC]
        self.dwm = C.WinDLL("dwmapi")
        self.dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, W.LPVOID, W.DWORD]

    def available(self):
        self.native.activity()  # Owner SID/session and input desktop via existing adapter.
        if self.user.GetSystemMetrics(0x1000):  # Remote sessions not yet qualified.
            raise Denied("REMOTE_CAPTURE_UNSUPPORTED")

    def window(self, hwnd, *, policy=True):
        if (
            not self.user.IsWindow(hwnd)
            or not self.user.IsWindowVisible(hwnd)
            or self.user.IsIconic(hwnd)
        ):
            raise Denied("WINDOW_NOT_VISIBLE")
        cloaked = W.DWORD()
        if (
            self.dwm.DwmGetWindowAttribute(hwnd, 14, C.byref(cloaked), C.sizeof(cloaked)) != 0
            or cloaked.value
        ):
            raise Denied("WINDOW_CLOAKED_OR_UNKNOWN")
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        process = self.native.process(pid.value)
        if (
            process["os_session"] != self.native.session
            or process["owner_sid"] != self.native.owner_sid
        ):
            raise Denied("WINDOW_SESSION_MISMATCH")
        bounds = W.RECT()
        if not self.user.GetWindowRect(hwnd, C.byref(bounds)):
            raise Denied("WINDOW_BOUNDS_UNAVAILABLE")
        if self.dwm.DwmGetWindowAttribute(hwnd, 9, C.byref(bounds), C.sizeof(bounds)) != 0:
            raise Denied("WINDOW_BOUNDS_UNAVAILABLE")
        name = Path(process["exe"]).name.casefold()
        title = C.create_unicode_buffer(1024)
        self.user.GetWindowTextW(hwnd, title, len(title))  # Policy only, never returned.
        affinity = W.DWORD()
        if self.user.GetWindowDisplayAffinity(hwnd, C.byref(affinity)) and affinity.value:
            raise Denied("PROTECTED_CAPTURE")
        if policy and (
            name in {s.casefold() for s in self.config.excluded_executables}
            or any(s.casefold() in title.value.casefold() for s in self.config.excluded_title_terms)
            or self.config.allowed_executables
            and name not in {s.casefold() for s in self.config.allowed_executables}
        ):
            raise Denied("CAPTURE_EXCLUDED")
        binding = {"hwnd": int(hwnd), "process": process}
        identity = hashlib.sha256(encode(binding).encode()).hexdigest()
        return Target(
            reference="screen_" + identity[:32],
            kind="window",
            identity=identity,
            application=Path(process["exe"]).stem,
            bounds=(bounds.left, bounds.top, bounds.right, bounds.bottom),
            dpi=int(self.user.GetDpiForWindow(hwnd)),
            native=binding,
        )

    def windows(self):
        records = []
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def visit(hwnd, _):
            if len(records) >= 256:
                return False
            try:
                records.append(self.window(hwnd))
            except (Denied, ValueError):
                pass
            return True

        self.user.EnumWindows(callback_type(visit), 0)
        return records

    def displays(self):
        records = []
        scaling = C.WinDLL("shcore")
        scaling.GetDpiForMonitor.argtypes = [
            W.HMONITOR,
            C.c_int,
            C.POINTER(W.UINT),
            C.POINTER(W.UINT),
        ]
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, C.POINTER(W.RECT), W.LPARAM)

        def visit(handle, dc, rect, data):
            bounds = rect.contents
            coords = (bounds.left, bounds.top, bounds.right, bounds.bottom)
            binding = {"monitor": int(handle), "bounds": list(coords)}
            identity = hashlib.sha256(encode(binding).encode()).hexdigest()
            dpi_x, dpi_y = W.UINT(), W.UINT()
            if scaling.GetDpiForMonitor(handle, 0, C.byref(dpi_x), C.byref(dpi_y)) != 0:
                return False
            records.append(
                Target(
                    reference="screen_" + identity[:32],
                    kind="display",
                    identity=identity,
                    application="Selected display",
                    bounds=coords,
                    dpi=dpi_x.value,
                    native=binding,
                )
            )
            return len(records) < 16

        self.user.EnumDisplayMonitors(None, None, callback_type(visit), 0)
        return records

    def desktop(self):
        displays = self.displays()
        if not displays:
            raise Denied("DISPLAY_UNAVAILABLE")
        bounds = (
            min(t.bounds[0] for t in displays),
            min(t.bounds[1] for t in displays),
            max(t.bounds[2] for t in displays),
            max(t.bounds[3] for t in displays),
        )
        binding = {"displays": [t.model_dump(mode="json") for t in displays]}
        identity = hashlib.sha256(encode(binding).encode()).hexdigest()
        return Target(
            reference="screen_" + identity[:32],
            kind="desktop",
            identity=identity,
            application="Entire visible desktop",
            bounds=bounds,
            dpi=displays[0].dpi,
            native=binding,
        )

    def validate(self, target):
        self.available()
        if target.kind == "window":
            current = self.window(target.native["hwnd"])
        elif target.kind == "display":
            current = next((r for r in self.displays() if r.identity == target.identity), None)
        elif target.kind == "desktop":
            current = self.desktop()
        else:
            raise Denied("FULL_DESKTOP_UNSUPPORTED_SELECT_DISPLAY")
        if current is None or current != target:
            raise Denied("CAPTURE_TARGET_CHANGED")

    def password_fields(self, hwnd):
        """Only visible password flags within the authorized window; never values/names."""
        import os

        import comtypes.client

        module = comtypes.client.GetModule(
            str(Path(os.environ["WINDIR"]) / "System32/UIAutomationCore.dll")
        )
        uia = comtypes.client.CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
        root = uia.ElementFromHandle(hwnd)
        condition = uia.CreateAndCondition(
            uia.CreatePropertyCondition(30019, True),  # IsPassword
            uia.CreatePropertyCondition(30022, False),  # IsOffscreen
        )
        if root.FindFirst(4, condition):
            raise Denied("VISIBLE_CREDENTIAL_FIELD")

    def visible_region(self, target, indicator_pid):
        """Conservative visible-only backend rejects overlapping/unsafe windows."""
        left, top, right, bottom = target.bounds
        seen_target = target.kind != "window"
        failure = []
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def visit(hwnd, _):
            nonlocal seen_target
            if target.kind == "window" and int(hwnd) == target.native["hwnd"]:
                seen_target = True
                return False  # EnumWindows is top to bottom; lower windows cannot cover.
            if not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):
                return True
            cloaked = W.DWORD()
            if (
                self.dwm.DwmGetWindowAttribute(hwnd, 14, C.byref(cloaked), C.sizeof(cloaked)) == 0
                and cloaked.value
            ):
                # DWM-cloaked surfaces contribute no visible pixels. Unknown status
                # still goes through the conservative identity/policy checks below.
                return True
            rect = W.RECT()
            self.user.GetWindowRect(hwnd, C.byref(rect))
            if rect.right <= left or rect.left >= right or rect.bottom <= top or rect.top >= bottom:
                return True
            if self.excluded_indicator(hwnd, indicator_pid):
                return True
            # Indicator is visible pixels too. Never ignore its overlap.
            try:
                self.window(hwnd)
                if target.kind in {"display", "desktop"}:
                    self.password_fields(hwnd)
            except (Denied, ValueError):
                failure.append("CAPTURE_REGION_EXCLUDED_OR_UNKNOWN")
                return False
            if target.kind == "window":
                failure.append("WINDOW_COVERED")
                return False
            return True

        self.user.EnumWindows(callback_type(visit), 0)
        if failure or not seen_target:
            raise Denied(failure[0] if failure else "WINDOW_NOT_VISIBLE")

    def excluded_indicator(self, hwnd, indicator_pid):
        """Only our exact owned UI process with verified OS exclusion is exempt.

        This never ignores an arbitrary app's protection or capture policy.
        """
        if not indicator_pid:
            return False
        pid, affinity = W.DWORD(), W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        name = C.create_unicode_buffer(128)
        self.user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
        self.user.GetClassNameW(hwnd, name, len(name))
        if name.value not in {"JarvisScreenStatusV1", "JarvisCompanionOrbV1"}:
            return False
        if (
            not self.user.GetWindowDisplayAffinity(hwnd, C.byref(affinity))
            or affinity.value != 0x11
        ):
            return False
        process = self.native.process(pid.value)
        interpreters = {Path(sys.executable).resolve(), Path(sys._base_executable).resolve()}
        if pid.value != indicator_pid:
            from jarvis.application_identity import process_parents

            if process_parents().get(pid.value) != indicator_pid:
                return False
            launcher = self.native.process(indicator_pid)
            if (
                launcher["owner_sid"] != self.native.owner_sid
                or launcher["os_session"] != self.native.session
                or Path(launcher["exe"]).resolve() not in interpreters
                or launcher["created"] > process["created"]
            ):
                return False
        return (
            process["owner_sid"] == self.native.owner_sid
            and process["os_session"] == self.native.session
            and Path(process["exe"]).resolve() in interpreters
        )

    def capture(self, target, indicator_pid):
        self.validate(target)
        if not covered_by_displays(target.bounds, [r.bounds for r in self.displays()]):
            raise Denied("CAPTURE_REGION_OFFSCREEN")
        if target.kind == "window":
            self.password_fields(target.native["hwnd"])
        self.visible_region(target, indicator_pid)
        left, top, right, bottom = target.bounds
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0 or width * height > self.config.max_pixels:
            raise Denied("CAPTURE_PIXEL_LIMIT_RESIZE_WINDOW")
        gdi = C.WinDLL("gdi32", use_last_error=True)
        gdi.CreateCompatibleDC.argtypes = [W.HDC]
        gdi.CreateCompatibleDC.restype = W.HDC
        gdi.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
        gdi.CreateCompatibleBitmap.restype = W.HBITMAP
        gdi.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
        gdi.SelectObject.restype = W.HGDIOBJ
        gdi.DeleteObject.argtypes = [W.HGDIOBJ]
        gdi.DeleteDC.argtypes = [W.HDC]
        gdi.BitBlt.argtypes = [
            W.HDC,
            C.c_int,
            C.c_int,
            C.c_int,
            C.c_int,
            W.HDC,
            C.c_int,
            C.c_int,
            W.DWORD,
        ]
        gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, W.LPVOID, W.LPVOID, W.UINT]
        screen = self.user.GetDC(None)
        memory, bitmap, previous = None, None, None
        try:
            memory = gdi.CreateCompatibleDC(screen)
            bitmap = gdi.CreateCompatibleBitmap(screen, width, height)
            if not screen or not memory or not bitmap:
                raise Denied("CAPTURE_DEVICE_FAILED")
            previous = gdi.SelectObject(memory, bitmap)
            captured_at = time.time()
            if not gdi.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x00CC0020):
                raise Denied("CAPTURE_DEVICE_FAILED")
            gdi.SelectObject(memory, previous)
            previous = None
            header = C.create_string_buffer(
                struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
            )
            pixels = C.create_string_buffer(width * height * 4)
            if gdi.GetDIBits(memory, bitmap, 0, height, pixels, header, 0) != height:
                raise Denied("CAPTURE_DEVICE_FAILED")
            self.validate(target)
            self.visible_region(target, indicator_pid)
            # Do not accept empty/solid screenshots as visible evidence.
            raw = pixels.raw
            if len(set(raw[:: max(4, len(raw) // 2048 // 4 * 4)])) <= 1:
                raise Denied("CAPTURE_EMPTY_OR_PROTECTED")
            png = png_bgra(raw, width, height)
            if len(png) > self.config.max_image_bytes:
                raise Denied("CAPTURE_IMAGE_LIMIT")
            return {
                "artifact": "image_" + uuid4().hex,
                "target_identity": target.identity,
                "generation": 1,
                "captured_at": captured_at,
                "width": width,
                "height": height,
                "bounds": target.bounds,
                "png": base64.b64encode(png).decode(),
                "pixel_digest": hashlib.sha256(raw).hexdigest(),
            }
        finally:
            if previous and memory:
                gdi.SelectObject(memory, previous)
            if bitmap:
                gdi.DeleteObject(bitmap)
            if memory:
                gdi.DeleteDC(memory)
            if screen:
                self.user.ReleaseDC(None, screen)


def main():
    request_id = ""
    try:
        from jarvis.models import reject_constant, unique_object

        raw = sys.stdin.buffer.readline(65537)
        if len(raw) > 65536:
            raise Denied("CAPTURE_ENVELOPE_LIMIT")
        request = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        request_id = request["id"]
        if (
            set(request) != {"version", "id", "operation", "config", "target", "indicator_pid"}
            or request["version"] != 1
        ):
            raise Denied("CAPTURE_ENVELOPE_INVALID")
        config = ScreenConfig.model_validate(request["config"], strict=True)
        if not config.enabled:
            raise Denied("CAPTURE_DISABLED")
        native = CaptureNative(config)
        native.available()
        operation = request["operation"]
        if operation == "inventory":
            result = [
                r.model_dump(mode="json")
                for r in native.windows() + native.displays() + [native.desktop()]
            ]
        elif operation == "foreground":
            result = native.window(native.user.GetForegroundWindow()).model_dump(mode="json")
        elif operation in {"validate", "capture"}:
            target = Target.model_validate_json(json.dumps(request["target"]))
            result = (
                native.capture(target, request["indicator_pid"])
                if operation == "capture"
                else native.validate(target)
            )
        else:
            raise Denied("CAPTURE_OPERATION_INVALID")
        reply = {"id": request_id, "result": result, "error": None}
    except Exception as exc:
        code = str(exc) if isinstance(exc, Denied) else "CAPTURE_WORKER_FAILED"
        reply = {"id": request_id, "result": None, "error": code}
    print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
