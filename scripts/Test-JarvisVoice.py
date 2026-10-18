"""Attended production-GUI voice lab. No automatic recording or tool requests.

Only inventory/scope setup is automatic. Click Mic and read the labelled synthetic
phrases. Screen questions are scoped to the owned synthetic fixture, not displays.
No audio/transcripts/replies/screenshots are saved in the report.
"""

import argparse
import ctypes
import importlib.util
import json
import os
import queue
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from jarvis.gui import ChatWindow
from jarvis.gui_startup import StartupServices
from jarvis.gui_voice import VoicePanel
from jarvis.screen_capture import WindowsCapture
from jarvis.screen_data import load_config
from jarvis.voice_data import request_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report preserved; choose a new filename")
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    helper = Path(__file__).with_name("Chat-JarvisAll.py")
    spec = importlib.util.spec_from_file_location("jarvis_voice_lab_launcher", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    services = StartupServices(private)
    report = {
        "version": "m6-production-gui-voice-v1",
        "started_at": time.time(),
        "status": "NOT FULLY VERIFIED",
        "automatic_recordings": 0,
        "automatic_app_media_actions": 0,
        "screen_scope": "owned synthetic window only",
        "states": [],
        "synthetic_transcripts": {},
        "spoken_stream_starts": 0,
        "stop_speaking_clicked": False,
        "timings": [],
        "audibility": "operator confirmation required",
    }
    root = tk.Tk()

    class AuditedPanel(VoicePanel):
        def __init__(self, window):
            # This attended fixture retains explicit Mic activation even though
            # the owner's ordinary GUI now opts into wake-word listening.
            super().__init__(window, interaction_mode="push_to_talk")

        def notify(self, kind, value):
            if kind == "state":
                print("Voice lab state: " + str(value), flush=True)
            elif kind == "notice" and "microphone" in value.casefold():
                # Only trusted fixed diagnostics; never transcript/audio content.
                print("Voice lab microphone: " + value, flush=True)
            if kind == "state":
                report["states"].append(str(value))
                report["states"] = report["states"][-256:]
                report["spoken_stream_starts"] += value == "SPEAKING"
            elif kind == "metrics":
                report["timings"].append(value)
                report["timings"] = report["timings"][-16:]
            elif kind == "transcript":
                normalized = request_text(value["text"]).casefold().rstrip(".!?")
                if normalized in {"what is your name", "what am i looking at"}:
                    report["synthetic_transcripts"][normalized] = True
            return super().notify(kind, value)

        def microphone(self):
            if not report.get("scope_confirmed"):
                self.label.configure(text="Wait for verified fixture scope setup.")
                return
            return super().microphone()

        def stop_speaking(self):
            if self.voice and self.voice.state == "SPEAKING":
                report["stop_speaking_clicked"] = True
            return super().stop_speaking()

    window = ChatWindow(
        root,
        module.chat_command,
        helper.parent.parent,
        prepare=services.prepare,
        auto_start=True,
        voice_factory=AuditedPanel,
    )
    root.geometry("940x760+20+50")
    fixture = tk.Toplevel(root)
    fixture.title("JARVIS M6 synthetic voice-screen fixture")
    fixture.geometry("720x480+1000+100")
    fixture.configure(bg="#17202b")
    tk.Label(
        fixture,
        text="Synthetic voice test\n\nModuleNotFoundError: No module named 'pandas'\n\n"
        "When setup is ready, click Mic and say:\nJarvis, what is your name?\n\n"
        "Then say: Jarvis, what am I looking at?\n\n"
        "Test Stop speaking during a reply. Close JARVIS to finish.\n"
        "Do not request app/media actions in this lab.",
        bg="#17202b",
        fg="#e1e8ff",
        font=("Segoe UI", 16),
        wraplength=680,
    ).pack(padx=20, pady=25)
    root.update_idletasks()
    user = ctypes.WinDLL("user32")
    user.GetAncestor.argtypes, user.GetAncestor.restype = (
        [wintypes.HWND, wintypes.UINT],
        wintypes.HWND,
    )
    targets = queue.Queue(maxsize=1)

    def discover(fixture_hwnd):
        try:
            capture = WindowsCapture(load_config(private / "screen.toml"))
            matches = [
                t
                for t in capture.inventory()
                if t.kind == "window" and t.native["hwnd"] == fixture_hwnd
            ]
            targets.put(matches[0].reference if len(matches) == 1 else None)
        except (ValueError, OSError):
            targets.put(None)

    def mapped_fixture():
        # Tk may replace its wrapper handle while first mapping the Toplevel.
        # Resolve the final HWND after the event loop has displayed the fixture.
        fixture_hwnd = int(user.GetAncestor(fixture.winfo_id(), 2))
        threading.Thread(target=discover, args=(fixture_hwnd,), daemon=True).start()

    window.schedule(500, mapped_fixture)
    phase, reference = [0], [None]
    original_send, original_message = window.send_text, window.add_message

    def restricted_send(text, **kwargs):
        controls = {"/screen-windows", "/screen-allow " + str(reference[0]), "/stop", "/quit"}
        normalized = request_text(text).casefold().rstrip(".!?")
        if text not in controls and normalized not in {"what is your name", "what am i looking at"}:
            window.voice.label.configure(text="This lab accepts only the two synthetic phrases.")
            return False
        return original_send(text, **kwargs)

    def observed_message(role, text):
        if role == "assistant" and phase[0] == 3:
            report["scope_confirmed"] = text.startswith(
                "Screen questions may inspect this exact window:"
            )
            if not report["scope_confirmed"]:
                report["setup_error"] = "SCOPE_CONFIRMATION_FAILED"
                window.stop()
        elif role == "assistant" and report.get("scope_confirmed") and "pandas" in text.casefold():
            report["synthetic_error_mentioned"] = True
        return original_message(role, text)

    window.send_text, window.add_message = restricted_send, observed_message

    def setup_scope():
        if window.closed:
            return
        if phase[0] == 0:
            try:
                reference[0] = targets.get_nowait()
            except queue.Empty:
                window.schedule(100, setup_scope)
                return
            if not reference[0]:
                window.close()
                report["setup_error"] = "OWNED_FIXTURE_NOT_FOUND"
                return
            phase[0] = 1
        if window.ready and not window.busy:
            if phase[0] == 1:
                window.send_text("/screen-windows")
                phase[0] = 2
            elif phase[0] == 2:
                window.send_text("/screen-allow " + reference[0])
                phase[0] = 3
            elif phase[0] == 3:
                report["scope_setup_sent"] = True
                phase[0] = 4
                if report.get("scope_confirmed"):
                    window.voice.label.configure(text="Lab ready · click Mic and read the fixture")
                return
            window.voice.reply_expected = False  # Never speak inventory/control diagnostics.
        window.schedule(100, setup_scope)

    window.schedule(100, setup_scope)
    try:
        root.mainloop()
    finally:
        report["ended_at"] = time.time()
        report["scope_setup_sent"] = report.get("scope_setup_sent", False)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
        print("Saved privacy-preserving GUI lab evidence. Audibility and acceptance need review.")


if __name__ == "__main__":
    main()
