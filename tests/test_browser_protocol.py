"""Worker supervision and qualification use controlled replies, not real processes."""

import json
import queue
import threading
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.bootstrap import ManualClock, load_profile
from jarvis.browser_transport import BrowserWorkerProvider, WorkerReply
from jarvis.domain import AdmissionRejected
from jarvis.media_data import (
    MediaArguments,
    MediaConfig,
    MediaError,
    MediaObservation,
    WorkerRequest,
    parse_record,
)
from jarvis.media_evaluation import CORPUS, contract_hash, qualified


def args():
    return MediaArguments(service="youtube", operation="current", session_ref="browser_" + "a" * 32)


def request():
    return WorkerRequest(request_id="a" * 32, command="observe", arguments=args(), deadline=1200.0)


def observation():
    return MediaObservation(
        session_ref=args().session_ref,
        service="youtube",
        generation=0,
        observed_at=1000.0,
        state="ready",
    )


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setattr("jarvis.spotify_api.credential_ready", lambda: False)
    clock = ManualClock()
    provider = BrowserWorkerProvider(clock, Path("synthetic"), MediaConfig(), threading.Event())
    provider.start = lambda: None
    provider.process = SimpleNamespace(stdin=BytesIO(), poll=lambda: None)
    provider.abort = lambda: setattr(provider, "dead", True)
    return provider


def reply(request_id="a" * 32, error="", admitted=False):
    return (
        json.dumps(
            {
                "version": 1,
                "request_id": request_id,
                "admitted": admitted,
                "observation": None if error else observation().model_dump(),
                "error": error,
            }
        ).encode()
        + b"\n"
    )


def test_supervisor_uses_matching_compact_typed_reply(worker):
    worker.replies.put(reply())
    assert worker.call(request(), lambda: False).state == "ready"
    assert b"observe" in worker.process.stdin.getvalue()


def test_supervisor_rejects_late_wrong_identity(worker):
    worker.replies.put(reply("b" * 32))
    with pytest.raises(MediaError, match="OBSOLETE"):
        worker.call(request(), lambda: False)
    assert worker.dead


@pytest.mark.parametrize(
    "error",
    [
        "STALE_NAVIGATION_GENERATION",
        "USER_TAKEOVER_REOBSERVE_REQUIRED",
        "SPOTIFY_OAUTH_SETUP_REQUIRED",
    ],
)
def test_worker_reports_proven_pre_effect_rejection(worker, error):
    worker.replies.put(reply(error=error))
    with pytest.raises(AdmissionRejected, match=error):
        worker.call(request(), lambda: False)


def test_error_after_delivery_is_unknown_not_pre_effect(worker):
    worker.replies.put(reply(error="BROWSER_OPERATION_FAILED", admitted=True))
    with pytest.raises(MediaError):
        worker.call(request(), lambda: False)


def test_stop_before_send_is_zero_worker_delivery(worker):
    worker.stop.set()
    with pytest.raises(AdmissionRejected):
        worker.call(request(), lambda: False)
    assert worker.process.stdin.getvalue() == b""


def test_stop_after_send_discards_pending_observation(worker):
    checks = []

    def cancelled():
        checks.append(True)
        return len(checks) > 1

    worker.replies.put(reply())
    with pytest.raises(MediaError, match="CANCELLED_AFTER_DELIVERY"):
        worker.call(request(), cancelled)
    assert worker.dead


def test_closed_worker_is_not_silently_restarted(worker):
    worker.replies.put(None)
    with pytest.raises(MediaError, match="CLOSED"):
        worker.call(request(), lambda: False)
    assert worker.dead


def test_worker_timeout_is_bounded_and_no_automatic_retry(worker):
    class ExpiringQueue:
        def get(self, timeout):
            worker.clock.advance(250)
            raise queue.Empty

    worker.replies = ExpiringQueue()
    with pytest.raises(MediaError, match="TIMEOUT"):
        worker.call(request(), lambda: False)
    assert worker.dead
    assert worker.process.stdin.getvalue().count(b"\n") == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("cookies", "secret"),
        ("headers", {"Authorization": "secret"}),
        ("version", 2),
        ("admitted", "true"),
    ],
)
def test_reply_schema_rejects_secret_or_invalid_envelope_fields(field, value):
    data = json.loads(reply())
    data[field] = value
    with pytest.raises(ValueError):
        parse_record(json.dumps(data).encode(), WorkerReply)


def report(profile, metadata):
    import hashlib

    corpus_raw = CORPUS.read_bytes()
    corpus = json.loads(corpus_raw)
    return {
        "version": "m4-evaluation-v1",
        "mode": "actual_local_model_fake_media",
        "profile": profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(),
        "corpus_sha256": hashlib.sha256(corpus_raw).hexdigest(),
        "gate": corpus["gate"],
        "passed": True,
        "correct": len(corpus["cases"]),
        "total": len(corpus["cases"]),
        "records": [
            {
                "id": case["id"],
                "correct": True,
                "unauthorized_calls": 0,
                "desktop_calls": 0,
                "kind": case["kind"],
                "state": "SUCCEEDED",
                "operation": case["operation"],
                "fake_media_calls": 1 if case["kind"] == "propose_action" else 0,
            }
            for case in corpus["cases"]
        ],
    }


@pytest.mark.parametrize(
    "mutation",
    ["failed", "profile", "contract", "corpus", "gate", "digest", "unauthorized", "missing_case"],
)
def test_qualification_rejects_stale_failed_or_tampered_results(tmp_path, mutation):
    profile = load_profile(Path("config/examples/desktop.toml"), allow_ollama=True)
    metadata = {"ready": True, "digest": "synthetic_digest", "runtime_version": "synthetic_runtime"}
    data = report(profile, metadata)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    assert qualified(path, profile, metadata)
    if mutation == "failed":
        data["passed"] = False
    elif mutation == "profile":
        data["profile"]["model_identity"] = "other_model"
    elif mutation == "contract":
        data["contract_sha256"] = "wrong"
    elif mutation == "corpus":
        data["corpus_sha256"] = "wrong"
    elif mutation == "gate":
        data["gate"]["minimum_correct_fraction"] = 0.5
    elif mutation == "digest":
        data["metadata"] = {**metadata, "digest": "wrong"}
    elif mutation == "unauthorized":
        data["records"][0]["unauthorized_calls"] = 1
    else:
        data["records"].pop()
    path.write_text(json.dumps(data))
    assert not qualified(path, profile, metadata)
