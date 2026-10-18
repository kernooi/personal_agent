"""Explicit operator-only speech-model setup. Never called by JARVIS startup/tools."""

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-base-en", action="store_true")
    parser.add_argument("--download-small-en", action="store_true")
    parser.add_argument(
        "--select", action="store_true", help="Select the installed model privately"
    )
    parser.add_argument("--complete-existing", action="store_true")
    parser.add_argument(
        "--approved", action="store_true", help="Owner approved this model download"
    )
    args = parser.parse_args()
    if args.download_base_en == args.download_small_en or not args.approved:
        parser.error("Choose exactly one --download-base-en/--download-small-en with --approved")
    from huggingface_hub import HfApi, snapshot_download

    from jarvis.voice import Voice
    from jarvis.voice_data import VoiceConfig, load_config

    model = "small.en" if args.download_small_en else "base.en"
    repo = "Systran/faster-whisper-" + model
    root = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    original = load_config(root)
    destination = root / "speech" / model
    if destination.exists():
        if not args.complete_existing:
            parser.error("Destination exists; inspect before using --complete-existing")
        existing = json.loads((destination / "jarvis-model.json").read_text(encoding="utf-8"))
        if existing["repository"] != repo or any(
            Path(name).name != name
            or hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest
            for name, digest in existing["files"].items()
        ):
            parser.error("Existing model identity or hashes differ; no changes performed")
        revision = existing["revision"]
    else:
        revision = (
            "d1d751a5f8271d482d14ca55d9e2deeebbae577f"
            if args.download_small_en
            else HfApi().model_info(repo).sha
        )
    snapshot_download(
        repo,
        revision=revision,
        local_dir=destination,
        allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"],
    )
    # Validate the actual runtime format before claiming successful installation.
    from faster_whisper import WhisperModel

    WhisperModel(str(destination), device="cpu", compute_type="int8", local_files_only=True)
    manifest = {
        "repository": repo,
        "revision": revision,
        "license": "MIT",
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in destination.iterdir()
            if p.is_file() and p.name != "jarvis-model.json"
        },
    }
    (destination / "jarvis-model.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.select:
        if load_config(root) != original:
            raise ValueError("Voice configuration changed during setup; selection not written")
        current = root / "voice.toml"
        if current.is_file():
            backup = root / ("voice.before-recognition-" + uuid.uuid4().hex + ".toml")
            with backup.open("xb") as stream:
                stream.write(current.read_bytes())
        data = original.model_dump() | {"model_directory": "speech/" + model}
        voice = Voice(root, lambda *args: None, lambda *args: False)
        voice.save(VoiceConfig.model_validate(data, strict=True))
        voice.close()
    print("Installed pinned local " + model + " assets. Startup never downloads or updates models.")


if __name__ == "__main__":
    main()
