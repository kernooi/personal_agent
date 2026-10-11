"""Native identity and supervisor tests; no desktop or Ollama effects."""

import io
import json
import os
import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest

from jarvis.domain import AdmissionRejected, Denied, Handoff
from jarvis.notepad import DesktopLease, Registration, WorkerTransport
from jarvis.notepad_fake import FakeNotepadTransport
from jarvis.win_worker import selected


@pytest.mark.parametrize(
    "key", ["pid", "created", "os_session", "exe_sha256", "package", "class_name", "runtime_id"]
)
def test_native_selected_rejects_reused_or_changed_identity(key):
    expected = FakeNotepadTransport().add()
    changed = deepcopy(expected)
    changed[key] = "changed"
    native = SimpleNamespace(windows=lambda _: [changed], metadata=lambda row: row)
    with pytest.raises(Denied, match="identity changed"):
        selected(native, {}, expected)


def test_title_decoy_outside_validated_inventory_is_rejected():
    expected = FakeNotepadTransport().add()
    native = SimpleNamespace(windows=lambda _: [], metadata=lambda _: pytest.fail("No target"))
    with pytest.raises(Denied, match="missing"):
        selected(native, {}, expected)


def test_desktop_lease_contention_and_release(tmp_path):
    pytest.importorskip("msvcrt")
    path = tmp_path / "lease.lock"
    with DesktopLease(path):
        with pytest.raises(AdmissionRejected, match="busy"):
            with DesktopLease(path):
                pytest.fail("Two tasks cannot own the same lease")
    with DesktopLease(path):
        pass


class Pipe(io.BytesIO):
    def __init__(self, process):
        super().__init__()
        self.process = process

    def flush(self):
        self.process.written.set()


class Process:
    def __init__(self, stages):
        self.stages = iter(stages)
        self.written = threading.Event()
        self.stdin = Pipe(self)
        self.stdout = self
        self.terminated = False

    def readline(self, bound):
        assert bound == 65537
        self.written.wait(0.5)
        stage = next(self.stages, None)
        if stage is None:
            return b""
        request = json.loads(self.stdin.getvalue().splitlines()[0])
        return (
            json.dumps(
                {
                    "version": 1,
                    "request_id": request["request_id"],
                    "stage": stage,
                    "data": {},
                }
            )
            + "\n"
        ).encode()

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        assert timeout == 2
        return 0

    def close(self):
        pass


@pytest.mark.parametrize(
    "stages,error",
    [
        (["result"], AdmissionRejected),
        (["error"], AdmissionRejected),
        ([], AdmissionRejected),
        (["ready", "error"], RuntimeError),
    ],
)
def test_supervisor_admission_and_unknown_timeout(monkeypatch, stages, error):
    import jarvis.notepad as module

    worker = Process(stages)
    calls = []

    def launch(argv, **options):
        assert argv[1:] == ["-m", "jarvis.win_worker"]
        assert options["shell"] is False
        calls.append(argv)
        return worker

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    registration = SimpleNamespace(model_dump=lambda: {})
    transport = WorkerTransport(registration, threading.Event(), timeout=0.03)
    with pytest.raises(error):
        transport.call("close", gate=lambda: None)
    assert calls and worker.terminated


def test_hotkey_conflict_fails_closed_without_unregistering_other_owner(monkeypatch):
    import jarvis.win_stop as module

    class Function:
        def __init__(self, value):
            self.value = value

        def __call__(self, *args):
            return self.value

    user = SimpleNamespace(
        RegisterHotKey=Function(0), UnregisterHotKey=Function(0), PeekMessageW=Function(0)
    )
    monkeypatch.setattr(module.C, "WinDLL", lambda *args, **kwargs: user)
    stop = threading.Event()
    with pytest.raises(Handoff, match="conflicts"):
        with module.StopHotkey(stop):
            pytest.fail("Conflicting global stop must prevent real startup")
    assert not stop.is_set()


@pytest.mark.skipif(os.name != "nt", reason="Windows registration path rules")
@pytest.mark.parametrize("change", ["launcher_path", "executable_path", "binary_hash"])
def test_registration_tampering_fails_closed(tmp_path, monkeypatch, change):
    import jarvis.win_native as native

    windir = tmp_path / "Windows"
    programs = tmp_path / "ProgramFiles"
    monkeypatch.setenv("WINDIR", str(windir))
    monkeypatch.setenv("ProgramFiles", str(programs))
    package = "Microsoft.WindowsNotepad_11.2607.14.0_x64__8wekyb3d8bbwe"
    data = {
        "version": "notepad-registration-v1",
        "app_id": "notepad",
        "launcher": str(windir / "System32/notepad.exe"),
        "launcher_sha256": "a" * 64,
        "executable": str(programs / "WindowsApps" / package / "Notepad/Notepad.exe"),
        "executable_sha256": "a" * 64,
        "package_full_name": package,
        "notepad_version": "11.2607.14.0",
        "microsoft_signature_verified": True,
    }
    monkeypatch.setattr(
        native, "file_hash", lambda _: "b" * 64 if change == "binary_hash" else "a" * 64
    )
    if change in {"launcher_path", "executable_path"}:
        data["launcher" if change == "launcher_path" else "executable"] = str(tmp_path / "evil.exe")
    with pytest.raises(Handoff):
        Registration.model_validate(data, strict=True).revalidate()


@pytest.mark.parametrize("operation", ["minimize", "focus"])
def test_native_minimize_and_restore_use_selected_handle_after_commit(monkeypatch, operation):
    import time

    import jarvis.win_worker as worker

    record = FakeNotepadTransport().add()
    iconic = operation == "focus"
    calls = []

    def show(hwnd, command):
        nonlocal iconic
        calls.append(("show", hwnd, command))
        iconic = command == 6
        return True

    native = SimpleNamespace(
        windows=lambda _: [record],
        metadata=lambda row: row,
        activity=lambda: {"foreground": 0, "last_input": 1},
        user=SimpleNamespace(
            IsIconic=lambda _: iconic,
            ShowWindowAsync=show,
            SetForegroundWindow=lambda hwnd: calls.append(("focus", hwnd)),
        ),
    )
    monkeypatch.setattr(worker, "Native", lambda: native)
    monkeypatch.setattr(Registration, "revalidate", lambda self: None)
    registration = dict(
        version="notepad-registration-v1",
        app_id="notepad",
        launcher="C:\\Windows\\System32\\notepad.exe",
        launcher_sha256="a" * 64,
        executable="C:\\Program Files\\WindowsApps\\Notepad.exe",
        executable_sha256="a" * 64,
        package_full_name="Microsoft.WindowsNotepad_11.2607.14.0_x64__8wekyb3d8bbwe",
        notepad_version="11.0",
        microsoft_signature_verified=True,
    )
    request = dict(
        version=1,
        request_id="test",
        deadline=time.time() + 10,
        operation=operation,
        registration=registration,
        payload={"window": record, "activity": native.activity()},
    )
    stages = []
    monkeypatch.setattr(worker, "send", lambda request, stage, data: stages.append(stage))

    def commit():
        assert not calls and stages == ["ready"]
        return {"version": 1, "request_id": "test", "commit": True}

    monkeypatch.setattr(worker, "read", commit)
    worker.run(request)
    assert stages == ["ready", "result"]
    assert calls == (
        [("show", record["hwnd"], 6)]
        if operation == "minimize"
        else [("show", record["hwnd"], 9), ("focus", record["hwnd"])]
    )
