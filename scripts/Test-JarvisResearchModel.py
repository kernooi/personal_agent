"""Explicit real local-model lab with SYNTHETIC search/pages; no public networking."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.conversation import Conversation
from jarvis.domain import State
from jarvis.models import OllamaProfile
from jarvis.web_data import SearchResult, WebConfig, stamp


class LabSearch:
    name = "synthetic-lab"
    last_receipt = {"synthetic": True, "downloaded_bytes": 0}

    def __init__(self):
        self.calls = []

    def search(self, request, config, cancel, deadline):
        self.calls.append(request.model_dump())
        return tuple(
            SearchResult(
                result_id="result_" + uuid4().hex,
                provider=self.name,
                title="Synthetic project release notes",
                domain="example.com",
                url=f"https://example.com/synthetic-{i}",
                snippet="Synthetic project release notes; not live public evidence.",
                published_at="2026-10-09",
                retrieved_at=stamp(SystemClock().now()),
                rank=i + 1,
            )
            for i in range(2)
        )


class LabPages:
    def __init__(self):
        self.calls = []

    def fetch(self, url, config, cancel, deadline):
        self.calls.append(url)
        return {
            "title": "Synthetic project release notes",
            "published_at": "2026-10-09",
            "chunks": (
                "The synthetic project released version 3.0 on 2026-10-09. "
                "Version 3.0 adds synthetic offline research fixtures.",
            ),
        }, {"url": url, "content_type": "text/plain", "downloaded_bytes": 0, "synthetic": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report is preserved; choose a new name")
    profile = load_profile(args.profile, allow_ollama=True)
    if not isinstance(profile, OllamaProfile):
        parser.error("This explicit local-model lab requires an Ollama profile; no fake fallback")
    search, pages = LabSearch(), LabPages()
    # Frozen synthetic owner request and follow-ups. No real public provider fallback.
    cases = ("Research synthetic project version", "What sources did you use?", "What changed?")
    records = []
    with tempfile.TemporaryDirectory(prefix="jarvis-research-model-lab-") as directory:
        broker = build(
            Path(directory) / "journal.sqlite",
            profile,
            web_config=WebConfig(enabled=True, provider="synthetic-lab"),
            search_provider=search,
            page_fetcher=pages,
        )
        metadata = broker.provider.inspect(profile)
        conversation = Conversation(broker)
        try:
            for owner in cases:
                result = conversation.submit(owner)
                records.append(
                    {
                        "synthetic_owner_request": owner,
                        "state": result.state,
                        "error": broker.last_error,
                        "answer": result.message,
                        "model_turns": broker.web.model_turns,
                        "assessment": broker.web.answer.assessment if broker.web.answer else None,
                        "correct": result.state == State.SUCCEEDED
                        and (
                            owner == "What sources did you use?"
                            or (
                                broker.web.answer is not None
                                and broker.web.answer.assessment == "supported"
                            )
                        ),
                    }
                )
            effects = getattr(broker.desktop, "effect_count", 0)
        finally:
            broker.provider.close()
            broker.store.close()
    passed = (
        all(row["correct"] for row in records)
        and effects == 0
        and bool(search.calls)
        and bool(pages.calls)
    )
    report = {
        "scope": "Real Ollama inference with synthetic search/pages; NOT live-search qualification",
        "passed": passed,
        "model": metadata,
        "profile": profile.model_dump(),
        "corpus_sha256": hashlib.sha256(json.dumps(cases).encode()).hexdigest(),
        "public_network_calls": 0,
        "windows_effects": effects,
        "synthetic_search_calls": search.calls,
        "synthetic_page_calls": pages.calls,
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
