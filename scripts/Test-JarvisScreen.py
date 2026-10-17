"""Explicit attended real capture + local-model test through JARVIS Conversation.

Only a newly owned synthetic fixture is displayed/captured. No everyday windows,
accounts, desktop control, downloads or public network requests are used.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from jarvis.bootstrap import build, load_profile
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import Denied, State
from jarvis.screen_data import load_config
from jarvis.screen_tools import attach
from jarvis.win_stop import StopHotkey


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", action="store_true", required=True)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--screen-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--watch-only",
        action="store_true",
        help="Separate native watching test; not recognition qualification",
    )
    parser.add_argument(
        "--interactive-watch",
        action="store_true",
        help="Wait up to two minutes for operator focus of the owned fixture",
    )
    parser.add_argument(
        "--watch-check",
        action="store_true",
        help="Bounded watching/exclusion test on the same owned fixture",
    )
    parser.add_argument(
        "--interactive-stop",
        action="store_true",
        help="Wait for the physical global-stop hotkey before closing the fixture",
    )
    parser.add_argument(
        "--plant-image",
        type=Path,
        help="Explicit public test PNG displayed only in the owned fixture",
    )
    parser.add_argument(
        "--capture-only",
        action="store_true",
        help="Explicit scripted vision fixture; validates native capture, not recognition",
    )
    args = parser.parse_args()
    if os.name != "nt" or args.report.exists():
        parser.error("Windows and a new, unused report filename are required")
    config = load_config(args.screen_config)
    if not config.enabled:
        parser.error("An enabled, explicitly selected screen config is required")
    profile = load_profile(args.profile, allow_ollama=True)
    report = {
        "milestone": "M5",
        "status": "NOT FULLY VERIFIED",
        "synthetic_content_only": args.plant_image is None,
        "private_user_content_captured": False,
        "windows": sys.getwindowsversion().build,
        "cases": [],
        "capture_method": "Win32 GDI visible pixels / per-monitor-v2",
        "plant_photograph": "NOT RUN; illustration does not establish photograph recognition",
        "watching_native": "NOT RUN",
        "physical_stop": "NOT RUN",
    }
    fixture = None
    screen = broker = None
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    private.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="screen-lab-", dir=private) as temporary:
            broker = build(Path(temporary) / "journal.sqlite", profile)
            if args.capture_only:
                from jarvis.screen_fake import FakeVision

                screen = attach(broker, config, vision=FakeVision())
                report["vision_mode"] = "explicit scripted fixture; NOT real-model recognition"
            else:
                screen = attach(broker, config)
                report["vision_mode"] = "real local model"
            screen.notice = lambda message: print(message, flush=True)
            # Inspect capabilities before creating or capturing a test window.
            metadata = screen.vision.inspect(lambda: False, time.time() + 30)
            report["vision"] = metadata
            fixture_command = [sys.executable, "-m", "jarvis.screen_fixture"]
            if args.plant_image:
                fixture_command.append(str(args.plant_image))
                report["plant_photograph"] = "Explicit operator-selected public test image"
            fixture = subprocess.Popen(
                fixture_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                shell=False,
                creationflags=0x08000000,
            )
            lines = queue.Queue(maxsize=8)

            def read():
                for line in fixture.stdout:
                    lines.put(json.loads(line))

            threading.Thread(target=read, daemon=True).start()
            hwnd = lines.get(timeout=10)["hwnd"]
            targets = screen.capture.inventory()
            target = next(t for t in targets if t.kind == "window" and t.native["hwnd"] == hwnd)
            screen.selected = target  # Consent covers only this owned synthetic window.
            conversation = Conversation(broker)
            with StopHotkey(broker.desktop.stop):
                broker.cancel_requested = broker.desktop.stop.is_set
                cases = [
                    ("error", "What does this error mean?"),
                    ("plant", "What is this plant?"),
                    ("wordle", "Help me solve this Wordle."),
                    ("wordle-next", "I entered another guess. Check again."),
                ]
                if args.watch_only:
                    cases = []
                for scene, question in cases:
                    fixture.stdin.write(scene + "\n")
                    fixture.stdin.flush()
                    if lines.get(timeout=5) != {"shown": scene}:
                        raise ValueError("Fixture state did not match")
                    start = time.perf_counter()
                    result = conversation.submit(question)
                    case = {
                        "scene": scene,
                        "request": question,
                        "state": result.state,
                        "answer": conversational_text(result),
                        "seconds": round(time.perf_counter() - start, 3),
                        "timings": dict(screen.timings),
                        "capture_error": getattr(screen.capture, "last_error", None),
                        "observation": screen.observation.model_dump(mode="json")
                        if result.state == State.SUCCEEDED and screen.observation
                        else None,
                    }
                    if not args.capture_only:
                        import re

                        observation = (
                            screen.observation if result.state == State.SUCCEEDED else None
                        )
                        if scene == "error":
                            case["content_check"] = bool(
                                observation
                                and "pandas"
                                in (
                                    observation.interpretation.description
                                    + " ".join(observation.interpretation.visible_text)
                                ).casefold()
                            )
                        elif scene.startswith("wordle"):
                            from jarvis.wordle import feedback

                            board = observation.interpretation.wordle if observation else None
                            expected = ["crane"] + (["slate"] if scene == "wordle-next" else [])
                            case["content_check"] = bool(
                                board
                                and [row.letters for row in board.guesses] == expected
                                and [row.feedback for row in board.guesses]
                                == [feedback("apple", w) for w in expected]
                            )
                            proposed = re.search(r"Try ([A-Z]{5})", case["answer"])
                            case["solver_check"] = bool(
                                proposed
                                and all(
                                    feedback(proposed[1].lower(), word) == feedback("apple", word)
                                    for word in expected
                                )
                            )
                        else:
                            case["content_check"] = "MANUAL REVIEW REQUIRED"
                    report["cases"].append(case)
                    print(json.dumps(case), flush=True)
                    if result.state != State.SUCCEEDED:
                        break
                if args.watch_check or args.watch_only:
                    if args.watch_only:
                        fixture.stdin.write("wordle-next\n")
                        fixture.stdin.flush()
                        assert lines.get(timeout=5) == {"shown": "wordle-next"}
                    fixture.stdin.write("focus\n")
                    fixture.stdin.flush()
                    focused = lines.get(timeout=5).get("foreground") is True
                    if args.interactive_watch:
                        screen.indicator.start()
                        print(
                            "WAITING_FOR_FIXTURE_FOCUS: reply ready, then click "
                            "the owned fixture and leave it focused",
                            flush=True,
                        )
                        acknowledgement = queue.Queue(maxsize=1)
                        threading.Thread(
                            target=lambda: acknowledgement.put(sys.stdin.readline()), daemon=True
                        ).start()
                        acknowledgement.get(timeout=120)
                        focused = False
                        deadline = time.monotonic() + 120
                        while time.monotonic() < deadline and not broker.desktop.stop.is_set():
                            try:
                                focused = screen.capture.foreground().identity == target.identity
                            except (ValueError, Denied):
                                focused = False
                            if focused:
                                break
                            time.sleep(0.2)
                    if focused:
                        screen.config = screen.config.model_copy(
                            update={
                                "watch_enabled": True,
                                "watch_seconds": 45,
                                "sample_seconds": 5,
                                "max_samples": 3,
                            }
                        )
                        print(screen.control("/screen-watch"), flush=True)
                        progress = None
                        change_sent = False
                        latest = {}
                        while screen.watching:
                            screen.poll()
                            if screen.watching:
                                latest = dict(screen.watching)
                                if latest["samples"] >= 2 and not change_sent:
                                    fixture.stdin.write("error\n")
                                    fixture.stdin.flush()
                                    assert lines.get(timeout=5) == {"shown": "error"}
                                    change_sent = True
                                if latest["samples"] != progress:
                                    print("Watch samples=" + str(latest["samples"]), flush=True)
                                    progress = latest["samples"]
                            time.sleep(0.05)
                        report["watching_native"] = {
                            "samples": latest.get("samples", 0),
                            "changes": latest.get("changes", 0),
                            "stopped_at_bound": screen.watching is None,
                            "changed_scene_requested": change_sent,
                        }
                    else:
                        report["watching_native"] = "NOT RUN; Windows did not grant foreground"
                    from jarvis.screen_capture import WindowsCapture

                    saved_capture = screen.capture
                    screen.capture = WindowsCapture(
                        config.model_copy(
                            update={"excluded_executables": ["python.exe", "pythonw.exe"]}
                        )
                    )
                    excluded = conversation.submit("What am I looking at?")
                    report["excluded_owned_window"] = {
                        "state": excluded.state,
                        "capture_generation": screen.capture.generation,
                        "code": screen.capture.last_error,
                    }
                    screen.capture = saved_capture
                if args.interactive_stop:
                    print(
                        "WAITING_FOR_GLOBAL_STOP: focus the owned fixture "
                        "and press Ctrl+Alt+Shift+F10",
                        flush=True,
                    )
                    deadline = time.monotonic() + 120
                    before = screen.capture.generation
                    while time.monotonic() < deadline and not broker.desktop.stop.is_set():
                        time.sleep(0.05)
                    if broker.desktop.stop.is_set():
                        cancelled = conversation.submit("What am I looking at?")
                        report["physical_stop"] = {
                            "state": cancelled.state,
                            "zero_new_captures": screen.capture.generation == before,
                        }
                    else:
                        report["physical_stop"] = "FAILED; no hotkey within the bounded wait"
            report["pipeline_passed"] = len(report["cases"]) == 4 and all(
                c["state"] == State.SUCCEEDED for c in report["cases"]
            )
            report["manual_answer_review"] = (
                "REQUIRED; successful dispatch is not recognition accuracy"
            )
            if not args.capture_only:
                report["wordle_recognition_passed"] = (
                    all(
                        case.get("content_check") is True and case.get("solver_check") is True
                        for case in report["cases"]
                        if case["scene"].startswith("wordle")
                    )
                    and len(report["cases"]) == 4
                )
            screen.close()
            broker.store.close()
            broker.provider.close()
            broker = None
    except Exception as exc:
        report["failure_category"] = type(exc).__name__
        report["capture_error"] = getattr(screen.capture, "last_error", None) if screen else None
        report["pipeline_passed"] = False
    finally:
        if screen:
            screen.close()
        if broker:
            broker.store.close()
            broker.provider.close()
        if fixture:
            if fixture.poll() is None:
                fixture.stdin.write("quit\n")
                fixture.stdin.flush()
                try:
                    fixture.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    fixture.terminate()  # Only our synthetic display process.
            fixture.stdin.close()
            fixture.stdout.close()
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    passed = report.get("pipeline_passed") and (
        args.capture_only or report.get("wordle_recognition_passed")
    )
    if args.watch_only:
        watch = report.get("watching_native", {})
        passed = (
            isinstance(watch, dict)
            and watch.get("samples", 0) >= 3
            and (watch.get("changes", 0) >= 1 and watch.get("stopped_at_bound") is True)
        )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
