"""Trusted Windows AppsFolder discovery and one gated native window operation."""

import ctypes as C
import json
import os
import re
import sys
import time
from ctypes import wintypes as W
from pathlib import Path
from xml.etree import ElementTree

from jarvis.application_data import Application, ApplicationsConfig, app_id
from jarvis.application_tools import identity
from jarvis.domain import Denied
from jarvis.models import reject_constant, unique_object
from jarvis.win_native import Native, clean, file_hash


def local_executable(path):
    if not isinstance(path, str) or not re.match(r"^[a-zA-Z]:\\", path) or path.startswith("\\\\"):
        raise Denied("Only local installed executables")
    target = Path(path).resolve(strict=True)
    if target.suffix.casefold() != ".exe" or not target.is_file():
        raise Denied("Not an executable application")
    if re.search(
        r"(?i)^(?:unins.*|uninstall.*|setup.*|install.*|msiexec|regedit|regedt32)$", target.stem
    ):
        raise Denied("Installation and security tools are outside application control")
    return str(target)


def package_executable(install, launch_id):
    root = Path(install).resolve(strict=True)
    with (root / "AppxManifest.xml").open("rb") as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise Denied("Package manifest limit")
    manifest = ElementTree.fromstring(raw)
    app_name = launch_id.split("!", 1)[1]
    apps = [
        e
        for e in manifest.iter()
        if e.tag.rsplit("}", 1)[-1] == "Application" and e.get("Id") == app_name
    ]
    if len(apps) != 1 or not apps[0].get("Executable"):
        raise Denied("Package launch identity unavailable")
    relative = apps[0].get("Executable")
    if relative.startswith(("\\", "/")) or ":" in relative:
        raise Denied("Package executable path invalid")
    exe = local_executable(str(root / relative))
    if os.path.commonpath([str(root), exe]).casefold() != str(root).casefold():
        raise Denied("Package executable escaped installation")
    return exe


def catalog(config):
    import comtypes.client

    folder = comtypes.client.CreateObject("Shell.Application", dynamic=True).NameSpace(
        "shell:AppsFolder"
    )
    items = folder.Items()
    if items.Count > config.maximum_apps:
        raise Denied("Application catalog exceeds configured bound")
    records = {}
    unsupported = 0
    for index in range(items.Count):
        item = items.Item(index)
        try:
            name = item.Name
            launch = item.ExtendedProperty("System.AppUserModel.ID") or item.Path
            if (
                not isinstance(launch, str)
                or not launch
                or len(launch) > 512
                or not isinstance(name, str)
                or any(ord(c) < 32 for c in name)
            ):
                raise Denied("Invalid application metadata")
            package = item.ExtendedProperty("System.AppUserModel.PackageFullName") or ""
            install = item.ExtendedProperty("System.AppUserModel.PackageInstallPath")
            if package and install and re.fullmatch(r"[A-Za-z0-9._-]+![A-Za-z0-9._-]+", launch):
                kind = "package"
                exe = package_executable(install, launch)
            else:
                kind = "exe"
                exe = local_executable(item.ExtendedProperty("System.Link.TargetParsingPath"))
            app = Application(
                app_id=app_id(launch),
                name=name,
                launch_id=launch,
                kind=kind,
                executable=exe,
                package=package,
            )
            if app.app_id in records and records[app.app_id] != app:
                raise Denied("Duplicate catalog identity")
            records[app.app_id] = app
        except (ValueError, OSError, TypeError, AttributeError, ElementTree.ParseError):
            unsupported += 1
    return list(records.values()), unsupported


class ApplicationNative(Native):
    def runtime_matches(self, process, apps):
        """Resolve OS package identity or a signed versioned runtime, never a title."""
        cache = getattr(self, "_identity_cache", None)
        if cache is None:
            self._identity_cache = cache = {}
        candidates = []
        for app in apps:
            if app.package != process["package"]:
                continue
            if os.path.normcase(app.executable) == os.path.normcase(process["exe"]):
                candidates.append(app)
                continue
            key = (app.app_id, process["exe"], process["pid"], process["created"])
            if key not in cache:
                cache[key] = self.runtime_association(process, app)
            if cache[key]:
                candidates.append(app)
        return candidates

    def runtime_association(self, process, app):
        from jarvis.application_identity import signer

        launch, runtime = (
            Path(app.executable).resolve(strict=True),
            Path(process["exe"]).resolve(strict=True),
        )
        root = launch.parent
        if root not in runtime.parents:
            return None
        proof = {
            "launch_id": app.launch_id,
            "launch_sha256": file_hash(launch),
            "runtime_sha256": file_hash(runtime),
        }
        if app.kind == "package":
            # OS application identity distinguishes multiple apps in one package.
            handle = self.kernel.OpenProcess(0x1000, False, process["pid"])
            if not handle:
                return None
            try:
                length = W.UINT(1024)
                value = C.create_unicode_buffer(length.value)
                self.kernel.GetApplicationUserModelId.argtypes = [
                    W.HANDLE,
                    C.POINTER(W.UINT),
                    W.LPWSTR,
                ]
                if (
                    self.kernel.GetApplicationUserModelId(handle, C.byref(length), value)
                    or value.value != app.launch_id
                ):
                    return None
            finally:
                self.kernel.CloseHandle(handle)
            return {**proof, "method": "os-application-id", "package": app.package}
        # A directory prefix alone or a matching label never establishes identity.
        if root.name.casefold() != launch.stem.casefold():
            return None
        publisher = signer(launch)
        if not publisher or signer(runtime) != publisher:
            return None
        if runtime.name.casefold() == launch.name.casefold() and runtime.parent != root:
            return {**proof, "method": "signed-versioned-runtime", "publisher_sha256": publisher}
        ancestry = self.launcher_ancestry(process, launch, publisher)
        if not ancestry:
            return None
        return {
            **proof,
            "method": "signed-descendant-runtime",
            "publisher_sha256": publisher,
            "ancestry": ancestry,
        }

    def launcher_ancestry(self, process, launch, publisher):
        """Bind a differently named UI helper to the live registered launcher.

        Each process must share the user's session, signature and dedicated
        installation. Creation times and repeated native reads reject PID reuse.
        Missing/exited parents never justify a title or directory-only fallback.
        """
        from jarvis.application_identity import process_parents, signer

        if not all(k in process for k in ("pid", "created", "owner_sid", "os_session")):
            return None
        try:
            parents = process_parents()
            chain, seen = [], set()
            current = process
            for _ in range(8):
                pid = current["pid"]
                if pid in seen or self.process(pid) != current:
                    return None
                seen.add(pid)
                path = Path(current["exe"]).resolve(strict=True)
                if (
                    current["owner_sid"] != process["owner_sid"]
                    or current["os_session"] != process["os_session"]
                    or current["package"]
                    or launch.parent not in path.parents
                    or signer(path) != publisher
                ):
                    return None
                chain.append({**current, "exe_sha256": file_hash(path)})
                if path == launch and len(chain) > 1:
                    # Revalidate the snapshot and process identities after hashing.
                    latest = process_parents()
                    if any(
                        latest.get(a["pid"]) != b["pid"]
                        for a, b in zip(chain, chain[1:], strict=False)
                    ):
                        return None
                    if any(
                        self.process(p["pid"]) != {k: v for k, v in p.items() if k != "exe_sha256"}
                        for p in chain
                    ):
                        return None
                    return chain
                parent = parents.get(pid)
                if not parent or parent in seen:
                    return None
                preceding = self.process(parent)
                if preceding["created"] > current["created"]:
                    return None
                current = preceding
        except (Denied, OSError, KeyError, ValueError):
            return None
        return None

    def associated_process(self, hwnd, apps):
        """Bind a top-level window to its app, including a Windows-owned host frame."""
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        proc = self.process(pid.value)
        if proc["owner_sid"] != self.owner_sid or proc["os_session"] != self.session:
            raise Denied("Window belongs to another user or session")

        def matches(process):
            return self.runtime_matches(process, apps)

        candidates = matches(proc)
        if len(candidates) == 1:
            if os.path.normcase(candidates[0].executable) != os.path.normcase(proc["exe"]):
                proc["association"] = self.runtime_association(proc, candidates[0])
                if not proc["association"]:
                    raise Denied("Application runtime association changed")
            return proc, candidates[0], None, 0
        cls = C.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd, cls, len(cls))
        system = C.create_unicode_buffer(32768)
        self.kernel.GetSystemDirectoryW.argtypes = [W.LPWSTR, W.UINT]
        length = self.kernel.GetSystemDirectoryW(system, len(system))
        if (
            cls.value != "ApplicationFrameWindow"
            or not 0 < length < len(system)
            or os.path.normcase(proc["exe"])
            != os.path.normcase(str(Path(system.value) / "ApplicationFrameHost.exe"))
        ):
            raise Denied("Application process association unavailable")
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        self.user.GetAncestor.argtypes = [W.HWND, W.UINT]
        self.user.GetAncestor.restype = W.HWND
        children, count, invalid_content = [], 0, False

        def visit(child, unused):
            nonlocal count, invalid_content
            count += 1
            if count > 256:
                return False
            child_pid = W.DWORD()
            self.user.GetWindowThreadProcessId(child, C.byref(child_pid))
            if (
                child_pid.value == proc["pid"]
                or not self.user.IsWindowVisible(child)
                or self.user.GetAncestor(child, 2) != hwnd
            ):
                return True
            try:
                content = self.process(child_pid.value)
                supported = matches(content)
                if (
                    len(supported) == 1
                    and supported[0].kind == "package"
                    and content["owner_sid"] == self.owner_sid
                    and content["os_session"] == self.session
                ):
                    children.append((content, supported[0], int(child)))
                else:
                    invalid_content = True
            except (OSError, Denied):
                invalid_content = True
            return True

        callback = callback_type(visit)
        self.user.EnumChildWindows.argtypes = [W.HWND, callback_type, W.LPARAM]
        self.user.EnumChildWindows(hwnd, callback, 0)
        if count > 256 or invalid_content or len(children) != 1:
            raise Denied("Hosted application content is ambiguous or unavailable")
        content, app, content_hwnd = children[0]
        if os.path.normcase(app.executable) != os.path.normcase(content["exe"]):
            content["association"] = self.runtime_association(content, app)
        return content, app, {**proc, "exe_sha256": file_hash(proc["exe"])}, content_hwnd

    def minimized_frame(self, app, expected):
        """Windows may detach package content while its remembered frame is minimized."""
        hwnd, child = expected["hwnd"], expected["content_hwnd"]
        if not expected["frame_host"] or not child or not self.user.IsIconic(hwnd):
            raise Denied("No remembered minimized frame")
        host = expected["frame_host"]
        pid, child_pid = W.DWORD(), W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        self.user.GetWindowThreadProcessId(child, C.byref(child_pid))
        actual_host, content = self.process(pid.value), self.process(child_pid.value)
        if actual_host != {k: v for k, v in host.items() if k != "exe_sha256"}:
            raise Denied("Minimized frame host changed")
        self.user.GetAncestor.argtypes = [W.HWND, W.UINT]
        self.user.GetAncestor.restype = W.HWND
        if (
            not self.user.IsWindow(child)
            or self.user.GetAncestor(child, 2) not in {hwnd, child}
            or content["owner_sid"] != self.owner_sid
            or content["os_session"] != self.session
            or self.runtime_matches(content, [app]) != [app]
        ):
            raise Denied("Minimized package content changed")
        cls = C.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd, cls, len(cls))
        actual = {
            **content,
            "app_id": app.app_id,
            "hwnd": hwnd,
            "exe_sha256": file_hash(content["exe"]),
            "class_name": cls.value,
            "frame_host": {**actual_host, "exe_sha256": file_hash(actual_host["exe"])},
            "content_hwnd": child,
        }
        if os.path.normcase(app.executable) != os.path.normcase(content["exe"]):
            actual["association"] = self.runtime_association(content, app)
        if identity(actual) != identity(expected):
            raise Denied("Remembered package or frame identity changed")
        return actual

    def inventory(self, apps, config, known_frames=()):
        records = []
        hashes = {}
        callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        if len(known_frames) > config.maximum_windows:
            raise Denied("Remembered frame limit")
        for expected in known_frames:
            matches = [a for a in apps if a.app_id == expected["app_id"]]
            if len(matches) == 1:
                try:
                    records.append(self.minimized_frame(matches[0], expected))
                except (OSError, Denied):
                    pass
        bound_handles = {r["hwnd"] for r in records} | {r["content_hwnd"] for r in records}

        def visit(hwnd, _):
            if hwnd in bound_handles:
                return True
            if not self.user.IsWindowVisible(hwnd) or self.user.GetWindow(hwnd, 4):
                return True
            try:
                proc, app, host, content_hwnd = self.associated_process(hwnd, apps)
                exe = proc["exe"]
                if exe not in hashes:
                    hashes[exe] = file_hash(exe)
                cls = C.create_unicode_buffer(256)
                self.user.GetClassNameW(hwnd, cls, len(cls))
                records.append(
                    {
                        **proc,
                        "app_id": app.app_id,
                        "hwnd": int(hwnd),
                        "exe_sha256": hashes[exe],
                        "class_name": cls.value,
                        "frame_host": host,
                        "content_hwnd": content_hwnd,
                    }
                )
            except (OSError, Denied):
                pass
            return len(records) <= config.maximum_windows

        callback = callback_type(visit)
        self.user.EnumWindows.argtypes = [callback_type, W.LPARAM]
        if not self.user.EnumWindows(callback, 0) or len(records) > config.maximum_windows:
            raise Denied("Application window inventory incomplete")
        return records

    def inspect_app(self, record):
        enabled = bool(self.user.IsWindowEnabled(record["hwnd"]))
        dialog = self.has_dialog(record["pid"], record["hwnd"])
        if record["frame_host"]:
            dialog = dialog or self.has_dialog(record["frame_host"]["pid"], record["hwnd"])
        # Preserve the existing independently verified Notepad close boundary.
        protected = (
            record["package"].startswith("Microsoft.WindowsNotepad_")
            or record["class_name"] == "Notepad"
        )
        row = {
            **record,
            "enabled": enabled,
            "owned_dialog": dialog,
            "minimized": bool(self.user.IsIconic(record["hwnd"])),
            "protected": protected,
            "close_safe": None,
        }
        if protected:
            detail = self.metadata(record)
            row["close_safe"] = clean(detail)
        return row


def fresh_app(config, expected):
    expected = Application.model_validate(expected, strict=True)
    apps, _ = catalog(config)
    matches = [a for a in apps if a.app_id == expected.app_id]
    if len(matches) != 1 or matches[0] != expected:
        raise Denied("Application catalog changed")
    return matches[0]


def selected(native, app, expected, config):
    frames = [expected] if expected["frame_host"] else []
    matches = [r for r in native.inventory([app], config, frames) if r["hwnd"] == expected["hwnd"]]
    if len(matches) != 1 or identity(matches[0]) != identity(expected):
        raise Denied("Application window identity changed")
    return native.inspect_app(matches[0])


def activate(app):
    if app.kind == "exe":
        from jarvis.application_identity import activate_identity

        activate_identity(app.launch_id)
        return
    import comtypes
    import comtypes.client

    class ActivationManager(comtypes.IUnknown):
        _iid_ = comtypes.GUID("{2e941141-7f97-4756-ba1d-9decde894a3d}")
        _methods_ = [
            comtypes.COMMETHOD(
                [],
                comtypes.HRESULT,
                "ActivateApplication",
                (["in"], W.LPCWSTR, "appUserModelId"),
                (["in"], W.LPCWSTR, "arguments"),
                (["in"], W.DWORD, "options"),
                (["out"], C.POINTER(W.DWORD), "processId"),
            )
        ]

    manager = comtypes.client.CreateObject(
        "{45BA127D-10A8-46EA-8AB7-56EA9078943C}", interface=ActivationManager
    )
    manager.ActivateApplication(app.launch_id, None, 2)


def read():
    raw = sys.stdin.buffer.readline(1048577)
    if not raw or len(raw) > 1048576:
        raise Denied("Application envelope limit")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def send(request, stage, data):
    raw = json.dumps(
        {"version": 1, "request_id": request["request_id"], "stage": stage, "data": data}
    )
    if len(raw.encode()) > 1048575:
        raise Denied("Application result limit")
    print(raw, flush=True)


def run(request):
    if (
        set(request) != {"version", "request_id", "deadline", "operation", "config", "payload"}
        or request["version"] != 1
        or time.time() >= request["deadline"]
    ):
        raise Denied("Invalid application request")
    config = ApplicationsConfig.model_validate(request["config"], strict=True)
    if not config.enabled or os.name != "nt":
        raise Denied("Windows application platform not enabled")
    operation = request["operation"]
    payload = request["payload"]
    concurrent = payload.get("allow_concurrent_input", False)
    if type(concurrent) is not bool:
        raise Denied("Invalid targeted window policy")
    if operation == "catalog":
        apps, unsupported = catalog(config)
        send(
            request,
            "result",
            {"apps": [a.model_dump() for a in apps], "unsupported_count": unsupported},
        )
        return
    native = ApplicationNative()
    if operation == "activity":
        send(request, "result", native.activity())
        return
    if operation == "absence":
        # A missing catalog match is insufficient proof of a closed window:
        # process metadata may temporarily be unreadable or change after delivery.
        hwnd = payload["hwnd"]
        present = bool(native.user.IsWindow(hwnd))
        state = {"present": present, "visible": bool(native.user.IsWindowVisible(hwnd))}
        if present and not state["visible"]:
            app = Application.model_validate(payload["app"], strict=True)
            proc, associated, host, child = native.associated_process(hwnd, [app])
            cls = C.create_unicode_buffer(256)
            native.user.GetClassNameW(hwnd, cls, len(cls))
            actual = {
                **proc,
                "app_id": associated.app_id,
                "hwnd": hwnd,
                "exe_sha256": file_hash(proc["exe"]),
                "class_name": cls.value,
                "frame_host": host,
                "content_hwnd": child,
            }
            if identity(actual) != identity(payload["window"]):
                raise Denied("Hidden window identity changed")
            state["identity"] = identity(actual)
        send(request, "result", state)
        return
    if operation == "inventory":
        apps = [Application.model_validate(a, strict=True) for a in payload["apps"]]
        send(
            request,
            "result",
            [
                native.inspect_app(r)
                for r in native.inventory(apps, config, payload.get("known_frames", []))
            ],
        )
        return
    app = fresh_app(config, payload["app"])
    if operation == "validate_app":
        send(request, "result", {"exe_sha256": file_hash(app.executable)})
        return
    expected = payload.get("window")
    if operation == "inspect":
        send(request, "result", selected(native, app, expected, config))
        return
    if operation not in {"open", "focus", "minimize", "close"} or (
        operation != "open" and not expected
    ):
        raise Denied("Unknown application effect")

    def preflight():
        fresh_app(config, payload["app"])
        if file_hash(app.executable) != payload["exe_sha256"]:
            raise Denied("Application binary changed")
        current = selected(native, app, expected, config) if expected else None
        if current and (not current["enabled"] or current["owned_dialog"]):
            raise Denied("Application has a dialog")
        if operation == "close" and (
            not payload["close_reviewed"]
            or time.time() >= payload["review_expires_at"]
            or current["close_safe"] is False
            or (current["protected"] and current["close_safe"] is not True)
        ):
            raise Denied("Unsafe close")
        activity = native.activity()  # Availability of this user's default desktop is mandatory.
        if time.time() >= request["deadline"] or (
            not concurrent and activity != payload["activity"]
        ):
            raise Denied("User takeover before application effect")

    preflight()
    send(request, "ready", {})
    if read() != {"version": 1, "request_id": request["request_id"], "commit": True}:
        raise Denied("Invalid application commit")
    try:
        preflight()
    except Denied:
        send(request, "rejected", {})
        return
    hwnd = expected["hwnd"] if expected else None
    if operation == "open":
        if not expected:
            activate(app)
    elif operation == "focus":
        if native.user.IsIconic(hwnd):
            if not native.user.ShowWindowAsync(hwnd, 9):
                raise Denied("Restore delivery uncertain")
            wait_restored(
                native,
                app,
                expected,
                config,
                request["deadline"],
                payload["activity"],
                concurrent=concurrent,
            )
            if native.user.IsIconic(hwnd) or (
                not concurrent
                and native.activity()["last_input"] != payload["activity"]["last_input"]
            ):
                raise Denied("Restore or takeover uncertain")
        native.user.SetForegroundWindow(hwnd)
    elif operation == "minimize":
        if not native.user.IsIconic(hwnd) and not native.user.ShowWindowAsync(hwnd, 6):
            raise Denied("Minimize delivery uncertain")
    elif not native.user.PostMessageW(hwnd, 0x0010, 0, 0):
        raise Denied("Close delivery uncertain")
    send(request, "result", {})


def wait_restored(native, app, expected, config, deadline, activity, *, concurrent=False):
    """Wait only for observation after one restore; never resend the effect."""
    until = min(time.time() + 4, deadline)
    while time.time() < until:
        current = native.activity()
        if not concurrent and current["last_input"] != activity["last_input"]:
            raise Denied("User takeover during restore")
        if not native.user.IsIconic(expected["hwnd"]):
            try:
                selected(native, app, expected, config)
                return
            except Denied:
                # Windows may still be reattaching the same package child.
                pass
        time.sleep(0.05)
    raise Denied("Restore identity did not settle")


def main():
    # Shell discovery/activation COM uses STA in its isolated worker.
    sys.coinit_flags = 2
    request = read()
    try:
        run(request)
    except Exception:
        send(request, "error", {})


if __name__ == "__main__":
    main()
