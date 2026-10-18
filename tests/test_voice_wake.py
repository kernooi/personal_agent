"""Fake-only wake address/lifecycle coverage. No microphones or speakers."""

import threading

import pytest
from test_voice import Jobs, transcript

from jarvis.voice import Voice
from jarvis.voice_data import VoiceConfig, VoiceState
from jarvis.voice_wake import SpeechBuffer, WakeGate


def test_custom_wake_call_replaces_jarvis_and_matches_whole_words():
    gate = WakeGate(wake_call="Hey Nova")
    assert gate.accept(transcript("Jarvis"), 1) == (None, False)
    assert gate.accept(transcript("Hey Novaline"), 2) == (None, False)
    assert gate.accept(transcript("I said Hey Nova"), 3) == (None, False)
    assert gate.accept(transcript("HEY   NOVA!"), 4) == (None, True)
    gate.arm(6)  # After acknowledgement/output and real mic restart.
    accepted, _ = gate.accept(transcript("what is your name"), 8, started_at=7)
    assert accepted.text == "what is your name"
    assert gate.accept(transcript("open Notepad"), 9) == (None, False)


def test_custom_wake_call_preserves_single_utterance_and_confidence_gate():
    gate = WakeGate(wake_call="Computer")
    assert gate.accept(transcript("Computer", uncertain=True), 1) == (None, False)
    accepted, armed = gate.accept(transcript("Computer, what is your name?"), 2)
    assert accepted.text == "what is your name?" and not armed


@pytest.mark.parametrize("call", ["", "   ", "a b c d e f", "Nova.*", "hello\x00there"])
def test_invalid_wake_calls_do_not_enable_listener(call):
    with pytest.raises(ValueError):
        VoiceConfig(wake_call=call)


def test_custom_wake_call_and_command_window_survive_private_save(tmp_path):
    from jarvis.voice_data import load_config

    voice = Voice(tmp_path, lambda *a: None, lambda *a: None, jobs=Jobs())
    voice.save(VoiceConfig(wake_call="  Hey   Nova  ", wake_followup_seconds=15))
    saved = load_config(tmp_path)
    assert saved.wake_call == "Hey Nova" and saved.wake_followup_seconds == 15
    assert WakeGate(15, wake_call=saved.wake_call).accept(transcript("Hey Nova"), 1) == (
        None,
        True,
    )


def test_wake_acknowledgement_pauses_input_and_keeps_worker_open(monkeypatch):
    from jarvis import voice_worker as worker

    events, calls = [], []

    class Stream:
        active = True

        def stop(self):
            self.active = False

    stream = Stream()
    cancel, finish = threading.Event(), threading.Event()

    def speak(text, config, token, *, report_done):
        assert not stream.active  # Never capture the spoken acknowledgement.
        assert token is cancel and not report_done
        assert config.speech_seconds == 10
        calls.append(text)
        worker.emit("stage", state="SPEAKING")

    monkeypatch.setattr(worker, "speak", speak)
    monkeypatch.setattr(worker, "emit", lambda kind, **data: events.append((kind, data)))
    assert worker.acknowledge_wake(stream, VoiceConfig(), finish, cancel)
    assert calls == ["Yes sir."]
    assert events == [
        ("stage", {"state": "WAKE_ACKNOWLEDGING"}),
        ("stage", {"state": "SPEAKING"}),
    ]  # No done or transcript; the same wake worker will resume capture.


@pytest.mark.parametrize("stop_at", ["before", "during"])
def test_stopped_wake_acknowledgement_cannot_resume_capture(monkeypatch, stop_at):
    from jarvis import voice_worker as worker

    cancel, finish = threading.Event(), threading.Event()
    if stop_at == "before":
        cancel.set()

    class Stream:
        active = True

        def stop(self):
            self.active = False

    calls = []

    def speak(*args, **kwargs):
        calls.append(args[0])
        cancel.set()

    stream = Stream()
    monkeypatch.setattr(worker, "speak", speak)
    monkeypatch.setattr(worker, "emit", lambda *a, **k: None)
    assert not worker.acknowledge_wake(stream, VoiceConfig(), finish, cancel)
    assert not stream.active
    assert calls == ([] if stop_at == "before" else ["Yes sir."])


def test_followup_starts_after_acknowledgement_not_initial_detection():
    gate = WakeGate(10)
    assert gate.accept(transcript("Jarvis"), 1) == (None, True)
    gate.arm(12)  # Actual capture restarted after acknowledgement.
    assert gate.accept(transcript("open Notepad"), 13, started_at=2) == (None, False)
    gate.arm(12)
    accepted, _ = gate.accept(transcript("what is your name"), 18, started_at=15)
    assert accepted.text == "what is your name"
    assert gate.accept(transcript("open Notepad"), 19) == (None, False)


def test_acknowledgement_states_use_same_orb_without_submitting_a_request(tmp_path):
    jobs, states, sent = Jobs(), [], []
    voice = Voice(
        tmp_path,
        lambda kind, value: states.append(value) if kind == "state" else None,
        lambda *args: sent.append(args),
        config=VoiceConfig(interaction_mode="wake_word"),
        jobs=jobs,
    )
    voice.devices.update(stt_ready=True, inputs=[{"id": "fake"}])
    assert voice.start_wake()
    for state in ("WAKE_LISTENING", "WAKE_CHECKING", "WAKE_ACKNOWLEDGING", "SPEAKING", "LISTENING"):
        jobs.emit("stage", state=state)
    jobs.emit("wake_ready")
    voice.poll()
    assert voice.state == VoiceState.LISTENING and not sent
    assert VoiceState.WAKE_ACKNOWLEDGING in states and VoiceState.SPEAKING in states
    assert len(jobs.calls) == 1 and jobs.active  # No second audio worker/model request.
    voice.cancel()
    jobs.emit("stage", state="LISTENING")  # A late event cannot undo Stop.
    jobs.emit("finished")
    voice.poll()
    assert voice.wake_paused and not voice.start_wake() and not sent


def test_unaddressed_ambient_words_never_become_a_request():
    gate = WakeGate()
    assert gate.accept(transcript("open Notepad"), 1) == (None, False)
    assert gate.accept(transcript("I told Jarvis to open it"), 2) == (None, False)
    result, armed = gate.accept(transcript("Hey Jarvis, open Notepad"), 3)
    assert result.text == "open Notepad" and not armed


def test_standalone_wake_has_one_short_followup_and_expires():
    gate = WakeGate(10)
    assert gate.accept(transcript("Jarvis"), 1) == (None, True)
    result, _ = gate.accept(transcript("what is your name"), 3)
    assert result.text == "what is your name"
    assert gate.accept(transcript("open Notepad"), 4) == (None, False)
    assert gate.accept(transcript("Jarvis"), 5) == (None, True)
    assert gate.accept(transcript("open Notepad"), 16) == (None, False)
    assert gate.accept(transcript("Jarvis, open Notepad", uncertain=True), 17) == (None, False)


def test_followup_uses_capture_time_when_recognition_finishes_later():
    gate = WakeGate(10)
    assert gate.accept(transcript("Jarvis"), 1) == (None, True)
    result, _ = gate.accept(transcript("what is your name"), 15, started_at=3)
    assert result.text == "what is your name"
    gate.accept(transcript("Jarvis"), 20)
    assert gate.accept(transcript("open Notepad"), 35, started_at=31) == (None, False)
    gate.accept(transcript("Jarvis"), 40)
    assert gate.accept(transcript("open Notepad"), 42, started_at=39) == (None, False)


def test_long_idle_silence_cannot_dilute_a_short_soft_wake_clip():
    import struct

    buffer = SpeechBuffer(16000, 20, 1.1, 100)
    at, clips = 0, []
    for rms in [0] * 200 + [140] * 8 + [0] * 24:
        at += 0.05
        clip = buffer.feed(struct.pack("<h", rms) * 800, 800, rms, at)
        if clip is not None:
            clips.append(clip)
    assert len(clips) == 1
    assert 6400 <= len(clips[0].pcm) < 64000  # Under two seconds, not the ten-second wait.
    assert clips[0].started_at >= 9.99
    assert not buffer.active


def test_overlong_speech_discards_the_whole_tail_then_recovers():
    import struct

    buffer = SpeechBuffer(16000, 2, 0.4, 100)
    at, clips = 0, []
    for rms in [200] * 60 + [0] * 12 + [140] * 8 + [0] * 12:
        at += 0.05
        clip = buffer.feed(struct.pack("<h", rms) * 800, 800, rms, at)
        if clip is not None:
            clips.append(clip)
    assert len(clips) == 2
    assert clips[0].pcm == b"" and clips[1].pcm
    assert not buffer.active and not buffer.parts


@pytest.mark.parametrize("addressed", [True, False])
def test_wake_uses_existing_submission_and_cannot_restart_through_stop(tmp_path, addressed):
    jobs, sent = Jobs(), []
    v = Voice(
        tmp_path,
        lambda *a: None,
        lambda *a: sent.append(a) or True,
        config=VoiceConfig(interaction_mode="wake_word"),
        jobs=jobs,
    )
    v.devices.update(stt_ready=True, inputs=[{"id": "fake"}])
    assert v.start_wake()
    jobs.emit("stage", state="WAKE_LISTENING")
    jobs.emit("stage", state="WAKE_CHECKING")
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit(
        "transcript", transcript=transcript("what is your name").model_dump(), addressed=addressed
    )
    jobs.emit("finished")
    v.poll()
    if not addressed:
        assert not sent and v.state == VoiceState.ERROR
        return
    assert sent == [("what is your name", "what is your name")]
    assert v.state == VoiceState.PROCESSING and not v.start_wake()
    v.reply("I am JARVIS.")
    v.ready()
    assert jobs.calls[-1][0] == "speak" and not v.start_wake()
    jobs.emit("stage", state="SPEAKING")
    jobs.emit("done")
    jobs.emit("finished")
    v.poll()
    assert v.start_wake()
    v.cancel()
    jobs.emit("finished")
    v.poll()
    assert v.wake_paused and not v.start_wake()


@pytest.mark.parametrize("stop_before_finished", [False, True])
def test_empty_command_ends_turn_and_rearms_only_after_shutdown_unless_stopped(
    tmp_path, stop_before_finished
):
    jobs, events, sent = Jobs(), [], []
    v = Voice(
        tmp_path,
        lambda *a: events.append(a),
        lambda *a: sent.append(a) or True,
        config=VoiceConfig(interaction_mode="wake_word", wake_call="Computer"),
        jobs=jobs,
    )
    v.devices.update(stt_ready=True, inputs=[{"id": "fake"}])
    assert v.start_wake()
    jobs.emit("stage", state="LISTENING")
    jobs.emit("stage", state="TRANSCRIBING")
    jobs.emit("error", code="NO_SPEECH_DETECTED")
    v.poll()
    assert v.state == VoiceState.TRANSCRIBING and v.error is None
    assert not v.cancelled and not jobs.cancelled and not sent
    assert not v.start_wake() and len(jobs.calls) == 1
    assert any(kind == "notice" and "Computer" in value for kind, value in events)
    if stop_before_finished:
        v.cancel()
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.IDLE and not sent and v.pending is None
    assert v.start_wake() is (not stop_before_finished)
    assert len(jobs.calls) == (1 if stop_before_finished else 2)


@pytest.mark.parametrize(
    "operation,state,code,extra",
    [
        ("listen", "TRANSCRIBING", "NO_SPEECH_DETECTED", {}),
        ("wake", "WAKE_LISTENING", "NO_SPEECH_DETECTED", {}),
        ("wake", "TRANSCRIBING", "MICROPHONE_DISCONNECTED_OR_OVERFLOW", {}),
        ("wake", "TRANSCRIBING", "VOICE_TIMEOUT", {}),
        ("speak", "SPEAKING", "SPEECH_PLAYBACK_NOT_STARTED", {}),
        ("wake", "TRANSCRIBING", "NO_SPEECH_DETECTED", {"unexpected": True}),
    ],
)
def test_empty_command_exception_does_not_hide_other_voice_failures(
    tmp_path, operation, state, code, extra
):
    jobs, sent = Jobs(), []
    v = Voice(tmp_path, lambda *a: None, lambda *a: sent.append(a), jobs=jobs)
    assert v.start(operation)
    v.state = VoiceState(state)
    jobs.emit("error", code=code, **extra)
    jobs.emit("finished")
    v.poll()
    assert v.state == VoiceState.ERROR and v.error == code
    assert jobs.cancelled and not sent
