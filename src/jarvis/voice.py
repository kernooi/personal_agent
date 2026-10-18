"""GUI-owned half-duplex state machine. Only the GUI may submit a transcript."""

import json
import queue
import re
from pathlib import Path

from jarvis.voice_data import (
    Devices,
    Transcript,
    VoiceConfig,
    VoiceState,
    WakeSetupDiagnostic,
    load_config,
    needs_review,
    request_text,
    spoken_text,
)
from jarvis.voice_runtime import AudioJobs


class Voice:
    def __init__(self, root, notify, submit, *, jobs=None, config=None):
        self.root, self.notify, self.submit = Path(root), notify, submit
        self.jobs = jobs or AudioJobs(root)
        self.config = config or load_config(root)
        self.state = VoiceState.IDLE if self.config.enabled else VoiceState.DISABLED
        self.devices = {"inputs": [], "voices": [], "outputs": [], "stt_ready": False}
        self.generation = 0
        self.operation = None
        self.pending = None
        self.pending_reply = None
        self.error = None
        self.cancelled = False
        self.closed = False
        self.interaction = 0
        self.backend_complete = False
        self.mute_turn = False
        self.wake_paused = False

    def transition(self, state):
        self.state = VoiceState(state)
        self.notify("state", self.state)

    def start(self, operation, text=""):
        if self.closed or self.jobs.active:
            return False
        self.cancelled, self.error = False, None
        self.operation = operation
        options = {}
        if (
            operation in {"listen", "wake"}
            and self.config.app_name_hints
            and self.devices.get("app_names")
        ):
            options["app_names"] = self.devices["app_names"]
        self.generation = self.jobs.start(operation, self.config, text, **options)
        return True

    def discover(self):
        if not self.config.enabled:
            return False
        return self.start("inspect")

    def microphone(self):
        if self.state == VoiceState.LISTENING:
            self.jobs.finish()
            return
        if self.state == VoiceState.SPEAKING:
            self.cancel()
            self.notify("notice", "Speech is stopping. Click the microphone again when idle.")
            return
        if not self.config.enabled or self.jobs.active or self.state == VoiceState.PROCESSING:
            return
        if not self.devices.get("stt_ready"):
            self.notify("notice", "Local speech recognition is unavailable. Open Voice settings.")
            return
        self.pending = self.pending_reply = None
        self.interaction += 1
        # LISTENING arrives only after the worker successfully opens the device.
        if self.start("listen"):
            self.notify("notice", "Opening microphone…")

    def start_wake(self):
        if (
            self.config.interaction_mode != "wake_word"
            or not self.config.enabled
            or not self.config.wake_enabled
            or self.wake_paused
            or self.state != VoiceState.IDLE
            or not self.devices.get("stt_ready")
            or not self.devices.get("inputs")
        ):
            return False
        self.pending = self.pending_reply = None
        if self.start("wake"):
            self.notify("notice", "Starting local wake-word listening…")
            return True
        return False

    def cancel(self, *, pause_wake=True):
        if pause_wake:
            self.wake_paused = True
        self.cancelled = True
        self.pending = self.pending_reply = None
        self.jobs.cancel()
        self.transition(VoiceState.STOPPING if self.jobs.active else VoiceState.IDLE)

    def stop_speaking(self):
        self.mute_turn = True
        self.pending_reply = None
        if self.operation == "speak" and self.jobs.active:
            self.cancel()

    def edited(self):
        if self.operation in {"listen", "wake"} and (self.jobs.active or self.pending):
            self.cancel(pause_wake=False)
            self.notify("notice", "Voice input cancelled; your typed draft is preserved.")

    def begin_request(self, *, voice=False):
        if not voice:
            self.cancel()
            self.generation = -1  # An earlier audio result cannot belong to this text turn.
        self.cancelled = False
        self.wake_paused = False
        self.mute_turn = False
        self.backend_complete = False
        self.pending_reply = None
        self.transition(VoiceState.PROCESSING if self.config.enabled else VoiceState.DISABLED)

    def reply(self, text):
        if (
            self.config.enabled
            and self.config.speak_responses
            and not self.cancelled
            and not self.mute_turn
        ):
            self.pending_reply = spoken_text(text)

    def ready(self):
        # Backend ready is the completion boundary: do not speak intermediate replies.
        self.backend_complete = True
        if self.pending_reply and not self.cancelled and not self.jobs.active:
            text, self.pending_reply = self.pending_reply, None
            if text:
                self.start("speak", text)
        elif not self.jobs.active:
            self.transition(VoiceState.IDLE if self.config.enabled else VoiceState.DISABLED)

    def poll(self):
        for _ in range(32):
            try:
                generation, event = self.jobs.events.get_nowait()
            except queue.Empty:
                break
            if self.closed or generation != self.generation:
                continue
            kind = event.get("kind")
            if kind == "finished":
                if self.pending and not self.cancelled:
                    transcript, self.pending = self.pending, None
                    review = needs_review(transcript, self.config)
                    self.notify("transcript", {"text": transcript.text, "review": review})
                    if not review:
                        self.transition(VoiceState.SUBMITTING)
                        if self.submit(request_text(transcript.text), transcript.text):
                            self.transition(VoiceState.PROCESSING)
                        else:
                            self.transition(VoiceState.IDLE)
                            self.notify("notice", "Transcript is ready. Review it and press Send.")
                    else:
                        self.transition(VoiceState.IDLE)
                        self.notify(
                            "notice", "Review the transcript and press Send. No request sent."
                        )
                elif self.state not in {VoiceState.ERROR, VoiceState.PROCESSING}:
                    self.transition(VoiceState.IDLE if self.config.enabled else VoiceState.DISABLED)
                continue
            if self.cancelled:
                continue
            try:
                if kind == "opening":
                    labels = {
                        "loading_audio": "Starting microphone (up to 8 seconds)…",
                        "checking_device": "Checking microphone format…",
                        "opening_stream": "Opening the microphone device…",
                    }
                    if self.operation not in {"listen", "wake"} or event.get("step") not in labels:
                        raise ValueError("Unexpected microphone startup")
                    self.notify("notice", labels[event["step"]])
                elif kind == "level":
                    value = event.get("value")
                    if (
                        self.operation not in {"listen", "wake"}
                        or self.state
                        not in {
                            VoiceState.LISTENING,
                            VoiceState.WAKE_LISTENING,
                            VoiceState.WAKE_CHECKING,
                        }
                        or type(value) not in {int, float}
                        or not 0 <= value <= 1
                    ):
                        raise ValueError("Invalid microphone level")
                    self.notify("level", value)
                elif kind == "stage":
                    allowed = (
                        {"LISTENING", "TRANSCRIBING"}
                        if self.operation == "listen"
                        else {
                            "WAKE_LISTENING",
                            "WAKE_CHECKING",
                            "WAKE_ACKNOWLEDGING",
                            "SPEAKING",
                            "LISTENING",
                            "TRANSCRIBING",
                        }
                        if self.operation == "wake"
                        else {"SPEAKING"}
                        if self.operation == "speak"
                        else set()
                    )
                    if event.get("state") not in allowed:
                        raise ValueError("Unexpected audio state")
                    if event.get("state") == "TRANSCRIBING" and self.state not in {
                        VoiceState.LISTENING,
                        VoiceState.WAKE_CHECKING,
                    }:
                        raise ValueError("Capture did not start")
                    self.transition(event["state"])
                elif kind == "devices" and self.operation == "inspect":
                    self.devices = Devices.model_validate(event, strict=True).model_dump()
                    self.notify("devices", self.devices)
                elif kind == "wake_ready" and self.operation == "wake":
                    if set(event) not in ({"kind"}, {"kind", "metrics"}):
                        raise ValueError("Invalid command input readiness")
                    if "metrics" in event:
                        metrics = event["metrics"]
                        if (
                            not isinstance(metrics, dict)
                            or set(metrics) != {"command_input_ready_seconds"}
                            or type(metrics["command_input_ready_seconds"]) not in {int, float}
                            or not 0 <= metrics["command_input_ready_seconds"] < 8
                        ):
                            raise ValueError("Invalid command input timing")
                        self.notify("metrics", metrics)
                    self.notify("notice", "Listening · say your command now")
                elif kind == "wake_status" and self.operation == "wake":
                    if set(event) != {"kind", "status"} or event["status"] not in {
                        "NO_MATCH",
                        "UNCLEAR",
                        "EXPIRED",
                    }:
                        raise ValueError("Invalid wake status")
                    self.notify("wake_status", event["status"])
                elif kind == "wake_level" and self.operation == "wake":
                    if (
                        set(event) != {"kind", "value"}
                        or type(event["value"]) is not int
                        or not 0 <= event["value"] <= 100
                        or self.state != VoiceState.WAKE_LISTENING
                    ):
                        raise ValueError("Invalid wake level")
                    self.notify("wake_level", event["value"])
                elif kind == "transcript" and self.operation in {"listen", "wake"}:
                    if self.state != VoiceState.TRANSCRIBING:
                        raise ValueError("Unexpected transcript")
                    if self.operation == "wake" and event.get("addressed") is not True:
                        raise ValueError("Missing wake address")
                    self.pending = Transcript.model_validate(event["transcript"], strict=True)
                    request_text(self.pending.text)
                    self.notify("metrics", event.get("metrics", {}))
                elif kind == "done" and self.operation == "speak":
                    self.notify("metrics", event.get("metrics", {}))
                elif kind == "error":
                    if (
                        self.operation == "wake"
                        and self.state == VoiceState.TRANSCRIBING
                        and event == {"kind": "error", "code": "NO_SPEECH_DETECTED"}
                    ):
                        # Empty command recognition ends this turn, not the voice
                        # service. Wait for worker shutdown/finished before the
                        # GUI may start a fresh wake session. Never retry the clip.
                        self.pending = self.pending_reply = None
                        self.notify(
                            "notice",
                            "No clear command recognized. Say “"
                            + self.config.wake_call
                            + "” again when listening resumes.",
                        )
                        continue
                    self.pending = None
                    self.cancelled = True
                    self.pending_reply = None
                    self.jobs.cancel()
                    self.error = event.get("code", "VOICE_FAILED")
                    if not isinstance(self.error, str) or not re.fullmatch(
                        r"[A-Z_]{1,80}", self.error
                    ):
                        self.error = "VOICE_FAILED"
                    setup = None
                    if "setup" in event:
                        setup = WakeSetupDiagnostic.model_validate(event["setup"], strict=True)
                        if self.operation != "wake" or self.error != "WAKE_SETUP_" + setup.stage:
                            raise ValueError("Invalid wake setup diagnostic")
                        self.notify("setup_diagnostic", setup.model_dump())
                    self.transition(VoiceState.ERROR)
                    explanation = {
                        "MICROPHONE_START_TIMEOUT": "Microphone did not start within 8 seconds. "
                        "Check your selected input in Voice settings.",
                        "MICROPHONE_CHANGED_OR_AMBIGUOUS": "The selected microphone could not be "
                        "matched uniquely. Choose your microphone in Settings and Save.",
                        "WAKE_ENGINE_MISSING_OR_AMBIGUOUS": "The installed Windows offline English "
                        "wake recognizer is unavailable or ambiguous. No microphone was opened.",
                        "WAKE_LANGUAGE_UNAVAILABLE": "Windows wake detection currently needs the "
                        "installed English recognizer. Check Language in Settings.",
                        "WAKE_RECOGNITION_FAILED": "Windows wake recognition failed. "
                        "Text chat still works; check Voice settings.",
                        "WAKE_ENGINE_START_FAILED": "Windows could not start offline wake "
                        "detection. Text chat still works; check the selected microphone.",
                    }.get(
                        self.error, "Voice unavailable: " + self.error + ". Text chat still works."
                    )
                    if setup is not None:
                        step = {
                            "CREATE": "creating the Windows recognizer",
                            "ENGINE": "loading the installed speech engine",
                            "INPUT": "connecting the selected microphone",
                            "CONTEXT": "creating the recognition context",
                            "EVENTS": "connecting Windows speech events",
                            "GRAMMAR": "building the wake-call grammar",
                            "ACTIVATE": "starting microphone recognition",
                            "STOP": "stopping the owned recognizer",
                        }[setup.stage]
                        explanation = (
                            "Wake setup failed while " + step + ". See Details for the code."
                        )
                    self.notify(
                        "notice",
                        explanation,
                    )
            except (ValueError, KeyError, TypeError):
                self.pending = None
                self.cancelled = True
                self.pending_reply = None
                self.jobs.cancel()
                self.transition(VoiceState.ERROR)
                self.notify("notice", "Invalid local voice result. No transcript was submitted.")
        if self.backend_complete and self.pending_reply and not self.jobs.active:
            self.ready()

    def save(self, config):
        if self.jobs.active or self.state == VoiceState.PROCESSING:
            raise ValueError("Finish or cancel the voice operation before changing settings.")
        config = VoiceConfig.model_validate(config.model_dump(), strict=True)
        self.root.mkdir(parents=True, exist_ok=True)
        lines = []
        for name, value in config.model_dump().items():
            if name == "language" and value is None:
                value = ""
            if value is not None:
                literal = str(value).lower() if isinstance(value, bool) else json.dumps(value)
                lines.append(f"{name} = {literal}")
        path = self.root / "voice.toml"
        temp = path.with_suffix(".tmp")
        temp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temp.replace(path)
        self.config = config
        self.transition(VoiceState.IDLE if config.enabled else VoiceState.DISABLED)

    def close(self):
        self.closed = True
        self.pending = self.pending_reply = None
        self.jobs.close()
