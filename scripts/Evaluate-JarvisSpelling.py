"""Synthetic same-audio spelling-hint comparison. No recording, playback or app effects."""

import argparse
import hashlib
import importlib.util
import json
import os
import threading
import time
from pathlib import Path

from jarvis.voice_data import load_config
from jarvis.voice_neural import NeuralSpeech
from jarvis.voice_vocabulary import installed_names, vocabulary
from jarvis.voice_worker import model_path, pcm_audio, transcribe

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/m6-app-spelling-corpus-v1.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved; choose a new filename")
    from faster_whisper import WhisperModel

    helper = importlib.util.spec_from_file_location(
        "speech_scoring", Path(__file__).with_name("Evaluate-JarvisRecognition.py")
    )
    scoring = importlib.util.module_from_spec(helper)
    helper.loader.exec_module(scoring)
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    config = load_config(private)
    names = installed_names(private)
    profiles = {
        "unhinted": config.model_copy(update={"recognition_terms": []}),
        "app_names": config.model_copy(
            update={"recognition_terms": vocabulary(config.recognition_terms, names)}
        ),
    }
    model = WhisperModel(
        str(model_path(private, config)),
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        num_workers=1,
        local_files_only=True,
    )
    tts, cancel = NeuralSpeech(private, config), threading.Event()
    raw = CORPUS.read_bytes()
    corpus = json.loads(raw)
    report = {
        "version": "m6-spelling-synthetic-v1",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "gate": corpus["gate"],
        "hint_source": "read-only installed application labels",
        "model_directory": config.model_directory,
        "hint_count": len(names),
        "microphone_or_speakers_opened": False,
        "app_effects": 0,
        "audio_or_transcripts_saved": False,
        "records": [],
        "status": "INCOMPLETE",
    }
    try:
        for case in corpus["cases"]:
            pcm = tts.render(case["text"], cancel, time.monotonic() + 30)
            audio = pcm_audio(pcm, 24000, config.recording_seconds)
            del pcm
            for variant, profile in profiles.items():
                result, metrics = transcribe(audio, private, profile, model=model)
                row = {
                    "case": case["id"],
                    "variant": variant,
                    **scoring.score(case["text"], result.text),
                    "uncertain": result.uncertain,
                    "vocabulary_terms": metrics["vocabulary_terms"],
                    "stt_seconds": round(metrics["stt_seconds"], 3),
                }
                report["records"].append(row)
                print(json.dumps(row), flush=True)
                del result
            del audio
        report["status"] = (
            "PASSED"
            if all(r["exact"] and not r["uncertain"] for r in report["records"])
            else "FAILED"
        )
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
