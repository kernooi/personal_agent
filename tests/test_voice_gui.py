"""Owned Tk widgets and fake audio/backend only; never records, speaks or launches tools."""

import io
import os
import subprocess
import sys
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

from test_voice import Jobs, transcript

from jarvis.gui_session import ChatSession, request_line
from jarvis.voice_presentation import PREFIX, parse_control


def isolated_tk_test(function):
    @wraps(function)
    def execute(*args, **kwargs):
        if os.environ.get("JARVIS_VOICE_TK_CHILD") == "1":
            return function(*args, **kwargs)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(Path(__file__).resolve()) + "::" + function.__name__,
                "-q",
            ],
            env=dict(os.environ, JARVIS_VOICE_TK_CHILD="1"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    return execute


def test_presentation_pipe_is_metadata_only_and_owner_text_cannot_forge_it():
    process = SimpleNamespace(stdin=io.StringIO(), poll=lambda: None)
    session = ChatSession(lambda **k: [], ".")
    session.process = process
    session.voice_state("LISTENING")
    raw = process.stdin.getvalue().rstrip("\n")
    assert raw.startswith(PREFIX)
    assert parse_control(raw) == {"sequence": 1, "state": "LISTENING"}
    assert not request_line(raw).startswith(PREFIX)


@isolated_tk_test
def test_real_voice_controls_reuse_one_gui_send_and_preserve_typed_input(monkeypatch, tmp_path):
    import tkinter as tk

    from jarvis import voice as voice_module
    from jarvis.gui import ChatWindow
    from jarvis.gui_voice import VoicePanel

    jobs = Jobs()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(voice_module, "AudioJobs", lambda _: jobs)
    root = tk.Tk()
    root.withdraw()
    w = ChatWindow(
        root,
        lambda **k: [],
        tmp_path,
        voice_factory=lambda window: VoicePanel(window, interaction_mode="push_to_talk"),
    )
    sent, presented = [], []
    w.session = SimpleNamespace(send=sent.append, voice_state=presented.append)
    w.connected, w.ready, w.busy = True, True, False
    try:
        assert jobs.calls[0][0] == "inspect"  # No recording at construction.
        jobs.emit(
            "devices",
            inputs=[{"id": "fake", "name": "Fake microphone"}],
            voices=[],
            outputs=[],
            stt_ready=True,
            errors=[],
        )
        jobs.emit("finished")
        w.voice.voice.poll()
        assert w.voice.mic.cget("state") == "normal"
        w.voice.microphone()
        jobs.emit("stage", state="LISTENING")
        w.voice.voice.poll()
        assert w.voice.mic.cget("text") == "Finish"
        assert w.stop_button.cget("state") == "normal"
        jobs.emit("stage", state="TRANSCRIBING")
        jobs.emit("transcript", transcript=transcript().model_dump())
        jobs.emit("finished")
        w.voice.voice.poll()
        assert sent == ["open Notepad."]
        assert w.busy and not w.ready
        assert w.transcript.messages[-1].message == "Voice: Jarvis, open Notepad."
        w.voice.reply("The result is in the chat.")
        w.voice.ready()
        assert jobs.calls[-1][0] == "speak"
        w.voice.stop_speaking()
        assert jobs.cancelled and sent == ["open Notepad."]  # No backend /stop for speech alone.
        jobs.emit("finished")
        w.voice.voice.poll()
        w.ready, w.busy = True, False
        w.input.insert("1.0", "typed question")
        w.send()
        assert sent[-1] == "typed question"
        assert w.transcript.messages[-1].message == "typed question"
    finally:
        w.voice.close()
        for timer in list(w.timers):
            root.after_cancel(timer)
        root.destroy()


def test_screen_privacy_state_has_priority_over_voice_without_second_overlay():
    from jarvis.companion import Animation, CompanionConfig
    from jarvis.companion_host import Host

    host = Host.__new__(Host)
    host.animation = Animation(CompanionConfig(), seed=1)
    host.voice_animation = Animation(CompanionConfig(), seed=1)
    host.animation.event("capturing", "screen", 2, 0)
    host.voice_animation.event("speaking", "voice", 3, 0)
    assert host.screen_priority(0.5)
    host.animation.event("analyzing", "screen", 4, 1)
    assert host.screen_priority(1.5)
    host.animation.event("watching", "screen", 5, 2)
    assert host.screen_priority(2.5)
    host.animation.event("completed", "screen", 6, 3)
    assert host.screen_priority(3.1)
    assert not host.screen_priority(4)
    assert host.voice_animation.pose(4).state == "speaking"


@isolated_tk_test
def test_wake_settings_save_custom_call_and_listening_window(monkeypatch, tmp_path):
    import tkinter as tk

    from jarvis import voice as voice_module
    from jarvis.gui import ChatWindow
    from jarvis.gui_voice import VoicePanel
    from jarvis.voice_data import load_config

    jobs = Jobs()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(voice_module, "AudioJobs", lambda _: jobs)
    root = tk.Tk()
    root.withdraw()
    window = ChatWindow(
        root, lambda **k: [], tmp_path, voice_factory=lambda owner: VoicePanel(owner)
    )
    try:
        jobs.emit("finished")
        window.voice.voice.poll()
        window.voice.settings()
        dialog = window.voice.settings_dialog

        def descendants(parent):
            for child in parent.winfo_children():
                yield child
                yield from descendants(child)

        for label, value in (
            ("Wake call", "Hey Nova"),
            ("Command listening window (seconds, 3–20)", "15"),
        ):
            widget = next(
                child
                for child in descendants(dialog)
                if isinstance(child, tk.Label) and child.cget("text") == label
            )
            siblings = widget.master.winfo_children()
            entry = siblings[siblings.index(widget) + 1]
            entry.delete(0, "end")
            entry.insert(0, value)
        save = next(
            child
            for child in dialog.winfo_children()
            if isinstance(child, tk.Button) and child.cget("text") == "Save"
        )
        engine_label = next(
            child
            for child in descendants(dialog)
            if isinstance(child, tk.Label) and child.cget("text") == "Speech engine"
        )
        siblings = engine_label.master.winfo_children()
        selector = siblings[siblings.index(engine_label) + 1]
        selector.set("Natural local voice (Kokoro)")
        spellings = next(child for child in descendants(dialog) if isinstance(child, tk.Text))
        spellings.insert("1.0", "My Music Mix\nFav Jpop")
        save.invoke()
        config = load_config(tmp_path / "Jarvis")
        assert config.wake_call == "Hey Nova" and config.wake_followup_seconds == 15
        assert config.tts_provider == "kokoro" and config.neural_voice == "am_michael"
        assert config.recognition_terms == ["My Music Mix", "Fav Jpop"]
        assert config.app_name_hints is False
        assert window.voice.voice.config == config
        assert not dialog.winfo_exists()
        assert all(call[0] == "inspect" for call in jobs.calls)
    finally:
        window.voice.close()
        for timer in list(window.timers):
            root.after_cancel(timer)
        root.destroy()


@isolated_tk_test
def test_voice_settings_save_zero_defaults_and_report_the_actual_error(monkeypatch, tmp_path):
    import tkinter as tk

    from jarvis import voice as voice_module
    from jarvis.gui import ChatWindow
    from jarvis.gui_voice import VoicePanel
    from jarvis.voice_data import load_config

    jobs = Jobs()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(voice_module, "AudioJobs", lambda _: jobs)
    root = tk.Tk()
    root.withdraw()
    window = ChatWindow(
        root,
        lambda **k: [],
        tmp_path,
        voice_factory=lambda window: VoicePanel(window, interaction_mode="push_to_talk"),
    )
    try:
        jobs.emit("finished")
        window.voice.voice.poll()
        window.voice.settings()
        dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        children = dialog.winfo_children()
        entries = [child for child in children if child.winfo_class() == "Entry"]
        status = [child for child in children if isinstance(child, tk.Label)][-1]
        save = next(
            child
            for child in children
            if isinstance(child, tk.Button) and child.cget("text") == "Save"
        )
        assert entries[3].get() == "0"  # Silence endpointing is deliberately off.
        assert entries[5].get() == "0"  # The normal speech rate must remain valid.

        entries[5].delete(0, "end")
        save.invoke()
        assert status.cget("text") == "Rate: enter a number."
        assert not (tmp_path / "Jarvis" / "voice.toml").exists()

        entries[5].insert(0, "99")
        save.invoke()
        assert status.cget("text").startswith("Rate: Input should be less than or equal to 5")
        entries[5].delete(0, "end")
        entries[5].insert(0, "0")

        jobs.active = True
        window.voice.voice.operation = "listen"
        save.invoke()
        assert "Finish the current voice request" in status.cget("text")
        assert not (tmp_path / "Jarvis" / "voice.toml").exists()
        jobs.active = False
        window.voice.voice.operation = "inspect"
        original_save = window.voice.voice.save

        def unavailable(config):
            raise OSError("synthetic write failure")

        monkeypatch.setattr(window.voice.voice, "save", unavailable)
        save.invoke()
        assert status.cget("text").startswith("Could not save the private voice settings file.")

        monkeypatch.setattr(window.voice.voice, "save", original_save)
        save.invoke()
        assert not dialog.winfo_exists()
        config = load_config(tmp_path / "Jarvis")
        assert config.rate == 0 and config.silence_seconds == 0
        assert jobs.calls[-1][0] == "inspect"
        assert all(call[0] == "inspect" for call in jobs.calls)
    finally:
        window.voice.close()
        for timer in list(window.timers):
            root.after_cancel(timer)
        root.destroy()
