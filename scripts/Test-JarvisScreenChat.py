"""Opt-in local-model screen/chat evaluation with synthetic evidence only.

No native capture, real app/media controller, GUI, downloads or public requests.
The frozen observation corpus uses real text inference and explicit fake vision;
the final color case uses BOTH real models with generated synthetic pixels.
"""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

from jarvis.bootstrap import build, load_profile
from jarvis.conversation import Conversation, conversational_text
from jarvis.models import Message, OllamaProfile
from jarvis.screen_data import Interpretation, load_config
from jarvis.screen_fake import FakeCapture, FakeIndicator, FakeVision
from jarvis.screen_tools import attach


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--screen-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("A new report filename is required; preserve failed runs")
    corpus_path = Path(__file__).resolve().parents[1] / "tests/fixtures/screen-chat-corpus-v1.json"
    raw = corpus_path.read_bytes()
    corpus = json.loads(raw)
    profile = load_profile(args.profile, allow_ollama=True)
    if not isinstance(profile, OllamaProfile):
        parser.error("Live evaluation requires an explicit local Ollama profile; no fake fallback")
    config = load_config(args.screen_config).model_copy(
        update={
            "enabled": True,
            "default_capture_scope": "foreground_window",
            "watch_enabled": False,
            "chat_answer_enabled": True,
        }
    )
    sources = Path(__file__).resolve().parents[1] / "src/jarvis"
    contract = b"".join(
        (sources / name).read_bytes()
        for name in (
            "screen_answer.py",
            "screen_data.py",
            "screen_tools.py",
            "screen_vision.py",
            "models.py",
            "ollama.py",
            "conversation.py",
            "application_tools.py",
        )
    )
    report = {
        "version": "screen-chat-v1",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "contract_sha256": hashlib.sha256(contract).hexdigest(),
        "primary_profile": {
            "model": profile.model_identity,
            "context_tokens": profile.context_tokens,
            "max_output_tokens": profile.max_output_tokens,
        },
        "acceptance": corpus["acceptance"],
        "status": "failed",
        "cases": [],
        "real_screen_captures": 0,
        "real_app_media_effects": 0,
        "limitations": (
            "Synthetic pixels/observations only; keyword and protocol checks "
            "do not establish universal grounding or naturalness."
        ),
    }
    try:
        with tempfile.TemporaryDirectory(prefix="jarvis-screen-chat-") as directory:
            for index, case in enumerate(corpus["cases"] + [{"id": "two-real-models"}]):
                broker = build(Path(directory) / f"{index}.sqlite", profile)
                capture, indicator = FakeCapture(broker.clock), FakeIndicator()
                vision = FakeVision() if case["id"] != "two-real-models" else None
                if vision:
                    vision.result = Interpretation.model_validate(case["observation"], strict=True)
                screen = attach(broker, config, capture=capture, indicator=indicator, vision=vision)
                started = time.perf_counter()
                try:
                    chat = Conversation(broker)
                    chat.history = [Message(**message) for message in case.get("history", [])]
                    before = tuple(chat.history)
                    question = case.get(
                        "question", "Read my screen and explain its color pattern simply."
                    )
                    result = chat.submit(question)
                    answer = conversational_text(result)
                    lowered = answer.casefold()
                    text_checks = all(
                        any(term.casefold() in lowered for term in group)
                        for group in case.get("required_groups", [])
                    )
                    text_checks = text_checks and not any(
                        term.casefold() in lowered for term in case.get("forbidden", [])
                    )
                    privacy = tuple(chat.history) == before
                    dump = "\n".join(broker.store.db.iterdump())
                    privacy = privacy and "SYNTHETIC_PRIVATE_CANARY" not in dump
                    passed = (
                        result.state == "SUCCEEDED"
                        and screen.answer_status == "generated"
                        and capture.calls == 1
                        and broker.desktop.execution_calls == 0
                        and privacy
                        and text_checks
                    )
                    record = {
                        "id": case["id"],
                        "passed": passed,
                        "state": result.state,
                        "answer_status": screen.answer_status,
                        "answer": answer,
                        "seconds": time.perf_counter() - started,
                        "timings": dict(screen.timings),
                        "privacy_checks": privacy,
                        "keyword_checks": text_checks,
                        "vision": "actual local model"
                        if vision is None
                        else "scripted observation",
                        "text": "actual local model",
                        "synthetic_capture_count": capture.calls,
                        "primary_model": {
                            key: broker.provider.metadata.get(key)
                            for key in ("identity", "digest", "runtime_version")
                        },
                    }
                    if screen.observation:
                        record["vision_model"] = screen.observation.model
                        record["vision_digest"] = screen.observation.model_digest
                        record["synthetic_observation"] = (
                            screen.observation.interpretation.model_dump()
                        )
                    report["cases"].append(record)
                    print(json.dumps({"case": case["id"], "passed": passed}), flush=True)
                finally:
                    screen.close()
                    if hasattr(screen.vision, "provider"):
                        screen.vision.provider.close()
                    broker.provider.close()
                    broker.store.close()
        report["correct"] = sum(case["passed"] for case in report["cases"])
        report["total"] = len(report["cases"])
        if report["correct"] == len(corpus["cases"]) + 1:
            report["status"] = "passed"
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
    finally:
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    print(json.dumps({"report": str(args.report), "status": report["status"]}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
