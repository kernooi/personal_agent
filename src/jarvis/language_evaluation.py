"""Frozen local-model wording gate; synthetic media/windows, never real-effects evidence."""

import hashlib
import json
import tempfile
import time
from pathlib import Path

from jarvis.application_data import ApplicationsConfig
from jarvis.application_fake import FakeApplicationPlatform
from jarvis.application_tools import attach
from jarvis.bootstrap import SystemClock, build
from jarvis.media_data import MediaConfig
from jarvis.media_evaluation import seed
from jarvis.media_fake import FakeBrowserProvider
from jarvis.models import reject_constant, unique_object
from jarvis.ollama import OllamaProvider

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/request-language-corpus-v3.json"


def contract_hash():
    from jarvis.application_evaluation import contract_hash as app_hash
    from jarvis.media_evaluation import contract_hash as media_hash

    return hashlib.sha256(
        json.dumps(
            {
                "apps": app_hash(),
                "media": media_hash(),
                "evaluation": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def observe(case, result, broker, fake, platform):
    media = broker.media.observation
    window = platform.windows[0] if len(platform.windows) == 1 else None
    state = case.get("window")
    media_calls, app_calls = case.get("media_calls", 0), case.get("app_calls", 0)
    actual_media, actual_apps = fake.execution_count, len(platform.calls)
    checks = [actual_media == media_calls, actual_apps == app_calls]
    if case.get("read_domain"):
        checks.append(
            broker.store.db.execute(
                "SELECT COUNT(*) FROM tasks WHERE request_key LIKE 'language/%'"
            ).fetchone()[0]
            == 0
            and not broker.registry.media_active
        )
    if case.get("media_state"):
        checks.append(media is not None and media.state == case["media_state"])
    if case.get("title"):
        checks.append(media is not None and media.title == case["title"])
    if case.get("service"):
        checks.append(broker.media.service == case["service"])
    if state:
        checks.append(
            not platform.windows
            if state == "closed"
            else window is not None
            and (
                window["minimized"]
                if state == "minimized"
                else platform.foreground == window["hwnd"]
                if state == "foreground"
                else not window["minimized"]
            )
        )
    if case.get("clarification"):
        checks.append("Which" in (result.display_message or result.message))
    if case.get("capability_answer"):
        answer = (result.display_message or result.message).casefold()
        checks.append(
            result.state == "ANSWERED"
            and "spotify" in answer
            and ("search" in answer or "playlist" in answer)
            and "cannot" not in answer
            and "can't" not in answer
        )
    if media_calls or app_calls:
        checks.append(result.state == "SUCCEEDED")
    return {
        "id": case["id"],
        "correct": all(checks),
        "state": result.state,
        "media_calls": actual_media,
        "app_calls": actual_apps,
        "unauthorized_dispatches": max(0, actual_media - media_calls)
        + max(0, actual_apps - app_calls),
        "postconditions_verified": all(checks[2:]),
        "error": broker.last_error,
    }


def evaluate(profile, path):
    if path.exists():
        raise ValueError("Existing report preserved; choose a new filename")
    raw = CORPUS.read_bytes()
    corpus = json.loads(raw)
    clock = SystemClock()
    provider = OllamaProvider(clock)
    metadata = provider.inspect(profile)
    rows = []
    try:
        if not metadata.get("ready"):
            raise ValueError("Actual local model required; no fallback")
        for case in corpus["cases"]:
            with tempfile.TemporaryDirectory(prefix="jarvis-language-fake-") as directory:
                fake = FakeBrowserProvider(clock)
                fake.catalog = [
                    (
                        "a" * 22,
                        case.get("catalog_title", "Fav Jpop"),
                        case.get("catalog_creator", "Test owner"),
                    ),
                    ("b" * 22, "Fav Jpop" if case.get("duplicate") else "my fav jpop", "Other"),
                    ("c" * 22, "Jpop FAVS", "Another owner"),
                ]
                platform = FakeApplicationPlatform()
                app = platform.add_app("Studio Note")
                broker = build(
                    Path(directory) / "journal.sqlite",
                    profile,
                    clock,
                    provider=provider,
                    media_config=MediaConfig(
                        enabled=True, youtube=True, spotify=True, spotify_backend="desktop"
                    ),
                    browser_provider=fake,
                )
                chat = attach(broker, ApplicationsConfig(enabled=True), platform=platform)
                if case.get("seed_media"):
                    seed(broker, fake, {"service": "spotify", "seed": "selected"})
                if case.get("seed_window"):
                    window = platform.add_window(app)
                    if case.get("dirty"):
                        window.update(protected=True, close_safe=False)
                    chat.desktop.select(chat.desktop.inventory()[0]["window_ref"])
                started = time.monotonic()
                try:
                    result = chat.submit(case["text"], case["id"])
                    for index, text in enumerate(case.get("followups", [])):
                        result = chat.submit(text, case["id"] + "/" + str(index))
                    row = observe(case, result, broker, fake, platform)
                except Exception as error:
                    row = {
                        "id": case["id"],
                        "correct": False,
                        "state": "FAILED",
                        "error": type(error).__name__,
                        "media_calls": fake.execution_count,
                        "app_calls": len(platform.calls),
                        "unauthorized_dispatches": fake.execution_count + len(platform.calls),
                        "postconditions_verified": False,
                    }
                finally:
                    row["latency_seconds"] = round(time.monotonic() - started, 3)
                    rows.append(row)
                    broker.store.close()
                    fake.close()
    finally:
        provider.close()
    passed = len(rows) == len(corpus["cases"]) and all(
        row["correct"] and row["unauthorized_dispatches"] == 0 for row in rows
    )
    report = {
        "version": "request-language-evaluation-v1",
        "execution_mode": "simulation",
        "profile": profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(),
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "gate": corpus["gate"],
        "passed": passed,
        "total": len(corpus["cases"]),
        "correct": sum(row["correct"] for row in rows),
        "records": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report, 0 if passed else 1


def qualified(path, profile, metadata):
    try:
        if path.stat().st_size > 262144:
            return False
        report = json.loads(
            path.read_bytes(), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        corpus = json.loads(CORPUS.read_bytes())
        return (
            metadata.get("ready") is True
            and report["passed"] is True
            and report["version"] == "request-language-evaluation-v1"
            and report["execution_mode"] == "simulation"
            and report["profile"] == profile.model_dump()
            and report["contract_sha256"] == contract_hash()
            and report["corpus_sha256"] == hashlib.sha256(CORPUS.read_bytes()).hexdigest()
            and report["gate"] == corpus["gate"]
            and report["correct"] == report["total"] == len(corpus["cases"])
            and report["metadata"]["digest"] == metadata["digest"]
            and report["metadata"]["runtime_version"] == metadata["runtime_version"]
            and [row["id"] for row in report["records"]] == [c["id"] for c in corpus["cases"]]
            and all(
                row["correct"] is True
                and row["unauthorized_dispatches"] == 0
                and row["postconditions_verified"] is True
                and row["media_calls"] == case.get("media_calls", 0)
                and row["app_calls"] == case.get("app_calls", 0)
                for row, case in zip(report["records"], corpus["cases"], strict=True)
            )
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False
