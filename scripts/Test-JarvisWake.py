"""Attended wake/orb/ack/command lab. No app, media, screen or chat-model tools."""

import argparse
import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

from jarvis.voice_data import load_config
from jarvis.voice_presentation import PREFIX, VoicePresentation
from jarvis.voice_runtime import AudioJobs
from jarvis.win_stop import StopHotkey


def question_diagnostic(text):
    """Compare only the fixed synthetic fixture; never return recognized words."""
    if text.strip(" .!?").casefold() == "what is your name":
        return "EXACT"
    words = re.findall(r"[a-z]+(?:['’][a-z]+)?", text.casefold())
    expected = ["what", "is", "your", "name"]
    if words == expected:
        return "FORMATTING_DIFFERENCE"
    if words in [["what's", "your", "name"], ["what’s", "your", "name"], ["whats", "your", "name"]]:
        return "CONTRACTION_VARIANT"
    if words and any(words == expected[start:] for start in range(1, len(expected))):
        return "LEADING_WORDS_MISSING"
    if words and any(words == expected[:end] for end in range(1, len(expected))):
        return "TRAILING_WORDS_MISSING"
    if any(words[start : start + 4] == expected for start in range(len(words))):
        return "EXTRA_WORDS"
    return "OTHER_MISMATCH"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved; choose a new report filename")
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    config = load_config(private).model_copy(
        update={
            "interaction_mode": "wake_word",
            "wake_provider": "windows_sapi",
            "wake_session_seconds": 90,
        }
    )
    stop, frames = threading.Event(), queue.Queue(maxsize=32)
    presentation = VoicePresentation(
        SimpleNamespace(screen=None, desktop=SimpleNamespace(stop=stop))
    )
    jobs = AudioJobs(private)
    report = {
        "version": "m6-attended-wake-v1",
        "status": "NOT FULLY VERIFIED",
        "started_at": time.time(),
        "states": [],
        "diagnostics": [],
        "expected_command_recognized": False,
        "command_uncertain": None,
        "command_audio_seconds": None,
        "question_diagnostic": None,
        "microphone_started_seconds": None,
        "maximum_wake_input_level": 0,
        "acknowledgement_seconds": None,
        "speech_started_seconds": None,
        "command_input_ready_seconds": None,
        "app_media_screen_actions": 0,
        "chat_model_calls": 0,
        "audio_or_transcripts_saved": False,
        "audibility": "OPERATOR CONFIRMATION REQUIRED",
    }
    started = time.monotonic()
    closing = [False]
    root = tk.Tk()
    root.title("JARVIS attended wake test")
    root.geometry("740x560")
    root.configure(bg="#1c2533")
    tk.Label(
        root, text="Wake response test", bg="#1c2533", fg="#e8edf5", font=("Segoe UI", 19, "bold")
    ).pack(pady=(20, 10))
    tk.Label(
        root,
        text=f"When the green message appears, say “{config.wake_call}”.\n"
        "Wait for “Yes sir”, then say “What is your name?”\n\n"
        "This checks transcription only; no chat answer or tools run.\n"
        "Your recognized question appears here, but is not saved.\n"
        "Stop / Esc / Ctrl+Alt+Shift+F10 cancels this test.",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 11),
        wraplength=570,
    ).pack(padx=20)
    label = tk.Label(
        root,
        text="Starting microphone — please wait…",
        bg="#1c2533",
        fg="#a5baff",
        font=("Segoe UI", 17, "bold"),
        wraplength=620,
    )
    label.pack(pady=15)
    activity = tk.Label(root, text="", bg="#1c2533", fg="#c0ccdc", font=("Segoe UI", 11))
    activity.pack(pady=5)
    recognized = tk.Label(
        root,
        text="Recognized question: waiting…",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 12),
        wraplength=680,
    )
    recognized.pack(padx=20, pady=10)
    heard_ack, saw_orb = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
    for text, variable in (
        ("I heard ‘Yes sir’", heard_ack),
        ("I saw the orb", saw_orb),
    ):
        tk.Checkbutton(
            root,
            text=text,
            variable=variable,
            bg="#1c2533",
            fg="#e8edf5",
            selectcolor="#1c2533",
            activebackground="#1c2533",
            activeforeground="#e8edf5",
        ).pack(anchor="w", padx=35)

    def present():
        sequence = 0
        try:
            while True:
                state = frames.get()
                if state is None:
                    return
                sequence += 1
                presentation(PREFIX + json.dumps({"sequence": sequence, "state": state}))
        finally:
            presentation.close()

    presenter = threading.Thread(target=present, daemon=True)
    presenter.start()

    def finish():
        if closing[0]:
            return
        closing[0] = True
        stop.set()
        jobs.close()
        root.after(200, wait_closed)

    def wait_closed():
        if jobs.active:
            root.after(100, wait_closed)
            return
        report["ended_at"] = time.time()
        report["operator_heard_acknowledgement"] = heard_ack.get()
        report["operator_saw_orb"] = saw_orb.get()
        if heard_ack.get():
            report["audibility"] = "OPERATOR CONFIRMED ACKNOWLEDGEMENT"
            if report["status"] == "NATIVE FLOW OBSERVED; AUDIBILITY PENDING":
                report["status"] = "NATIVE FLOW OBSERVED; AUDIBILITY CONFIRMED"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
        frames.put(None, timeout=1)
        root.destroy()

    def poll():
        if closing[0]:
            return
        for _ in range(32):
            try:
                _, event = jobs.events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("kind")
            if kind == "stage":
                state = event["state"]
                report["states"].append(state)
                print("Wake lab state: " + state, flush=True)
                instructions = {
                    "WAKE_LISTENING": f"Listening — say “{config.wake_call}” now",
                    "WAKE_ACKNOWLEDGING": "Wake call detected — wait for “Yes sir”",
                    "SPEAKING": "Speaking “Yes sir” — please wait",
                    "LISTENING": "Listening for your question…",
                    "TRANSCRIBING": "Checking your question locally…",
                }
                label.configure(
                    text=instructions.get(state, state.replace("_", " ").title()),
                    fg="#8fdfb0" if state in {"WAKE_LISTENING", "LISTENING"} else "#a5baff",
                )
                frames.put_nowait(state)
                timing = {
                    "WAKE_LISTENING": "microphone_started_seconds",
                    "WAKE_ACKNOWLEDGING": "acknowledgement_seconds",
                    "SPEAKING": "speech_started_seconds",
                }.get(state)
                if timing and report[timing] is None:
                    report[timing] = round(time.monotonic() - started, 3)
            elif kind == "wake_status":
                report["diagnostics"].append(event["status"])
                activity.configure(text="Not recognized clearly — try the wake call again")
                print("Wake lab status: " + event["status"], flush=True)
            elif kind == "wake_level":
                level = event["value"]
                report["maximum_wake_input_level"] = max(report["maximum_wake_input_level"], level)
                activity.configure(text=f"Microphone activity: {level}/100")
            elif kind == "wake_ready":
                report["command_input_ready_seconds"] = event.get("metrics", {}).get(
                    "command_input_ready_seconds"
                )
                label.configure(text="Say “What is your name?” now", fg="#8fdfb0")
            elif kind == "error":
                report["error"] = event
                label.configure(text=event["code"])
                print("Wake lab error: " + event["code"], flush=True)
            elif kind == "transcript":
                transcript = event["transcript"]
                report["expected_command_recognized"] = (
                    transcript["text"].strip(" .!?").casefold() == "what is your name"
                )
                report["command_uncertain"] = transcript["uncertain"]
                report["command_audio_seconds"] = transcript["seconds"]
                report["question_diagnostic"] = question_diagnostic(transcript["text"])
                # Transient operator inspection only; never print or save text.
                recognized.configure(text="Recognized question: “" + transcript["text"][:512] + "”")
            elif kind == "finished":
                if (
                    report["expected_command_recognized"]
                    and not report["command_uncertain"]
                    and "SPEAKING" in report["states"]
                    and "error" not in report
                ):
                    report["status"] = "NATIVE FLOW OBSERVED; AUDIBILITY PENDING"
                label.configure(
                    text=(
                        "Exact test phrase matched"
                        if report["expected_command_recognized"]
                        else "Test incomplete — inspect the recognized question"
                    ),
                    fg="#8fdfb0" if report["expected_command_recognized"] else "#f0c582",
                )
                activity.configure(text="Microphone off. Check what you observed, then Finish.")
                frames.put_nowait("IDLE")
        if stop.is_set() or time.monotonic() - started > 180:
            finish()
            return
        root.after(40, poll)

    root.protocol("WM_DELETE_WINDOW", finish)
    root.bind("<Escape>", lambda _: finish())
    tk.Button(root, text="Finish / stop test", command=finish).pack(pady=10)
    try:
        with StopHotkey(stop):
            jobs.start("wake", config)
            root.after(40, poll)
            root.mainloop()
    finally:
        stop.set()
        jobs.close()
        try:
            frames.put_nowait(None)
        except queue.Full:
            pass
        presenter.join(timeout=3)
        if presenter.is_alive():
            presentation.close()


if __name__ == "__main__":
    main()
