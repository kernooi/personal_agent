"""Reviewed native observations. Imported only inside disposable Windows workers.

No document bodies, window titles, tab names or keyboard contents are collected.
"""

import ctypes as C
import hashlib
import os
from ctypes import wintypes as W
from pathlib import Path

from jarvis.domain import Denied


def file_hash(path: str) -> str:
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Native:
    def __init__(self):
        if os.name != "nt":
            raise Denied("Windows interactive session required")
        self.user = C.WinDLL("user32", use_last_error=True)
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        # Explicit 64-bit-safe prototypes; never truncate handles.
        self.user.GetForegroundWindow.restype = W.HWND
        self.user.GetWindow.restype = W.HWND
        self.user.GetWindow.argtypes = [W.HWND, W.UINT]
        self.user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        self.user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
        self.user.IsWindow.argtypes = [W.HWND]
        self.user.IsWindowVisible.argtypes = [W.HWND]
        self.user.IsWindowEnabled.argtypes = [W.HWND]
        self.user.SetForegroundWindow.argtypes = [W.HWND]
        self.user.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        self.user.OpenInputDesktop.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.user.OpenInputDesktop.restype = W.HANDLE
        self.user.CloseDesktop.argtypes = [W.HANDLE]
        self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.kernel.OpenProcess.restype = W.HANDLE
        self.kernel.CloseHandle.argtypes = [W.HANDLE]
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            W.HANDLE,
            W.DWORD,
            W.LPWSTR,
            C.POINTER(W.DWORD),
        ]
        self.kernel.GetProcessTimes.argtypes = [W.HANDLE, *([C.POINTER(W.FILETIME)] * 4)]
        self.kernel.GetPackageFullName.argtypes = [W.HANDLE, C.POINTER(W.UINT), W.LPWSTR]
        own = self.process(os.getpid())
        self.session = own["os_session"]
        self.owner_sid = own["owner_sid"]
        self.uia = None

    def process(self, pid):
        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            raise Denied("Process identity unavailable")
        try:
            path = C.create_unicode_buffer(32768)
            length = W.DWORD(len(path))
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, path, C.byref(length)):
                raise Denied("Executable identity unavailable")
            times = [W.FILETIME() for _ in range(4)]
            if not self.kernel.GetProcessTimes(handle, *(C.byref(item) for item in times)):
                raise Denied("Process creation time unavailable")
            session = W.DWORD()
            if not self.kernel.ProcessIdToSessionId(pid, C.byref(session)):
                raise Denied("User session unavailable")
            package_len = W.UINT(1024)
            package = C.create_unicode_buffer(1024)
            error = self.kernel.GetPackageFullName(handle, C.byref(package_len), package)
            if error not in (0, 15700):
                raise Denied("Package identity unavailable")
            return {
                "pid": pid,
                "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                "os_session": session.value,
                "exe": str(Path(path.value).resolve()),
                "package": package.value if error == 0 else "",
                "owner_sid": self.owner(handle),
            }
        finally:
            self.kernel.CloseHandle(handle)

    def owner(self, process):
        advapi = C.WinDLL("advapi32", use_last_error=True)
        advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
        advapi.GetTokenInformation.argtypes = [
            W.HANDLE,
            C.c_int,
            W.LPVOID,
            W.DWORD,
            C.POINTER(W.DWORD),
        ]
        advapi.ConvertSidToStringSidW.argtypes = [W.LPVOID, C.POINTER(W.LPWSTR)]
        token = W.HANDLE()
        if not advapi.OpenProcessToken(process, 8, C.byref(token)):
            raise Denied("Process user identity unavailable")
        try:
            length = W.DWORD()
            advapi.GetTokenInformation(token, 1, None, 0, C.byref(length))
            if not 0 < length.value <= 4096:
                raise Denied("Invalid process user identity")
            buffer = C.create_string_buffer(length.value)
            if not advapi.GetTokenInformation(token, 1, buffer, length, C.byref(length)):
                raise Denied("Process token unavailable")
            sid = C.cast(buffer, C.POINTER(C.c_void_p))[0]
            text = W.LPWSTR()
            if not advapi.ConvertSidToStringSidW(sid, C.byref(text)):
                raise Denied("Process SID unavailable")
            try:
                return hashlib.sha256(text.value.encode()).hexdigest()
            finally:
                self.kernel.LocalFree.argtypes = [W.LPVOID]
                self.kernel.LocalFree(C.cast(text, W.LPVOID))
        finally:
            self.kernel.CloseHandle(token)

    def activity(self):
        class LastInput(C.Structure):
            _fields_ = [("cbSize", W.UINT), ("dwTime", W.DWORD)]

        info = LastInput(C.sizeof(LastInput), 0)
        if not self.user.GetLastInputInfo(C.byref(info)):
            raise Denied("Input activity unavailable")
        desktop = self.user.OpenInputDesktop(0, False, 1)
        if not desktop:
            raise Denied("Session locked or desktop inaccessible")
        try:
            name = C.create_unicode_buffer(128)
            needed = W.DWORD()
            self.user.GetUserObjectInformationW.argtypes = [
                W.HANDLE,
                C.c_int,
                W.LPVOID,
                W.DWORD,
                C.POINTER(W.DWORD),
            ]
            if (
                not self.user.GetUserObjectInformationW(
                    desktop, 2, name, C.sizeof(name), C.byref(needed)
                )
                or name.value != "Default"
            ):
                raise Denied("Non-default desktop; manual handoff")
        finally:
            self.user.CloseDesktop(desktop)
        return {"foreground": int(self.user.GetForegroundWindow() or 0), "last_input": info.dwTime}

    def windows(self, registration):
        records = []
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def visit(hwnd, _):
            if not self.user.IsWindowVisible(hwnd):
                return True
            cls = C.create_unicode_buffer(256)
            self.user.GetClassNameW(hwnd, cls, len(cls))
            if cls.value != "Notepad":
                return True
            pid = W.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            try:
                proc = self.process(pid.value)
                if proc["owner_sid"] != self.owner_sid:
                    return True
                if proc["os_session"] != self.session or os.path.normcase(
                    proc["exe"]
                ) != os.path.normcase(registration["executable"]):
                    return True
                if proc["package"] != registration["package_full_name"]:
                    return True
                record = {
                    **proc,
                    "hwnd": int(hwnd),
                    "class_name": cls.value,
                    "exe_sha256": file_hash(proc["exe"]),
                }
                if record["exe_sha256"] != registration["executable_sha256"]:
                    return True
                records.append(record)
            except (OSError, Denied):
                pass
            return len(records) < 32

        callback = callback_type(visit)
        self.user.EnumWindows.argtypes = [callback_type, W.LPARAM]
        if not self.user.EnumWindows(callback, 0):
            raise Denied("Window inventory incomplete")
        return records

    def metadata(self, record):
        import comtypes.client

        if self.uia is None:
            module = comtypes.client.GetModule(
                str(Path(os.environ["WINDIR"]) / "System32/UIAutomationCore.dll")
            )
            self.uia = comtypes.client.CreateObject(
                module.CUIAutomation, interface=module.IUIAutomation
            )
            self.module = module
        module = self.module
        root = self.uia.ElementFromHandle(record["hwnd"])
        runtime = tuple(root.GetRuntimeId())
        condition = self.uia.CreatePropertyCondition(30003, 50019)  # ControlType TabItem
        tabs = root.FindAll(4, condition)  # descendants, never Name/Value/Text
        if tabs.Length > 64:
            raise Denied("Tab inventory exceeded bound")
        tab_ids = [list(tabs.GetElement(index).GetRuntimeId()) for index in range(tabs.Length)]
        # Packaged Notepad 11.2607 exposes its native RichEdit as Document,
        # not Edit. Select only the measured native editor classes, never labels.
        condition = self.uia.CreateOrCondition(
            self.uia.CreatePropertyCondition(30003, 50004),
            self.uia.CreatePropertyCondition(30003, 50030),
        )
        edits = root.FindAll(4, condition)
        empty = None
        modified = None
        if edits.Length == 1:
            try:
                pattern = (
                    edits.GetElement(0)
                    .GetCurrentPattern(10014)
                    .QueryInterface(module.IUIAutomationTextPattern)
                )
                document = pattern.DocumentRange
                empty = document.CompareEndpoints(0, document, 1) == 0
                edit_hwnd = edits.GetElement(0).CurrentNativeWindowHandle
                edit_class = C.create_unicode_buffer(256)
                self.user.GetClassNameW(edit_hwnd, edit_class, len(edit_class))
                if edit_hwnd and edit_class.value in {
                    "Edit",
                    "RichEditD2DPT",
                    "RICHEDIT50W",
                    "RichEdit20W",
                }:
                    answer = C.c_size_t()
                    self.user.SendMessageTimeoutW.argtypes = [
                        W.HWND,
                        W.UINT,
                        W.WPARAM,
                        W.LPARAM,
                        W.UINT,
                        W.UINT,
                        C.POINTER(C.c_size_t),
                    ]
                    self.user.SendMessageTimeoutW.restype = W.LPARAM
                    if self.user.SendMessageTimeoutW(
                        edit_hwnd, 0x00B8, 0, 0, 2, 500, C.byref(answer)
                    ):
                        modified = bool(answer.value)
            except Exception:
                empty = None
        return {
            **record,
            "runtime_id": list(runtime),
            "tab_ids": tab_ids,
            "empty": empty,
            "modified": modified,
            "enabled": bool(self.user.IsWindowEnabled(record["hwnd"])),
            "owned_dialog": self.has_dialog(record["pid"], record["hwnd"]),
        }

    def has_dialog(self, pid, target):
        found = []
        cb_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def visit(hwnd, _):
            if (
                hwnd != target
                and self.user.IsWindowVisible(hwnd)
                and self.user.GetWindow(hwnd, 4) == target
            ):
                owner = W.DWORD()
                self.user.GetWindowThreadProcessId(hwnd, C.byref(owner))
                if owner.value == pid:
                    found.append(True)
            return True

        callback = cb_type(visit)
        self.user.EnumWindows.argtypes = [cb_type, W.LPARAM]
        self.user.EnumWindows(callback, 0)
        return bool(found)


def window_identity(record):
    keys = (
        "hwnd",
        "pid",
        "created",
        "os_session",
        "exe_sha256",
        "package",
        "class_name",
        "runtime_id",
    )
    return {key: record[key] for key in keys}


def clean(record):
    # Packaged/tabbed app: never infer the state of hidden tabs from the active editor.
    return (
        record["empty"] is True
        and record.get("modified") is False
        and len(record["tab_ids"]) == 1
        and record["enabled"]
        and not record["owned_dialog"]
    )
