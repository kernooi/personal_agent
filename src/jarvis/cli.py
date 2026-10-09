"""Runnable, visibly simulated scenarios. No arbitrary natural-language executor."""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import ManualClock, build, load_profile
from jarvis.domain import SimulatedCrash, UserRequest
from jarvis.models import OllamaProfile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JARVIS local text assistant; desktop actions are SIMULATED"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="SIMULATED scenarios only")
    demo.add_argument(
        "--scenario",
        choices=["open-editor", "denied", "cancelled", "recovery-unknown"],
        required=True,
    )
    demo.add_argument("--profile", type=Path, default=Path("config/defaults.toml"))
    for command in ("doctor", "chat", "eval"):
        child = sub.add_parser(command, help=f"M1 {command}; actions remain SIMULATED")
        child.add_argument("--profile", type=Path, required=True)
        if command == "doctor":
            child.add_argument("--evaluation-report", type=Path)
        if command == "eval":
            child.add_argument("--live", action="store_true", required=True)
            child.add_argument(
                "--corpus", type=Path, default=Path("tests/fixtures/m1-corpus-v1.json")
            )
            child.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
            child.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command != "demo":
        live_command(args, parser)
        return
    profile = load_profile(args.profile)
    # Every demo gets isolated temporary persistence; never touches personal app data.
    with tempfile.TemporaryDirectory(prefix="jarvis-simulated-") as directory:
        path = Path(directory) / "journal.sqlite"
        clock = ManualClock()
        broker = build(path, profile, clock)
        print(
            f"SIMULATED | scripted provider={profile.model_identity} | fake desktop | network=none"
        )
        print('SIMULATED request: "Open my registered text editor."')
        before = len(broker.desktop.running)
        if args.scenario == "denied":
            broker.grant = replace(broker.grant, apps=frozenset())
        elif args.scenario == "cancelled":
            broker.before_admission = lambda: broker.store.cancel(
                broker.store.db.execute("SELECT task_id FROM tasks").fetchone()[0]
            )
        elif args.scenario == "recovery-unknown":
            broker.desktop.crash = "after_effect"
        try:
            result = broker.submit(
                UserRequest("demo-delivery-1", "demo-session", "Open my registered text editor.")
            )
        except SimulatedCrash:
            broker.store.close()
            broker.provider.close()
            # Reopen the actual durable journal with an empty fake desktop observation world.
            old_desktop = broker.desktop
            broker = build(path, profile, clock)
            result = broker.recover()[0]
            broker.desktop = old_desktop  # Only to display the injected effect; no replay.
        print(
            json.dumps(
                {
                    **asdict(result),
                    "fake_running_before": before,
                    "fake_running_after": len(broker.desktop.running),
                    "execution_calls": broker.desktop.execution_calls,
                    "effect_count": broker.desktop.effect_count,
                    "observation_calls": broker.desktop.observation_calls,
                },
                indent=2,
            )
        )
        broker.store.close()
        broker.provider.close()


def live_command(args, parser):
    from jarvis.bootstrap import SystemClock
    from jarvis.conversation import Conversation
    from jarvis.evaluation import evaluate, read_evaluation_summary, write_report
    from jarvis.ollama import OllamaProvider
    from jarvis.terminal import chat_loop

    try:
        profile = load_profile(args.profile, allow_ollama=True)
    except (OSError, ValueError):
        parser.error("Profile unavailable or invalid; see the strict M1 profile examples")
    if not isinstance(profile, OllamaProfile):
        parser.error("M1 commands require an explicit Ollama profile; no fake fallback")
    if args.command == "eval":
        result = evaluate(profile, args.corpus, args.repeats)
        if args.report:
            write_report(args.report, result.report)
        print(json.dumps(result.report, indent=2))
        raise SystemExit(result.exit_code)
    provider = OllamaProvider(SystemClock())
    metadata = provider.inspect(profile)
    if args.command == "doctor":
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        standard = local_appdata / "Programs/Ollama/ollama.exe"
        portable = local_appdata / "Jarvis/runtime"
        installed = bool(
            shutil.which("ollama")
            or standard.is_file()
            or (portable.exists() and any(portable.glob("ollama-*/bin/ollama.exe")))
        )
        print(
            json.dumps(
                {
                    "cli_installed": installed,
                    "execution_mode": "simulation",
                    "last_evaluation": read_evaluation_summary(
                        args.evaluation_report, profile, metadata
                    ),
                    **metadata,
                },
                indent=2,
            )
        )
        provider.close()
        raise SystemExit(0 if metadata.get("ready") else 2)
    if not metadata.get("ready"):
        provider.close()
        parser.exit(
            2,
            f"Ollama not ready: {metadata.get('error', 'LOCAL_MODE_UNVERIFIED')}. "
            "No fake/cloud fallback; doctor is observational.\n",
        )
    print(f"JARVIS | model={profile.model_identity} | provider=ollama | execution=SIMULATED")
    print("Model unqualified for real actions; local-mode evidence is user/operator verified.")
    data_home = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "Jarvis"
    data_home.mkdir(parents=True, exist_ok=True)
    try:
        broker = build(
            data_home / "journal.sqlite", profile, provider=provider, session=str(uuid4())
        )
    except (OSError, sqlite3.Error):
        provider.close()
        parser.exit(2, "Private JARVIS journal unavailable; no execution or fallback.\n")
    try:
        for result in broker.recover():
            print(result.message)
        chat_loop(Conversation(broker), sys.stdin)
    finally:
        broker.store.close()
        provider.close()
