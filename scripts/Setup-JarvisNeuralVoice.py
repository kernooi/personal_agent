"""Explicit approved local Kokoro setup; never called by GUI startup or tools."""

import argparse
import hashlib
import json
import os
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path

from jarvis.voice import Voice
from jarvis.voice_data import VoiceConfig, load_config
from jarvis.voice_neural import (
    ASSETS,
    RELEASE,
    SAMPLE_RATE,
    NeuralSpeech,
    acknowledgement_name,
    digest,
)


def download(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, (size, expected) in ASSETS.items():
        destination = directory / name
        if destination.exists():
            if destination.stat().st_size != size or digest(destination) != expected:
                raise ValueError("Existing asset differs; inspect it manually before setup.")
            print("Verified installed " + name, flush=True)
            continue
        temporary = destination.with_suffix(destination.suffix + ".download")
        if temporary.exists():
            raise ValueError("An earlier partial download exists; inspect before retrying.")
        request = urllib.request.Request(
            RELEASE + "/" + name, headers={"User-Agent": "Jarvis-setup"}
        )
        hashed, count = hashlib.sha256(), 0
        deadline = time.monotonic() + 300
        with urllib.request.urlopen(request, timeout=30) as response, temporary.open("xb") as out:
            if not response.url.startswith("https://"):
                raise ValueError("HTTPS download required")
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > size or time.monotonic() >= deadline:
                    raise ValueError("Download size/deadline exceeded")
                hashed.update(block)
                out.write(block)
        if count != size or hashed.hexdigest() != expected:
            raise ValueError("Asset checksum/size differs; partial result preserved.")
        if destination.exists():
            raise ValueError("Destination changed during download")
        temporary.rename(destination)
        print("Downloaded and SHA-256 verified " + name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--select", action="store_true", help="Select in private voice.toml")
    parser.add_argument("--voice", default="am_michael", choices=["am_michael", "bm_george"])
    args = parser.parse_args()
    if not args.approved:
        parser.error("Explicit model-download approval required: --approved")
    root = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    original = load_config(root)
    data = original.model_dump() | {"tts_provider": "kokoro", "neural_voice": args.voice}
    config = VoiceConfig.model_validate(data, strict=True)
    directory = (root / config.tts_model_directory).resolve()
    if not directory.is_relative_to(root.resolve()) or directory == root.resolve():
        parser.error("Neural model directory must stay below private JARVIS root")
    download(directory)
    began = time.monotonic()
    engine = NeuralSpeech(root, config)
    loaded = time.monotonic()
    pcm = engine.render("Yes sir.", threading.Event(), time.monotonic() + 30)
    rendered = time.monotonic()
    path = directory / acknowledgement_name(config)
    receipt = path.with_suffix(".json")
    if path.exists() != receipt.exists():
        raise ValueError("Incomplete acknowledgement cache preserved; inspect before retrying.")
    if path.exists() or receipt.exists():
        from jarvis.voice_neural import acknowledgement

        acknowledgement(root, config, threading.Event())  # Validate; never overwrite existing.
    else:
        with path.open("xb") as stream, wave.open(stream, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm)
        with receipt.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "voice": config.neural_voice,
                    "rate": config.rate,
                    "text": "Yes sir.",
                    "sha256": digest(path),
                    "model_sha256": ASSETS["kokoro-v1.0.onnx"][1],
                },
                stream,
                indent=2,
            )
    if args.select:
        # Preserve the owner's exact input/output/wake/rate choices and a private backup.
        if load_config(root) != original:
            raise ValueError("Voice settings changed during setup; no selection was written.")
        current = root / "voice.toml"
        if current.exists():
            backup = current.with_name("voice.before-neural-" + uuid.uuid4().hex + ".toml")
            with backup.open("xb") as stream:
                stream.write(current.read_bytes())
        voice = Voice(root, lambda *args: None, lambda *args: False)
        voice.save(config)
        voice.close()
    print(
        json.dumps(
            {
                "engine": "kokoro-onnx",
                "voice": config.neural_voice,
                "execution_provider": "CPUExecutionProvider",
                "threads": 2,
                "load_seconds": round(loaded - began, 3),
                "ack_synthesis_seconds": round(rendered - loaded, 3),
                "ack_audio_seconds": round(len(pcm) / 48000, 3),
                "selected": args.select,
                "microphone_opened": False,
                "audio_played": False,
            }
        )
    )


if __name__ == "__main__":
    main()
