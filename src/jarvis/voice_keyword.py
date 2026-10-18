"""Owned offline Windows wake grammar; no dictation, tools or stored audio."""

import time

from jarvis.voice_data import Transcript, WakeSetupDiagnostic
from jarvis.voice_wake import WakeGate


class WakeMessagePump:
    """Dispatch this owned STA worker's Windows messages, including SAPI notices."""

    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w

        self.c, self.message = c, w.MSG()
        self.user = c.WinDLL("user32", use_last_error=True)
        self.user.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
        self.user.PeekMessageW.restype = w.BOOL
        self.user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
        self.user.TranslateMessage.restype = w.BOOL
        self.user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
        self.user.DispatchMessageW.restype = c.c_ssize_t

    def pump(self):
        # Never inspect another thread's queue or send input to a desktop target.
        pointer = self.c.byref(self.message)
        for _ in range(64):
            if not self.user.PeekMessageW(pointer, None, 0, 0, 1):
                break
            if self.message.message == 0x0012:  # WM_QUIT belongs to this owned worker.
                raise ValueError("VOICE_CANCELLED")
            self.user.TranslateMessage(pointer)
            self.user.DispatchMessageW(pointer)


class WakeSetupError(ValueError):
    def __init__(self, stage, cause):
        hresult = getattr(cause, "hresult", None)
        if type(hresult) is not int or not -(2**31) <= hresult < 2**31:
            hresult = None
        self.diagnostic = WakeSetupDiagnostic(
            stage=stage,
            category="BINDING"
            if isinstance(cause, (TypeError, AttributeError, NotImplementedError))
            else "NATIVE"
            if hresult is not None
            else "SETUP",
            hresult=hresult,
        )
        super().__init__("WAKE_SETUP_" + stage)


class WakeEvents:
    def __init__(self, config, cancel, emit):
        self.gate = WakeGate(config.wake_followup_seconds, wake_call=config.wake_call)
        self.cancel, self.emit = cancel, emit
        self.started = self.matched = self.closed = False
        self.failure = None
        self.resume = False
        self.last_level = 0

    def StartStream(self, stream_number, stream_position):
        if not self.closed and not self.cancel.is_set():
            self.started = True
            self.emit("stage", state="WAKE_LISTENING")

    def EndStream(self, stream_number, stream_position, stream_released):
        if not self.closed and not self.matched and not self.cancel.is_set():
            self.failure = "MICROPHONE_DISCONNECTED_OR_OVERFLOW"

    def Recognition(self, stream_number, stream_position, recognition_type, result):
        if self.closed or self.matched or self.cancel.is_set():
            return
        try:
            # Hypotheses and emulated recognitions are not wake detections.
            if recognition_type not in {0, 1}:  # Standard or auto-paused; never emulated.
                return
            self.resume = recognition_type == 1
            phrase = result.PhraseInfo
            if phrase.Rule.Name != "jarvis_wake" or phrase.Rule.Id != 1:
                return
            text = phrase.GetText()
            if not isinstance(text, str) or len(text) > 128:
                return
            transcript = Transcript(
                text=text,
                language="en",
                uncertain=phrase.Rule.Confidence != 1,  # SAPI high confidence required.
                seconds=0.0,
            )
            _, armed = self.gate.accept(transcript, time.monotonic())
            self.matched = armed
            if armed:
                self.emit("stage", state="WAKE_ACKNOWLEDGING")
            else:
                self.emit("wake_status", status="UNCLEAR" if transcript.uncertain else "NO_MATCH")
        except Exception:
            self.failure = "WAKE_RECOGNITION_FAILED"

    def FalseRecognition(self, stream_number, stream_position, result):
        if not self.closed and not self.matched and not self.cancel.is_set():
            self.emit("wake_status", status="NO_MATCH")

    def AudioLevel(self, stream_number, stream_position, audio_level):
        if self.closed or self.matched or not self.started or self.cancel.is_set():
            return
        now = time.monotonic()
        if now - self.last_level >= 0.25 and type(audio_level) is int and 0 <= audio_level <= 100:
            self.last_level = now
            self.emit("wake_level", value=audio_level)


def choose_input(collection, config, default_id):
    if not 0 < collection.Count <= 256:
        raise ValueError("MICROPHONE_UNAVAILABLE_OR_DENIED")
    if config.input_device:
        # Resolve only the exact friendly name of the selected trusted OS input.
        # PortAudio host APIs have separate entries; never switch to another mic.
        _, separator, name = config.input_device.partition(" / ")
        if not separator:
            raise ValueError("MICROPHONE_CHANGED_OR_AMBIGUOUS")
        matches = [
            collection.Item(i)
            for i in range(collection.Count)
            if collection.Item(i).GetDescription().casefold() == name.casefold()
        ]
    else:
        matches = [
            collection.Item(i)
            for i in range(collection.Count)
            if collection.Item(i).Id == default_id
        ]
    if len(matches) != 1:
        raise ValueError("MICROPHONE_CHANGED_OR_AMBIGUOUS")
    return matches[0]


class WindowsWakeDetector:
    def __init__(self, config, cancel, emit):
        self.config, self.cancel, self.emit = config, cancel, emit
        self.events = WakeEvents(config, cancel, emit)
        self.recognizer = self.context = self.grammar = self.connection = None
        self.setup_stage = "CREATE"

    def open(self, *, activate=True):
        try:
            self._open(activate=activate)
        except ValueError:
            raise
        except Exception as exc:
            raise WakeSetupError(self.setup_stage, exc) from None

    def _open(self, *, activate):
        from ctypes import byref

        from comtypes.automation import VARIANT
        from comtypes.client import CreateObject, GetEvents

        if self.cancel.is_set():
            return
        if self.config.language not in {None, "en"}:
            raise ValueError("WAKE_LANGUAGE_UNAVAILABLE")
        # Never use SpSharedRecognizer: all state changes belong to this worker.
        self.recognizer = recognizer = CreateObject("SAPI.SpInprocRecognizer")
        if recognizer.IsShared:
            self.recognizer = None
            raise ValueError("WAKE_ENGINE_NOT_PRIVATE")
        recognizer.State = 0  # Inactive until grammar, device and event sink are ready.
        self.setup_stage = "ENGINE"
        engines = recognizer.GetRecognizers("Language=409;Vendor=Microsoft")
        if engines.Count != 1:
            raise ValueError("WAKE_ENGINE_MISSING_OR_AMBIGUOUS")
        recognizer.Recognizer = engines.Item(0)
        self.setup_stage = "INPUT"
        default_id = ""
        if not self.config.input_device:
            category = CreateObject("SAPI.SpObjectTokenCategory")
            category.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\AudioInput", False)
            default_id = category.Default
        recognizer.AudioInput = choose_input(recognizer.GetAudioInputs(), self.config, default_id)
        self.setup_stage = "CONTEXT"
        self.context = context = recognizer.CreateRecoContext()
        context.RetainedAudio = 0
        # Recognition, false recognition, stream start/end, and input level only.
        context.EventInterests = 16 | 512 | 16384 | 1 | 65536
        self.setup_stage = "EVENTS"
        from comtypes.gen.SpeechLib import _ISpeechRecoContextEvents

        # Context pointers need not expose a discoverable default source/CLSID.
        self.connection = GetEvents(context, self.events, interface=_ISpeechRecoContextEvents)
        self.setup_stage = "GRAMMAR"
        self.grammar = grammar = context.CreateGrammar(1)
        grammar.Reset(0x409)
        rule = grammar.Rules.Add("jarvis_wake", 1 | 32, 1)  # Top-level, dynamic.
        empty = VARIANT()
        for prefix in ("", "hey ", "okay ", "ok "):
            rule.InitialState.AddWordTransition(
                None, prefix + self.config.wake_call, " ", 1, "", 0, byref(empty), 1.0
            )
        grammar.Rules.Commit()
        if not activate:
            if recognizer.State != 0:
                raise ValueError("WAKE_INACTIVE_SETUP_NOT_INACTIVE")
            return  # No active rule, event pump, recording or speech in setup inspection.
        if self.cancel.is_set():
            return
        self.setup_stage = "ACTIVATE"
        recognizer.State = 1
        # Auto-pause after a full grammar match, never on an unfinished hypothesis.
        grammar.CmdSetRuleState("jarvis_wake", 3)

    def wait(self, deadline):
        pump = WakeMessagePump()
        start_until = time.monotonic() + 8
        while not self.cancel.is_set() and time.monotonic() < deadline:
            pump.pump()
            if self.events.failure:
                raise ValueError(self.events.failure)
            if self.events.matched:
                return True
            if self.events.resume:
                self.context.Resume()  # Rejected auto-paused result must not stop listening.
                self.events.resume = False
            if not self.events.started and time.monotonic() >= start_until:
                raise ValueError("MICROPHONE_START_TIMEOUT")
            self.cancel.wait(0.01)
        return False

    def close(self):
        self.events.closed = True
        try:
            if self.recognizer is not None:
                self.recognizer.State = 3  # Inactive with purge; this instance only.
                if self.recognizer.State not in {0, 3}:
                    raise ValueError("WAKE_INPUT_DID_NOT_STOP")
        except ValueError:
            raise
        except Exception as exc:
            raise WakeSetupError("STOP", exc) from None
        finally:
            try:
                if self.connection is not None:
                    self.connection.disconnect()
            finally:
                self.connection = self.grammar = self.context = self.recognizer = None
