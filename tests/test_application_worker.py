"""Native worker boundary checks without launching or manipulating Windows apps."""

import time
from types import SimpleNamespace

import pytest

from jarvis import application_worker as worker
from jarvis.application_data import ApplicationsConfig
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.domain import Denied


@pytest.fixture
def native_boundary(monkeypatch):
    platform = FakeApplicationPlatform()
    app = platform.add_app("Arbitrary Installed App")
    row = platform.add_window(app)
    sent, effects = [], []
    activity = {"last_input": 1, "foreground": row["hwnd"]}
    native = SimpleNamespace(activity=lambda: activity.copy())
    monkeypatch.setattr(worker, "ApplicationNative", lambda: native)
    monkeypatch.setattr(worker, "fresh_app", lambda config, expected: app)
    monkeypatch.setattr(worker, "selected", lambda *args: row.copy())
    monkeypatch.setattr(worker, "file_hash", lambda path: "a" * 64)
    monkeypatch.setattr(worker, "activate", lambda target: effects.append(target.app_id))
    monkeypatch.setattr(worker, "send", lambda request, stage, data: sent.append(stage))
    request = {
        "version": 1,
        "request_id": "worker-test",
        "deadline": time.time() + 20,
        "operation": "open",
        "config": ApplicationsConfig(enabled=True).model_dump(),
        "payload": {
            "app": app.model_dump(),
            "window": None,
            "activity": activity.copy(),
            "exe_sha256": "a" * 64,
            "close_reviewed": False,
            "review_expires_at": 0,
        },
    }
    commit = {"version": 1, "request_id": "worker-test", "commit": True}
    monkeypatch.setattr(worker, "read", lambda: commit)
    return request, row, activity, sent, effects


def test_exact_commit_required_before_launch(native_boundary, monkeypatch):
    request, _, _, sent, effects = native_boundary
    monkeypatch.setattr(worker, "read", lambda: {"commit": True})
    with pytest.raises(Denied):
        worker.run(request)
    assert sent == ["ready"] and not effects


def test_user_takeover_between_ready_and_commit_has_zero_delivery(native_boundary, monkeypatch):
    request, _, activity, sent, effects = native_boundary

    def commit():
        activity["last_input"] += 1
        return {"version": 1, "request_id": "worker-test", "commit": True}

    monkeypatch.setattr(worker, "read", commit)
    worker.run(request)
    assert sent == ["ready", "rejected"] and not effects


def test_launch_only_after_two_preflights_and_exact_commit(native_boundary):
    request, _, _, sent, effects = native_boundary
    worker.run(request)
    assert sent == ["ready", "result"] and len(effects) == 1


@pytest.mark.parametrize("failure", ["hash", "dirty", "expired", "unreviewed", "dialog"])
def test_close_rejection_before_ready(native_boundary, failure):
    request, row, _, sent, effects = native_boundary
    request["operation"] = "close"
    request["payload"].update(window=row, close_reviewed=True, review_expires_at=time.time() + 60)
    if failure == "hash":
        request["payload"]["exe_sha256"] = "b" * 64
    elif failure == "dirty":
        row.update(protected=True, close_safe=False)
    elif failure == "expired":
        request["payload"]["review_expires_at"] = time.time() - 1
    elif failure == "unreviewed":
        request["payload"]["close_reviewed"] = False
    else:
        row["owned_dialog"] = True
    with pytest.raises(Denied):
        worker.run(request)
    assert not sent and not effects


def test_package_manifest_cannot_escape_installation(tmp_path):
    (tmp_path / "AppxManifest.xml").write_text(
        '<Package><Application Id="Test" Executable="../outside.exe"/></Package>'
    )
    (tmp_path.parent / "outside.exe").write_bytes(b"fixture")
    with pytest.raises(Denied):
        worker.package_executable(str(tmp_path), "fixture!Test")


@pytest.mark.parametrize(
    "path",
    [r"\\server\share\app.exe", "https://example.com/app.exe", "app.exe", r"C:\app.exe --argument"],
)
def test_no_remote_or_argument_launch_paths(path):
    with pytest.raises((Denied, OSError)):
        worker.local_executable(path)


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "foreign-user",
        "foreign-session",
        "two-children",
        "wrong-host",
        "wrong-root",
        "child-limit",
        "unknown-package",
    ],
)
def test_host_frame_requires_unique_same_user_package_child(monkeypatch, failure):
    platform = FakeApplicationPlatform()
    app = platform.add_app("Hosted Fixture").model_copy(
        update={"kind": "package", "package": "fixture-package"}
    )
    host = dict(
        pid=10,
        created=20,
        exe=r"C:\Windows\System32\ApplicationFrameHost.exe",
        package="",
        owner_sid="fixture-owner",
        os_session=1,
    )
    content = dict(
        pid=11,
        created=21,
        exe=app.executable,
        package=app.package,
        owner_sid="fixture-owner",
        os_session=1,
    )
    if failure == "foreign-user":
        content["owner_sid"] = "other-owner"
    if failure == "foreign-session":
        content["os_session"] = 2
    if failure == "unknown-package":
        content["package"] = "not-the-installed-package"
    if failure == "wrong-host":
        host["exe"] = r"C:\Fake\ApplicationFrameHost.exe"

    def pid(hwnd, pointer):
        pointer._obj.value = 10 if hwnd == 100 else 11

    def class_name(hwnd, buffer, maximum):
        buffer.value = "ApplicationFrameWindow"

    def system(buffer, maximum):
        buffer.value = r"C:\Windows\System32"
        return len(buffer.value)

    def children(hwnd, callback, unused):
        count = 257 if failure == "child-limit" else 2 if failure == "two-children" else 1
        for index in range(count):
            if not callback(200 + index, 0):
                break

    user = SimpleNamespace(
        GetWindowThreadProcessId=pid,
        GetClassNameW=class_name,
        IsWindowVisible=lambda hwnd: True,
        GetAncestor=lambda hwnd, kind: 999 if failure == "wrong-root" else 100,
        EnumChildWindows=children,
    )
    native = object.__new__(worker.ApplicationNative)
    native.user = user
    native.kernel = SimpleNamespace(GetSystemDirectoryW=system)
    native.owner_sid, native.session = "fixture-owner", 1
    native.process = lambda pid: host.copy() if pid == 10 else content.copy()
    monkeypatch.setattr(worker, "file_hash", lambda path: "a" * 64)
    if failure:
        with pytest.raises(Denied):
            native.associated_process(100, [app])
    else:
        proc, selected, frame, child = native.associated_process(100, [app])
        assert selected == app and proc == content
        assert frame["pid"] == 10 and frame["exe_sha256"] == "a" * 64 and child == 200


@pytest.mark.parametrize(
    "failure", [None, "host-reuse", "content-reuse", "reparented", "binary", "not-minimized"]
)
def test_detached_minimized_frame_retains_both_process_identities(monkeypatch, failure):
    from jarvis.application_tools import identity

    platform = FakeApplicationPlatform()
    app = platform.add_app("Detached Fixture").model_copy(
        update={"kind": "package", "package": "fixture-package"}
    )
    expected = platform.add_window(app)
    expected.update(
        hwnd=100, content_hwnd=200, class_name="ApplicationFrameWindow", package=app.package
    )
    content = {k: expected[k] for k in ("pid", "created", "os_session", "owner_sid", "package")}
    content["exe"] = app.executable
    host = dict(
        pid=10,
        created=20,
        exe=r"C:\Windows\System32\ApplicationFrameHost.exe",
        package="",
        owner_sid="fixture",
        os_session=1,
    )
    expected["frame_host"] = {**host, "exe_sha256": "a" * 64}
    if failure == "host-reuse":
        host["created"] += 1
    if failure == "content-reuse":
        content["created"] += 1

    def pid(hwnd, pointer):
        pointer._obj.value = 10 if hwnd == 100 else expected["pid"]

    def cls(hwnd, buffer, maximum):
        buffer.value = "ApplicationFrameWindow"

    native = object.__new__(worker.ApplicationNative)
    native.owner_sid, native.session = "fixture", 1
    native.user = SimpleNamespace(
        GetWindowThreadProcessId=pid,
        GetClassNameW=cls,
        IsIconic=lambda hwnd: failure != "not-minimized",
        IsWindow=lambda hwnd: True,
        GetAncestor=lambda hwnd, kind: 999 if failure == "reparented" else 200,
    )
    native.process = lambda pid: host.copy() if pid == 10 else content.copy()
    monkeypatch.setattr(
        worker, "file_hash", lambda path: "b" * 64 if failure == "binary" else "a" * 64
    )
    if failure:
        with pytest.raises(Denied):
            native.minimized_frame(app, expected)
    else:
        assert identity(native.minimized_frame(app, expected)) == identity(expected)


@pytest.mark.parametrize("failure", [None, "input", "deadline"])
def test_restore_waits_for_same_identity_without_another_effect(monkeypatch, failure):
    reads = []
    native = SimpleNamespace(
        user=SimpleNamespace(IsIconic=lambda hwnd: False),
        activity=lambda: {"last_input": 2 if failure == "input" else 1},
    )

    def observe(*args):
        reads.append(True)
        if len(reads) < 3:
            raise Denied("Reattachment still settling")

    monkeypatch.setattr(worker, "selected", observe)
    deadline = time.time() - 1 if failure == "deadline" else time.time() + 2
    if failure:
        with pytest.raises(Denied):
            worker.wait_restored(native, None, {"hwnd": 100}, None, deadline, {"last_input": 1})
        assert not reads
    else:
        worker.wait_restored(native, None, {"hwnd": 100}, None, deadline, {"last_input": 1})
        assert len(reads) == 3


def test_signed_versioned_runtime_requires_matching_certificate_and_install_root(
    tmp_path, monkeypatch
):
    from jarvis import application_identity
    from jarvis.application_data import Application, app_id

    root = tmp_path / "Sample"
    root.mkdir()
    launcher = root / "Sample.exe"
    launcher.write_bytes(b"launcher")
    version = root / "version-42"
    version.mkdir()
    runtime = version / "Sample.exe"
    runtime.write_bytes(b"runtime")
    app = Application(
        app_id=app_id("sample"),
        name="Sample",
        launch_id="sample",
        kind="exe",
        executable=str(launcher),
    )
    native = worker.ApplicationNative.__new__(worker.ApplicationNative)
    monkeypatch.setattr(application_identity, "signer", lambda p: "c" * 64)
    result = native.runtime_association({"exe": str(runtime)}, app)
    assert result["method"] == "signed-versioned-runtime"
    assert result["launch_sha256"] != result["runtime_sha256"]
    monkeypatch.setattr(
        application_identity, "signer", lambda p: "c" * 64 if p == launcher else "d" * 64
    )
    assert native.runtime_association({"exe": str(runtime)}, app) is None
    monkeypatch.setattr(application_identity, "signer", lambda p: "")
    assert native.runtime_association({"exe": str(runtime)}, app) is None
    outside = tmp_path / "Sample.exe"
    outside.write_bytes(b"foreign")
    assert native.runtime_association({"exe": str(outside)}, app) is None


def test_same_folder_foreign_filename_is_not_a_launcher_runtime(tmp_path, monkeypatch):
    from jarvis import application_identity
    from jarvis.application_data import Application, app_id

    root = tmp_path / "Sample"
    root.mkdir()
    launcher = root / "Sample.exe"
    launcher.write_bytes(b"launcher")
    runtime = root / "Other.exe"
    runtime.write_bytes(b"other")
    monkeypatch.setattr(application_identity, "signer", lambda p: "c" * 64)
    app = Application(
        app_id=app_id("sample"),
        name="Sample",
        launch_id="sample",
        kind="exe",
        executable=str(launcher),
    )
    native = worker.ApplicationNative.__new__(worker.ApplicationNative)
    assert native.runtime_association({"exe": str(runtime)}, app) is None


@pytest.mark.parametrize(
    "failure",
    [None, "missing", "cycle", "newer", "user", "session", "publisher", "changed", "outside"],
)
def test_signed_descendant_runtime_requires_live_bounded_launcher_chain(
    tmp_path, monkeypatch, failure
):
    from jarvis import application_identity
    from jarvis.application_data import Application, app_id, valid_runtime_proof
    from jarvis.win_native import file_hash

    root = tmp_path / "Invented"
    root.mkdir()
    launch = root / "Invented.exe"
    runtime = root / "DifferentHelper.exe"
    launch.write_bytes(b"launcher")
    runtime.write_bytes(b"helper")
    app = Application(
        app_id=app_id("invented"),
        name="Invented",
        launch_id="invented",
        kind="exe",
        executable=str(launch),
    )
    child = dict(pid=20, created=200, exe=str(runtime), package="", owner_sid="owner", os_session=1)
    parent = {**child, "pid": 10, "created": 100, "exe": str(launch)}
    parents = {20: 10, 10: 1}
    if failure == "missing":
        parents = {}
    if failure == "cycle":
        parents[20] = 20
    if failure == "newer":
        parent["created"] = 201
    if failure == "user":
        parent["owner_sid"] = "another"
    if failure == "session":
        parent["os_session"] = 2
    if failure == "outside":
        outside = tmp_path / "Elsewhere.exe"
        outside.write_bytes(b"launcher")
        parent["exe"] = str(outside)
    snapshots = []

    def snapshot():
        snapshots.append(True)
        return {20: 30} if failure == "changed" and len(snapshots) > 1 else parents

    monkeypatch.setattr(application_identity, "process_parents", snapshot)
    monkeypatch.setattr(
        application_identity,
        "signer",
        lambda p: "d" * 64 if failure == "publisher" and p == runtime else "c" * 64,
    )
    native = worker.ApplicationNative.__new__(worker.ApplicationNative)
    native.process = lambda pid: {20: child, 10: parent}[pid].copy()
    proof = native.runtime_association(child, app)
    if failure:
        assert proof is None
        return
    assert proof["method"] == "signed-descendant-runtime"
    target = {"app": app.model_dump(), "exe_sha256": file_hash(launch)}
    observed = {**child, "exe_sha256": file_hash(runtime), "association": proof}
    assert valid_runtime_proof(observed, target)
    import copy

    for key, value in [
        ("pid", 10),
        ("created", 201),
        ("owner_sid", "other"),
        ("exe_sha256", "bad"),
    ]:
        forged = copy.deepcopy(observed)
        forged["association"]["ancestry"][-1][key] = value
        # The duplicate parent PID is already 10; change it to child's PID instead.
        if key == "pid":
            forged["association"]["ancestry"][-1][key] = 20
        assert not valid_runtime_proof(forged, target)
