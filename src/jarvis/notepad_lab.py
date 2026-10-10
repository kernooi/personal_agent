"""Explicit development lab, scripted proposals, genuine Notepad via existing broker."""

import json
import tempfile
import time
from pathlib import Path

from jarvis.bootstrap import build
from jarvis.domain import State, UserRequest
from jarvis.models import Profile
from jarvis.notepad import clean
from jarvis.win_stop import StopHotkey


def run_lab(args):
    if args.takeover_only:
        return run_takeover(args)
    profile = Profile(
        profile_name="attended-notepad-lab",
        model_identity="scripted-lab",
        prompt_version="planner-m2-v1",
        decision_version="decision-m2-v1",
        task_seconds=120,
        reply='{"kind":"say","text":"Lab"}',
    )
    rows = []
    with tempfile.TemporaryDirectory(prefix="jarvis-notepad-lab-") as directory:
        broker = build(
            Path(directory) / "journal.sqlite",
            profile,
            real=True,
            registration=args.registration,
            attended=args.attended,
        )
        broker.cancel_requested = broker.desktop.stop.is_set
        baseline = broker.desktop.inventory()
        baseline_refs = {row["window_ref"] for row in baseline}

        def request(case, text, capability, ref=""):
            arguments = {"app_id": "notepad"} if capability == "apps.open" else {"window_ref": ref}
            broker.profile = broker.profile.model_copy(
                update={
                    "reply": json.dumps(
                        {
                            "kind": "propose_action",
                            "action": {"capability": capability, "arguments": arguments},
                        }
                    )
                }
            )
            started = time.monotonic()
            result = broker.converse(UserRequest(case, "demo-session", text))
            row = {
                "case_id": case,
                "broker_state": result.state,
                "message": result.message,
                "simulated": result.simulated,
                "latency_seconds": round(time.monotonic() - started, 4),
                "executions": broker.desktop.execution_calls,
                "observations": broker.desktop.observation_calls,
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
            return result

        try:
            with StopHotkey(broker.desktop.stop):
                print(
                    "Attended scope: at most two new Notepad windows; no personal-window effects. "
                    "Only empty single-tab disposable windows may close. "
                    "Stop: Ctrl+Alt+Shift+F10 from any application. "
                    "Unknown/dirty windows remain open.",
                    flush=True,
                )
                first = request("open-1", "Open Notepad.", "apps.open")
                first_ref = broker.desktop.selected_ref
                if first.state != State.SUCCEEDED or not first_ref or first_ref in baseline_refs:
                    raise ValueError(
                        "Isolated new Notepad readiness not established; manual handoff"
                    )
                record = broker.desktop.windows[first_ref]
                if not clean(record):
                    raise ValueError(
                        "New window empty single-tab safety not established; manual handoff"
                    )
                # --attended is consent for only newly identified empty single-tab lab windows.
                broker.desktop.select(first_ref, confirm_disposable=True)
                request("reuse-1", "Open Notepad.", "apps.open")
                request("focus-1", "Focus Notepad.", "windows.focus", first_ref)
                broker.desktop.selected_ref = ""
                second = request("open-2", "Open Notepad.", "apps.open")
                second_ref = broker.desktop.selected_ref
                if (
                    second.state != State.SUCCEEDED
                    or not second_ref
                    or second_ref == first_ref
                    or second_ref in baseline_refs
                ):
                    raise ValueError(
                        "Second isolated Notepad window unavailable; no automatic cleanup"
                    )
                broker.desktop.select(second_ref, confirm_disposable=True)
                request("focus-2", "Focus Notepad.", "windows.focus", second_ref)
                request("close-2", "Close that Notepad window.", "windows.close", second_ref)
                broker.desktop.select(first_ref, confirm_disposable=True)
                if args.interactive:
                    input(
                        "Manually enter synthetic text in the remaining lab Notepad, "
                        "then return here and press Enter. "
                    )
                    before = broker.desktop.execution_calls
                    dirty = request(
                        "dirty-close-handoff",
                        "Close that Notepad window.",
                        "windows.close",
                        first_ref,
                    )
                    rows.append(
                        {
                            "case_id": "dirty-handoff-verification",
                            "passed": dirty.state == State.WAITING_INPUT
                            and broker.desktop.execution_calls == before,
                        }
                    )
                    input(
                        "Focus the lab Notepad and press Ctrl+Alt+Shift+F10. "
                        "Then return here and press Enter. "
                    )
                    rows.append(
                        {"case_id": "physical-stop", "passed": broker.desktop.stop.is_set()}
                    )
                    request("stopped-request", "Focus Notepad.", "windows.focus", first_ref)
                    print(
                        "Dirty window is left for manual handling. "
                        "No save/discard or force cleanup."
                    )
                else:
                    request("close-1", "Close that Notepad window.", "windows.close", first_ref)
        except Exception:
            rows.append(
                {
                    "case_id": "lab-blocked",
                    "passed": False,
                    "reason": "Required native identity, isolation, focus or close safety "
                    "unavailable; manual handling required",
                }
            )
        finally:
            try:
                remaining = broker.desktop.inventory()
            except Exception:
                remaining = []
                rows.append({"case_id": "final-inventory-unavailable", "passed": False})
            baseline_preserved = baseline_refs <= {row["window_ref"] for row in remaining}
            report = {
                "version": "m2-notepad-adapter-lab-v1",
                "provider": "scripted",
                "execution_mode": "windows",
                "notepad_version": broker.desktop.transport.registration.notepad_version,
                "preexisting_window_count": len(baseline),
                "preexisting_preserved": baseline_preserved,
                "remaining_window_count": len(remaining),
                "interactive_checks_requested": args.interactive,
                "cases": rows,
                "completion_gate": "adapter evidence only; live-model evidence is separate",
            }
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            broker.store.close()
            broker.provider.close()
    required = {"open-1", "reuse-1", "focus-1", "open-2", "focus-2", "close-2"}
    verified = {row["case_id"] for row in rows if row.get("broker_state") == State.SUCCEEDED}
    if not args.interactive:
        required.add("close-1")
    return (
        0
        if required <= verified
        and baseline_preserved
        and not any(row.get("passed") is False for row in rows)
        else 1
    )


def run_takeover(args):
    """Attended admission test: a user-confirmed synthetic window, no close/open."""
    if not args.prepared_synthetic:
        raise ValueError("Takeover check requires a confirmed prepared synthetic window")
    profile = Profile(
        profile_name="attended-takeover-lab",
        model_identity="scripted-lab",
        prompt_version="planner-m2-v4",
        decision_version="decision-m2-v1",
        task_seconds=120,
        reply='{"kind":"say","text":"Lab"}',
    )
    with tempfile.TemporaryDirectory(prefix="jarvis-takeover-") as directory:
        broker = build(
            Path(directory) / "journal.sqlite",
            profile,
            real=True,
            registration=args.registration,
            attended=args.attended,
        )
        try:
            windows = broker.desktop.inventory()
            if len(windows) != 1:
                raise ValueError("Prepare exactly one confirmed synthetic test window")
            ref = windows[0]["window_ref"]
            broker.desktop.select(ref)
            broker.profile = profile.model_copy(
                update={
                    "reply": json.dumps(
                        {
                            "kind": "propose_action",
                            "action": {
                                "capability": "windows.focus",
                                "arguments": {"window_ref": ref},
                            },
                        }
                    )
                }
            )
            # Development-only attended pause, not a runtime increase or model option.
            broker.desktop.transport.timeout = 90
            broker.before_admission = lambda: input(
                "Admission paused. Click the synthetic Notepad window now, "
                "then return here and press Enter. No close/open is tested. "
            )
            broker.cancel_requested = broker.desktop.stop.is_set
            with StopHotkey(broker.desktop.stop):
                result = broker.converse(UserRequest("takeover", "demo-session", "Focus Notepad."))
            report = {
                "version": "m2-native-takeover-v1",
                "provider": "scripted",
                "execution_mode": "windows",
                "broker_state": result.state,
                "message": result.message,
                "native_deliveries": broker.desktop.execution_calls,
                "window_preserved": len(broker.desktop.inventory()) == 1,
                "passed": result.state == State.FAILED and broker.desktop.execution_calls == 0,
                "scope": "User-confirmed synthetic window; focus only; no open/close",
            }
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report), flush=True)
            return 0 if report["passed"] and report["window_preserved"] else 1
        finally:
            broker.store.close()
            broker.provider.close()
