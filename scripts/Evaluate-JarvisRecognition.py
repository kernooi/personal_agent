"""Explicit synthetic speech-model comparison. Never opens microphones/speakers or tools."""

import argparse
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

from jarvis.voice_data import load_config
from jarvis.voice_neural import NeuralSpeech
from jarvis.voice_worker import model_path, pcm_audio, transcribe

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/m6-recognition-corpus-v1.json"


def score(expected, observed):
    reference = re.findall(r"\w+", expected.casefold())
    hypothesis = re.findall(r"\w+", observed.casefold())
    previous = list(range(len(hypothesis) + 1))
    for row, word in enumerate(reference, 1):
        current = [row]
        for column, other in enumerate(hypothesis, 1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (word != other))
            )
        previous = current
    return {
        "exact": reference == hypothesis,
        "word_errors": previous[-1],
        "reference_words": len(reference),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report preserved; choose a new filename")
    from faster_whisper import WhisperModel

    root = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    config = load_config(root)
    corpus_raw = CORPUS.read_bytes()
    corpus = json.loads(corpus_raw)
    configurations = [config.model_copy(update={"model_directory": "speech/base.en"}), config]
    if configurations[0].model_directory == configurations[1].model_directory:
        parser.error("Select the approved new recognizer before running this comparison")
    models = []
    for profile in configurations:
        models.append(
            WhisperModel(
                str(model_path(root, profile)),
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
                num_workers=1,
                local_files_only=True,
            )
        )
    tts, cancel = NeuralSpeech(root, config), threading.Event()
    report = {
        "version": "m6-recognition-synthetic-v1",
        "corpus_sha256": hashlib.sha256(corpus_raw).hexdigest(),
        "gate": corpus["gate"],
        "speech_source": config.neural_voice,
        "scope": "Synthetic speech only; does not qualify the owner's microphone/accent",
        "microphone_or_speakers_opened": False,
        "app_media_screen_actions": 0,
        "audio_or_transcripts_saved": False,
        "models": [p.model_directory for p in configurations],
        "records": [],
        "status": "INCOMPLETE",
    }
    try:
        for case in corpus["cases"]:
            pcm = tts.render(case["text"], cancel, time.monotonic() + 30)
            audio = pcm_audio(pcm, 24000, config.recording_seconds)
            pcm = None
            for profile, model in zip(configurations, models, strict=True):
                began = time.monotonic()
                result, _ = transcribe(audio, root, profile, model=model)
                row = {
                    "case": case["id"],
                    "model": profile.model_directory,
                    **score(case["text"], result.text),
                    "uncertain": result.uncertain,
                    "seconds": round(time.monotonic() - began, 3),
                }
                report["records"].append(row)
                print(json.dumps(row), flush=True)
                del result
            del audio
        report["summary"] = []
        for profile in configurations:
            rows = [r for r in report["records"] if r["model"] == profile.model_directory]
            report["summary"].append(
                {
                    "model": profile.model_directory,
                    "correct": sum(r["exact"] for r in rows),
                    "total": len(rows),
                    "word_error_rate": sum(r["word_errors"] for r in rows)
                    / sum(r["reference_words"] for r in rows),
                }
            )
        report["status"] = (
            "PASSED"
            if all(r["exact"] and not r["uncertain"] for r in report["records"])
            else "FAILED"
        )
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
