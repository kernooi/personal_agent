"""Explicit actual local inference/public retrieval smoke; Windows remains simulated."""

import argparse
import json
import tempfile
from pathlib import Path

from jarvis.bootstrap import build, load_profile
from jarvis.conversation import Conversation, conversational_text
from jarvis.currency_tools import load_public_config
from jarvis.domain import State
from jarvis.m3_evaluation import checked_calculation, save_report
from jarvis.public_data import CurrencyArguments, utc
from jarvis.web_data import load_web_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--public-data-config", type=Path, required=True)
    parser.add_argument("--web-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report is preserved; select a new path")
    profile = load_profile(args.profile, allow_ollama=True)
    if profile.assistant_version != "assistant-v1":
        parser.error("Select an assistant-v1 profile")
    from jarvis.assistant_evaluation import contract_hash

    report = {
        "version": "assistant-live-smoke-v1",
        "profile": profile.model_dump(),
        "contract_sha256": contract_hash(profile),
        "execution_mode": "simulation",
        "scope": "fixed public smoke only; not broad research qualification",
        "records": [],
    }
    cases = [
        (
            "reported-tickets",
            "if i buy 40 tickets each worth 40 sgd. how much would 40 tickets worth in usd",
            "1600",
        ),
        (
            "discount-fee-split",
            "20 tickets at 30 SGD each. Apply a 10% discount, then add one 20 SGD fee, "
            "and split the final bill between 4 people. What is each share in USD?",
            "140",
        ),
        ("public-biography", "Who is Lee Zii Jia?", None),
    ]
    with tempfile.TemporaryDirectory(prefix="jarvis-assistant-public-") as directory:
        broker = build(
            Path(directory) / "journal.sqlite",
            profile,
            public_config=load_public_config(args.public_data_config),
            web_config=load_web_config(args.web_config),
        )
        chat = Conversation(broker)
        try:
            report["metadata"] = broker.provider.inspect(profile)
            report["checked_at_utc"] = utc(broker.clock.now())
            for name, text, amount in cases:
                started = broker.clock.now()
                result = chat.submit(text)
                task = broker.store.get(result.task_id)
                answer = conversational_text(result)
                correct = result.state == State.SUCCEEDED and broker.desktop.execution_calls == 0
                record = {
                    "id": name,
                    "state": result.state,
                    "error": broker.last_error,
                    "final_answer": answer,
                    "latency_seconds": broker.clock.now() - started,
                    "model_turns": broker.model_turns,
                }
                if amount:
                    bound = (
                        CurrencyArguments.model_validate_json(task.scope.window_ref)
                        if task.scope.app_id == "currency"
                        else None
                    )
                    quote = broker.currency.observation
                    correct &= bool(
                        bound
                        and quote
                        and bound.amount == amount
                        and bound.base == "SGD"
                        and bound.quote == "USD"
                        and quote.sensitivity == "public"
                    )
                    if correct:
                        converted = checked_calculation(amount, quote.rate, "USD")
                        correct &= f"{amount} SGD = {converted} USD" in answer
                    record["arguments"] = bound.model_dump() if bound else None
                    record["quote"] = quote.model_dump() if quote else None
                    record["connection_receipt"] = broker.currency.provider.last_receipt
                else:
                    correct &= task.scope.app_id == "web" and broker.web.answer is not None
                    correct &= bool(
                        broker.web.answer and broker.web.answer.assessment == "supported"
                    )
                    correct &= "badminton" in answer.casefold()
                    record["sources"] = [s.model_dump() for s in broker.web.sources]
                    record["failures"] = broker.web.failures
                    record["network_receipts"] = broker.web.receipts
                    record["summary_bindings"] = [
                        json.loads(r[0])
                        for r in broker.store.db.execute(
                            "SELECT redacted_payload_json FROM events "
                            "WHERE task_id=? AND kind='summary_grounded'",
                            (task.task_id,),
                        )
                    ]
                record["correct"] = bool(correct)
                report["records"].append(record)
            report["desktop_execution_calls"] = broker.desktop.execution_calls
        finally:
            broker.provider.close()
            broker.store.close()
    report["passed"] = all(r["correct"] for r in report["records"])
    save_report(args.report, report)
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
