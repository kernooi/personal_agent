"""Optional local CPU speech synthesis. No audio devices, downloads or agent authority."""

import hashlib
import io
import json
import re
import time
import wave
from pathlib import Path

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
ASSETS = {
    "kokoro-v1.0.onnx": (
        325505369,
        "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    ),
    "voices-v1.0.bin": (
        28214398,
        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
    ),
}
SAMPLE_RATE = 24000


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def asset_directory(root, config, *, verify=False):
    root = Path(root).resolve()
    directory = (root / config.tts_model_directory).resolve()
    if not directory.is_relative_to(root) or directory == root:
        raise ValueError("TTS_MODEL_PATH_INVALID")
    for name, (size, expected) in ASSETS.items():
        path = directory / name
        if (
            not path.is_file()
            or not path.resolve().is_relative_to(root)
            or path.stat().st_size != size
        ):
            raise ValueError("TTS_MODEL_MISSING_OR_CHANGED")
        if verify and digest(path) != expected:
            raise ValueError("TTS_MODEL_MISSING_OR_CHANGED")
    return directory


def speed(config):
    return 2 ** (config.rate / 10)


def chunks(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 2400:
        raise ValueError("SPEECH_TEXT_LIMIT")
    # Bounded complete text, split at punctuation/word boundaries. No summary or truncation.
    pending = text.strip()
    while pending:
        if len(pending) <= 220:
            yield pending
            return
        boundaries = list(re.finditer(r"[.!?;:]\s+", pending[:221]))
        cut = boundaries[-1].end() if boundaries else pending.rfind(" ", 0, 221)
        if cut <= 0:
            cut = 220
        yield pending[:cut].strip()
        pending = pending[cut:].lstrip()


class NeuralSpeech:
    def __init__(self, root, config):
        import onnxruntime as ort
        from kokoro_onnx import Kokoro

        directory = asset_directory(root, config, verify=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        session = ort.InferenceSession(
            str(directory / "kokoro-v1.0.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.engine = Kokoro.from_session(session, str(directory / "voices-v1.0.bin"))
        if config.neural_voice not in self.engine.get_voices():
            raise ValueError("NEURAL_VOICE_UNAVAILABLE")
        self.config = config

    def render(self, text, cancel, deadline):
        import numpy as np

        if cancel.is_set():
            raise ValueError("VOICE_CANCELLED")
        if time.monotonic() >= deadline:
            raise ValueError("SPEECH_TIMEOUT")
        audio, rate = self.engine.create(
            text,
            voice=self.config.neural_voice,
            speed=speed(self.config),
            lang="en-us" if self.config.neural_voice.startswith("a") else "en-gb",
        )
        if cancel.is_set():
            raise ValueError("VOICE_CANCELLED")
        if time.monotonic() >= deadline:
            raise ValueError("SPEECH_TIMEOUT")
        if (
            rate != SAMPLE_RATE
            or not isinstance(audio, np.ndarray)
            or audio.ndim != 1
            or not 240 <= audio.size <= SAMPLE_RATE * self.config.speech_seconds
            or not np.isfinite(audio).all()
            or float(np.max(np.abs(audio))) < 0.0001
        ):
            raise ValueError("NEURAL_AUDIO_INVALID")
        return (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()


def acknowledgement_name(config):
    return f"ack-{config.neural_voice}-{config.rate}.wav"


def acknowledgement(root, config, cancel):
    """Only the fixed synthetic 'Yes sir.' may have a private, setup-created cache."""
    directory = asset_directory(root, config)
    path = directory / acknowledgement_name(config)
    receipt = path.with_suffix(".json")
    if path.is_file() and receipt.is_file():
        if path.stat().st_size > SAMPLE_RATE * 2 * 10 + 44 or receipt.stat().st_size > 2048:
            raise ValueError("WAKE_ACK_INVALID")
        metadata = json.loads(receipt.read_text(encoding="utf-8"))
        if metadata != {
            "voice": config.neural_voice,
            "rate": config.rate,
            "text": "Yes sir.",
            "sha256": digest(path),
            "model_sha256": ASSETS["kokoro-v1.0.onnx"][1],
        }:
            raise ValueError("WAKE_ACK_INVALID")
        with wave.open(io.BytesIO(path.read_bytes()), "rb") as wav:
            if (
                wav.getframerate() != SAMPLE_RATE
                or wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or not 240 <= wav.getnframes() <= SAMPLE_RATE * 10
                or wav.getcomptype() != "NONE"
            ):
                raise ValueError("WAKE_ACK_INVALID")
            pcm = wav.readframes(wav.getnframes())
            if len(pcm) != wav.getnframes() * 2:
                raise ValueError("WAKE_ACK_INVALID")
            return pcm
    # A manually changed voice/rate has no cache yet. Synthesize while the mic is
    # still inactive, never between acknowledgement completion and command start.
    return NeuralSpeech(root, config).render("Yes sir.", cancel, time.monotonic() + 10)


def speak_reply(root, text, config, cancel, started, play, done):
    start = time.monotonic()
    deadline = start + config.speech_seconds
    parts = iter(chunks(text))
    first = next(parts, None)
    if first is None:
        raise ValueError("SPEECH_TEXT_LIMIT")
    if cancel.is_set():
        return
    engine = NeuralSpeech(root, config)
    playback_at = None

    def began():
        nonlocal playback_at
        if playback_at is None:
            playback_at = time.monotonic()
            started()

    import itertools

    completed = None
    for part in itertools.chain([first], parts):
        pcm = engine.render(part, cancel, deadline)
        if cancel.is_set():
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("SPEECH_TIMEOUT")
        # Keep the global deadline even across multiple streams. The owned
        # supervisor remains authoritative for a blocking native inference call.
        completed = play(
            part,
            config,
            cancel,
            began,
            report_done=False,
            pcm=pcm,
            deadline=deadline,
        )
        if cancel.is_set():
            return
        if completed is None or playback_at is None:
            raise ValueError("SPEECH_OUTPUT_FAILED")
    done(
        "done",
        metrics={"start_seconds": playback_at - start, "speech_seconds": time.monotonic() - start},
    )
    return completed
