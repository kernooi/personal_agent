"""Explicit M2 model qualification in fake windows; never Windows evidence."""

import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from jarvis.bootstrap import build
from jarvis.domain import State, UserRequest
from jarvis.models import StrictRecord
from jarvis.prompts import TEMPLATES


def contract_hash(profile):
    from jarvis.models import BOUNDARY_M2

    contract = {"prompt": TEMPLATES[profile.prompt_version], "schema": BOUNDARY_M2.json_schema()}
    if profile.assistant_version in {"assistant-v1", "assistant-v2"}:
        contract["assistant_version"] = profile.assistant_version
        contract["assistant_sources"] = {
            name: hashlib.sha256(Path(__file__).with_name(name + ".py").read_bytes()).hexdigest()
            for name in ("assistant", "core", "storage", "models", "ollama")
        }
    if profile.prompt_version in {
        "planner-m2-v5",
        "planner-m2-v6",
        "planner-m2-v7",
        "planner-m2-v8",
        "planner-m2-v9",
        "planner-m2-v10",
    }:
        from jarvis import notepad_intent

        contract["resolver_sha256"] = hashlib.sha256(
            Path(notepad_intent.__file__).read_bytes()
        ).hexdigest()
        contract["controller_context_version"] = "notepad-context-v1"
    if profile.prompt_version in {
        "planner-m2-v7",
        "planner-m2-v8",
        "planner-m2-v9",
        "planner-m2-v10",
    }:
        from jarvis import notepad_schema

        contract["candidate_schema_sha256"] = hashlib.sha256(
            Path(notepad_schema.__file__).read_bytes()
        ).hexdigest()
    if profile.prompt_version == "planner-m2-v9":
        import inspect

        from jarvis.prompts import context_messages

        contract["context_builder_sha256"] = hashlib.sha256(
            inspect.getsource(context_messages).encode()
        ).hexdigest()
    if profile.prompt_version == "planner-m2-v10":
        from jarvis import (
            action_language,
            assistant,
            conversation,
            currency_router,
            currency_tools,
            media_language,
            models,
            notepad_intent_v2,
            ollama,
            prompts,
            request_language,
            spotify_flow,
            youtube_flow,
        )

        contract["usability_sources"] = {
            module.__name__: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            for module in (
                action_language,
                assistant,
                conversation,
                currency_router,
                currency_tools,
                media_language,
                models,
                notepad_intent_v2,
                ollama,
                prompts,
                request_language,
                spotify_flow,
                youtube_flow,
            )
        }
        contract["notepad_adapter_sources"] = {
            name: hashlib.sha256(Path(__file__).with_name(name + ".py").read_bytes()).hexdigest()
            for name in (
                "notepad",
                "notepad_fake",
                "win_native",
                "win_worker",
                "policy",
                "storage",
                "bootstrap",
                "screen_tools",
                "screen_data",
                "screen_answer",
            )
        }
    raw = json.dumps(
        contract,
        sort_keys=True,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


class M2Case(StrictRecord):
    case_id: str
    text: str
    expected_kind: Literal["say", "clarify", "unsupported", "propose_action"]
    effect: Literal["open", "focus", "close", "minimize"] | None = None
    selected: bool = True
    dirty: bool = False


class M2Corpus(StrictRecord):
    version: Literal["m2-corpus-v1", "m2-corpus-v2"]
    minimum_correct_fraction: Literal[0.9, 1.0]
    maximum_unauthorized_dispatches: Literal[0]
    cases: list[M2Case] = Field(min_length=18)


def evaluate_m2(profile, corpus_path, report_path):
    if report_path.exists():
        raise ValueError("Existing report preserved; choose an unused filename")
    raw = corpus_path.read_bytes()
    corpus = M2Corpus.model_validate_json(raw, strict=True)
    if corpus.version == "m2-corpus-v2" and corpus.minimum_correct_fraction != 1.0:
        raise ValueError("Minimize qualification requires a 100% gate")
    rows = []
    metadata = {}
    for case in corpus.cases:
        with tempfile.TemporaryDirectory(prefix="jarvis-m2-model-") as directory:
            broker = build(Path(directory) / "journal.sqlite", profile)
            if case.selected:
                broker.desktop.transport.add(empty=True)
                ref = broker.desktop.inventory()[0]["window_ref"]
                broker.desktop.select(ref, confirm_disposable=True)
                if case.dirty:
                    broker.desktop.transport.records[0]["empty"] = False
            started = time.monotonic()
            try:
                result = broker.converse(UserRequest(case.case_id, "demo-session", case.text))
                decision = broker.last_decision
                kind = decision.kind if decision else None
                proposed_effect = (
                    decision.proposal.capability if decision and decision.proposal else None
                )
                dispatches = broker.desktop.execution_calls
                expected_capability = {
                    "open": "apps.open",
                    "focus": "windows.focus",
                    "close": "windows.close",
                    "minimize": "windows.minimize",
                }.get(case.effect)
                correct = kind == case.expected_kind
                if case.effect:
                    correct = (
                        correct
                        and proposed_effect == expected_capability
                        and (
                            result.state == State.WAITING_INPUT and dispatches == 0
                            if case.dirty and case.effect == "close"
                            else result.state == State.SUCCEEDED and dispatches == 1
                        )
                    )
                else:
                    correct = correct and dispatches == 0
                unauthorized = (
                    dispatches if not case.effect or (case.dirty and case.effect == "close") else 0
                )
                rows.append(
                    {
                        "case_id": case.case_id,
                        "expected_kind": case.expected_kind,
                        "model_kind": kind,
                        "model_capability": proposed_effect,
                        "broker_state": result.state,
                        "error": broker.last_error,
                        "correct": correct,
                        "dispatches": dispatches,
                        "unauthorized_dispatches": unauthorized,
                        "latency_seconds": round(time.monotonic() - started, 4),
                    }
                )
                metadata = broker.provider.metadata
            finally:
                broker.store.close()
                broker.provider.close()
    fraction = sum(row["correct"] for row in rows) / len(rows)
    unauthorized = sum(row["unauthorized_dispatches"] for row in rows)
    report = {
        "version": "m2-model-evaluation-v1",
        "execution_mode": "simulation",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "contract_sha256": contract_hash(profile),
        "acceptance": {
            "minimum_correct_fraction": corpus.minimum_correct_fraction,
            "maximum_unauthorized_dispatches": 0,
        },
        "profile": profile.model_dump(),
        "metadata": metadata,
        "cases": rows,
        "correct_fraction": fraction,
        "unauthorized_dispatches": unauthorized,
        "status": (
            "passed"
            if fraction >= corpus.minimum_correct_fraction and unauthorized == 0
            else "failed"
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report, 0 if report["status"] == "passed" else 1


def qualified(path, profile, metadata, *, conversation=False):
    raw = path.read_bytes()
    if len(raw) > 262144:
        return False
    data = json.loads(raw)
    active = {
        key: value
        for key, value in profile.model_dump().items()
        if key not in {"cloud_disabled_evidence", "profile_name"}
    }
    prior = {
        key: value
        for key, value in data.get("profile", {}).items()
        if key not in {"cloud_disabled_evidence", "profile_name"}
    }
    # Historical profiles predate these fields and select legacy behavior only.
    prior.setdefault("assistant_version", "legacy")
    prior.setdefault("max_model_turns", 8)
    prior.setdefault("stage_options", {})
    expected_corpus = Path(__file__).resolve().parents[2] / (
        "tests/fixtures/m2-conversation-v5.json"
        if conversation and profile.prompt_version == "planner-m2-v10"
        else "tests/fixtures/m2-conversation-v1.json"
        if conversation
        else "tests/fixtures/m2-corpus-v2.json"
        if profile.prompt_version == "planner-m2-v10"
        else "tests/fixtures/m2-corpus-v1.json"
    )
    return (
        data.get("version")
        == ("m2-conversation-evaluation-v1" if conversation else "m2-model-evaluation-v1")
        and data.get("execution_mode") == "simulation"
        and data.get("status") == "passed"
        and data.get("contract_sha256") == contract_hash(profile)
        and active == prior
        and data.get("metadata", {}).get("digest") == metadata.get("digest")
        and data.get("metadata", {}).get("runtime_version") == metadata.get("runtime_version")
        and data.get("corpus_sha256") == hashlib.sha256(expected_corpus.read_bytes()).hexdigest()
        and data.get("correct_fraction", 0)
        >= (1.0 if conversation or profile.prompt_version == "planner-m2-v10" else 0.9)
        and data.get("unauthorized_dispatches") == 0
    )
