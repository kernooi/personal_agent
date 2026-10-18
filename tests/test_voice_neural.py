"""Synthetic neural speech and output only; no models, microphones or speakers."""

import hashlib
import json
import sys
import threading
import time
import wave
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from jarvis import voice_neural as neural
from jarvis.voice_data import VoiceConfig


def test_legacy_voice_config_keeps_explicit_windows_engine():
    assert VoiceConfig().tts_provider == "windows_sapi"
    assert VoiceConfig(tts_provider="kokoro").neural_voice == "am_michael"
    with pytest.raises(ValidationError):
        VoiceConfig(tts_provider="cloud")


@pytest.fixture
def assets(monkeypatch, tmp_path):
    directory = tmp_path / "speech/kokoro-v1.0"
    directory.mkdir(parents=True)
    manifest = {}
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        data = b"synthetic " + name.encode()
        (directory / name).write_bytes(data)
        manifest[name] = (len(data), hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(neural, "ASSETS", manifest)
    return tmp_path, directory


def test_model_paths_and_identity_fail_without_download_or_substitution(assets):
    root, directory = assets
    assert neural.asset_directory(root, VoiceConfig(), verify=True) == directory
    with pytest.raises(ValueError, match="PATH_INVALID"):
        neural.asset_directory(root, VoiceConfig(tts_model_directory="../escape"))
    path = directory / "kokoro-v1.0.onnx"
    path.write_bytes(b"x" * path.stat().st_size)
    with pytest.raises(ValueError, match="MISSING_OR_CHANGED"):
        neural.asset_directory(root, VoiceConfig(), verify=True)


@pytest.mark.parametrize("text", ["Hello. " * 110, "x" * 1000, "Hello! How are you?"])
def test_chunks_preserve_entire_answer_with_bounded_synthesis(text):
    pieces = list(neural.chunks(text))
    assert all(1 <= len(piece) <= 220 for piece in pieces)
    assert "".join("".join(pieces).split()) == "".join(text.split())
    with pytest.raises(ValueError, match="TEXT_LIMIT"):
        list(neural.chunks("x" * 2401))


@pytest.mark.parametrize("invalid", ["nan", "silence", "stereo", "rate", "too_long"])
def test_neural_audio_validation_before_any_output(invalid):
    config = VoiceConfig()
    audio = np.full(1000, 0.2, dtype=np.float32)
    rate = 24000
    if invalid == "nan":
        audio[0] = np.nan
    elif invalid == "silence":
        audio[:] = 0
    elif invalid == "stereo":
        audio = audio.reshape(-1, 2)
    elif invalid == "rate":
        rate = 16000
    else:
        audio = np.ones(24000 * config.speech_seconds + 1, dtype=np.float32)
    engine = object.__new__(neural.NeuralSpeech)
    engine.config = config
    engine.engine = SimpleNamespace(create=lambda *a, **k: (audio, rate))
    with pytest.raises(ValueError, match="AUDIO_INVALID"):
        engine.render("A synthetic answer.", threading.Event(), time.monotonic() + 10)


def test_engine_is_cpu_only_and_uses_private_verified_assets(assets, monkeypatch):
    root, directory = assets
    observed = []
    fake = SimpleNamespace(get_voices=lambda: ["am_michael"])

    def session(path, *, sess_options, providers):
        observed.append((path, sess_options.intra_op_num_threads, providers))
        return "session"

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=session),
    )
    monkeypatch.setitem(
        sys.modules,
        "kokoro_onnx",
        SimpleNamespace(Kokoro=SimpleNamespace(from_session=lambda session, path: fake)),
    )
    engine = neural.NeuralSpeech(root, VoiceConfig())
    assert engine.engine is fake
    assert observed == [(str(directory / "kokoro-v1.0.onnx"), 2, ["CPUExecutionProvider"])]


def test_fixed_ack_cache_requires_matching_voice_rate_hash_and_audio_format(assets, monkeypatch):
    root, directory = assets
    config = VoiceConfig(tts_provider="kokoro")
    path = directory / neural.acknowledgement_name(config)
    pcm = b"\x00\x01" * 1000
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    receipt = {
        "voice": "am_michael",
        "rate": 0,
        "text": "Yes sir.",
        "sha256": neural.digest(path),
        "model_sha256": neural.ASSETS["kokoro-v1.0.onnx"][1],
    }
    path.with_suffix(".json").write_text(json.dumps(receipt))
    monkeypatch.setattr(
        neural,
        "NeuralSpeech",
        lambda *a: pytest.fail("Cached acknowledgement must not load a model"),
    )
    assert neural.acknowledgement(root, config, threading.Event()) == pcm
    receipt["voice"] = "bm_george"
    path.with_suffix(".json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="ACK_INVALID"):
        neural.acknowledgement(root, config, threading.Event())


@pytest.mark.parametrize("cancel_at", ["before", "synthesis", "play", "none"])
def test_reply_cancellation_prevents_new_output_and_false_completion(
    monkeypatch, tmp_path, cancel_at
):
    cancelled = threading.Event()
    calls, events = [], []
    config = VoiceConfig(tts_provider="kokoro")

    def render(text, cancel, deadline):
        calls.append("render")
        if cancel_at == "synthesis":
            cancel.set()
        return b"\x00\x01" * 1000

    def engine(*args):
        calls.append("load")
        return SimpleNamespace(render=render)

    def play(text, config, cancel, began, **options):
        calls.append("play")
        assert options["report_done"] is False and options["pcm"]
        began()
        if cancel_at == "play":
            cancel.set()
        return time.monotonic()

    monkeypatch.setattr(neural, "NeuralSpeech", engine)
    if cancel_at == "before":
        cancelled.set()
    neural.speak_reply(
        tmp_path,
        "A result. " * 60,
        config,
        cancelled,
        lambda: events.append("started"),
        play,
        lambda *a, **k: events.append("done"),
    )
    if cancel_at == "before":
        assert calls == [] and events == []
    elif cancel_at == "synthesis":
        assert calls == ["load", "render"] and events == []
    elif cancel_at == "play":
        assert calls == ["load", "render", "play"] and events == ["started"]
    else:
        assert calls.count("play") >= 2 and events == ["started", "done"]


def test_neural_pcm_uses_exact_selected_output_and_verified_stream_events(monkeypatch):
    from jarvis import voice_worker as worker

    calls, events = [], []
    output = SimpleNamespace(Id="selected-output")
    queue = [SimpleNamespace(eEventId=k, ulStreamNum=7) for k in (1, 2)]
    native = SimpleNamespace(
        GetVoices=lambda: SimpleNamespace(Count=0),
        GetAudioOutputs=lambda: SimpleNamespace(Count=1, Item=lambda _: output),
        Speak=lambda text, flags: calls.append((text, flags)),
        SpeakStream=lambda pcm, flags: calls.append((pcm, flags)) or 7,
        GetEvents=lambda count: (queue.pop(0), 1) if queue else (None, 0),
        GetStatus=lambda: (SimpleNamespace(hrLastResult=0), None),
        WaitUntilDone=lambda timeout: True,
    )
    monkeypatch.setattr(worker, "sapi", lambda: native)
    monkeypatch.setattr(worker, "pcm_stream", lambda pcm, maximum: "memory-pcm")
    monkeypatch.setattr(worker, "sapi_event_source", lambda voice: voice)
    monkeypatch.setattr(worker, "emit", lambda kind, **data: events.append(kind))
    worker.speak(
        "Synthetic.",
        VoiceConfig(tts_provider="kokoro", output_device="selected-output", rate=3),
        threading.Event(),
        pcm=b"synthetic",
    )
    assert native.AudioOutput is output and native.Rate == 0
    assert calls == [("memory-pcm", 3), ("", 3)]
    assert events == ["stage", "done"]


def test_neural_pcm_cannot_retarget_a_missing_selected_output(monkeypatch):
    from jarvis import voice_worker as worker

    native = SimpleNamespace(
        GetVoices=lambda: SimpleNamespace(Count=0), GetAudioOutputs=lambda: SimpleNamespace(Count=0)
    )
    monkeypatch.setattr(worker, "sapi", lambda: native)
    monkeypatch.setattr(worker, "pcm_stream", lambda *a: pytest.fail("Must not open audio"))
    with pytest.raises(ValueError, match="DEVICE_CHANGED"):
        worker.speak(
            "Synthetic.", VoiceConfig(output_device="missing"), threading.Event(), pcm=b"synthetic"
        )
