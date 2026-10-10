"""Explicit synthetic-amount live checks; never enables real Windows control."""

import hashlib
import json
import tempfile
import time
from dataclasses import asdict
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

from jarvis.bootstrap import SystemClock, build
from jarvis.conversation import Conversation, conversational_text
from jarvis.currency_router import route
from jarvis.models import Profile
from jarvis.public_data import PublicDataError, utc

CORPUS = Path("tests/fixtures/m3-corpus-v2.json")


def contract_hash():
    names = (
        "public_data",
        "public_catalogue",
        "public_transport",
        "public_worker",
        "currency_provider",
        "currency_cache",
        "currency_router",
        "currency_decisions",
        "currency_tools",
        "core",
        "policy",
        "storage",
        "bootstrap",
        "ollama",
        "models",
        "m3_evaluation",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name + ".py").read_bytes())
    return digest.hexdigest()


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves failed evidence instead of silently replacing it.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


def qualification_summary(path, profile, metadata, config):
    try:
        if path is None or config is None or path.stat().st_size > 262144:
            raise ValueError("Missing selected evidence")
        report = json.loads(path.read_bytes())
        corpus_bytes = CORPUS.read_bytes()
        corpus = json.loads(corpus_bytes)
        if (
            report["version"] != "m3-evaluation-v2"
            or report["contract_sha256"] != contract_hash()
            or report["corpus_sha256"] != hashlib.sha256(corpus_bytes).hexdigest()
            or report["profile"] != profile.model_dump()
            or report["config"] != config.model_dump()
            or report["gate"] != corpus["gate"]
            or report["passed"] is not True
            or report["correct_fraction"] != 1.0
            or report["correct"] != len(corpus["cases"])
            or report["total"] != len(corpus["cases"])
            or report["desktop_execution_calls"] != 0
            or len(report["records"]) != len(corpus["cases"])
            or any(
                row["correct"] is not True or row["desktop_execution_calls"] != 0
                for row in report["records"]
            )
            or [row["id"] for row in report["records"]] != [row["id"] for row in corpus["cases"]]
            or any(
                report["metadata"].get(key) != metadata.get(key)
                for key in ("digest", "identity", "runtime_version", "transport_version")
            )
        ):
            raise ValueError("Evidence mismatch")
        if any(
            record["broker_state"] != case["state"]
            for record, case in zip(report["records"], corpus["cases"], strict=True)
        ):
            raise ValueError("Outcome mismatch")
        return {
            "status": "passed",
            "milestone": "M3 generic provider-supported currency/chat",
            "correct": report["correct"],
            "total": report["total"],
            "physical_network_disconnection_tested": False,
            "real_windows_qualification": "separate M2 evidence required",
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unknown", "reason": "Missing or nonmatching M3 evidence"}


def checked_calculation(amount, rate, quote):
    with localcontext() as context:
        context.prec = 64
        return format(
            (Decimal(amount) * Decimal(rate)).quantize(
                Decimal("1") if quote == "JPY" else Decimal("0.01"), rounding=ROUND_HALF_EVEN
            ),
            "f",
        )


def provider_check(config, report_path):
    if report_path.exists():
        raise ValueError("Report already exists; select a new path to preserve evidence")
    if config.mode != "enabled":
        raise ValueError("Live provider check requires mode=enabled")
    profile = Profile(
        profile_name="m3-adapter-lab",
        model_identity="scripted-lab-only",
        reply="{}",
        context_bytes=20000,
    )
    records = []
    with tempfile.TemporaryDirectory(prefix="jarvis-m3-public-check-") as directory:
        broker = build(Path(directory) / "journal.sqlite", profile, public_config=config)
        try:
            conversation = Conversation(broker)
            for base, quote in [("MYR", "JPY"), ("JPY", "MYR"), ("EUR", "USD")]:
                text = f"What is the {base} to {quote} exchange rate now?"
                arguments = route(text).arguments.model_dump()
                broker.profile = profile.model_copy(
                    update={
                        "reply": json.dumps(
                            {
                                "kind": "propose_action",
                                "action": {
                                    "capability": "currency.quote",
                                    "arguments": arguments,
                                },
                            }
                        )
                    }
                )
                started = time.monotonic()
                result = conversation.submit(text)
                observation = broker.currency.last_quote
                records.append(
                    {
                        "base": base,
                        "quote": quote,
                        "state": result.state,
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "error": broker.last_error,
                        "observation": observation.model_dump()
                        if result.state == "SUCCEEDED"
                        else None,
                        "connection_receipt": broker.currency.provider.last_receipt,
                        "correct": result.state == "SUCCEEDED"
                        and observation is not None
                        and observation.sensitivity == "public"
                        and observation.base == base
                        and observation.quote == quote,
                    }
                )
            report = {
                "version": "m3-provider-v2",
                "checked_at_utc": utc(time.time()),
                "contract_sha256": contract_hash(),
                "config": config.model_dump(),
                "local_model_used": False,
                "desktop_execution_calls": broker.desktop.execution_calls,
                "records": records,
                "supported_currency_metadata": broker.currency.catalogue_cache.record.model_dump()
                if broker.currency.catalogue_cache.record
                else None,
                "passed": all(row["correct"] for row in records)
                and broker.desktop.execution_calls == 0,
            }
            save_report(report_path, report)
            return report, 0 if report["passed"] else 1
        finally:
            broker.provider.close()
            broker.store.close()


class OfflineFault:
    """Clearly labeled failure injection, not physical network isolation."""

    last_receipt = None

    def fetch(self, *args):
        raise PublicDataError("OFFLINE_FAULT_INJECTION")


def evaluate(profile, config, report_path):
    from jarvis.ollama import OllamaProvider

    if report_path.exists():
        raise ValueError("Report already exists; select a new path to preserve evidence")
    if config.mode != "enabled":
        raise ValueError("Live M3 evaluation requires mode=enabled")
    corpus_bytes = CORPUS.read_bytes()
    corpus = json.loads(corpus_bytes)
    provider = OllamaProvider(SystemClock())
    metadata = provider.inspect(profile)
    report = {
        "version": "m3-evaluation-v2",
        "checked_at_utc": utc(time.time()),
        "profile": profile.model_dump(),
        "metadata": metadata,
        "config": config.model_dump(),
        "contract_sha256": contract_hash(),
        "corpus_version": corpus["version"],
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "gate": corpus["gate"],
        "physical_network_disconnection_tested": False,
        "offline_check": "explicit provider-failure injection plus real disabled-policy check",
        "records": [],
        "passed": False,
    }
    if not metadata.get("ready"):
        report["status"] = "BLOCKED"
        save_report(report_path, report)
        provider.close()
        return report, 2
    with tempfile.TemporaryDirectory(prefix="jarvis-m3-live-eval-") as directory:
        broker = build(
            Path(directory) / "journal.sqlite", profile, provider=provider, public_config=config
        )
        conversation = Conversation(broker)
        live_provider = broker.currency.provider
        try:
            for case in corpus["cases"]:
                mode = case.get("mode")
                broker.currency.config = (
                    config.model_copy(update={"mode": "disabled"}) if mode == "disabled" else config
                )
                broker.currency.provider = (
                    OfflineFault() if mode == "offline_fault" else live_provider
                )
                if mode == "offline_fault":
                    broker.currency.cache.clear()
                before_desktop = broker.desktop.execution_calls
                before_currency = broker.currency.execution_calls
                started = time.monotonic()
                result = conversation.submit(case["text"])
                task = broker.store.get(result.task_id)
                proposed = broker.last_decision.proposal if broker.last_decision else None
                observation = (
                    broker.currency.observation if task.scope.app_id == "currency" else None
                )
                amount = case.get("amount")
                expected_calculation = None
                correct = result.state == case["state"]
                answer = conversational_text(result)
                if "operation" in case:
                    arguments = (
                        json.loads(task.scope.window_ref) if task.scope.app_id == "currency" else {}
                    )
                    correct &= all(
                        arguments.get(key) == case.get(key)
                        for key in ("base", "quote", "amount", "operation")
                    )
                    correct &= proposed is not None and proposed.capability == "currency.quote"
                    if case["operation"] not in {"supplied", "identity"}:
                        correct &= observation is not None and observation.sensitivity == "public"
                        if observation:
                            correct &= all(
                                value in answer
                                for value in [
                                    observation.source_id,
                                    observation.effective_date,
                                    observation.retrieved_at_utc,
                                    observation.source_url,
                                    f"1 {case['base']} = {observation.rate} {case['quote']}",
                                ]
                            )
                    rate = (
                        "1"
                        if case["operation"] == "identity"
                        else case.get("supplied_rate")
                        or (observation.rate if observation else None)
                    )
                    if amount is not None and rate is not None:
                        expected_calculation = checked_calculation(amount, rate, case["quote"])
                        correct &= (
                            f"{amount} {case['base']} = {expected_calculation} {case['quote']}"
                            in answer
                        )
                if "decision" in case:
                    correct &= result.decision_kind == case["decision"]
                if "contains" in case:
                    correct &= case["contains"] in answer.replace(",", "")
                if "error" in case:
                    correct &= broker.last_error == case["error"] and "1 MYR =" not in answer
                if case["id"] in {
                    "ambiguous",
                    "unsupported-current",
                    "static-explanation",
                    "static-arithmetic",
                }:
                    correct &= broker.currency.execution_calls == before_currency
                correct &= broker.desktop.execution_calls == before_desktop == 0
                audit = [
                    row[0]
                    for row in broker.store.db.execute(
                        "SELECT kind FROM events WHERE task_id=? ORDER BY sequence",
                        (result.task_id,),
                    )
                ]
                report["records"].append(
                    {
                        "id": case["id"],
                        "route": task.scope.app_id,
                        "decision_kind": result.decision_kind
                        or (broker.last_decision.kind if broker.last_decision else None),
                        "proposal": asdict(proposed) if proposed else None,
                        "broker_state": result.state,
                        "error": broker.last_error,
                        "evidence": observation.model_dump()
                        if observation and result.state == "SUCCEEDED"
                        else None,
                        "expected_calculation": expected_calculation,
                        "final_answer": answer,
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "audit_events": audit,
                        "desktop_execution_calls": broker.desktop.execution_calls,
                        "correct": bool(correct),
                    }
                )
                # Report only public/synthetic lab material; never raw model replies/prompts.
            report["correct"] = sum(row["correct"] for row in report["records"])
            report["total"] = len(report["records"])
            report["correct_fraction"] = report["correct"] / report["total"]
            report["desktop_execution_calls"] = broker.desktop.execution_calls
            report["passed"] = (
                report["correct_fraction"] == 1.0 and broker.desktop.execution_calls == 0
            )
            report["status"] = "PASSED" if report["passed"] else "FAILED"
            save_report(report_path, report)
            return report, 0 if report["passed"] else 1
        finally:
            broker.store.close()
            provider.close()
