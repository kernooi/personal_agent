"""Native no-activate stop indicator on the existing tkinter/Tcl event loop.

Tk's first toplevel map activates a hidden wrapper on this Windows/Tk build.
A Tcl interpreter needs no Tk window and still dispatches timers/native messages.
"""

import ctypes as C
import os
import tkinter
from ctypes import wintypes as W

from jarvis.companion_windows import function
from jarvis.screen_indicator import invalidates_session


class Status:
    width, height = 340, 52

    def __init__(self):
        self.tcl = tkinter.Tcl()
        self.user, self.gdi = C.WinDLL("user32"), C.WinDLL("gdi32")
        self.closed = False
        self.text = "JARVIS SCREEN ACCESS\nPreparing · Click to stop"
        self.font = function(self.gdi, "CreateFontW", W.HFONT, *([C.c_int] * 13), W.LPCWSTR)(
            -14, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        self.brush = function(self.gdi, "CreateSolidBrush", W.HBRUSH, W.DWORD)(0x24211E)
        self.callback_type = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        default = function(
            self.user, "DefWindowProcW", C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM
        )

        class Paint(C.Structure):
            _fields_ = [
                ("dc", W.HDC),
                ("erase", W.BOOL),
                ("rect", W.RECT),
                ("restore", W.BOOL),
                ("incremental", W.BOOL),
                ("reserved", C.c_byte * 32),
            ]

        def receive(hwnd, message, wparam, lparam):
            if invalidates_session(message, wparam):
                os._exit(0)
            if message == 0x21:
                return 3
            if message in {0x202, 0x10}:  # Click or close stops access.
                self.destroy()
                return 0
            if message == 0x0F:
                paint = Paint()
                dc = function(self.user, "BeginPaint", W.HDC, W.HWND, C.c_void_p)(
                    hwnd, C.byref(paint)
                )
                rect = W.RECT()
                function(self.user, "GetClientRect", W.BOOL, W.HWND, C.c_void_p)(
                    hwnd, C.byref(rect)
                )
                function(self.user, "FillRect", C.c_int, W.HDC, C.c_void_p, W.HBRUSH)(
                    dc, C.byref(rect), self.brush
                )
                old = function(self.gdi, "SelectObject", W.HGDIOBJ, W.HDC, W.HGDIOBJ)(dc, self.font)
                function(self.gdi, "SetBkMode", C.c_int, W.HDC, C.c_int)(dc, 1)
                function(self.gdi, "SetTextColor", W.DWORD, W.HDC, W.DWORD)(dc, 0xF8F8FF)
                rect.top, rect.bottom = 8, rect.bottom - 4
                function(
                    self.user, "DrawTextW", C.c_int, W.HDC, W.LPCWSTR, C.c_int, C.c_void_p, W.UINT
                )(dc, self.text, -1, C.byref(rect), 0x811)
                self.gdi.SelectObject(dc, old)
                function(self.user, "EndPaint", W.BOOL, W.HWND, C.c_void_p)(hwnd, C.byref(paint))
                return 0
            return default(hwnd, message, wparam, lparam)

        self.callback = self.callback_type(receive)

        class WindowClass(C.Structure):
            _fields_ = [
                ("style", W.UINT),
                ("proc", C.c_void_p),
                ("extra", C.c_int),
                ("window_extra", C.c_int),
                ("instance", W.HINSTANCE),
                ("icon", W.HICON),
                ("cursor", W.HANDLE),
                ("background", W.HBRUSH),
                ("menu", W.LPCWSTR),
                ("name", W.LPCWSTR),
            ]

        instance = function(C.WinDLL("kernel32"), "GetModuleHandleW", W.HMODULE, W.LPCWSTR)(None)
        record = WindowClass(
            0,
            C.cast(self.callback, C.c_void_p),
            0,
            0,
            instance,
            None,
            None,
            None,
            None,
            "JarvisScreenStatusV1",
        )
        if not function(self.user, "RegisterClassW", W.ATOM, C.c_void_p)(C.byref(record)):
            raise OSError("Screen indicator registration failed")
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
            C.c_void_p,
        )(
            0x08000088,
            record.name,
            "JARVIS screen access",
            0x80000000,
            0,
            0,
            self.width,
            self.height,
            None,
            None,
            instance,
            None,
        )
        if not self.hwnd:
            raise OSError("Screen indicator unavailable")
        # A quiet rounded badge, rather than the previous red rectangular panel.
        region = function(self.gdi, "CreateRoundRectRgn", W.HRGN, *([C.c_int] * 6))(
            0, 0, self.width + 1, self.height + 1, 20, 20
        )
        if region and not function(self.user, "SetWindowRgn", C.c_int, W.HWND, W.HRGN, W.BOOL)(
            self.hwnd, region, True
        ):
            function(self.gdi, "DeleteObject", W.BOOL, W.HGDIOBJ)(region)
        # Windows owns the region after successful assignment.
        self.notifications = C.WinDLL("wtsapi32")
        if not function(
            self.notifications, "WTSRegisterSessionNotification", W.BOOL, W.HWND, W.DWORD
        )(self.hwnd, 0):
            self.destroy()
            raise OSError("Screen session notifications unavailable")
        function(self.user, "SetWindowDisplayAffinity", W.BOOL, W.HWND, W.DWORD)(self.hwnd, 0x11)
        # Delay visible mapping until trusted CAPTURING/WATCHING positions it.

    def configure(self, *, text):
        self.text = text.replace("Close to stop", "Click to stop")
        function(self.user, "InvalidateRect", W.BOOL, W.HWND, C.c_void_p, W.BOOL)(
            self.hwnd, None, True
        )
        function(self.user, "ShowWindow", W.BOOL, W.HWND, C.c_int)(self.hwnd, 4)

    def after(self, milliseconds, callback):
        self.tcl.after(milliseconds, callback)

    def update_idletasks(self):
        self.tcl.update_idletasks()

    def winfo_id(self):
        return self.hwnd

    def winfo_reqwidth(self):
        return self.width

    def winfo_reqheight(self):
        return self.height

    def mainloop(self):
        self.tcl.eval("vwait ::jarvis_companion_closed")

    def destroy(self):
        if self.closed:
            return
        self.closed = True
        if hasattr(self, "notifications"):
            function(self.notifications, "WTSUnRegisterSessionNotification", W.BOOL, W.HWND)(
                self.hwnd
            )
        function(self.user, "DestroyWindow", W.BOOL, W.HWND)(self.hwnd)
        function(self.gdi, "DeleteObject", W.BOOL, W.HGDIOBJ)(self.font)
        self.gdi.DeleteObject(self.brush)
        self.tcl.setvar("::jarvis_companion_closed", 1)
