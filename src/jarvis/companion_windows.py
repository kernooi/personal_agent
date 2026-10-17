"""Windows GDI+ vector drawing and a small per-pixel-alpha native overlay.

Imported only for explicit native UI/preview. No screenshots, input injection,
model/network access, installations or global settings.
"""

import ctypes as C
import math
import struct
import zlib
from ctypes import wintypes as W

from jarvis.companion import eyes, placement

P = C.c_void_p
F = C.c_float


class PointF(C.Structure):
    _fields_ = [("x", F), ("y", F)]


class BitmapInfo(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("width", W.LONG),
        ("height", W.LONG),
        ("planes", W.WORD),
        ("bits", W.WORD),
        ("compression", W.DWORD),
        ("image_size", W.DWORD),
        ("xppm", W.LONG),
        ("yppm", W.LONG),
        ("used", W.DWORD),
        ("important", W.DWORD),
    ]


def function(dll, name, result, *arguments):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, list(arguments)
    return fn


def checked(status):
    if status:
        raise OSError("Companion vector renderer unavailable")


class Renderer:
    def __init__(self, diameter=80, dpi=96):
        self.diameter = diameter * dpi / 96
        self.edge = round(self.diameter * 1.32)
        self.gdi = C.WinDLL("gdi32")
        self.gp = C.WinDLL("gdiplus")
        self.token = C.c_size_t()

        class Startup(C.Structure):
            _fields_ = [
                ("version", W.UINT),
                ("callback", P),
                ("thread", W.BOOL),
                ("codecs", W.BOOL),
            ]

        checked(
            function(self.gp, "GdiplusStartup", C.c_int, P, P, P)(
                C.byref(self.token), C.byref(Startup(1, None, False, False)), None
            )
        )
        self.dc = function(self.gdi, "CreateCompatibleDC", W.HDC, W.HDC)(None)
        self.bits = P()
        info = BitmapInfo(C.sizeof(BitmapInfo), self.edge, -self.edge, 1, 32)
        self.bitmap = function(
            self.gdi, "CreateDIBSection", W.HBITMAP, W.HDC, P, W.UINT, P, W.HANDLE, W.DWORD
        )(self.dc, C.byref(info), 0, C.byref(self.bits), None, 0)
        if not self.bitmap or not self.dc:
            raise OSError("Companion bitmap unavailable")
        self.old = function(self.gdi, "SelectObject", W.HGDIOBJ, W.HDC, W.HGDIOBJ)(
            self.dc, self.bitmap
        )
        self.image, self.graphics = P(), P()
        checked(
            function(
                self.gp,
                "GdipCreateBitmapFromScan0",
                C.c_int,
                C.c_int,
                C.c_int,
                C.c_int,
                C.c_int,
                P,
                P,
            )(self.edge, self.edge, self.edge * 4, 0xE200B, self.bits, C.byref(self.image))
        )
        checked(
            function(self.gp, "GdipGetImageGraphicsContext", C.c_int, P, P)(
                self.image, C.byref(self.graphics)
            )
        )
        checked(function(self.gp, "GdipSetSmoothingMode", C.c_int, P, C.c_int)(self.graphics, 4))
        checked(function(self.gp, "GdipSetPixelOffsetMode", C.c_int, P, C.c_int)(self.graphics, 4))
        self.closed = False

    def call(self, name, signature, *values):
        checked(function(self.gp, name, C.c_int, *signature)(*values))

    def solid(self, color):
        brush = P()
        self.call("GdipCreateSolidFill", [W.UINT, P], color, C.byref(brush))
        return brush

    def ellipse(self, brush, x, y, width, height):
        self.call("GdipFillEllipse", [P, P, F, F, F, F], self.graphics, brush, x, y, width, height)

    def render(self, pose):
        self.call("GdipGraphicsClear", [P, W.UINT], self.graphics, 0)
        if pose.opacity <= 0:
            return
        d = self.diameter * pose.scale
        origin_x = (self.edge - d) / 2
        origin_y = (self.edge - d) / 2 + pose.bob * self.diameter / 80
        # A low-contrast, graphite rim and two smooth vector gradients, no glow.
        line = P()
        a, b = PointF(origin_x, origin_y), PointF(origin_x + d, origin_y + d)
        self.call(
            "GdipCreateLineBrush",
            [P, P, W.UINT, W.UINT, C.c_int, P],
            C.byref(a),
            C.byref(b),
            0xFF565968,
            0xFF1C1E23,
            0,
            C.byref(line),
        )
        self.ellipse(line, origin_x, origin_y, d, d)
        self.call("GdipDeleteBrush", [P], line)
        path, brush = P(), P()
        self.call("GdipCreatePath", [C.c_int, P], 0, C.byref(path))
        inset = max(0.55, d * 0.006)
        self.call(
            "GdipAddPathEllipse",
            [P, F, F, F, F],
            path,
            origin_x + inset,
            origin_y + inset,
            d - 2 * inset,
            d - 2 * inset,
        )
        self.call("GdipCreatePathGradientFromPath", [P, P], path, C.byref(brush))
        self.call("GdipSetPathGradientCenterColor", [P, W.UINT], brush, 0xFF101114)
        color, count = W.UINT(0xFF454854), C.c_int(1)
        self.call(
            "GdipSetPathGradientSurroundColorsWithCount",
            [P, P, P],
            brush,
            C.byref(color),
            C.byref(count),
        )
        center = PointF(origin_x + d * 0.60, origin_y + d * 0.63)
        self.call("GdipSetPathGradientCenterPoint", [P, P], brush, C.byref(center))
        self.call("GdipFillPath", [P, P, P], self.graphics, brush, path)
        self.call("GdipDeleteBrush", [P], brush)
        # A translucent directional shade softens the lower-right edge while
        # preserving the broad upper-left material highlight.
        shade = P()
        self.call(
            "GdipCreateLineBrush",
            [P, P, W.UINT, W.UINT, C.c_int, P],
            C.byref(a),
            C.byref(b),
            0x000F1013,
            0xCE0F1013,
            0,
            C.byref(shade),
        )
        self.call("GdipFillPath", [P, P, P], self.graphics, shade, path)
        self.call("GdipDeleteBrush", [P], shade)
        self.call("GdipDeletePath", [P], path)
        white = self.solid(0xFFFCFCFB)
        try:
            for cx, cy, width, height in eyes(pose, d):
                path, matrix = P(), P()
                self.call("GdipCreatePath", [C.c_int, P], 0, C.byref(path))
                radius = min(width, height) / 2
                for x, y, angle in [
                    (-width / 2, -height / 2, 180),
                    (width / 2 - 2 * radius, -height / 2, 270),
                    (width / 2 - 2 * radius, height / 2 - 2 * radius, 0),
                    (-width / 2, height / 2 - 2 * radius, 90),
                ]:
                    self.call(
                        "GdipAddPathArc",
                        [P, F, F, F, F, F, F],
                        path,
                        x,
                        y,
                        2 * radius,
                        2 * radius,
                        angle,
                        90,
                    )
                self.call("GdipClosePathFigure", [P], path)
                theta = math.radians(pose.tilt)
                cosine, sine = math.cos(theta), math.sin(theta)
                self.call(
                    "GdipCreateMatrix2",
                    [F, F, F, F, F, F, P],
                    cosine,
                    sine,
                    -sine,
                    cosine,
                    origin_x + cx,
                    origin_y + cy,
                    C.byref(matrix),
                )
                self.call("GdipTransformPath", [P, P], path, matrix)
                self.call("GdipFillPath", [P, P, P], self.graphics, white, path)
                self.call("GdipDeleteMatrix", [P], matrix)
                self.call("GdipDeletePath", [P], path)
        finally:
            self.call("GdipDeleteBrush", [P], white)
        self.call("GdipFlush", [P, C.c_int], self.graphics, 1)

    def rgba(self):
        raw = C.string_at(self.bits, self.edge * self.edge * 4)
        result = bytearray()
        for i in range(0, len(raw), 4):
            blue, green, red, alpha = raw[i : i + 4]
            result.extend(
                (
                    min(255, round(red * 255 / alpha)) if alpha else 0,
                    min(255, round(green * 255 / alpha)) if alpha else 0,
                    min(255, round(blue * 255 / alpha)) if alpha else 0,
                    alpha,
                )
            )
        return bytes(result)

    def close(self):
        if self.closed:
            return
        self.call("GdipDeleteGraphics", [P], self.graphics)
        self.call("GdipDisposeImage", [P], self.image)
        function(self.gdi, "SelectObject", W.HGDIOBJ, W.HDC, W.HGDIOBJ)(self.dc, self.old)
        function(self.gdi, "DeleteObject", W.BOOL, W.HGDIOBJ)(self.bitmap)
        function(self.gdi, "DeleteDC", W.BOOL, W.HDC)(self.dc)
        function(self.gp, "GdiplusShutdown", None, C.c_size_t)(self.token)
        self.closed = True


def rgba_png(width, height, pixels):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    raw = b"".join(b"\0" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class Overlay:
    """Tk's existing UI thread dispatches messages for this native childless window."""

    def __init__(self, config):
        self.config = config
        self.user = C.WinDLL("user32", use_last_error=True)
        self.kernel = C.WinDLL("kernel32")
        self.dpi = 96
        self.renderer = None
        self.closed = False
        self.callback_type = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        self.default = function(
            self.user, "DefWindowProcW", C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM
        )

        def receive(hwnd, message, wparam, lparam):
            if message == 0x84:  # HTTRANSPARENT; layered WS_EX_TRANSPARENT crosses processes.
                return -1
            if message == 0x21:  # MA_NOACTIVATE
                return 3
            return self.default(hwnd, message, wparam, lparam)

        self.callback = self.callback_type(receive)

        class WindowClass(C.Structure):
            _fields_ = [
                ("style", W.UINT),
                ("proc", P),
                ("extra", C.c_int),
                ("window_extra", C.c_int),
                ("instance", W.HINSTANCE),
                ("icon", W.HICON),
                ("cursor", W.HANDLE),
                ("background", W.HBRUSH),
                ("menu", W.LPCWSTR),
                ("name", W.LPCWSTR),
            ]

        instance = function(self.kernel, "GetModuleHandleW", W.HMODULE, W.LPCWSTR)(None)
        record = WindowClass(
            0,
            C.cast(self.callback, P),
            0,
            0,
            instance,
            None,
            None,
            None,
            None,
            "JarvisCompanionOrbV1",
        )
        atom = function(self.user, "RegisterClassW", W.ATOM, P)(C.byref(record))
        if not atom and C.get_last_error() != 1410:
            raise OSError("Companion window class unavailable")
        self.hwnd = function(
            self.user,
            "CreateWindowExW",
            W.HWND,
            W.DWORD,
            W.LPCWSTR,
            W.LPCWSTR,
            W.DWORD,
            C.c_int,
            C.c_int,
            C.c_int,
            C.c_int,
            W.HWND,
            W.HMENU,
            W.HINSTANCE,
            P,
        )(
            0x080800A0,
            record.name,
            "JARVIS companion",
            0x80000000,
            0,
            0,
            1,
            1,
            None,
            None,
            instance,
            None,
        )
        if not self.hwnd:
            raise OSError("Companion overlay unavailable")
        self.excluded = bool(
            function(self.user, "SetWindowDisplayAffinity", W.BOOL, W.HWND, W.DWORD)(
                self.hwnd, 0x11
            )
        )
        affinity = W.DWORD()
        self.excluded = (
            self.excluded
            and bool(
                function(self.user, "GetWindowDisplayAffinity", W.BOOL, W.HWND, P)(
                    self.hwnd, C.byref(affinity)
                )
            )
            and affinity.value == 0x11
        )
        self.move((0, 0, 1, 1))

    def move(self, bounds):
        class MonitorInfo(C.Structure):
            _fields_ = [
                ("size", W.DWORD),
                ("monitor", W.RECT),
                ("work", W.RECT),
                ("flags", W.DWORD),
            ]

        rect = W.RECT(*bounds)
        monitor = function(self.user, "MonitorFromRect", W.HMONITOR, P, W.DWORD)(C.byref(rect), 2)
        info = MonitorInfo(C.sizeof(MonitorInfo))
        if not function(self.user, "GetMonitorInfoW", W.BOOL, W.HMONITOR, P)(
            monitor, C.byref(info)
        ):
            raise OSError("Companion monitor unavailable")
        dpi_x, dpi_y = W.UINT(96), W.UINT(96)
        function(C.WinDLL("shcore"), "GetDpiForMonitor", C.c_int, W.HMONITOR, C.c_int, P, P)(
            monitor, 0, C.byref(dpi_x), C.byref(dpi_y)
        )
        self.work = (info.work.left, info.work.top, info.work.right, info.work.bottom)
        self.x, self.y, edge = placement(
            self.work, self.config.size, dpi_x.value, self.config.position
        )
        if not self.renderer or self.dpi != dpi_x.value:
            if self.renderer:
                self.renderer.close()
            self.dpi = dpi_x.value
            self.renderer = Renderer(self.config.size, self.dpi)
        self.edge = edge

    def show(self, pose):
        if self.closed:
            return
        if pose.opacity <= 0 or (pose.state == "capturing" and not self.excluded):
            function(self.user, "ShowWindow", W.BOOL, W.HWND, C.c_int)(self.hwnd, 0)
            return
        self.renderer.render(pose)

        class Blend(C.Structure):
            _fields_ = [
                ("operation", C.c_byte),
                ("flags", C.c_byte),
                ("alpha", C.c_ubyte),
                ("format", C.c_byte),
            ]

        dest, origin, size = W.POINT(self.x, self.y), W.POINT(0, 0), W.SIZE(self.edge, self.edge)
        blend = Blend(0, 0, round(pose.opacity * 255), 1)
        if not function(
            self.user,
            "UpdateLayeredWindow",
            W.BOOL,
            W.HWND,
            W.HDC,
            P,
            P,
            W.HDC,
            P,
            W.DWORD,
            P,
            W.DWORD,
        )(
            self.hwnd,
            None,
            C.byref(dest),
            C.byref(size),
            self.renderer.dc,
            C.byref(origin),
            0,
            C.byref(blend),
            2,
        ):
            raise OSError("Companion composition failed")
        function(
            self.user,
            "SetWindowPos",
            W.BOOL,
            W.HWND,
            W.HWND,
            C.c_int,
            C.c_int,
            C.c_int,
            C.c_int,
            W.UINT,
        )(self.hwnd, W.HWND(-1), self.x, self.y, self.edge, self.edge, 0x50)

    def close(self):
        if self.closed:
            return
        function(self.user, "DestroyWindow", W.BOOL, W.HWND)(self.hwnd)
        if self.renderer:
            self.renderer.close()
        self.closed = True


def system_reduced_motion():
    enabled = W.BOOL(True)
    ok = function(C.WinDLL("user32"), "SystemParametersInfoW", W.BOOL, W.UINT, W.UINT, P, W.UINT)(
        0x1042, 0, C.byref(enabled), 0
    )
    return bool(ok) and not enabled.value
