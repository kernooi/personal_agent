"""Native, cache-only signed launcher identity and Shell namespace activation.

No paths or arguments come from the model. These functions run in the bounded
worker, against identities rediscovered from Windows AppsFolder.
"""

import ctypes as C
import hashlib
from ctypes import wintypes as W


class ProcessEntry(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("usage", W.DWORD),
        ("pid", W.DWORD),
        ("heap", C.c_size_t),
        ("module", W.DWORD),
        ("threads", W.DWORD),
        ("parent", W.DWORD),
        ("priority", W.LONG),
        ("flags", W.DWORD),
        ("name", W.WCHAR * 260),
    ]


def process_parents():
    """Bounded Tool Help snapshot; names are not used as application identity."""
    from jarvis.domain import Denied

    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = W.HANDLE
    kernel.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [W.HANDLE, C.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == C.c_void_p(-1).value:
        raise Denied("Process ancestry unavailable")
    try:
        entry = ProcessEntry()
        entry.size = C.sizeof(entry)
        parents = {}
        available = kernel.Process32FirstW(snapshot, C.byref(entry))
        while available:
            if len(parents) >= 4096 or entry.pid in parents:
                raise Denied("Process ancestry snapshot limit")
            parents[entry.pid] = entry.parent
            available = kernel.Process32NextW(snapshot, C.byref(entry))
        if C.get_last_error() != 18:  # ERROR_NO_MORE_FILES, not a partial snapshot.
            raise Denied("Process ancestry snapshot incomplete")
        return parents
    finally:
        kernel.CloseHandle(snapshot)


class TrustFile(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("path", W.LPCWSTR),
        ("handle", W.HANDLE),
        ("subject", C.c_void_p),
    ]


class TrustData(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("policy", C.c_void_p),
        ("sip", C.c_void_p),
        ("ui", W.DWORD),
        ("revocation", W.DWORD),
        ("choice", W.DWORD),
        ("file", C.POINTER(TrustFile)),
        ("state_action", W.DWORD),
        ("state", W.HANDLE),
        ("url", W.LPWSTR),
        ("flags", W.DWORD),
        ("context", W.DWORD),
        ("settings", C.c_void_p),
    ]


class CertContext(C.Structure):
    _fields_ = [("encoding", W.DWORD), ("encoded", C.c_void_p), ("length", W.DWORD)]


class ProviderCert(C.Structure):
    # Only the documented prefix is accessed; the provider owns the allocation.
    _fields_ = [("size", W.DWORD), ("cert", C.POINTER(CertContext))]


def signer(path):
    """SHA-256 of the leaf signing certificate only after Authenticode succeeds.

    Cache-only retrieval prevents implicit certificate network requests. This is
    local chain/signature validation, not a claim of fresh online revocation.
    """
    from comtypes import GUID

    trust = C.WinDLL("wintrust", use_last_error=True)
    action = GUID("{00AAC56B-CD44-11d0-8CC2-00C04FC295EE}")
    file = TrustFile(C.sizeof(TrustFile), str(path), None, None)
    data = TrustData()
    data.size, data.ui, data.choice = C.sizeof(TrustData), 2, 1
    data.file, data.state_action, data.flags = C.pointer(file), 1, 0x1000 | 0x10
    trust.WinVerifyTrust.argtypes = [W.HWND, C.POINTER(GUID), C.POINTER(TrustData)]
    trust.WinVerifyTrust.restype = W.LONG
    trust.WTHelperProvDataFromStateData.argtypes = [W.HANDLE]
    trust.WTHelperProvDataFromStateData.restype = C.c_void_p
    trust.WTHelperGetProvSignerFromChain.argtypes = [C.c_void_p, W.DWORD, W.BOOL, W.DWORD]
    trust.WTHelperGetProvSignerFromChain.restype = C.c_void_p
    trust.WTHelperGetProvCertFromChain.argtypes = [C.c_void_p, W.DWORD]
    trust.WTHelperGetProvCertFromChain.restype = C.POINTER(ProviderCert)
    try:
        if trust.WinVerifyTrust(None, C.byref(action), C.byref(data)) != 0:
            return ""
        provider = trust.WTHelperProvDataFromStateData(data.state)
        if not provider:
            return ""
        signing = trust.WTHelperGetProvSignerFromChain(provider, 0, False, 0)
        if not signing:
            return ""
        result = trust.WTHelperGetProvCertFromChain(signing, 0)
        if not result or not result.contents.cert:
            return ""
        cert = result.contents.cert.contents
        if not cert.encoded or not 0 < cert.length <= 65536:
            return ""
        return hashlib.sha256(C.string_at(cert.encoded, cert.length)).hexdigest()
    finally:
        data.state_action = 2
        trust.WinVerifyTrust(None, C.byref(action), C.byref(data))


class ShellExecuteInfo(C.Structure):
    _fields_ = [
        ("size", W.DWORD),
        ("mask", W.ULONG),
        ("hwnd", W.HWND),
        ("verb", W.LPCWSTR),
        ("file", W.LPCWSTR),
        ("parameters", W.LPCWSTR),
        ("directory", W.LPCWSTR),
        ("show", C.c_int),
        ("instance", W.HINSTANCE),
        ("id_list", C.c_void_p),
        ("class_name", W.LPCWSTR),
        ("class_key", W.HKEY),
        ("hotkey", W.DWORD),
        ("icon", W.HANDLE),
        ("process", W.HANDLE),
    ]


def activate_identity(launch_id):
    """Invoke only the default open verb of one trusted AppsFolder PIDL."""
    from jarvis.domain import Denied

    shell, ole = C.WinDLL("shell32", use_last_error=True), C.WinDLL("ole32")
    pidl = C.c_void_p()
    shell.SHParseDisplayName.argtypes = [
        W.LPCWSTR,
        C.c_void_p,
        C.POINTER(C.c_void_p),
        W.ULONG,
        C.c_void_p,
    ]
    shell.SHParseDisplayName.restype = W.LONG
    shell.ShellExecuteExW.argtypes = [C.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = W.BOOL
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    if shell.SHParseDisplayName("shell:AppsFolder\\" + launch_id, None, C.byref(pidl), 0, None) < 0:
        raise Denied("Installed launch identity unavailable")
    try:
        info = ShellExecuteInfo()
        info.size, info.mask, info.verb, info.id_list, info.show = (
            C.sizeof(info),
            0x0C | 0x100 | 0x400,
            "open",
            pidl.value,
            1,
        )
        if not shell.ShellExecuteExW(C.byref(info)):
            raise Denied("Installed application activation failed")
    finally:
        ole.CoTaskMemFree(pidl)
