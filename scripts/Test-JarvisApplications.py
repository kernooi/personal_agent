"""Explicit attended application lab; only newly opened disposable lab windows."""

import argparse
import ctypes
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from jarvis.application_data import ApplicationsConfig, resolve_app
from jarvis.application_evaluation import qualified
from jarvis.application_tools import attach
from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.domain import State
from jarvis.ollama import OllamaProvider
from jarvis.win_stop import StopHotkey


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apps", nargs=2, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.stop_file.exists():
        parser.error("Existing artifacts preserved; choose unused paths")
    clock = SystemClock()
    profile = load_profile(args.profile, allow_ollama=True)
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    if not qualified(args.model_report, profile, metadata):
        model.close()
        parser.error("Matching passed application qualification required")
    journal = (
        Path(os.environ["LOCALAPPDATA"])
        / "Jarvis"
        / ("applications-lab-" + uuid4().hex + ".sqlite")
    )
    broker = build(journal, profile, clock, provider=model)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.IsIconic.argtypes = [ctypes.c_void_p]
    user.IsIconic.restype = ctypes.c_bool
    user.IsWindow.argtypes = [ctypes.c_void_p]
    user.IsWindow.restype = ctypes.c_bool
    user.GetForegroundWindow.restype = ctypes.c_void_p
    rows, baseline, remaining = [], [], []
    passed = False
    try:
        chat = attach(broker, ApplicationsConfig(enabled=True), real=True, attended=True)
        broker.cancel_requested = chat.desktop.stop.is_set
        with StopHotkey(chat.desktop.stop):
            baseline = chat.desktop.inventory()
            baseline_refs = {r["window_ref"] for r in baseline}
            targets = [resolve_app(name, list(chat.desktop.apps.values())) for name in args.apps]
            if any(len(matches) != 1 for matches in targets):
                raise ValueError("Lab applications must resolve uniquely")
            if any(r["app_id"] in {a[0].app_id for a in targets} for r in baseline):
                raise ValueError("Pre-existing target windows excluded; handle them manually")
            for index, matches in enumerate(targets):
                app = matches[0]
                hwnd = None
                for operation, text in [
                    ("open", "open " + app.name),
                    ("minimize", "minimize it"),
                    ("repeat-minimize", "minimize it"),
                    ("focus", "bring it to the front"),
                    ("close", "close it"),
                ]:
                    if operation == "close":
                        chat.control("/app-confirm-close")
                    started = time.monotonic()
                    result = chat.submit(text)
                    row = {
                        "case_id": app.kind + "-" + operation,
                        "state": result.state,
                        "message": result.message,
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "passed": result.state == State.SUCCEEDED,
                    }
                    if operation == "open" and row["passed"]:
                        ref = chat.desktop.selected_ref
                        hwnd = chat.desktop.windows[ref]["hwnd"]
                        row["passed"] = ref not in baseline_refs and bool(user.IsWindow(hwnd))
                    elif operation in {"minimize", "repeat-minimize", "focus"}:
                        row["independent_is_iconic"] = bool(user.IsIconic(hwnd))
                        row["passed"] &= row["independent_is_iconic"] == (operation != "focus")
                        if operation == "focus":
                            row["independent_foreground_matches"] = (
                                user.GetForegroundWindow() == hwnd
                            )
                            row["passed"] &= row["independent_foreground_matches"]
                    elif operation == "close":
                        row["independent_window_absent"] = not user.IsWindow(hwnd)
                        row["passed"] &= row["independent_window_absent"]
                    rows.append(row)
                    print(json.dumps(row), flush=True)
                    if not row["passed"]:
                        raise ValueError("Lab stopped; manually inspect uncertain outcomes")
                    if index == 1 and operation == "focus":
                        print(
                            "READY_FOR_STOP: focus the second lab app and press the stop hotkey.",
                            flush=True,
                        )
                        args.stop_file.write_text("ready", encoding="utf-8")
                        until = time.monotonic() + 120
                        while not chat.desktop.stop.is_set() and time.monotonic() < until:
                            time.sleep(0.05)
                        admissions = broker.store.db.execute(
                            "SELECT COUNT(*) FROM actions"
                        ).fetchone()[0]
                        result = chat.submit("minimize it")
                        after = broker.store.db.execute("SELECT COUNT(*) FROM actions").fetchone()[
                            0
                        ]
                        stop_row = {
                            "case_id": "global-stop",
                            "state": result.state,
                            "zero_new_admissions": after == admissions,
                            "passed": chat.desktop.stop.is_set()
                            and result.state == State.CANCELLED
                            and after == admissions,
                        }
                        rows.append(stop_row)
                        print(json.dumps(stop_row), flush=True)
                        if not stop_row["passed"]:
                            raise ValueError("Stop check failed")
                        # Stop stays latched. Leave the second lab window for manual cleanup.
                        break
            remaining = chat.desktop.inventory()
            preserved = baseline_refs <= {r["window_ref"] for r in remaining}
            passed = len(rows) == 10 and all(r["passed"] for r in rows) and preserved
    except Exception as exc:
        rows.append({"case_id": "lab-blocked", "passed": False, "error_type": type(exc).__name__})
        print("Lab paused. Inspect any remaining lab window manually; no replay.", flush=True)
    finally:
        report = {
            "version": "applications-native-lab-v1",
            "execution_mode": "windows",
            "status": "passed" if passed else "failed",
            "metadata": metadata,
            "cases": rows,
            "preexisting_window_count": len(baseline),
            "remaining_lab_windows": len(remaining) - len(baseline),
            "model_report": args.model_report.name,
            "journal_retained": True,
            "qualification": "attended two application launch types; not all installed apps",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        broker.store.close()
        model.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
