"""Explicit actual-local-model routing check with synthetic quotes, apps and media."""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path

from jarvis.application_data import ApplicationsConfig
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.application_tools import attach
from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.conversation import conversational_text
from jarvis.currency_provider import FixtureProvider
from jarvis.currency_router import requests_currency_operation
from jarvis.m2_evaluation import contract_hash as m2_hash
from jarvis.m3_evaluation import contract_hash as m3_hash
from jarvis.media_data import MediaConfig
from jarvis.media_fake import FakeBrowserProvider
from jarvis.ollama import OllamaProvider
from jarvis.public_data import PublicConfig, utc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved; choose a new report path")
    profile = load_profile(args.profile, allow_ollama=True)
    clock = SystemClock()
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    corpus_path = Path(__file__).resolve().parents[1] / "tests/fixtures/currency-topics-v1.json"
    corpus = json.loads(corpus_path.read_bytes())
    rows = []
    try:
        if not metadata.get("ready"):
            parser.error("Actual configured local model required; no fallback")
        for case in corpus["cases"]:
            with tempfile.TemporaryDirectory(prefix="jarvis-currency-topic-") as directory:
                quotes = FixtureProvider(
                    lambda base, quote: json.dumps(
                        {
                            "date": utc(clock.now())[:10],
                            "base": base,
                            "quote": quote,
                            "rate": 0.75,
                        }
                    ).encode()
                )
                fake = FakeBrowserProvider(clock)
                platform = FakeApplicationPlatform()
                platform.add_app("Studio Note")
                broker = build(
                    Path(directory) / "j.sqlite",
                    profile,
                    clock,
                    provider=model,
                    public_config=PublicConfig(mode="fixture"),
                    currency_provider=quotes,
                    media_config=MediaConfig(
                        enabled=True, youtube=True, spotify=True, spotify_backend="desktop"
                    ),
                    browser_provider=fake,
                )
                chat = attach(broker, ApplicationsConfig(enabled=True), platform=platform)
                try:
                    for index, turn in enumerate(case["turns"]):
                        started = time.monotonic()
                        try:
                            result = chat.submit(turn["text"], case["id"] + "/" + str(index))
                            scope = broker.store.get(result.task_id).scope
                            reply = conversational_text(result)
                            correct = (
                                result.state == turn["state"]
                                and broker.currency.execution_calls == turn["currency_calls"]
                                and (
                                    scope.app_id == "currency"
                                    if turn["state"] == "SUCCEEDED"
                                    else scope.app_id != "currency"
                                )
                                and (
                                    turn["contains"] in reply.replace(",", "")
                                    if "contains" in turn
                                    else True
                                )
                            )
                            if turn["state"] != "SUCCEEDED" and not requests_currency_operation(
                                turn["text"], broker.registry.context, broker.registry.known_codes()
                            ):
                                correct = correct and not reply.casefold().startswith(
                                    (
                                        "please specify one source",
                                        "which currencies",
                                        "please name both currencies",
                                        "what amount should i convert",
                                    )
                                )
                            row = {
                                "id": case["id"],
                                "turn": index,
                                "state": result.state,
                                "scope": scope.app_id,
                                "correct": bool(correct),
                                "currency_calls": broker.currency.execution_calls,
                                "unauthorized_currency_calls": max(
                                    0, broker.currency.execution_calls - turn["currency_calls"]
                                ),
                                "other_effects": len(platform.calls)
                                + fake.execution_count
                                + broker.desktop.original.execution_calls,
                                "error": broker.last_error,
                            }
                        except Exception as error:
                            row = {
                                "id": case["id"],
                                "turn": index,
                                "correct": False,
                                "error": type(error).__name__,
                            }
                        row["latency_seconds"] = round(time.monotonic() - started, 3)
                        rows.append(row)
                finally:
                    broker.store.close()
                    fake.close()
    finally:
        model.close()
    total = sum(len(c["turns"]) for c in corpus["cases"])
    passed = len(rows) == total and all(
        r["correct"]
        and r.get("unauthorized_currency_calls", 1) == 0
        and r.get("other_effects", 1) == 0
        for r in rows
    )
    report = {
        "version": "currency-topics-evaluation-v1",
        "passed": passed,
        "correct": sum(r["correct"] for r in rows),
        "total": total,
        "profile": profile.model_dump(),
        "metadata": metadata,
        "gate": corpus["gate"],
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "contract_sha256": hashlib.sha256(
            (m2_hash(profile) + m3_hash()).encode() + Path(__file__).read_bytes()
        ).hexdigest(),
        "execution_mode": "simulation",
        "public_network_used": False,
        "records": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("passed", "correct", "total")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
