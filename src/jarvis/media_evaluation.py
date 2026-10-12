"""Explicit local-model qualification against frozen fake media, never live Chrome evidence."""

import hashlib
import json
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build
from jarvis.domain import State
from jarvis.media_data import MediaConfig, MediaItem, MediaObservation
from jarvis.media_fake import FakeBrowserProvider
from jarvis.models import reject_constant, unique_object
from jarvis.ollama import OllamaProvider

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/m4-corpus-v2.json"
WINDOWS_CORPUS = CORPUS.with_name("m4-windows-media-corpus-v1.json")
SPOTIFY_DESKTOP_CORPUS = CORPUS.with_name("m4-spotify-desktop-corpus-v1.json")


def contract_hash():
    sources = [
        "media_data",
        "media_tools",
        "conversation",
        "youtube_flow",
        "spotify_flow",
        "spotify_desktop",
        "spotify_accessibility",
        "media_evaluation",
        "media_fake",
        "browser_transport",
        "browser_worker",
        "chrome_identity",
        "spotify_api",
        "windows_media",
        "core",
        "storage",
        "policy",
        "models",
        "ollama",
        "bootstrap",
        "cli",
        "terminal",
        "media_lab",
    ]
    return hashlib.sha256(
        json.dumps(
            {
                s: hashlib.sha256(Path(__file__).with_name(s + ".py").read_bytes()).hexdigest()
                for s in sources
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def seed(broker, fake, case):
    service = case.get("service", "youtube")
    adapter = broker.media
    if adapter.config.spotify_backend == "desktop":
        fake.catalog = [
            (
                "a" * 22,
                "Deep Focus" if case.get("playlist") else "Never Gonna Give You Up",
                "Spotify" if case.get("playlist") else "Rick Astley",
            ),
            ("b" * 22, "Synthetic other result", "Test creator"),
        ]
    adapter.activate_service(service)
    adapter.service = service
    adapter.owner_session = broker.grant.session
    adapter.spotify_ready = not case.get("setup_missing", False)
    items = [
        MediaItem(reference="media_" + uuid4().hex, item_id=identity, title=title, creator=creator)
        for identity, title, creator in fake.catalog
    ]
    if case.get("seed"):
        fake.results = {r.reference: r for r in items}
        adapter.results = items
        adapter.results_observed_at = broker.clock.now()
        if case["seed"] == "selected":
            adapter.current_reference = items[0].reference
        observed = MediaObservation(
            session_ref=adapter.session_ref,
            service=service,
            generation=0,
            observed_at=float(broker.clock.now()),
            state="playing" if case["seed"] == "selected" else "results",
            item_id=items[0].item_id if case["seed"] == "selected" else "",
            title=items[0].title,
            results=items if case["seed"] == "results" else [],
        )
        fake.states[service] = observed
        adapter.observation = observed


def evaluate(profile, path, *, windows_media=False, spotify_desktop=False):
    if path.exists():
        raise ValueError("Existing report preserved; choose an unused filename")
    corpus_raw = (
        SPOTIFY_DESKTOP_CORPUS if spotify_desktop else WINDOWS_CORPUS if windows_media else CORPUS
    ).read_bytes()
    corpus = json.loads(corpus_raw)
    clock = SystemClock()
    provider = OllamaProvider(clock)
    metadata = provider.inspect(profile)
    rows = []
    if metadata.get("ready"):
        for case in corpus["cases"]:
            with tempfile.TemporaryDirectory(prefix="jarvis-m4-fake-") as directory:
                fake = FakeBrowserProvider(clock)
                broker = build(
                    Path(directory) / "journal.sqlite",
                    profile,
                    clock,
                    provider=provider,
                    media_config=MediaConfig(
                        enabled=True,
                        youtube=True,
                        netflix=True,
                        spotify=True,
                        spotify_backend="desktop"
                        if spotify_desktop
                        else "windows"
                        if windows_media
                        else "api",
                    ),
                    browser_provider=fake,
                )
                seed(broker, fake, case)
                from jarvis.conversation import Conversation

                conversation = Conversation(broker)
                started = time.monotonic()
                try:
                    result = conversation.submit(case["text"], case["id"])
                    for index, followup in enumerate(case.get("followups", [])):
                        result = conversation.submit(
                            followup, case["id"] + "/followup-" + str(index)
                        )
                    decision = broker.last_decision
                    args = broker.media.pending["arguments"]
                    correct = (
                        decision is not None
                        and decision.kind == case["kind"]
                        and (
                            result.state == State.SUCCEEDED
                            and args.operation == case["operation"]
                            and fake.execution_count == case.get("calls", 1)
                            if case["kind"] == "propose_action"
                            else fake.execution_count == 0
                        )
                    )
                    authorized = case.get("calls", 1) if case["kind"] == "propose_action" else 0
                    unauthorized = max(0, fake.execution_count - authorized)
                    rows.append(
                        {
                            "id": case["id"],
                            "correct": correct,
                            "kind": decision.kind if decision else None,
                            "state": result.state,
                            "error": broker.last_error,
                            "operation": args.operation,
                            "fake_media_calls": fake.execution_count,
                            "desktop_calls": broker.desktop.execution_calls,
                            "unauthorized_calls": unauthorized,
                            "latency_seconds": round(time.monotonic() - started, 3),
                        }
                    )
                finally:
                    broker.store.close()
                    fake.close()
    provider.close()
    correct = sum(r["correct"] for r in rows)
    passed = (
        bool(metadata.get("ready"))
        and correct == len(corpus["cases"])
        and all(r["unauthorized_calls"] == 0 and r["desktop_calls"] == 0 for r in rows)
    )
    report = {
        "version": "m4-evaluation-v1",
        "mode": "actual_local_model_fake_media",
        "profile": profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(),
        "corpus_sha256": hashlib.sha256(corpus_raw).hexdigest(),
        "gate": corpus["gate"],
        "passed": passed,
        "correct": correct,
        "total": len(corpus["cases"]),
        "records": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    return report, 0 if passed else 1 if metadata.get("ready") else 2


def qualified(path, profile, metadata, *, windows_media=False, spotify_desktop=False):
    try:
        if path.stat().st_size > 262144:
            return False
        report = json.loads(
            path.read_bytes(), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        corpus_raw = (
            SPOTIFY_DESKTOP_CORPUS
            if spotify_desktop
            else WINDOWS_CORPUS
            if windows_media
            else CORPUS
        ).read_bytes()
        corpus = json.loads(corpus_raw)
        return (
            metadata.get("ready") is True
            and report["version"] == "m4-evaluation-v1"
            and report["mode"] == "actual_local_model_fake_media"
            and report["profile"] == profile.model_dump()
            and report["contract_sha256"] == contract_hash()
            and report["corpus_sha256"] == hashlib.sha256(corpus_raw).hexdigest()
            and report["gate"] == corpus["gate"]
            and report["passed"] is True
            and report["correct"] == report["total"] == len(corpus["cases"])
            and [r["id"] for r in report["records"]] == [c["id"] for c in corpus["cases"]]
            and all(
                r["correct"] is True
                and r["unauthorized_calls"] == 0
                and r["desktop_calls"] == 0
                and r["kind"] == case["kind"]
                and (
                    r["state"] == State.SUCCEEDED
                    and r["operation"] == case["operation"]
                    and r["fake_media_calls"] == case.get("calls", 1)
                    if case["kind"] == "propose_action"
                    else r["fake_media_calls"] == 0
                )
                for r, case in zip(report["records"], corpus["cases"], strict=True)
            )
            and report["metadata"]["digest"] == metadata.get("digest")
            and report["metadata"]["runtime_version"] == metadata.get("runtime_version")
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False
