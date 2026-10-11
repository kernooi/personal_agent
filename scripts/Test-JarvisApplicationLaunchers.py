"""Attended launcher regression: only owner-approved, newly opened lab windows."""

import argparse
import ctypes
import json
import os
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from jarvis.application_data import ApplicationsConfig, resolve_app
from jarvis.application_evaluation import qualified
from jarvis.application_tools import attach, identity
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
    parser.add_argument("--apps", nargs="+", default=["Discord", "Spotify", "Notepad"])
    parser.add_argument("--continuation-report", type=Path)
    parser.add_argument("--continuation-journal", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report already exists; preserved")
    clock = SystemClock()
    profile = load_profile(args.profile, allow_ollama=True)
    provider = OllamaProvider(clock)
    metadata = provider.inspect(profile)
    if not qualified(args.model_report, profile, metadata):
        parser.error("Current passed application model qualification required")
    journal = (
        Path(os.environ["LOCALAPPDATA"]) / "Jarvis" / ("launcher-lab-" + uuid4().hex + ".sqlite")
    )
    broker = build(journal, profile, clock, provider=provider)
    native = ctypes.WinDLL("user32")
    for name in ["IsWindow", "IsWindowVisible", "IsIconic"]:
        getattr(native, name).argtypes = [ctypes.c_void_p]
        getattr(native, name).restype = ctypes.c_bool
    native.GetForegroundWindow.restype = ctypes.c_void_p
    cases, baseline, passed = [], [], False
    try:
        chat = attach(broker, ApplicationsConfig(enabled=True), real=True, attended=True)
        broker.cancel_requested = chat.desktop.stop.is_set
        with StopHotkey(chat.desktop.stop):
            baseline = chat.desktop.inventory()
            baseline_refs = {r["window_ref"] for r in baseline}
            apps = [resolve_app(name, list(chat.desktop.apps.values())) for name in args.apps]
            if any(len(a) != 1 for a in apps):
                raise ValueError("Unique installed application required")
            continuing = None
            if args.continuation_report and args.continuation_journal:
                prior = json.loads(args.continuation_report.read_bytes())
                if prior["model_report"] != args.model_report.name or prior["metadata"] != metadata:
                    raise ValueError("Continuation qualification changed")
                blocked = prior["cases"][-2]
                if (
                    blocked.get("application") != "Spotify"
                    or blocked.get("effect") != "close"
                    or blocked.get("state") != "WAITING_INPUT"
                ):
                    raise ValueError("Only a proven pre-admission pause can continue")
                with sqlite3.connect(
                    "file:" + str(args.continuation_journal) + "?mode=ro", uri=True
                ) as old:
                    actions = old.execute(
                        "SELECT prepared_json FROM actions WHERE state='VERIFIED' ORDER BY rowid"
                    ).fetchall()
                    if (
                        len(actions) != 7
                        or old.execute("SELECT 1 FROM actions WHERE state!='VERIFIED'").fetchone()
                    ):
                        raise ValueError("Continuation journal has uncertain effects")
                    expected = json.loads(json.loads(actions[-1][0])["target_identity"])["window"]
                matches = [
                    r
                    for r in baseline
                    if identity(chat.desktop.windows[r["window_ref"]]) == identity(expected)
                ]
                if len(matches) != 1:
                    raise ValueError("Owned continuation window changed")
                continuing = matches[0]["window_ref"]
                baseline_refs.remove(continuing)
                cases.extend(r for r in prior["cases"] if r.get("passed"))
            if any(
                r["app_id"] in {a[0].app_id for a in apps} and r["window_ref"] != continuing
                for r in baseline
            ):
                raise ValueError("Existing target window excluded; manual handling required")
            for candidates in apps:
                app = candidates[0]
                if continuing and app.name == "Discord":
                    continue
                hwnd = None
                operations = [
                    ("open", "open " + app.name),
                    ("minimize", "minimize it"),
                    ("focus", "bring it to the front"),
                    ("close", "close " + app.name),
                ]
                if continuing and app.name == "Spotify":
                    chat.desktop.select(continuing)
                    hwnd = chat.desktop.windows[continuing]["hwnd"]
                    operations = [("close", "close Spotify")]
                for effect, text in operations:
                    start = time.monotonic()
                    result = chat.submit(text)
                    row = {
                        "application": app.name,
                        "effect": effect,
                        "state": result.state,
                        "message": result.message,
                        "seconds": round(time.monotonic() - start, 3),
                        "passed": result.state == State.SUCCEEDED,
                    }
                    if effect == "open" and row["passed"]:
                        ref = chat.desktop.selected_ref
                        window = chat.desktop.windows[ref]
                        hwnd = window["hwnd"]
                        row["runtime_association"] = (window.get("association") or {}).get(
                            "method", "direct"
                        )
                        row["independent_visible"] = bool(native.IsWindowVisible(hwnd))
                        row["passed"] &= ref not in baseline_refs and row["independent_visible"]
                    elif effect == "minimize" and hwnd:
                        row["independent_minimized"] = bool(native.IsIconic(hwnd))
                        row["passed"] &= row["independent_minimized"]
                    elif effect == "focus" and hwnd:
                        row["independent_foreground"] = native.GetForegroundWindow() == hwnd
                        row["passed"] &= row["independent_foreground"]
                    elif effect == "close" and hwnd:
                        row["independent_absent"] = not native.IsWindow(hwnd)
                        row["independent_hidden"] = not native.IsWindowVisible(hwnd)
                        row["passed"] &= row["independent_absent"] or row["independent_hidden"]
                    cases.append(row)
                    print(json.dumps(row), flush=True)
                    if not row["passed"]:
                        raise ValueError("Outcome failed or uncertain; no replay")
            before = broker.store.db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
            chat.desktop.stop.set()
            result = chat.submit("open " + apps[0][0].name)
            after = broker.store.db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
            cases.append(
                {
                    "effect": "cancel-before-admission",
                    "passed": result.state == State.CANCELLED and before == after,
                    "zero_new_admissions": before == after,
                }
            )
            remaining = chat.desktop.inventory()
            preserved = baseline_refs <= {r["window_ref"] for r in remaining}
            passed = (
                len(cases) == 4 * len(apps) + 1 and all(r["passed"] for r in cases) and preserved
            )
    except Exception as exc:
        cases.append({"effect": "lab-paused", "passed": False, "error_type": type(exc).__name__})
        print("Lab paused; inspect the remaining test window manually. No replay.", flush=True)
    finally:
        report = {
            "version": "application-launcher-lab-v1",
            "status": "passed" if passed else "failed",
            "execution_mode": "windows",
            "metadata": metadata,
            "model_report": args.model_report.name,
            "preexisting_windows": len(baseline),
            "cases": cases,
            "journal_retained": True,
            "continuation_of": args.continuation_report.name if args.continuation_report else None,
            "stop_test": "software cancellation; earlier physical global-hotkey evidence retained",
        }
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        broker.store.close()
        provider.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
