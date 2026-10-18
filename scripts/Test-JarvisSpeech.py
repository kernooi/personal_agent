"""Attended speaker-only preview using the real owned voice worker. No microphone/tools."""

import argparse
import json
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path

from jarvis.voice_data import load_config
from jarvis.voice_runtime import AudioJobs
from jarvis.win_stop import StopHotkey

SAMPLE = "Yes sir. Hello, I am Jarvis. How can I help you today?"
STOP_SAMPLE = ("This is a local speech interruption check. Press Stop now to end this reply. ") * 10


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved; choose a new report filename")
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    config = load_config(private)
    jobs, global_stop = AudioJobs(private), threading.Event()
    root = tk.Tk()
    root.title("JARVIS local voice preview · microphone off")
    root.geometry("660x420")
    root.configure(bg="#1c2533")
    report = {
        "version": "m6-neural-speech-preview-v1",
        "tts_provider": config.tts_provider,
        "voice": config.neural_voice,
        "microphone_opened": False,
        "app_media_screen_actions": 0,
        "audio_or_transcripts_saved": False,
        "runs": [],
        "status": "NOT FULLY VERIFIED",
    }
    closing, phase, launched = [False], [None], time.monotonic()
    heard, stopped = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
    tk.Label(
        root,
        text="Michael · American English",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 20, "bold"),
    ).pack(pady=18)
    tk.Label(
        root,
        text="Listen to the sample. Then run the Stop check and press Stop\n"
        "while it is speaking. Check what you actually heard, then Finish.\n"
        "Your microphone stays off. Esc / Ctrl+Alt+Shift+F10 stops audio.",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 11),
    ).pack(pady=8)
    label = tk.Label(
        root, text="Preparing the sample…", bg="#1c2533", fg="#a5baff", font=("Segoe UI", 14)
    )
    label.pack(pady=10)

    def play(kind):
        if jobs.active or closing[0] or global_stop.is_set():
            return
        phase[0] = {
            "kind": kind,
            "playback_started": False,
            "completed": False,
            "stop_requested": False,
        }
        report["runs"].append(phase[0])
        label.configure(text="Preparing speech locally…")
        jobs.start("speak", config, SAMPLE if kind == "preview" else STOP_SAMPLE)

    def stop():
        if jobs.active:
            if phase[0] is not None:
                phase[0]["stop_requested"] = True
                phase[0]["stop_at"] = time.monotonic()
            jobs.cancel()
            label.configure(text="Stopping speech…")

    def finish():
        if not closing[0]:
            closing[0] = True
            jobs.close()
            root.after(50, save)

    def save():
        if jobs.active:
            root.after(50, save)
            return
        report["operator_heard_clear_voice"] = heard.get()
        report["operator_heard_audio_stop"] = stopped.get()
        if (
            heard.get()
            and stopped.get()
            and any(r["completed"] for r in report["runs"])
            and any(
                r.get("stopped_worker_seconds") is not None and r["playback_started"]
                for r in report["runs"]
            )
            and not any(r.get("errors") for r in report["runs"])
        ):
            report["status"] = "SPEAKER PREVIEW AND STOP OBSERVED; OPERATOR CONFIRMED"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
        root.destroy()

    def poll():
        if closing[0]:
            return
        if global_stop.is_set():
            stop()
        for _ in range(32):
            try:
                _, event = jobs.events.get_nowait()
            except queue.Empty:
                break
            if phase[0] is None:
                continue
            if event["kind"] == "stage" and event.get("state") == "SPEAKING":
                phase[0]["playback_started"] = True
                label.configure(text="Speaking · press Stop during the Stop check")
            elif event["kind"] == "done":
                phase[0]["completed"] = True
                phase[0]["metrics"] = event.get("metrics", {})
            elif event["kind"] == "error":
                phase[0].setdefault("errors", []).append(event["code"])
                label.configure(text=event["code"])
            elif event["kind"] == "finished":
                if phase[0].get("stop_at") is not None:
                    phase[0]["stopped_worker_seconds"] = round(
                        time.monotonic() - phase[0].pop("stop_at"), 3
                    )
                if not phase[0].get("errors"):
                    label.configure(
                        text="Audio stopped" if phase[0]["stop_requested"] else "Sample finished"
                    )
        if time.monotonic() - launched >= 180:
            finish()
        else:
            root.after(40, poll)

    buttons = tk.Frame(root, bg="#1c2533")
    buttons.pack(pady=12)
    for text, command in (
        ("Replay sample", lambda: play("preview")),
        ("Run Stop check", lambda: play("stop")),
        ("Stop", stop),
        ("Finish", finish),
    ):
        tk.Button(buttons, text=text, command=command).pack(side="left", padx=5)
    for text, variable in (
        ("I heard Michael clearly", heard),
        ("I heard audio stop when I pressed Stop", stopped),
    ):
        tk.Checkbutton(
            root, text=text, variable=variable, bg="#1c2533", fg="#e8edf5", selectcolor="#1c2533"
        ).pack(anchor="w", padx=35)
    root.bind("<Escape>", lambda _: stop())
    root.protocol("WM_DELETE_WINDOW", finish)
    try:
        with StopHotkey(global_stop):
            root.after(250, lambda: play("preview"))
            root.after(40, poll)
            root.mainloop()
    finally:
        jobs.close()


if __name__ == "__main__":
    main()
