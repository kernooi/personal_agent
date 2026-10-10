"""Explicit synthetic public live evaluation; exclusive reports retain failures."""

import hashlib
import json
import tempfile
from pathlib import Path

from jarvis.bootstrap import build
from jarvis.conversation import Conversation
from jarvis.domain import State
from jarvis.web_decisions import validate_answer


def evaluate_web(profile, config, report_path, *, owner_url_only=False):
    if report_path.exists():
        raise ValueError("Evaluation report already exists; choose a new name")
    corpus_path = Path("tests/fixtures/m3_5-corpus-v1.json")
    corpus = json.loads(corpus_path.read_text())
    cases = corpus["cases"]
    if owner_url_only:
        cases = [case for case in cases if case["id"] == "owner-public-url"]
    records = []
    with tempfile.TemporaryDirectory(prefix="jarvis-public-evaluation-") as directory:
        broker = build(Path(directory) / "journal.sqlite", profile, web_config=config)
        metadata = broker.provider.inspect(profile)
        conversation = Conversation(broker)
        try:
            for case in cases:
                start = broker.clock.now()
                result = conversation.submit(case["query"])
                supported = result.state == State.SUCCEEDED
                if supported:
                    validate_answer(broker.web.answer, broker.web.sources)
                    supported = broker.web.answer.assessment == "supported" and bool(
                        broker.web.answer.excerpts
                    )
                    if "two sources" in case["query"].casefold():
                        supported = (
                            supported
                            and len({e.source_id for e in broker.web.answer.excerpts}) >= 2
                        )
                expected_failure = case.get("expected") == "honest_failure"
                correct = (
                    (result.state == State.FAILED and broker.last_error is not None)
                    if expected_failure
                    else supported
                )
                records.append(
                    {
                        "case_id": case["id"],
                        "synthetic_public_query": case["query"],
                        "state": result.state,
                        "correct": correct,
                        "error": broker.last_error,
                        "latency_seconds": broker.clock.now() - start,
                        "metrics": broker.web.metrics,
                        "retrieval_failures": broker.web.failures,
                        "network_receipts": broker.web.receipts,
                        "model_turns": broker.web.model_turns,
                        "sources": [s.model_dump() for s in broker.web.sources],
                        "final_answer": result.message,
                    }
                )
            desktop_effects = getattr(broker.desktop, "effect_count", 0)
        finally:
            broker.provider.close()
            broker.store.close()
    passed = all(r["correct"] for r in records) and desktop_effects == 0
    report = {
        "milestone": "M3.5 public research",
        "scope": "owner URL only; search gate NOT tested"
        if owner_url_only
        else "frozen research corpus",
        "passed": passed,
        "corpus_gate_passed": passed and not owner_url_only,
        "full_milestone_passed": False,
        "qualification_limits": "Evidence-binding/retrieval check only. Broad semantic relevance, "
        "latest-event ordering and conflict adjudication still require independent qualification.",
        "correct": sum(r["correct"] for r in records),
        "total": len(records),
        "model": metadata,
        "config": config.model_dump(),
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "contract_sha256": hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted(Path("src/jarvis").glob("*.py")))
        ).hexdigest(),
        "windows_effects": desktop_effects,
        "records": records,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
    return report, 0 if passed else 1
