"""Opt-in native orb lab. Only an owned synthetic fixture is ever captured."""

import argparse
import ctypes as C
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes as W
from pathlib import Path


def fixture():
    import tkinter as tk

    from jarvis.companion_windows import function

    user = C.WinDLL("user32")
    function(user, "SetThreadDpiAwarenessContext", C.c_void_p, C.c_void_p)(C.c_void_p(-4))
    root = tk.Tk()
    root.title("JARVIS companion lab · synthetic content only")
    root.attributes("-topmost", True)
    work = W.RECT()
    function(user, "SystemParametersInfoW", W.BOOL, W.UINT, W.UINT, C.c_void_p, W.UINT)(
        0x30, 0, C.byref(work), 0
    )
    root.geometry(f"620x340+{work.right - 640}+{work.bottom - 380}")
    canvas = tk.Canvas(root, bg="#eeeeF2", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        24,
        30,
        anchor="nw",
        text="JARVIS orb lab — synthetic content only",
        font=("Segoe UI", 15),
        fill="#77808f",
    )
    canvas.create_text(
        24,
        70,
        anchor="nw",
        text="Click through the orb and type JARVIS when prompted.",
        font=("Segoe UI", 11),
        fill="#77808f",
    )
    inputs = {"clicks": 0, "keys": 0}

    def clicked(event):
        inputs["clicks"] += 1
        print(json.dumps(inputs), flush=True)

    def typed(event):
        inputs["keys"] += 1
        print(json.dumps(inputs), flush=True)

    root.bind_all("<Button-1>", clicked)
    root.bind_all("<KeyPress>", typed)
    messages = queue.Queue(maxsize=32)

    def read():
        for line in sys.stdin:
            messages.put(line.strip())

    threading.Thread(target=read, daemon=True).start()

    def tick():
        try:
            message = messages.get_nowait()
            if message == "quit":
                root.destroy()
                return
            if message in {"light", "dark"}:
                canvas.configure(bg="#eeeeF2" if message == "light" else "#121721")
                print(json.dumps({"shown": message}), flush=True)
        except queue.Empty:
            pass
        root.after(20, tick)

    root.update()
    hwnd = function(user, "GetAncestor", W.HWND, W.HWND, W.UINT)(root.winfo_id(), 2)
    function(user, "SetForegroundWindow", W.BOOL, W.HWND)(hwnd)
    print(json.dumps({"hwnd": int(hwnd)}), flush=True)
    root.after(20, tick)
    root.mainloop()


def main():
    from jarvis.bootstrap import build, load_profile
    from jarvis.companion_windows import function
    from jarvis.conversation import Conversation
    from jarvis.screen_capture import CaptureIndicator, WindowsCapture
    from jarvis.screen_data import load_config
    from jarvis.screen_fake import FakeVision
    from jarvis.screen_tools import attach
    from jarvis.win_stop import StopHotkey

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", action="store_true", required=True)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--screen-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt" or args.report.exists():
        parser.error("Windows and a new report filename are required")
    report = {
        "fixture_only": True,
        "private_desktop_captured": False,
        "checks": {},
        "status": "NOT FULLY VERIFIED",
    }
    child = indicator = broker = screen = None
    try:
        config = load_config(args.screen_config)
        child = subprocess.Popen(
            [sys.executable, __file__, "--fixture"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=0x08000000,
        )
        lines = queue.Queue(maxsize=64)

        def read():
            for line in child.stdout:
                lines.put(json.loads(line))

        threading.Thread(target=read, daemon=True).start()
        hwnd = lines.get(timeout=10)["hwnd"]
        capture = WindowsCapture(config)
        target = next(
            t for t in capture.inventory() if t.kind == "window" and t.native["hwnd"] == hwnd
        )
        user = C.WinDLL("user32")
        foreground = function(user, "GetForegroundWindow", W.HWND)
        is_visible = function(user, "IsWindowVisible", W.BOOL, W.HWND)
        for scene in ("light", "dark"):
            child.stdin.write(scene + "\n")
            child.stdin.flush()
            assert lines.get(timeout=5) == {"shown": scene}
            time.sleep(0.1)
            baseline = capture.capture(target, lambda: False)
            previous = foreground()
            indicator = CaptureIndicator(config.companion)
            indicator.start()
            indicator.update("capturing", scene, target.bounds)
            time.sleep(0.6)
            details = indicator.update("probe")
            report["last_overlay_metadata"] = details
            report["last_indicator_pid"] = indicator.pid
            overlay_hwnd = details["hwnd"]
            frame = capture.capture(
                target, lambda current=indicator: not current.alive, indicator.pid
            )
            x, y, edge = details["position"]
            below = function(user, "WindowFromPoint", W.HWND, W.POINT)(
                W.POINT(x + edge // 2, y + edge // 2)
            )
            ancestor = function(user, "GetAncestor", W.HWND, W.HWND, W.UINT)(below, 2)
            report["checks"][scene] = {
                "orb_visible": bool(is_visible(overlay_hwnd)),
                "focus_unchanged": foreground() == previous,
                "hit_test_reaches_fixture": ancestor == hwnd,
                "capture_exclusion_verified": details["excluded"]
                and frame.pixel_digest == baseline.pixel_digest,
                "metadata": details,
            }
            indicator.update("analyzing", scene, target.bounds)
            time.sleep(0.5)
            indicator.update("completed", scene, target.bounds)
            indicator.close()
            indicator = None
            report["checks"][scene]["destroyed"] = not bool(
                function(user, "IsWindow", W.BOOL, W.HWND)(overlay_hwnd)
            )
        stop = threading.Event()
        with tempfile.TemporaryDirectory(
            prefix="companion-lab-", dir=args.screen_config.parent
        ) as d:
            broker = build(
                Path(d) / "journal.sqlite", load_profile(args.profile, allow_ollama=True)
            )
            screen = attach(broker, config)
            screen.selected = target
            events = []
            notices = []
            screen.notice = notices.append
            original = screen.indicator.update

            def update(event, *values, **kw):
                result = original(event, *values, **kw)
                events.append(event)
                return result

            screen.indicator.update = update
            broker.cancel_requested = stop.is_set
            with StopHotkey(stop):
                result = Conversation(broker).submit("What am I looking at?")
                report["checks"]["real_m5"] = {
                    "state": result.state,
                    "events": events[:],
                    "timings": dict(screen.timings),
                    "real_local_vision": True,
                }
                # Actual bounded native watching, explicitly scripted interpretation.
                screen.vision = FakeVision()
                screen.config = config.model_copy(
                    update={
                        "watch_enabled": True,
                        "watch_seconds": 25,
                        "sample_seconds": 5,
                        "max_samples": 2,
                    }
                )
                function(user, "SetForegroundWindow", W.BOOL, W.HWND)(hwnd)
                deadline = time.monotonic() + 60
                if foreground() != hwnd:
                    print("WAITING_FOR_WATCH_FOCUS: click the synthetic orb lab window", flush=True)
                while foreground() != hwnd and time.monotonic() < deadline:
                    time.sleep(0.1)
                report["checks"]["watch_foreground_ready"] = foreground() == hwnd
                screen.control("/screen-watch")
                last = 0
                start = time.monotonic()
                while screen.watching and time.monotonic() - start < 26:
                    screen.poll()
                    if screen.watching:
                        last = screen.watching["samples"]
                    time.sleep(0.05)
                report["checks"]["watching"] = {
                    "samples": last,
                    "ended": not screen.watching,
                    "scripted_interpretation": True,
                    "events": events[-10:],
                    "notices": notices,
                    "failure": [screen.failure_stage, screen.failure_code],
                }
                if args.interactive:
                    screen.indicator.start()
                    screen.indicator.update("watching", "input-lab", target.bounds)
                    print(
                        "WAITING_FOR_CLICK_AND_KEYS: click through the orb, type JARVIS", flush=True
                    )
                    deadline = time.monotonic() + 120
                    inputs = {"clicks": 0, "keys": 0}
                    while time.monotonic() < deadline and not stop.is_set():
                        try:
                            inputs.update(lines.get(timeout=0.1))
                        except queue.Empty:
                            pass
                        if inputs.get("clicks", 0) and inputs.get("keys", 0) >= 3:
                            break
                    report["checks"]["physical_input"] = inputs
                    print(
                        "WAITING_FOR_GLOBAL_STOP: focus fixture, press Ctrl+Alt+Shift+F10",
                        flush=True,
                    )
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline and not stop.is_set():
                        time.sleep(0.05)
                    before = screen.capture.generation
                    cancelled = screen.submit("What am I looking at?") if stop.is_set() else None
                    screen.indicator.update("cancelled", "input-lab", target.bounds)
                    screen.close()
                    report["checks"]["stop"] = {
                        "physical_hotkey": stop.is_set(),
                        "state": cancelled.state if cancelled else None,
                        "zero_new_captures": screen.capture.generation == before,
                        "overlay_process_ended": not screen.indicator.alive,
                    }
            screen.close()
            broker.store.close()
            broker.provider.close()
            broker = None
        report["status"] = "REVIEW REQUIRED"
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        report["capture_error"] = getattr(locals().get("capture"), "last_error", None)
    finally:
        if indicator:
            indicator.close()
        if screen:
            screen.close()
        if broker:
            broker.store.close()
            broker.provider.close()
        if child:
            if child.poll() is None:
                child.stdin.write("quit\n")
                child.stdin.flush()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.terminate()
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report), "status": report["status"]}), flush=True)
    return 0 if report["status"] == "REVIEW REQUIRED" else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--fixture"]:
        fixture()
    else:
        raise SystemExit(main())
