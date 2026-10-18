"""Synthetic PCM and recognizer results only. No microphone, speaker or model inference."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from jarvis.voice_data import Audio, VoiceConfig, needs_review
from jarvis.voice_worker import pcm_audio, transcribe


def test_native_16k_pcm_is_preserved_exactly():
    pcm = np.arange(-4000, 4000, dtype="<i2").tobytes()
    assert pcm_audio(pcm, 16000, 20).pcm == pcm


@pytest.mark.parametrize("rate", [44100, 48000])
def test_headset_resampling_preserves_speech_band_and_rejects_aliasing(rate):
    times = np.arange(rate) / rate
    voice = (12000 * np.sin(2 * np.pi * 1000 * times)).astype("<i2")
    high_frequency = (12000 * np.sin(2 * np.pi * 12000 * times)).astype("<i2")
    converted = np.frombuffer(pcm_audio(voice.tobytes(), rate, 20).pcm, dtype="<i2")
    filtered = np.frombuffer(pcm_audio(high_frequency.tobytes(), rate, 20).pcm, dtype="<i2")
    assert 15999 <= len(converted) <= 16001

    # Exclude filter boundaries from spectral-quality assertions; keep them in PCM.
    def rms(values):
        return np.sqrt(np.mean(values.astype(np.float64) ** 2))

    assert 0.95 <= rms(converted[160:-160]) / rms(voice) <= 1.05
    assert rms(filtered[160:-160]) < rms(high_frequency) * 0.01


@pytest.mark.parametrize("beam", [0, 9, True, "5"])
def test_recognition_search_budget_is_strict_and_bounded(beam):
    with pytest.raises(ValidationError):
        VoiceConfig(stt_beam_size=beam)


@pytest.fixture
def recognition(monkeypatch, tmp_path):
    calls = []
    segments = [
        SimpleNamespace(
            text="what is your name", no_speech_prob=0.1, avg_logprob=-0.2, compression_ratio=1.0
        )
    ]

    def decode(samples, **options):
        assert samples.dtype == np.float32 and samples.ndim == 1
        calls.append(options)
        return iter(segments), SimpleNamespace(language="en")

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=lambda *a, **k: pytest.fail("No model load/download")),
    )
    model = SimpleNamespace(transcribe=decode, model=SimpleNamespace(is_multilingual=False))
    audio = Audio((np.full(16000, 300, dtype="<i2")).tobytes())
    return calls, segments, model, audio, tmp_path


def test_decoder_uses_bounded_search_without_history_or_vocabulary_bias(recognition):
    calls, _, model, audio, root = recognition
    result, metrics = transcribe(audio, root, VoiceConfig(), model=model)
    assert result.text == "what is your name" and not result.uncertain
    assert calls[0]["beam_size"] == 5
    assert calls[0]["condition_on_previous_text"] is False
    assert calls[0]["temperature"] == 0
    assert calls[0]["vad_parameters"]["speech_pad_ms"] == 500
    assert "initial_prompt" not in calls[0] and "hotwords" not in calls[0]
    assert metrics["audio_seconds"] == 1.0
    assert 0 < metrics["audio_rms"] <= metrics["audio_peak"] < 1
    assert metrics["clipped_fraction"] == 0
    assert metrics["minimum_logprob"] == -0.2
    assert all("text" not in key and "pcm" not in key for key in metrics)


def test_high_no_speech_segment_is_not_silently_removed_from_the_request(recognition):
    _, segments, model, audio, root = recognition
    segments.insert(
        0,
        SimpleNamespace(text="do not", no_speech_prob=0.7, avg_logprob=-0.2, compression_ratio=1.0),
    )
    result, _ = transcribe(audio, root, VoiceConfig(), model=model)
    assert result.text == "do not what is your name" and result.uncertain
    assert needs_review(result, VoiceConfig())  # Never auto-submit an incomplete command.


@pytest.mark.parametrize("field", ["no_speech_prob", "avg_logprob", "compression_ratio"])
def test_nonfinite_recognition_confidence_cannot_auto_submit(recognition, field):
    _, segments, model, audio, root = recognition
    setattr(segments[0], field, float("nan"))
    with pytest.raises(ValueError, match="STT_RESULT_INVALID"):
        transcribe(audio, root, VoiceConfig(), model=model)


def test_cancelled_recognition_never_calls_the_decoder(recognition):
    calls, _, model, audio, root = recognition
    with pytest.raises(ValueError, match="CANCELLED"):
        transcribe(audio, root, VoiceConfig(), cancel=lambda: True, model=model)
    assert calls == []


def test_command_pause_keeps_two_parts_of_a_sentence_in_one_clip():
    from jarvis.voice_wake import SpeechBuffer

    buffer = SpeechBuffer(16000, 20, 1.0, 100)
    clips, at = [], 0
    for level in [400] * 8 + [0] * 13 + [500] * 8 + [0] * 21:
        at += 0.05
        pcm = np.full(800, level, dtype="<i2").tobytes()
        clip = buffer.feed(pcm, 800, level, at)
        if clip is not None:
            clips.append(clip)
    assert len(clips) == 1
    samples = np.frombuffer(clips[0].pcm, dtype="<i2")
    assert np.any(samples == 400) and np.any(samples == 500)


def test_callback_delay_cannot_masquerade_as_recorded_silence():
    from jarvis.voice_wake import SpeechBuffer

    buffer = SpeechBuffer(16000, 20, 1.0, 100)
    sound = np.full(800, 400, dtype="<i2").tobytes()
    quiet = bytes(1600)
    assert buffer.feed(sound, 800, 400, 1.0) is None
    assert buffer.feed(sound, 800, 400, 1.05) is None
    assert buffer.feed(quiet, 800, 0, 5.0) is None  # Only 50ms of actual quiet.
    for index in range(18):
        assert buffer.feed(quiet, 800, 0, 5.05 + index * 0.05) is None
    assert buffer.feed(quiet, 800, 0, 6.0) is not None
