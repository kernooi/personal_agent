"""Explicit attended minimize lab; local model and selected real Notepad only."""

import argparse
import ctypes
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.domain import State, UserRequest
from jarvis.m2_evaluation import qualified
from jarvis.notepad import clean
from jarvis.ollama import OllamaProvider
from jarvis.win_stop import StopHotkey


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--conversation-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report preserved; choose an unused filename")
    clock = SystemClock()
    profile = load_profile(args.profile, allow_ollama=True)
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    if not (
        qualified(args.model_report, profile, metadata)
        and qualified(args.conversation_report, profile, metadata, conversation=True)
    ):
        model.close()
        parser.error("Matching minimize model and conversation qualification required")
    directory = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    journal = directory / ("minimize-lab-" + uuid4().hex + ".sqlite")
    broker = build(
        journal,
        profile,
        clock,
        provider=model,
        real=True,
        registration=args.registration,
        attended=args.attended,
    )
    broker.cancel_requested = broker.desktop.stop.is_set
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.IsIconic.argtypes = [ctypes.c_void_p]
    user.IsIconic.restype = ctypes.c_bool
    user.GetForegroundWindow.restype = ctypes.c_void_p
    rows = []
    passed = False
    preserved = False
    baseline = []
    try:
        with StopHotkey(broker.desktop.stop):
            baseline = broker.desktop.inventory()
            baseline_refs = {r["window_ref"] for r in baseline}
            print(
                "Attended: one new disposable Notepad; pre-existing windows excluded.", flush=True
            )
            ref = ""
            for case, text in [
                ("open", "open notepad"),
                ("minimize", "minimize notepad"),
                ("repeat", "minimize it"),
                ("restore", "bring it to the front"),
                ("close", "close notepad"),
            ]:
                if case == "close":
                    broker.desktop.select(ref, confirm_disposable=True)
                started = time.monotonic()
                result = broker.converse(UserRequest(case, broker.grant.session, text))
                row = {
                    "case_id": case,
                    "state": result.state,
                    "latency_seconds": round(time.monotonic() - started, 3),
                    "message": result.message,
                    "passed": result.state == State.SUCCEEDED,
                }
                if case == "open" and row["passed"]:
                    ref = broker.desktop.selected_ref
                    row["passed"] = bool(
                        ref and ref not in baseline_refs and clean(broker.desktop.windows[ref])
                    )
                elif case in {"minimize", "repeat", "restore"}:
                    hwnd = broker.desktop.windows[ref]["hwnd"]
                    row["independent_is_iconic"] = bool(user.IsIconic(hwnd))
                    row["passed"] = row["passed"] and row["independent_is_iconic"] == (
                        case != "restore"
                    )
                    if case == "restore":
                        row["independent_foreground_matches"] = user.GetForegroundWindow() == hwnd
                        row["passed"] = row["passed"] and row["independent_foreground_matches"]
                rows.append(row)
                print(json.dumps(row), flush=True)
                if not row["passed"]:
                    break
            remaining = broker.desktop.inventory()
            preserved = baseline_refs <= {r["window_ref"] for r in remaining}
            passed = len(rows) == 5 and all(r["passed"] for r in rows) and preserved
    except Exception as exc:
        rows.append({"case_id": "lab-blocked", "passed": False, "error_type": type(exc).__name__})
        print("Test paused; review any remaining test window manually.", flush=True)
    finally:
        report = {
            "version": "m2-minimize-native-lab-v1",
            "execution_mode": "windows",
            "provider": "ollama",
            "status": "passed" if passed else "failed",
            "metadata": metadata,
            "cases": rows,
            "preexisting_window_count": len(baseline),
            "preexisting_preserved": preserved,
            "model_report": args.model_report.name,
            "conversation_report": args.conversation_report.name,
            "notepad_version": broker.desktop.transport.registration.notepad_version,
            "journal_retained": True,
            "qualification": "attended bounded minimize and restore only",
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
