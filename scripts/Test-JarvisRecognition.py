"""Attended normal wake/command recognition only. No chat model, app/media/screen tools."""

import argparse
import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path

from jarvis.voice_data import load_config
from jarvis.voice_runtime import AudioJobs
from jarvis.voice_vocabulary import installed_names
from jarvis.win_stop import StopHotkey

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/m6-recognition-corpus-v1.json"


def diagnostic(expected, observed):
    """Fixed categories only; never save words or soften the exact-match gate."""
    reference = re.findall(r"\w+", expected.casefold())
    hypothesis = re.findall(r"\w+", observed.casefold())
    if reference == hypothesis:
        return "EXACT"
    numbers = {"six": "6", "eight": "8"}
    if [numbers.get(w, w) for w in reference] == [numbers.get(w, w) for w in hypothesis]:
        return "NUMBER_FORMAT_ONLY"
    expanded = re.sub(r"\bwhat['’]s\b", "what is", observed.casefold())
    if re.findall(r"\w+", expanded) == reference:
        return "CONTRACTION_ONLY"
    if hypothesis and len(hypothesis) < len(reference):
        if hypothesis == reference[-len(hypothesis) :]:
            return "LEADING_WORDS_MISSING"
        if hypothesis == reference[: len(hypothesis)]:
            return "TRAILING_WORDS_MISSING"
    return "WORDS_DIFFER"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--corpus", choices=["general", "app-spelling"], default="general")
    parser.add_argument(
        "--case",
        action="append",
        choices=[
            "identity",
            "notepad",
            "spotify-song",
            "general-question",
            "negation",
            "youtube",
            "playlist-name",
        ],
    )
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report preserved; choose a new filename")
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    config = load_config(private).model_copy(
        update={"interaction_mode": "wake_word", "wake_session_seconds": 45}
    )
    app_names = installed_names(private) if config.app_name_hints else []
    corpus_path = (
        CORPUS if args.corpus == "general" else CORPUS.with_name("m6-app-spelling-corpus-v1.json")
    )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = corpus["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] in args.case]
    if not cases:
        parser.error("No selected cases in this corpus")
    jobs, stop = AudioJobs(private), threading.Event()
    report = {
        "version": "m6-recognition-attended-v1",
        "corpus_version": corpus["version"],
        "model_directory": config.model_directory,
        "command_pause_seconds": config.wake_silence_seconds,
        "beam_size": config.stt_beam_size,
        "application_name_hint_count": len(app_names),
        "gate": corpus["gate"],
        "scope": "selected diagnostic subset" if args.case else "full frozen corpus",
        "selected_cases": [case["id"] for case in cases],
        "records": [],
        "status": "INCOMPLETE",
        "audio_or_transcripts_saved": False,
        "app_media_screen_actions": 0,
    }
    index, active, closing = [0], [None], [False]
    began = time.monotonic()
    root = tk.Tk()
    root.title("JARVIS recognition check · no actions")
    root.geometry("820x560")
    root.configure(bg="#1c2533")
    tk.Label(
        root,
        text="Voice recognition check",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 20, "bold"),
    ).pack(pady=16)
    tk.Label(
        root,
        text=f"Click Start sentence. When listening, say “{config.wake_call}”.\n"
        "After “Yes sir”, read the sentence below at your normal pace.\n"
        "This only checks recognition. Nothing you say can control applications.\n"
        "Audio and transcripts are not saved. Stop/Esc/global hotkey cancels.",
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 11),
    ).pack(pady=8)
    phrase = tk.Label(
        root,
        text=cases[0]["text"],
        bg="#1c2533",
        fg="#e8edf5",
        font=("Segoe UI", 17),
        wraplength=740,
    )
    phrase.pack(padx=24, pady=16)
    status = tk.Label(
        root,
        text=f"Ready · sentence 1 of {len(cases)}",
        bg="#1c2533",
        fg="#a5baff",
        font=("Segoe UI", 12),
    )
    status.pack(pady=6)
    observed = tk.Label(
        root, text="Recognized: waiting", bg="#1c2533", fg="#e8edf5", wraplength=740
    )
    observed.pack(padx=24, pady=12)

    def start():
        if jobs.active or closing[0] or stop.is_set() or index[0] >= len(cases):
            return
        active[0] = {
            "case": cases[index[0]]["id"],
            "exact": False,
            "uncertain": None,
            "command_input_ready_seconds": None,
            "transcript_received": False,
        }
        report["records"].append(active[0])
        status.configure(text="Starting the selected microphone…")
        button.configure(state="disabled")
        observed.configure(text="Recognized: waiting")
        jobs.start("wake", config, app_names=app_names)

    def finish():
        if closing[0]:
            return
        closing[0] = True
        jobs.close()
        root.after(50, save)

    def save():
        if jobs.active:
            root.after(50, save)
            return
        rows = report["records"]
        report["correct"] = sum(
            row["exact"] and row["uncertain"] is False and not row.get("error") for row in rows
        )
        report["total"] = len(cases)
        report["status"] = (
            "PASSED"
            if report["correct"] == len(cases)
            else "FAILED"
            if len(rows) == len(cases)
            else "INCOMPLETE"
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
        root.destroy()

    def poll():
        if closing[0]:
            return
        for _ in range(32):
            try:
                _, event = jobs.events.get_nowait()
            except queue.Empty:
                break
            if active[0] is None:
                continue
            kind = event["kind"]
            if kind == "stage":
                status.configure(
                    text={
                        "WAKE_LISTENING": f"Say “{config.wake_call}” now",
                        "WAKE_ACKNOWLEDGING": "Wake call heard…",
                        "SPEAKING": "Wait for “Yes sir” to finish…",
                        "LISTENING": "Read the sentence now",
                        "TRANSCRIBING": "Recognizing locally…",
                    }.get(event["state"], event["state"])
                )
            elif kind == "wake_ready":
                active[0]["command_input_ready_seconds"] = event.get("metrics", {}).get(
                    "command_input_ready_seconds"
                )
            elif kind == "transcript":
                result = event["transcript"]
                active[0]["audio_seconds"] = result["seconds"]
                active[0]["diagnostic"] = diagnostic(cases[index[0]]["text"], result["text"])
                active[0]["quality"] = {
                    key: value
                    for key, value in event.get("metrics", {}).items()
                    if key
                    in {
                        "audio_rms",
                        "audio_peak",
                        "clipped_fraction",
                        "minimum_logprob",
                        "maximum_no_speech_probability",
                    }
                }
                active[0]["exact"] = re.findall(r"\w+", result["text"].casefold()) == re.findall(
                    r"\w+", cases[index[0]]["text"].casefold()
                )
                active[0]["uncertain"] = result["uncertain"]
                active[0]["transcript_received"] = True
                observed.configure(text="Recognized: “" + result["text"][:512] + "”")
            elif kind == "error":
                active[0]["error"] = event["code"]
                observed.configure(text=event["code"])
            elif kind == "finished":
                matched = active[0]["exact"] and active[0]["uncertain"] is False
                index[0] += 1
                status.configure(
                    text=("Matched" if matched else "Did not match exactly · result preserved")
                    + f" · {index[0]} of {len(cases)} checked"
                )
                if index[0] < len(cases):
                    phrase.configure(text=cases[index[0]]["text"])
                    button.configure(text="Start next sentence", state="normal")
                else:
                    phrase.configure(text="Check the last result, then click Finish.")
        if stop.is_set() or time.monotonic() - began >= 600:
            finish()
        else:
            root.after(40, poll)

    button = tk.Button(root, text="Start sentence", command=start)
    button.pack(pady=12)
    tk.Button(root, text="Finish / stop", command=finish).pack(pady=8)
    root.bind("<Escape>", lambda _: finish())
    root.protocol("WM_DELETE_WINDOW", finish)
    try:
        with StopHotkey(stop):
            root.after(40, poll)
            root.mainloop()
    finally:
        jobs.close()


if __name__ == "__main__":
    main()
