"""Fake-only offline wake grammar and handoff cases. No native audio."""

import threading
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from jarvis.voice_data import VoiceConfig
from jarvis.voice_keyword import (
    WakeEvents,
    WakeMessagePump,
    WakeSetupError,
    WindowsWakeDetector,
    choose_input,
)


@pytest.mark.parametrize("quit_message", [False, True])
def test_owned_message_pump_bounds_dispatch_and_honors_quit(quit_message):
    # Fake queue only: no native messages, microphone, or desktop input.
    import ctypes
    from ctypes import wintypes

    pump = object.__new__(WakeMessagePump)
    pump.c, pump.message = ctypes, wintypes.MSG()
    calls = []

    def peek(pointer, window, first, last, remove):
        assert window is None and (first, last, remove) == (0, 0, 1)
        calls.append("peek")
        pump.message.message = 0x0012 if quit_message else 0x0113
        return True

    pump.user = SimpleNamespace(
        PeekMessageW=peek,
        TranslateMessage=lambda pointer: calls.append("translate"),
        DispatchMessageW=lambda pointer: calls.append("dispatch"),
    )
    if quit_message:
        with pytest.raises(ValueError, match="VOICE_CANCELLED"):
            pump.pump()
        assert calls == ["peek"]
    else:
        pump.pump()
        assert calls == ["peek", "translate", "dispatch"] * 64


def test_inactive_setup_binds_exact_event_interface_without_activating_audio(monkeypatch):
    import comtypes.client
    from comtypes.gen.SpeechLib import _ISpeechRecoContextEvents

    bound, activated, disconnected = [], [], []
    microphone = SimpleNamespace(Id="mic", GetDescription=lambda: "Headset")
    inputs = SimpleNamespace(Count=1, Item=lambda i: microphone)
    engines = SimpleNamespace(Count=1, Item=lambda i: SimpleNamespace(Id="engine"))
    rule = SimpleNamespace(InitialState=SimpleNamespace(AddWordTransition=lambda *a: None))
    grammar = SimpleNamespace(
        Reset=lambda language: None,
        Rules=SimpleNamespace(Add=lambda *a: rule, Commit=lambda: None),
        CmdSetRuleState=lambda *a: activated.append(a),
    )
    context = SimpleNamespace(CreateGrammar=lambda *a: grammar)
    recognizer = SimpleNamespace(
        State=0,
        IsShared=False,
        GetRecognizers=lambda *a: engines,
        GetAudioInputs=lambda: inputs,
        CreateRecoContext=lambda: context,
    )

    def connect(source, events, *, interface):
        assert source is context and interface is _ISpeechRecoContextEvents
        bound.append(interface)
        return SimpleNamespace(disconnect=lambda: disconnected.append(True))

    monkeypatch.setattr(comtypes.client, "CreateObject", lambda name: recognizer)
    monkeypatch.setattr(comtypes.client, "GetEvents", connect)
    detector = WindowsWakeDetector(
        VoiceConfig(input_device="MME / Headset"), threading.Event(), lambda *a, **k: None
    )
    try:
        detector.open(activate=False)
        assert recognizer.State == 0 and not activated
        assert recognizer.AudioInput is microphone
        assert len(bound) == 1 and not detector.events.started
    finally:
        detector.close()
    assert disconnected == [True]


def test_setup_error_metadata_excludes_native_exception_text():
    error = WakeSetupError("EVENTS", TypeError("private exception details must not be logged"))
    assert str(error) == "WAKE_SETUP_EVENTS"
    assert error.diagnostic.model_dump() == {
        "stage": "EVENTS",
        "category": "BINDING",
        "hresult": None,
    }


def test_original_setup_error_survives_cleanup_failure(monkeypatch, tmp_path):
    from jarvis import voice_keyword, voice_worker

    original = WakeSetupError("EVENTS", TypeError())

    class Detector:
        def __init__(self, *a):
            pass

        def open(self):
            raise original

        def close(self):
            raise WakeSetupError("STOP", OSError())

    monkeypatch.setattr(voice_keyword, "WindowsWakeDetector", Detector)
    monkeypatch.setattr(voice_worker, "prepare_wake_command", lambda *a: nullcontext(None))
    monkeypatch.setattr(voice_worker, "emit", lambda *a, **k: None)
    with pytest.raises(WakeSetupError) as raised:
        voice_worker.wake(tmp_path, VoiceConfig(), threading.Event(), threading.Event())
    assert raised.value is original


def result(text, confidence=1, rule="jarvis_wake"):
    return SimpleNamespace(
        PhraseInfo=SimpleNamespace(
            Rule=SimpleNamespace(Name=rule, Id=1, Confidence=confidence), GetText=lambda: text
        )
    )


@pytest.mark.parametrize("kind", [0, 1])
def test_complete_confident_custom_wake_shows_orb_without_transcription(kind):
    emitted = []
    events = WakeEvents(
        VoiceConfig(wake_call="Hey Nova"),
        threading.Event(),
        lambda event, **data: emitted.append((event, data)),
    )
    events.Recognition(1, 0, kind, result("Hey Nova"))
    assert events.matched
    assert emitted == [("stage", {"state": "WAKE_ACKNOWLEDGING"})]
    events.AudioLevel(1, 0, 20)  # No stale input level after switching to acknowledgement.
    assert len(emitted) == 1


@pytest.mark.parametrize(
    "text,confidence,kind,rule",
    [
        ("Jarvis", 0, 1, "jarvis_wake"),
        ("Jarvis", -1, 0, "jarvis_wake"),
        ("Jarvis", 1, 2, "jarvis_wake"),  # Emulation is not microphone evidence.
        ("Jarvis", 1, 0, "different_rule"),
        ("Jarvis, close Notepad", 1, 0, "jarvis_wake"),
        ("Jarvison", 1, 0, "jarvis_wake"),
        ("ordinary ambient words", 1, 0, "jarvis_wake"),
    ],
)
def test_uncertain_partial_emulated_or_unrelated_results_cannot_wake(text, confidence, kind, rule):
    emitted = []
    events = WakeEvents(
        VoiceConfig(), threading.Event(), lambda event, **data: emitted.append((event, data))
    )
    events.Recognition(1, 0, kind, result(text, confidence, rule))
    assert not events.matched
    assert all(event == "wake_status" for event, _ in emitted)
    assert all(set(data) == {"status"} for _, data in emitted)  # No ambient text leaves worker.


def test_stop_blocks_late_recognition_and_microphone_presentation():
    cancelled, emitted = threading.Event(), []
    events = WakeEvents(
        VoiceConfig(), cancelled, lambda event, **data: emitted.append((event, data))
    )
    cancelled.set()
    events.StartStream(1, 0)
    events.Recognition(1, 0, 0, result("Jarvis"))
    events.AudioLevel(1, 0, 50)
    assert not events.matched and not emitted


def test_rejected_auto_paused_result_resumes_only_owned_context(monkeypatch):
    from jarvis import voice_keyword

    detector = WindowsWakeDetector(VoiceConfig(), threading.Event(), lambda *a, **k: None)
    resumed = []
    detector.context = SimpleNamespace(Resume=lambda: resumed.append(True))
    detector.events.started = True
    detector.events.Recognition(1, 0, 1, result("Jarvis", 0))
    count = [0]

    def pump():
        count[0] += 1
        if count[0] == 2:
            detector.events.Recognition(1, 0, 1, result("Jarvis"))

    monkeypatch.setattr(voice_keyword, "WakeMessagePump", lambda: SimpleNamespace(pump=pump))
    assert detector.wait(time.monotonic() + 1)
    assert resumed == [True] and count[0] == 2


def test_exact_microphone_mapping_never_chooses_a_similarly_named_input():
    microphones = [
        SimpleNamespace(Id="a", GetDescription=lambda: "Headset"),
        SimpleNamespace(Id="b", GetDescription=lambda: "Headset Monitor"),
    ]
    collection = SimpleNamespace(Count=2, Item=lambda i: microphones[i])
    assert choose_input(collection, VoiceConfig(input_device="MME / Headset"), "") is microphones[0]
    assert choose_input(collection, VoiceConfig(), "b") is microphones[1]
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        choose_input(collection, VoiceConfig(input_device="MME / Head"), "a")
    microphones.append(microphones[0])
    collection.Count = 3
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        choose_input(collection, VoiceConfig(input_device="MME / Headset"), "")


@pytest.mark.parametrize("cancel_on_close", [False, True])
def test_native_wake_releases_input_before_ack_and_command_capture(
    monkeypatch, tmp_path, cancel_on_close
):
    from jarvis import voice_keyword, voice_worker

    order, emitted = [], []
    cancel, finish = threading.Event(), threading.Event()

    class Detector:
        def __init__(self, *args):
            pass

        def open(self):
            order.append("open")

        def wait(self, deadline):
            order.append("matched")
            return True

        def close(self):
            order.append("closed")
            if cancel_on_close:
                cancel.set()

    monkeypatch.setattr(voice_keyword, "WindowsWakeDetector", Detector)
    monkeypatch.setattr(voice_worker, "prepare_wake_command", lambda *a: nullcontext(None))
    monkeypatch.setattr(
        voice_worker, "speak", lambda *a, **k: order.append("ack") or time.monotonic()
    )
    monkeypatch.setattr(
        voice_worker, "record_wake_command", lambda *a: order.append("capture") or None
    )
    monkeypatch.setattr(voice_worker, "emit", lambda event, **data: emitted.append((event, data)))
    voice_worker.wake(tmp_path, VoiceConfig(), finish, cancel)
    assert order == (
        ["open", "matched", "closed"]
        if cancel_on_close
        else [
            "open",
            "matched",
            "closed",
            "ack",
            "capture",
        ]
    )
    assert not any(event == "transcript" for event, _ in emitted)
