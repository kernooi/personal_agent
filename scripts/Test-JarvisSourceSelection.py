"""Explicit live, simulated-desktop diagnostics for two fixed public questions."""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path

from jarvis.bootstrap import build, load_profile
from jarvis.conversation import Conversation
from jarvis.models import OllamaProfile
from jarvis.web_data import load_web_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--web-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report is preserved; choose a new name")
    profile = load_profile(args.profile, allow_ollama=True)
    if not isinstance(profile, OllamaProfile):
        parser.error("An Ollama profile is required; no fake or cloud fallback")
    config = load_web_config(args.web_config)
    report = {
        "scope": "Two public questions; manual answer review required, not milestone qualification",
        "real_windows_adapter": False,
        "config": config.model_dump(),
        "contract_sha256": hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted(Path("src/jarvis").glob("*.py")))
        ).hexdigest(),
        "records": [],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # Save each completed case before printing. Keep partial/failing evidence if
    # the harness or a Windows output encoding fails later.
    with args.report.open("x", encoding="utf-8") as output:

        def save():
            output.seek(0)
            json.dump(report, output, indent=2)
            output.truncate()
            output.flush()

        save()
        with tempfile.TemporaryDirectory(prefix="jarvis-source-selection-") as directory:
            broker = build(Path(directory) / "journal.sqlite", profile, web_config=config)
            if broker.desktop.real:
                raise RuntimeError("Live source diagnostics must use simulated desktop execution")
            report["model"] = broker.provider.inspect(profile)
            try:
                for question in (
                    "Who is Lee Zii Jia?",
                    "What is the smallest shrimp in the world?",
                ):
                    start = time.time()
                    result = Conversation(broker).submit(question)
                    row = {
                        "synthetic_public_question": question,
                        "state": result.state,
                        "error": broker.last_error,
                        "latency_seconds": time.time() - start,
                        "metrics": broker.web.metrics,
                        "failures": broker.web.failures,
                        "receipts": broker.web.receipts,
                        "sources": [s.model_dump() for s in broker.web.sources],
                        "answer": result.message,
                        "assessment": broker.web.answer.assessment if broker.web.answer else None,
                    }
                    report["records"].append(row)
                    save()
                    print(json.dumps({k: v for k, v in row.items() if k != "sources"}), flush=True)
            except Exception as exc:
                report["harness_error"] = type(exc).__name__
                save()
                raise
            finally:
                broker.provider.close()
                broker.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
