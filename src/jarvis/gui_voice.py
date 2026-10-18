"""Small voice controls on the existing composer; all Tk updates stay on its thread."""

import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from pydantic import ValidationError

from jarvis.gui_chrome import style_native_titlebar
from jarvis.gui_scrollbar import ChatScrollbar
from jarvis.gui_theme import BG, INK, MUTED, PANEL
from jarvis.voice import Voice
from jarvis.voice_data import VoiceConfig, VoiceState


class VoicePanel:
    def __init__(self, window, *, interaction_mode="wake_word"):
        self.window = window
        self.closed = False
        self.voice = None
        self.last_transcript = ""
        self.reply_expected = False
        self.interaction_mode = interaction_mode
        self.settings_open = False
        self.settings_dialog = None
        self.wake_feedback = ""
        bar = tk.Frame(window.composer.body, bg=PANEL)
        bar.pack(side="bottom", fill="x", pady=(4, 0))
        self.mic = None
        if interaction_mode == "push_to_talk":  # Explicit attended-lab compatibility.
            self.mic = window.button(bar, "Mic", self.microphone)
            self.mic.pack(side="left")
            self.mic.configure(state="disabled")
        self.label = tk.Label(
            bar,
            text="Voice · checking local setup",
            fg=MUTED,
            bg=PANEL,
            font=("Segoe UI", 9),
            wraplength=640,
            height=2,
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True)
        try:
            self.voice = Voice(
                Path(os.environ["LOCALAPPDATA"]) / "Jarvis", self.notify, self.submit
            )
            self.voice.config = self.voice.config.model_copy(
                update={
                    "interaction_mode": interaction_mode,
                    "enabled": True,
                    "speak_responses": True,
                }
            )
            self.notify("state", self.voice.state)
            if self.mic:
                window.root.bind("<Control-Shift-space>", lambda _: self.microphone(), add="+")
            window.input.bind("<KeyPress>", lambda _: self.voice.edited(), add="+")
            self.voice.discover()  # Enumerate/check only. Never opens a recording stream.
        except (OSError, ValueError, KeyError):
            self.label.configure(text="Voice setup unavailable · text chat is ready to use")
            if self.mic:
                self.mic.configure(state="disabled")
        window.schedule(40, self.poll)

    def notify(self, kind, value):
        if self.closed:
            return
        if kind == "state":
            if value == VoiceState.WAKE_ACKNOWLEDGING:
                self.wake_feedback = ""
            labels = {
                VoiceState.WAKE_LISTENING: f"Microphone on · say “{self.voice.config.wake_call}”",
                VoiceState.WAKE_CHECKING: "Microphone on · checking wake phrase locally…",
                VoiceState.WAKE_ACKNOWLEDGING: "Wake call heard · preparing “Yes sir”…",
                VoiceState.LISTENING: (
                    "Listening · start your command within "
                    f"{self.voice.config.wake_followup_seconds} seconds"
                    if self.interaction_mode == "wake_word"
                    else "Listening to your request · finishes when you stop talking"
                ),
            }
            self.label.configure(
                text=labels.get(value, "Voice · " + value.value.replace("_", " ").title())
            )
            if value == VoiceState.IDLE and self.voice and self.interaction_mode == "wake_word":
                if self.voice.wake_paused:
                    self.label.configure(text="Microphone paused · open Settings to resume")
                elif not self.voice.config.wake_enabled:
                    self.label.configure(text="Microphone off · spoken replies stay on")
            if self.mic:
                self.mic.configure(text="Finish" if value == VoiceState.LISTENING else "Mic")
                if value == VoiceState.DISABLED:
                    self.mic.configure(state="disabled")
            if value in {
                VoiceState.LISTENING,
                VoiceState.TRANSCRIBING,
                VoiceState.SUBMITTING,
                VoiceState.PROCESSING,
                VoiceState.SPEAKING,
                VoiceState.STOPPING,
                VoiceState.WAKE_LISTENING,
                VoiceState.WAKE_CHECKING,
                VoiceState.WAKE_ACKNOWLEDGING,
            }:
                self.window.stop_button.configure(state="normal")
            elif not self.window.busy:
                self.window.stop_button.configure(state="disabled")
            self.present(value)
        elif kind == "notice":
            self.label.configure(text=value)
            self.window.logs = (self.window.logs + ["Voice: " + value])[-300:]
        elif kind == "level":
            threshold = (
                self.voice.config.wake_minimum_rms if self.interaction_mode == "wake_word" else 100
            )
            signal = "sound detected" if value * 32768 >= threshold else "input quiet"
            prefix = (
                f"Microphone on · say “{self.voice.config.wake_call}”"
                if self.voice.state in {VoiceState.WAKE_LISTENING, VoiceState.WAKE_CHECKING}
                else (
                    f"Listening · start within {self.voice.config.wake_followup_seconds} seconds"
                    if self.interaction_mode == "wake_word"
                    else "Listening to your request"
                )
            )
            self.label.configure(text=prefix + " · " + signal)
        elif kind == "wake_level":
            if self.voice.state == VoiceState.WAKE_LISTENING:
                self.label.configure(
                    text=f"Microphone on · say “{self.voice.config.wake_call}” · "
                    + ("sound detected" if value else "input quiet")
                    + ("\n" + self.wake_feedback if self.wake_feedback else "")
                )
        elif kind == "wake_status":
            self.wake_feedback = {
                "NO_MATCH": "Heard sound, but not the wake call. Try saying it on its own.",
                "UNCLEAR": "Heard the wake call unclearly. Please repeat it.",
                "EXPIRED": "No command started in time. Say your wake call again.",
            }[value]
            self.label.configure(text=self.wake_feedback)
        elif kind == "transcript":
            self.last_transcript = value["text"]
            if not self.window.input.get("1.0", "end-1c").strip():
                self.window.input.insert("1.0", value["text"])
                self.window.update_composer()
        elif kind == "devices":
            errors = value.get("errors", [])
            self.label.configure(text="Voice · " + (", ".join(errors) if errors else "Ready"))
            available = value.get("stt_ready") and value.get("inputs") and self.voice.config.enabled
            if self.mic:
                self.mic.configure(state="normal" if available else "disabled")
        elif kind == "metrics":
            safe = {
                key: round(seconds, 3)
                for key, seconds in value.items()
                if key
                in {
                    "load_seconds",
                    "stt_seconds",
                    "start_seconds",
                    "speech_seconds",
                    "command_input_ready_seconds",
                }
                and isinstance(seconds, (int, float))
                and 0 <= seconds <= 300
            }
            self.window.logs = (self.window.logs + ["Voice timing: " + str(safe)])[-300:]
        elif kind == "setup_diagnostic":
            hresult = value["hresult"]
            code = f"0x{hresult & 0xFFFFFFFF:08X}" if hresult is not None else "none"
            self.window.logs = (
                self.window.logs
                + [f"Wake setup: {value['stage']} / {value['category']} / HRESULT={code}"]
            )[-300:]

    def present(self, state):
        session = self.window.session
        if session and self.window.ready or session and self.window.busy:
            try:
                session.voice_state(state.value)
            except (ValueError, OSError, AttributeError):
                pass  # Presentation failure never grants or blocks a tool effect.

    def microphone(self):
        if not self.voice:
            return
        if self.voice.state == VoiceState.LISTENING:
            self.voice.microphone()
            return
        if not self.window.ready or self.window.busy:
            self.label.configure(text="Wait for the current request, or use Stop.")
            return
        if self.window.input.get("1.0", "end-1c").strip():
            self.label.configure(text="Send or clear your typed draft before recording.")
            return
        self.voice.microphone()
        if self.voice.jobs.active:
            self.window.stop_button.configure(state="normal")

    def submit(self, text, original):
        if self.closed or self.window.global_stopped:
            return False
        current = self.window.input.get("1.0", "end-1c").strip()
        if current != original:
            return False
        return self.window.send_text(text, from_voice=True, display_text=original)

    def submitted(self, from_voice=False):
        self.reply_expected = True
        if self.voice:
            self.voice.begin_request(voice=from_voice)

    def reply(self, text):
        if self.voice and self.reply_expected:
            self.voice.reply(text)

    def ready(self):
        self.reply_expected = False
        if self.voice:
            self.voice.ready()
            if not self.voice.devices.get("stt_ready"):
                self.label.configure(text="Voice input needs setup · Settings")

    def stop(self):
        self.reply_expected = False
        if self.voice:
            self.voice.cancel()

    def stop_speaking(self):
        if self.voice:
            self.voice.stop_speaking()

    def poll(self):
        if self.closed or self.window.closed:
            return
        if self.voice:
            self.voice.poll()
            if (
                self.window.ready
                and not self.window.busy
                and not self.window.global_stopped
                and not self.settings_open
                and not self.window.input.get("1.0", "end-1c").strip()
            ):
                self.voice.start_wake()
                if self.voice.jobs.active:
                    self.window.stop_button.configure(state="normal")
        self.window.schedule(40, self.poll)

    def settings(self):
        if not self.voice:
            return
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return
        self.settings_open = True
        if self.voice.jobs.active and self.voice.operation in {"wake", "inspect", "speak"}:
            if self.voice.operation == "speak":
                self.voice.stop_speaking()
                self.voice.wake_paused = False
            else:
                self.voice.cancel(pause_wake=False)
        dialog = tk.Toplevel(self.window.root)
        self.settings_dialog = dialog
        dialog.title("JARVIS · Settings")
        dialog.bind(
            "<Map>",
            lambda event: style_native_titlebar(dialog) if event.widget is dialog else None,
            add="+",
        )
        dialog.configure(bg=BG)
        dialog.transient(self.window.root)
        form = dialog
        if self.interaction_mode == "wake_word":
            dialog.geometry(f"540x{min(800, max(400, dialog.winfo_screenheight() - 120))}")
            body = tk.Frame(dialog, bg=BG)
            body.pack(fill="both", expand=True)
            viewport = tk.Canvas(body, bg=BG, highlightthickness=0, yscrollincrement=20)
            scrollbar = ChatScrollbar(body, command=viewport.yview, background=BG)
            scrollbar.pack(side="right", fill="y")
            viewport.pack(side="left", fill="both", expand=True)
            viewport.configure(yscrollcommand=scrollbar.set)
            form = tk.Frame(viewport, bg=BG)
            item = viewport.create_window((0, 0), window=form, anchor="nw")
            form.bind(
                "<Configure>", lambda _: viewport.configure(scrollregion=viewport.bbox("all"))
            )
            viewport.bind(
                "<Configure>", lambda event: viewport.itemconfigure(item, width=event.width)
            )
            dialog.bind("<MouseWheel>", scrollbar.wheel, add="+")

        saving = [None]

        def dismissed():
            if saving[0] is not None:
                dialog.after_cancel(saving[0])
            self.settings_open = False
            self.settings_dialog = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", dismissed)
        fields = {}
        config = self.voice.config
        if self.interaction_mode == "wake_word":
            tk.Label(form, text="Wake call", bg=BG, fg=INK).pack(anchor="w", padx=16)
            fields["wake_call"] = tk.StringVar(value=config.wake_call)
            tk.Entry(
                form, textvariable=fields["wake_call"], bg=PANEL, fg=INK, insertbackground=INK
            ).pack(fill="x", padx=16, pady=(0, 8))
            tk.Label(
                form,
                text="Say this phrase and pause. The character says “Yes sir”, "
                "then listens for your command. Choose 1–5 clear spoken words.",
                bg=BG,
                fg=MUTED,
                wraplength=450,
            ).pack(anchor="w", padx=16, pady=(0, 8))
        options = {}
        for field, label, choices in (
            (
                "tts_provider",
                "Speech engine",
                {"Natural local voice (Kokoro)": "kokoro", "Windows offline voice": "windows_sapi"},
            ),
            (
                "neural_voice",
                "Natural voice",
                {"Michael · American male": "am_michael", "George · British male": "bm_george"},
            ),
        ):
            selected = next((k for k, v in choices.items() if v == getattr(config, field)), None)
            if selected is None:
                choices["Configured voice"] = getattr(config, field)
                selected = "Configured voice"
            options[field] = choices
            fields[field] = tk.StringVar(value=selected)
            tk.Label(form, text=label, bg=BG, fg=INK).pack(anchor="w", padx=16)
            ttk.Combobox(
                form, values=list(choices), textvariable=fields[field], state="readonly", width=55
            ).pack(fill="x", padx=16, pady=(0, 8))
        for field, section in (
            ("input_device", "inputs"),
            ("voice", "voices"),
            ("output_device", "outputs"),
        ):
            choices = {"System default": ""}
            for i, device in enumerate(self.voice.devices.get(section, []), 1):
                choices[f"{device['name']} ({i})"] = device["id"]
            selected = next((k for k, v in choices.items() if v == getattr(config, field)), None)
            if selected is None:
                choices["Configured device (currently unavailable)"] = getattr(config, field)
                selected = "Configured device (currently unavailable)"
            options[field] = choices
            fields[field] = tk.StringVar(value=selected)
            tk.Label(
                form,
                text="Windows voice (Windows engine only)"
                if field == "voice"
                else field.replace("_", " ").title(),
                bg=BG,
                fg=INK,
            ).pack(anchor="w", padx=16)
            ttk.Combobox(
                form, values=list(choices), textvariable=fields[field], state="readonly", width=55
            ).pack(fill="x", padx=16, pady=(0, 8))
        numeric_fields = (
            ("wake_followup_seconds", "wake_silence_seconds", "wake_minimum_rms")
            if self.interaction_mode == "wake_word"
            else ("silence_seconds",)
        )
        for field in (
            "model_directory",
            "language",
            "recording_seconds",
            *numeric_fields,
            "volume",
            "rate",
        ):
            label = (
                "Voice activation level"
                if field == "wake_minimum_rms"
                else "Command listening window (seconds, 3–20)"
                if field == "wake_followup_seconds"
                else "Command pause before sending (seconds)"
                if field == "wake_silence_seconds"
                else field.replace("_", " ").title()
            )
            tk.Label(form, text=label, bg=BG, fg=INK).pack(anchor="w", padx=16)
            value = getattr(config, field)
            fields[field] = tk.StringVar(value="" if value is None else str(value))
            tk.Entry(form, textvariable=fields[field], bg=PANEL, fg=INK, insertbackground=INK).pack(
                fill="x", padx=16, pady=(0, 8)
            )
        enabled = tk.BooleanVar(value=config.wake_enabled)
        hints_enabled = tk.BooleanVar(value=config.app_name_hints)
        tk.Label(form, text="Names and spellings (optional, one per line)", bg=BG, fg=INK).pack(
            anchor="w", padx=16
        )
        terms = tk.Text(form, height=3, bg=PANEL, fg=INK, insertbackground=INK, wrap="word")
        terms.insert("1.0", "\n".join(config.recognition_terms))
        terms.pack(fill="x", padx=16, pady=(0, 8))
        review = tk.BooleanVar(value=config.review_transcript)
        for text, variable in (
            ("Listen locally for my wake call while chat is ready", enabled),
            ("Review every transcript before sending", review),
            ("Experimental app-name hints (may mishear ordinary words)", hints_enabled),
        ):
            tk.Checkbutton(
                form, text=text, variable=variable, bg=BG, fg=INK, selectcolor=PANEL
            ).pack(anchor="w", padx=16)
        status = tk.Label(
            dialog,
            text="Local microphone listening · pauses during replies. "
            "Spoken replies are always on.",
            bg=BG,
            fg=MUTED,
            wraplength=450,
        )
        status.pack(padx=16, pady=8)
        if self.interaction_mode == "wake_word":
            tk.Label(
                form,
                text=(
                    "Wake detection: installed Windows offline speech grammar. "
                    "Say the wake call first, wait for “Yes sir”, then give your command. "
                    "The silence duration applies to the command, not wake detection."
                    if config.wake_provider == "windows_sapi"
                    else "Wake detection: legacy local Whisper. "
                    "This mode waits for silence before recognizing the wake call."
                ),
                bg=BG,
                fg=MUTED,
                wraplength=450,
            ).pack(padx=16, pady=(0, 8))
            tk.Label(
                form,
                text="Voice activation level: lower values hear softer speech; "
                "higher values reject more background noise. Default: 100.",
                bg=BG,
                fg=MUTED,
                wraplength=450,
            ).pack(padx=16, pady=(0, 8))

        def save():
            saving[0] = None
            if self.voice.jobs.active and self.voice.operation in {"wake", "inspect", "speak"}:
                status.configure(text="Releasing voice device…")
                if self.voice.operation == "speak":
                    self.voice.stop_speaking()
                    self.voice.wake_paused = False
                else:
                    self.voice.cancel(pause_wake=False)
                saving[0] = dialog.after(100, save)
                return
            if self.voice.state == VoiceState.PROCESSING and self.interaction_mode == "wake_word":
                status.configure(text="Waiting for the current reply before saving…")
                saving[0] = dialog.after(100, save)
                return
            if self.voice.jobs.active or self.voice.state == VoiceState.PROCESSING:
                status.configure(
                    text="Finish the current voice request, or press Stop in the chat, then Save."
                )
                return
            try:
                changes = {
                    field: choices[fields[field].get()] for field, choices in options.items()
                }
                conversions = [
                    ("recording_seconds", int),
                    ("volume", int),
                    ("rate", int),
                ] + [
                    (
                        field,
                        int if field in {"wake_minimum_rms", "wake_followup_seconds"} else float,
                    )
                    for field in numeric_fields
                ]
                for field, convert in conversions:
                    try:
                        changes[field] = convert(fields[field].get())
                    except ValueError:
                        status.configure(text=field.replace("_", " ").title() + ": enter a number.")
                        return
                if self.interaction_mode == "wake_word":
                    changes["wake_call"] = fields["wake_call"].get()
                changes.update(
                    model_directory=fields["model_directory"].get(),
                    language=fields["language"].get() or None,
                    enabled=True,
                    wake_enabled=enabled.get(),
                    review_transcript=review.get(),
                    speak_responses=True,
                    interaction_mode=self.interaction_mode,
                    app_name_hints=hints_enabled.get(),
                    recognition_terms=[
                        line.strip()
                        for line in terms.get("1.0", "end-1c").splitlines()
                        if line.strip()
                    ],
                )
                data = config.model_dump() | changes
                self.voice.save(VoiceConfig.model_validate(data, strict=True))
                self.voice.wake_paused = False
                self.voice.discover()
                dismissed()
            except ValidationError as exc:
                field = str(exc.errors()[0]["loc"][0]).replace("_", " ").title()
                status.configure(text=field + ": " + exc.errors()[0]["msg"])
            except OSError:
                status.configure(text="Could not save the private voice settings file. Try again.")
            except ValueError:
                status.configure(text="Voice work is still stopping. Wait briefly, then Save.")

        self.window.button(dialog, "Save", save, accent=True).pack(pady=12)
        self.window.button(dialog, "Refresh devices", self.voice.discover).pack(pady=(0, 12))
        self.window.button(dialog, "Cancel", dismissed).pack(pady=(0, 12))

    def close(self):
        self.closed = True
        if self.voice:
            self.voice.close()
