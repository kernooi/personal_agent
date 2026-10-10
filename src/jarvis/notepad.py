"""M2 registration, scoped windows and bounded broker-only Notepad adapter."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from jarvis.domain import AdmissionRejected, Evidence, Handoff, PreparedAction, Scope
from jarvis.models import BOUNDARY_M2, StrictRecord, reject_constant, unique_object
from jarvis.policy import POLICY_VERSION
from jarvis.tools import RegisteredApp, Registry, digest


class Registration(StrictRecord):
    version: Literal["notepad-registration-v1"]
    app_id: Literal["notepad"]
    launcher: str
    launcher_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    executable: str
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_full_name: str = Field(
        pattern=r"^Microsoft\.WindowsNotepad_[0-9.]+_x64__8wekyb3d8bbwe$"
    )
    notepad_version: str
    microsoft_signature_verified: Literal[True]

    def revalidate(self):
        if os.name != "nt":
            raise Handoff("Real Notepad requires Windows")
        from jarvis.win_native import file_hash

        launcher = Path(os.environ["WINDIR"]) / "System32/notepad.exe"
        if Path(self.launcher).resolve() != launcher.resolve():
            raise Handoff("Untrusted Notepad launch path")
        expected = (
            Path(os.environ["ProgramFiles"])
            / "WindowsApps"
            / self.package_full_name
            / "Notepad/Notepad.exe"
        )
        if Path(self.executable).resolve() != expected.resolve():
            raise Handoff("Untrusted Notepad package path")
        if (
            file_hash(self.launcher) != self.launcher_sha256
            or file_hash(self.executable) != self.executable_sha256
        ):
            raise Handoff("Notepad installation changed; re-register before real use")


def load_registration(path: Path):
    if path.stat().st_size > 16384:
        raise Handoff("Registration size exceeded")
    registration = Registration.model_validate(
        json.loads(
            path.read_bytes(), object_pairs_hook=unique_object, parse_constant=reject_constant
        ),
        strict=True,
    )
    registration.revalidate()
    return registration


class WorkerTransport:
    """No uncontrolled background calls. Every worker is bounded and supervised."""

    def __init__(self, registration, stop: threading.Event, timeout=8.0):
        self.registration = registration
        self.stop = stop
        self.timeout = timeout

    def call(self, operation, payload=None, gate: Callable[[], None] | None = None):
        request_id = uuid4().hex
        deadline = time.time() + self.timeout
        request = {
            "version": 1,
            "request_id": request_id,
            "deadline": deadline,
            "operation": operation,
            "registration": self.registration.model_dump(),
            "payload": payload or {},
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "jarvis.win_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            shell=False,
            close_fds=True,
        )
        messages = queue.Queue(maxsize=4)

        def read():
            try:
                while raw := process.stdout.readline(65537):
                    if len(raw) > 65536:
                        raise ValueError("Worker output limit")
                    item = json.loads(
                        raw, object_pairs_hook=unique_object, parse_constant=reject_constant
                    )
                    if (
                        set(item) != {"version", "request_id", "stage", "data"}
                        or item["version"] != 1
                        or item["request_id"] != request_id
                    ):
                        raise ValueError("Invalid worker reply")
                    messages.put_nowait(item)
            except Exception:
                try:
                    messages.put_nowait({"stage": "error", "data": {}})
                except queue.Full:
                    pass

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        committed = False
        try:
            process.stdin.write((json.dumps(request) + "\n").encode())
            process.stdin.flush()
            while time.time() < deadline:
                if self.stop.is_set() and gate is not None:
                    if not committed:
                        raise AdmissionRejected("Stopped before native effect")
                    raise RuntimeError("Stopped after possible native effect; review required")
                try:
                    message = messages.get(timeout=0.025)
                except queue.Empty:
                    if process.poll() is not None:
                        if gate is not None and not committed:
                            raise AdmissionRejected(
                                "Worker exited before native admission"
                            ) from None
                        raise RuntimeError("Worker exited without a bounded result") from None
                    continue
                if message["stage"] == "ready":
                    if gate is None or committed:
                        raise RuntimeError("Unexpected worker admission")
                    gate()
                    if self.stop.is_set():
                        raise AdmissionRejected("Stopped at native admission")
                    committed = True
                    process.stdin.write(
                        (
                            json.dumps({"version": 1, "request_id": request_id, "commit": True})
                            + "\n"
                        ).encode()
                    )
                    process.stdin.flush()
                elif message["stage"] == "rejected":
                    raise AdmissionRejected("Native gate rejected; no effect delivered")
                elif message["stage"] == "result":
                    if gate is not None and not committed:
                        raise AdmissionRejected("Worker returned before native admission")
                    return message["data"]
                else:
                    if not committed and gate is not None:
                        raise AdmissionRejected("Native preparation unavailable; zero delivery")
                    raise RuntimeError("Native result unavailable")
            if not committed and gate is not None:
                raise AdmissionRejected("Worker timed out before native admission")
            raise RuntimeError("Worker timeout; effect may be unknown")
        finally:
            # These handles belong only to the automation worker, never Notepad.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)
            process.stdin.close()
            process.stdout.close()
            reader.join(timeout=1)


def identity(record):
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
    return (
        record.get("empty") is True
        and record.get("modified") is False
        and len(record.get("tab_ids", [])) == 1
        and record.get("enabled") is True
        and not record.get("owned_dialog", True)
    )


class DesktopLease:
    def __init__(self, path):
        self.path = path
        self.stream = None

    def __enter__(self):
        import msvcrt

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        try:
            # Reading a byte locked by another Windows handle itself fails.
            # Inspect file length without accessing the locked byte.
            self.stream.seek(0, 2)
            if self.stream.tell() == 0:
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self.stream.close()
            raise AdmissionRejected("Desktop interaction lease is busy") from exc
        return self

    def __exit__(self, *_):
        import msvcrt

        self.stream.seek(0)
        msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


class NotepadDesktop:
    evidence_source = "notepad-native-observer-v1"
    evidence_kind = "windows_uia_state"
    failure_message = (
        "The Notepad operation was not verified. Handle any dialog or focus restriction "
        "manually; I will not retry it."
    )

    def __init__(self, clock, transport, *, real=False, lease=None):
        self.clock = clock
        self.transport = transport
        self.real = real
        self.stop = threading.Event()
        self.lease = lease
        self.windows = {}
        self.confirmed = {}
        self.selected_ref = ""
        self.activity = None
        self.last_window = ""
        self.execution_calls = 0
        self.observation_calls = 0
        self.pending_open = None
        self.blocked_unknown = False
        self.lease_held = False
        self.reference_clear = False
        self.last_outcome = None
        self.review_task_id = ""
        self.verification_note = ""

    def begin(self):
        self.verification_note = ""
        self.activity = self.transport.call("activity")

    def refresh_selection(self):
        if not self.selected_ref:
            return
        expected = self.windows[self.selected_ref]
        keys = ("hwnd", "pid", "created", "os_session", "exe_sha256", "package", "class_name")
        live = self.transport.call("inventory")
        if not any(all(row[key] == expected[key] for key in keys) for row in live):
            self.confirmed.pop(self.selected_ref, None)
            self.selected_ref = ""
            self.reference_clear = False

    def inventory(self):
        records = self.transport.call("inventory")
        for record in records:
            existing = next(
                (
                    ref
                    for ref, old in self.windows.items()
                    if old["hwnd"] == record["hwnd"] and old["created"] == record["created"]
                ),
                None,
            )
            if existing is None:
                # Only native identity, no document metadata read for personal windows.
                ref = "win_" + uuid4().hex
                self.windows[ref] = record
        return [
            {
                "window_ref": ref,
                "selected": ref == self.selected_ref,
                "disposable_confirmed": ref in self.confirmed,
            }
            for ref in self.windows
            if any(
                row["hwnd"] == self.windows[ref]["hwnd"]
                and row["created"] == self.windows[ref]["created"]
                for row in records
            )
        ]

    def select(self, ref, *, confirm_disposable=False):
        if ref not in self.windows:
            raise Handoff("Unknown broker-issued window reference")
        # No body or labels are observed, only boolean empty state and tab identities.
        record = self.transport.call("inspect", {"window": self.windows[ref]})
        self.windows[ref] = record
        self.selected_ref = ref
        self.reference_clear = True
        if confirm_disposable:
            if not clean(record):
                raise Handoff("Window is not known empty and single-tab; handle it manually")
            self.confirmed[ref] = record["tab_ids"]
        return ref

    def pin(self, effect, ref):
        if self.stop.is_set():
            raise Handoff(
                "Desktop stop is latched. Restart chat after reviewing any pending effect."
            )
        if self.blocked_unknown:
            raise Handoff(
                "A previous Notepad outcome is uncertain. Manual review is required; "
                "no automatic replay. "
                + (
                    f"Inspect Notepad, then /review {self.review_task_id} manually-handled."
                    if self.review_task_id
                    else ""
                )
            )
        if self.activity is None:
            self.begin()
        if self.transport.call("activity") != self.activity:
            raise Handoff(
                "User activity or focus changed during planning; "
                "please request the operation again."
            )
        if effect == "open" and not ref:
            return json.dumps({"activity": self.activity, "window": None}, sort_keys=True)
        if ref not in self.windows:
            raise Handoff("Select a specific Notepad window using /windows and /select first.")
        record = self.transport.call("inspect", {"window": self.windows[ref]})
        self.windows[ref] = record
        if effect == "close" and (
            not clean(record) or self.confirmed.get(ref) != record["tab_ids"]
        ):
            if self.real and clean(record):
                raise Handoff(
                    "Before I close it, check that the selected Notepad is your empty, "
                    "unmodified, single-tab test window. Then enter /confirm-empty and "
                    "ask me to close it again. No close was sent."
                )
            if not self.real and clean(record):
                raise Handoff(
                    "Confirm the selected empty test window with /confirm-empty, "
                    "then ask me to close it again; no close was sent."
                )
            raise Handoff(
                "I can't safely close this Notepad window: it contains text or unsaved "
                "changes, has multiple tabs, a dialog, or its safety is unknown. "
                "Please handle it manually; no close was sent."
            )
        return json.dumps({"activity": self.activity, "window": record}, sort_keys=True)

    def execute(self, action, admission_gate):
        if self.lease is not None:
            self.lease.__enter__()
            self.lease_held = True
        try:
            self._execute(action, admission_gate)
        except BaseException:
            self._release_lease()
            raise

    def _release_lease(self):
        if self.lease_held:
            self.lease_held = False
            self.lease.__exit__(None, None, None)

    def _execute(self, action, admission_gate):
        payload = json.loads(action.target_identity)
        effect = action.effects[0]
        if effect == "open" and payload["window"] is not None:
            admission_gate()
            self.execution_calls += 1
            self.last_window = action.window_ref
            return
        try:
            result = self.transport.call(effect, payload, admission_gate)
        except AdmissionRejected:
            raise
        except Exception:
            self.blocked_unknown = True
            raise
        self.execution_calls += 1
        if effect == "open":
            self.pending_open = result["baseline"]
        self.last_window = action.window_ref

    def observe(self, action):
        try:
            return self._observe(action)
        finally:
            self._release_lease()

    def _observe(self, action):
        self.observation_calls += 1
        payload = json.loads(action.target_identity)
        effect = action.effects[0]
        postcondition = None
        running = None
        observed_identity = ""
        until = time.monotonic() + 4
        while True:
            records = self.transport.call("inventory")
            if effect == "open" and payload["window"] is None:
                candidates = [
                    row
                    for row in records
                    if not any(
                        row["hwnd"] == old["hwnd"] and row["created"] == old["created"]
                        for old in (self.pending_open or [])
                    )
                ]
                if len(candidates) == 1:
                    window = self.transport.call("inspect", {"window": candidates[0]})
                    # A ready window is not automatically a disposable close grant.
                    ref = "win_" + uuid4().hex
                    self.windows[ref] = window
                    self.selected_ref = self.last_window = ref
                    self.reference_clear = True
                    observed_identity = json.dumps(identity(window), sort_keys=True)
                    postcondition = running = window["enabled"] and not window["owned_dialog"]
                    break
            else:
                expected = payload["window"]
                matching = [
                    row
                    for row in records
                    if row["hwnd"] == expected["hwnd"] and row["created"] == expected["created"]
                ]
                if effect == "close":
                    postcondition = not matching
                    running = bool(matching)
                    if postcondition:
                        observed_identity = json.dumps(
                            {**identity(expected), "present": False}, sort_keys=True
                        )
                        self.confirmed.pop(action.window_ref, None)
                        if self.selected_ref == action.window_ref:
                            self.selected_ref = ""
                            self.reference_clear = False
                        break
                elif matching:
                    actual = self.transport.call("inspect", {"window": expected})
                    same = identity(actual) == identity(expected)
                    observed_identity = json.dumps(identity(actual), sort_keys=True)
                    running = same
                    postcondition = same and (
                        effect == "open"
                        or self.transport.call("activity")["foreground"] == expected["hwnd"]
                    )
                    if postcondition:
                        self.reference_clear = True
                    break
            if self.stop.is_set() or time.monotonic() >= until or not self.real:
                if effect == "open":
                    self.blocked_unknown = True
                break
            time.sleep(0.05)
        # Effect-generated foreground transitions are expected, ordinary user
        # input during verification is not. Never claim verified completion then.
        if self.transport.call("activity")["last_input"] != payload["activity"]["last_input"]:
            self.verification_note = "Windows input changed while I was verifying the operation. "
            postcondition = None
            self.blocked_unknown = True
        return Evidence(
            action.target_identity,
            action.session,
            self.clock.now(),
            running,
            self.evidence_source,
            "tool_output",
            "personal",
            self.evidence_kind,
            postcondition,
            self.last_window,
            observed_identity,
        )

    def success_message(self, action):
        verb = {"open": "open and ready", "focus": "in the foreground", "close": "closed"}[
            action.effects[0]
        ]
        prefix = "" if self.real else "SIMULATED: "
        return prefix + "The selected Notepad window is " + verb + "."


class NotepadRegistry(Registry):
    m2 = True

    def __init__(self, desktop, *, conversational=False):
        self.desktop = desktop
        self.conversational = conversational
        self.intent = None
        self.adapter_version = "notepad-windows-v1" if desktop.real else "notepad-fake-v1"
        self.apps = {
            "notepad": RegisteredApp(
                "notepad", "registered:microsoft-notepad", "Microsoft Windows Notepad"
            )
        }

    def schema(self):
        return BOUNDARY_M2.json_schema()

    def scope_for(self, session, text):
        self.desktop.begin()
        if self.conversational:
            from jarvis.notepad_intent import interpret

            if getattr(self, "extended", False):
                from jarvis.notepad_intent_v2 import interpret

            self.desktop.refresh_selection()
            self.intent = interpret(text)
            ref = self.desktop.selected_ref
            intent = self.intent
            if intent is None:
                return Scope(session, "none")
            if intent.target in {"ambiguous", "unregistered"}:
                self.desktop.reference_clear = False
                return Scope(session, "none", intent.effect)
            if intent.target == "selected" and (not ref or not self.desktop.reference_clear):
                return Scope(session, "none", intent.effect)
            if intent.effect != "open" and not ref:
                return Scope(session, "none", intent.effect)
            return Scope(session, "notepad", intent.effect, ref)
        value = text.strip().casefold().rstrip(".!?")
        opens = {
            "open notepad",
            "open my text editor",
            "open my registered text editor",
            "launch notepad",
            "please open notepad",
        }
        focus = {
            "bring that notepad window to the front",
            "focus that notepad window",
            "focus notepad",
            "bring notepad to the front",
        }
        closes = {"close that notepad window", "close notepad", "close my text editor"}
        effect = (
            "open"
            if value in opens
            else "focus"
            if value in focus
            else "close"
            if value in closes
            else None
        )
        if effect is None:
            return Scope(session, "none")
        ref = self.desktop.selected_ref
        if effect != "open" and not ref:
            return Scope(session, "none", effect)
        return Scope(session, "notepad", effect, ref)

    def schema_for(self, scope):
        from jarvis.notepad_schema import candidate_schema

        return candidate_schema(scope)

    def planner_context(self):
        ref = self.desktop.selected_ref
        return {
            "registered_application": "notepad",
            "selected_window_ref": ref or None,
            "selected_window_exists": bool(ref),
            "pronoun_reference_unambiguous": self.desktop.reference_clear,
            "disposable_confirmation_recorded": ref in self.desktop.confirmed,
            "close_safety": "always rechecked; no automatic dirty/multiple-tab/unknown close",
            "requested_effect": self.intent.effect if self.intent else None,
            "request_target": self.intent.target if self.intent else None,
            "last_controller_outcome": self.desktop.last_outcome,
        }

    def prepare(self, task, proposal, grant):
        effects = {"apps.open": "open", "windows.focus": "focus", "windows.close": "close"}
        if proposal.app_id != "notepad" or proposal.capability not in effects:
            raise Handoff("Unregistered application or operation; no Windows effect")
        effect = effects[proposal.capability]
        if (
            task.scope.app_id != "notepad"
            or task.scope.effect != effect
            or (effect != "open" and proposal.window_ref != task.scope.window_ref)
        ):
            raise Handoff(
                "The proposal does not match your selected Notepad scope; no Windows effect"
            )
        target = self.desktop.pin(effect, task.scope.window_ref)
        action = PreparedAction(
            task.task_id,
            task.revision,
            proposal.capability,
            "notepad",
            target,
            task.scope.session,
            (effect,),
            self.adapter_version,
            POLICY_VERSION,
            grant.grant_id,
            grant.version,
            min(task.deadline, grant.expires_at),
            "",
            task.scope.window_ref,
        )
        return PreparedAction(**{**asdict(action), "digest": digest(action)})

    def validate(self, action: PreparedAction):
        if (
            action.adapter_version != self.adapter_version
            or action.app_id != "notepad"
            or digest(action) != action.digest
            or action.policy_version != POLICY_VERSION
        ):
            raise AdmissionRejected("Prepared Notepad action changed")
        if self.desktop.real:
            self.desktop.transport.registration.revalidate()
