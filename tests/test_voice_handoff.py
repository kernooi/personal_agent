"""Synthetic audio/devices only; no microphone, SAPI playback or subprocesses."""

import queue
import struct
import sys
import threading
from types import SimpleNamespace

import pytest

from jarvis.voice_data import Transcript, VoiceConfig


@pytest.fixture
def handoff(monkeypatch, tmp_path):
    from jarvis import voice_keyword
    from jarvis import voice_worker as worker

    order, events = [], []
    clock = SimpleNamespace(value=100.0)
    state = SimpleNamespace(
        stream=None, start_error=False, active_on_open=False, matched=True, on_ack=lambda: None
    )

    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.active, self.closed = state.active_on_open, False
            state.stream = self
            order.append("reserve")

        def start(self):
            assert "ack" in order and "wake_closed" in order
            order.append("capture")
            if state.start_error:
                raise OSError("synthetic start failure")
            self.active = True
            for value in [400] * 4 + [0] * 12:
                clock.value += 0.05
                self.callback(struct.pack("<h", value) * 800, 800, None, False)

        def close(self):
            order.append("input_closed")
            self.active, self.closed = False, True

    class Detector:
        def __init__(self, *args):
            pass

        def open(self):
            assert state.stream is not None and not state.stream.active
            order.append("wake_open")

        def wait(self, deadline):
            return state.matched

        def close(self):
            order.append("wake_closed")

    def acknowledgement(*args, **kwargs):
        assert not state.stream.active
        order.append("ack")
        state.on_ack()
        return clock.value

    def transcribe(audio, config, cancel):
        assert state.stream.closed and not state.stream.active
        audio.validate()
        assert audio.pcm[:2] == struct.pack("<h", 400)
        order.append("transcribe")
        return Transcript(
            text="What is your name?", language="en", uncertain=False, seconds=1.0
        ), {}

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawInputStream=Stream, CallbackStop=RuntimeError, CallbackAbort=RuntimeError
        ),
    )
    monkeypatch.setattr(worker, "time", SimpleNamespace(monotonic=lambda: clock.value))
    monkeypatch.setattr(worker, "input_format", lambda config: (0, 16000))
    monkeypatch.setattr(worker, "emit", lambda kind, **data: events.append((kind, data)))
    monkeypatch.setattr(worker, "speak", acknowledgement)
    monkeypatch.setattr(
        worker, "FasterWhisperSTT", lambda root: SimpleNamespace(transcribe=transcribe)
    )
    monkeypatch.setattr(voice_keyword, "WindowsWakeDetector", Detector)
    return worker, state, clock, order, events, tmp_path


def test_command_input_is_reserved_early_starts_after_ack_and_preserves_first_samples(handoff):
    worker, state, _, order, events, root = handoff
    worker.wake(root, VoiceConfig(wake_silence_seconds=0.4), threading.Event(), threading.Event())
    assert order == [
        "reserve",
        "wake_open",
        "wake_closed",
        "ack",
        "capture",
        "input_closed",
        "transcribe",
    ]
    assert state.stream.closed
    ready = [data for kind, data in events if kind == "wake_ready"]
    assert len(ready) == 1
    assert ready[0]["metrics"]["command_input_ready_seconds"] == pytest.approx(0.05)
    assert [kind for kind, _ in events].count("transcript") == 1


@pytest.mark.parametrize("stop_kind", ["cancel", "finish"])
def test_stop_during_ack_never_starts_reserved_input(handoff, stop_kind):
    worker, state, _, order, events, root = handoff
    finish, cancel = threading.Event(), threading.Event()
    state.on_ack = (cancel if stop_kind == "cancel" else finish).set
    worker.wake(root, VoiceConfig(), finish, cancel)
    assert "capture" not in order and "transcribe" not in order
    assert state.stream.closed
    assert not any(kind in {"wake_ready", "transcript"} for kind, _ in events)


def test_no_wake_closes_reserved_input_without_ack_or_capture(handoff):
    worker, state, _, order, _, root = handoff
    state.matched = False
    worker.wake(root, VoiceConfig(), threading.Event(), threading.Event())
    assert order == ["reserve", "wake_open", "wake_closed", "input_closed"]
    assert state.stream.closed


def test_neural_ack_is_prepared_before_input_and_uses_the_same_verified_handoff(
    handoff, monkeypatch
):
    from jarvis import voice_neural

    worker, state, _, order, events, root = handoff
    pcm = b"\x00\x01" * 1000

    def acknowledgement(*args):
        assert state.stream is None
        order.append("load_ack")
        return pcm

    play = worker.speak

    def verified_play(*args, **kwargs):
        assert kwargs["pcm"] == pcm
        return play(*args, **kwargs)

    monkeypatch.setattr(voice_neural, "acknowledgement", acknowledgement)
    monkeypatch.setattr(worker, "speak", verified_play)
    worker.wake(
        root,
        VoiceConfig(tts_provider="kokoro", wake_silence_seconds=0.4),
        threading.Event(),
        threading.Event(),
    )
    assert order == [
        "load_ack",
        "reserve",
        "wake_open",
        "wake_closed",
        "ack",
        "capture",
        "input_closed",
        "transcribe",
    ]
    assert any(kind == "wake_ready" for kind, _ in events)


@pytest.mark.parametrize("failure", ["start_error", "active_on_open"])
def test_native_input_failure_cannot_claim_readiness_or_submit(handoff, failure):
    worker, state, _, order, events, root = handoff
    setattr(state, failure, True)
    with pytest.raises(ValueError, match="MICROPHONE|WAKE_INPUT_NOT_INACTIVE"):
        worker.wake(root, VoiceConfig(), threading.Event(), threading.Event())
    assert state.stream.closed and "transcribe" not in order
    assert not any(kind in {"wake_ready", "transcript"} for kind, _ in events)


@pytest.mark.parametrize("late_frame", [False, True])
def test_input_active_without_timely_samples_is_not_listening(handoff, late_frame):
    worker, _, clock, _, events, _ = handoff

    def get(timeout):
        clock.value = 109.0
        if late_frame:
            return bytes(1600), 800, 0, clock.value
        raise queue.Empty

    stream = SimpleNamespace(active=False)
    stream.start = lambda: setattr(stream, "active", True)
    prepared = (stream, 16000, SimpleNamespace(get=get), threading.Event(), threading.Event())
    with pytest.raises(ValueError, match="MICROPHONE_START_TIMEOUT"):
        worker.record_wake_command(
            VoiceConfig(), threading.Event(), threading.Event(), prepared, 100.0
        )
    assert not any(kind in {"wake_ready", "stage"} for kind, _ in events)
