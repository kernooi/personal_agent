"""Opt-in actual local inference with explicitly synthetic quotes and no Windows effects."""

import hashlib
import json
import re
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from jarvis.bootstrap import SystemClock, build
from jarvis.conversation import Conversation, conversational_text
from jarvis.currency_provider import FixtureProvider
from jarvis.m2_evaluation import contract_hash as m2_contract_hash
from jarvis.m3_evaluation import contract_hash as m3_contract_hash
from jarvis.m3_evaluation import save_report
from jarvis.ollama import OllamaProvider
from jarvis.public_data import CurrencyArguments, PublicConfig, conversion, utc

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/assistant-corpus-v1.json"


def contract_hash(profile):
    value = m2_contract_hash(profile) + m3_contract_hash()
    return hashlib.sha256(value.encode() + Path(__file__).read_bytes()).hexdigest()


def qualification_summary(path, profile, metadata):
    try:
        if path is None or path.stat().st_size > 262144:
            raise ValueError("Missing evidence")
        report = json.loads(path.read_bytes())
        corpus_bytes = CORPUS.read_bytes()
        corpus = json.loads(corpus_bytes)
        if (
            not metadata.get("ready")
            or report["version"] != "assistant-evaluation-v1"
            or report["profile"] != profile.model_dump()
            or report["contract_sha256"] != contract_hash(profile)
            or report["corpus_sha256"] != hashlib.sha256(corpus_bytes).hexdigest()
            or report["gate"] != corpus["gate"]
            or report["passed"] is not True
            or report["correct_fraction"] != 1.0
            or report["correct"] != len(corpus["cases"])
            or report["total"] != len(corpus["cases"])
            or [r["id"] for r in report["records"]] != [c["id"] for c in corpus["cases"]]
            or any(
                r["correct"] is not True or r["desktop_execution_calls"] != 0
                for r in report["records"]
            )
            or report["metadata"]["digest"] != metadata.get("digest")
            or report["metadata"]["runtime_version"] != metadata.get("runtime_version")
        ):
            raise ValueError("Qualification mismatch")
        return {
            "status": "passed",
            "scope": "synthetic conversation/tool interpretation only",
            "native_windows_qualification": "separate M2 reports required",
            "live_currency_and_research_qualification": "separate evidence required",
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unknown", "reason": "No matching passed assistant evidence"}


def evaluate(profile, report_path):
    if profile.assistant_version not in {"assistant-v1", "assistant-v2"} or report_path.exists():
        raise ValueError("Select an assistant-v1 profile and a new report path")
    corpus_bytes = CORPUS.read_bytes()
    corpus = json.loads(corpus_bytes)
    clock = SystemClock()
    provider = OllamaProvider(clock)
    metadata = provider.inspect(profile)
    report = {
        "version": "assistant-evaluation-v1",
        "checked_at_utc": utc(clock.now()),
        "profile": profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(profile),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "corpus_version": corpus["version"],
        "gate": corpus["gate"],
        "local_inference": "actual Ollama",
        "currency_evidence": "synthetic fixture rate 0.75",
        "execution_mode": "simulation",
        "public_network_used": False,
        "records": [],
    }
    try:
        if not metadata.get("ready"):
            report.update(status="BLOCKED", passed=False)
            save_report(report_path, report)
            return report, 2

        def quote(base, target):
            return json.dumps(
                {"date": utc(clock.now())[:10], "base": base, "quote": target, "rate": 0.75}
            ).encode()

        with tempfile.TemporaryDirectory(prefix="jarvis-assistant-eval-") as directory:
            broker = build(
                Path(directory) / "journal.sqlite",
                profile,
                clock,
                provider=provider,
                public_config=PublicConfig(mode="fixture"),
                currency_provider=FixtureProvider(quote),
            )
            chat = Conversation(broker)
            try:
                for case in corpus["cases"]:
                    if case.get("reset"):
                        chat.history.clear()
                        broker.assistant_memory = None
                        broker.registry.context = None
                        broker.currency.last_quote = None
                    before = broker.currency.provider.calls[:]
                    started = time.monotonic()
                    result = chat.submit(case["text"])
                    task = broker.store.get(result.task_id)
                    answer = conversational_text(result)
                    correct = result.state == case["state"]
                    arguments = (
                        CurrencyArguments.model_validate_json(task.scope.window_ref)
                        if task.scope.app_id == "currency"
                        else None
                    )
                    if "amount" in case:
                        correct &= arguments is not None
                        if arguments:
                            correct &= (
                                arguments.base == case["base"] and arguments.quote == case["quote"]
                            )
                            correct &= Decimal(arguments.amount or "-1") == Decimal(case["amount"])
                            correct &= arguments.operation == case.get("operation", "latest")
                            correct &= arguments.supplied_rate == case.get("supplied_rate")
                            rate = (
                                "1"
                                if arguments.operation == "identity"
                                else arguments.supplied_rate or "0.75"
                            )
                            total = conversion(case["amount"], rate, case["quote"])
                            correct &= Decimal(total) in {
                                Decimal(n.replace(",", ""))
                                for n in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", answer)
                            }
                    if case.get("contains"):
                        correct &= case["contains"].casefold() in answer.casefold()
                    if case["state"] != "SUCCEEDED" or case.get("operation") in {
                        "supplied",
                        "identity",
                    }:
                        correct &= before == broker.currency.provider.calls
                    correct &= broker.desktop.execution_calls == 0
                    report["records"].append(
                        {
                            "id": case["id"],
                            "state": result.state,
                            "error": broker.last_error,
                            "arguments": arguments.model_dump() if arguments else None,
                            "final_answer": answer,
                            "correct": bool(correct),
                            "model_turns": broker.model_turns,
                            "model_stages": broker.model_metrics[:],
                            "latency_seconds": round(time.monotonic() - started, 3),
                            "desktop_execution_calls": broker.desktop.execution_calls,
                        }
                    )
                report["correct"] = sum(r["correct"] for r in report["records"])
                report["total"] = len(corpus["cases"])
                report["passed"] = report["correct"] == report["total"]
                report["correct_fraction"] = report["correct"] / report["total"]
                report["status"] = "PASSED" if report["passed"] else "FAILED"
            finally:
                broker.store.close()
    finally:
        provider.close()
    save_report(report_path, report)
    return report, 0 if report["passed"] else 1
