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
        description="JARVIS local text assistant; simulation default, explicit attended Notepad"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="SIMULATED scenarios only")
    demo.add_argument(
        "--scenario",
        choices=["open-editor", "denied", "cancelled", "recovery-unknown"],
        required=True,
    )
    demo.add_argument("--profile", type=Path, default=Path("config/defaults.toml"))
    inspect = sub.add_parser("inspect-notepad", help="Observational Notepad metadata only")
    inspect.add_argument("--registration", type=Path, required=True)
    lab = sub.add_parser("test-notepad", help="Opt-in attended genuine Notepad broker tests")
    lab.add_argument("--registration", type=Path, required=True)
    lab.add_argument("--windows", action="store_true", required=True)
    lab.add_argument("--attended", action="store_true", required=True)
    lab.add_argument("--report", type=Path, required=True)
    lab.add_argument("--interactive", action="store_true")
    lab.add_argument("--takeover-only", action="store_true")
    lab.add_argument("--prepared-synthetic", action="store_true")
    currency = sub.add_parser(
        "currency-check", help="Explicit live public adapter check; no model or Windows effects"
    )
    currency.add_argument("--public-data-config", type=Path, required=True)
    currency.add_argument("--live", action="store_true", required=True)
    currency.add_argument("--report", type=Path, required=True)
    for command in ("doctor", "chat", "eval", "eval-m2", "eval-m2-chat", "eval-m3", "eval-web"):
        child = sub.add_parser(command, help=f"Local {command}; real chat requires explicit opt-in")
        child.add_argument("--profile", type=Path, required=True)
        if command in {"doctor", "chat", "eval-m3"}:
            child.add_argument("--public-data-config", type=Path, required=command == "eval-m3")
        if command in {"doctor", "chat", "eval-web"}:
            child.add_argument("--web-config", type=Path, required=command == "eval-web")
        if command == "eval-web":
            child.add_argument("--owner-url-only", action="store_true")
        if command == "doctor":
            child.add_argument("--evaluation-report", type=Path)
        if command == "chat":
            child.add_argument("--real", action="store_true")
            child.add_argument("--attended", action="store_true")
            child.add_argument("--registration", type=Path)
            child.add_argument("--model-report", type=Path)
            child.add_argument("--conversation-report", type=Path)
        if command in {"eval", "eval-m2", "eval-m2-chat", "eval-m3", "eval-web"}:
            child.add_argument("--live", action="store_true", required=True)
            child.add_argument("--report", type=Path)
        if command == "eval":
            child.add_argument(
                "--corpus", type=Path, default=Path("tests/fixtures/m1-corpus-v1.json")
            )
            child.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    if args.command == "currency-check":
        from jarvis.currency_tools import load_public_config
        from jarvis.m3_evaluation import provider_check

        try:
            report, code = provider_check(load_public_config(args.public_data_config), args.report)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(report, indent=2))
        raise SystemExit(code)
    if args.command == "inspect-notepad":
        import threading

        from jarvis.notepad import WorkerTransport, load_registration

        transport = WorkerTransport(load_registration(args.registration), threading.Event())
        windows = transport.call("inventory")
        print(
            json.dumps(
                {
                    "notepad_version": transport.registration.notepad_version,
                    "package": transport.registration.package_full_name,
                    "visible_notepad_window_count": len(windows),
                    "private_labels_read": False,
                },
                indent=2,
            )
        )
        return
    if args.command == "test-notepad":
        from jarvis.notepad_lab import run_lab

        raise SystemExit(run_lab(args))
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
    public_config = None
    web_config = None
    if getattr(args, "web_config", None) is not None:
        from jarvis.web_data import load_web_config

        try:
            web_config = load_web_config(args.web_config)
        except (OSError, ValueError):
            parser.error("Web research configuration unavailable or invalid")
    if args.command == "eval-web":
        from jarvis.web_evaluation import evaluate_web

        if args.report is None:
            parser.error("eval-web requires --report; existing reports are never overwritten")
        report, code = evaluate_web(
            profile, web_config, args.report, owner_url_only=args.owner_url_only
        )
        print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
        raise SystemExit(code)
    if getattr(args, "public_data_config", None) is not None:
        from jarvis.currency_tools import load_public_config

        try:
            public_config = load_public_config(args.public_data_config)
        except (OSError, ValueError):
            parser.error("Public-data configuration unavailable or invalid")
        if public_config.mode == "fixture":
            parser.error(
                "Fixture mode requires explicit fixture-provider injection in tests; "
                "no live fallback"
            )
    if args.command == "eval-m3":
        from jarvis.m3_evaluation import evaluate as evaluate_m3

        if args.report is None:
            parser.error("eval-m3 requires --report; existing reports are never overwritten")
        try:
            report, code = evaluate_m3(profile, public_config, args.report)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(
            json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2)
        )
        raise SystemExit(code)
    if args.command in {"eval-m2", "eval-m2-chat"}:
        from jarvis.m2_evaluation import evaluate_m2

        if profile.decision_version != "decision-m2-v1" or args.report is None:
            parser.error("eval-m2 requires an M2 profile and --report")
        if args.command == "eval-m2-chat":
            from jarvis.m2_conversation_evaluation import evaluate_conversation

            report, code = evaluate_conversation(
                profile,
                Path(
                    "tests/fixtures/m2-conversation-v2.json"
                    if profile.prompt_version == "planner-m2-v10"
                    else "tests/fixtures/m2-conversation-v1.json"
                ),
                args.report,
            )
        else:
            report, code = evaluate_m2(
                profile, Path("tests/fixtures/m2-corpus-v1.json"), args.report
            )
        print(json.dumps(report, indent=2))
        raise SystemExit(code)
    if args.command == "eval":
        if profile.decision_version != "decision-v1":
            parser.error("M1 eval requires decision-v1; use eval-m2 for M2")
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
        selected_summary = read_evaluation_summary(args.evaluation_report, profile, metadata)
        if public_config and args.evaluation_report:
            from jarvis.m3_evaluation import qualification_summary

            m3_summary = qualification_summary(
                args.evaluation_report, profile, metadata, public_config
            )
            if m3_summary["status"] == "passed":
                selected_summary = m3_summary
        print(
            json.dumps(
                {
                    "cli_installed": installed,
                    "execution_mode": "simulation",
                    "public_data": public_config.model_dump()
                    if public_config
                    else {"mode": "disabled"},
                    "public_provider_contacted": False,
                    "web_research": web_config.model_dump() if web_config else {"enabled": False},
                    "web_provider_contacted": False,
                    "last_evaluation": selected_summary,
                    **metadata,
                    "qualification": "M3 currency/chat passed; Windows qualification is separate"
                    if selected_summary.get("status") == "passed"
                    and str(selected_summary.get("milestone", "")).startswith("M3 ")
                    else metadata.get("qualification"),
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
    if args.real:
        from jarvis.m2_evaluation import qualified

        if not args.attended or args.registration is None or args.model_report is None:
            parser.error("Real chat requires --attended, --registration and --model-report")
        if profile.decision_version != "decision-m2-v1" or not qualified(
            args.model_report, profile, metadata
        ):
            parser.error(
                "Matching passed M2 model qualification is required; no real effect enabled"
            )
        if profile.prompt_version in {
            "planner-m2-v5",
            "planner-m2-v6",
            "planner-m2-v7",
            "planner-m2-v8",
            "planner-m2-v9",
            "planner-m2-v10",
        } and (
            args.conversation_report is None
            or not qualified(args.conversation_report, profile, metadata, conversation=True)
        ):
            parser.error("Matching passed multi-turn M2 qualification is also required")
    elif args.registration or args.attended or args.model_report or args.conversation_report:
        parser.error("Real-mode options require --real; no implicit Windows activation")
    mode = "WINDOWS" if args.real else "SIMULATED"
    targets = "notepad" if profile.decision_version == "decision-m2-v1" else "text_editor"
    print(
        f"JARVIS | model={profile.model_identity} | provider=ollama | "
        f"execution={mode} | targets={targets}"
    )
    if args.real:
        print("Attended Notepad only. Ctrl+Alt+Shift+F10 stops new effects globally.")
        print(
            "Use /windows to inspect selection; "
            "/confirm-empty confirms your empty disposable test window."
        )
    else:
        print("Model unqualified for real actions; local-mode evidence is user/operator verified.")
    data_home = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "Jarvis"
    data_home.mkdir(parents=True, exist_ok=True)
    if public_config:
        print(f"Public currency data: {public_config.mode} | provider=Frankfurter v2 / ECB.")
        print(
            "Public-data controls: /cache, /cache-clear, /refresh-rate. "
            "Windows permission is separate."
        )
    if web_config:
        print(
            f"Public web research: {'enabled' if web_config.enabled else 'disabled'} "
            f"| provider={web_config.provider}."
        )
        print(
            "Web controls: /web-status, /web-enable, /web-disable, /sources, "
            "/web-cache, /web-cache-clear, /web-refresh."
        )
    try:
        broker = build(
            data_home
            / (
                "m2-journal.sqlite"
                if args.real
                else "m3-journal.sqlite"
                if public_config
                else "journal.sqlite"
            ),
            profile,
            provider=provider,
            session=str(uuid4()),
            real=args.real,
            registration=args.registration,
            attended=args.attended,
            public_config=public_config,
            cache_path=data_home / "public-quotes-v2.json" if public_config else None,
            web_config=web_config,
        )
    except (OSError, sqlite3.Error, ValueError):
        provider.close()
        parser.exit(2, "Private JARVIS journal unavailable; no execution or fallback.\n")
    try:
        recovered = broker.recover()
        waiting = [result for result in recovered if result.state == "NEEDS_REVIEW"]
        if recovered and len(recovered) != len(waiting):
            print("Earlier unfinished requests were ended safely; no actions were replayed.")
        for result in waiting:
            print(result.message)
        if args.real:
            pending = broker.store.db.execute(
                "SELECT DISTINCT a.task_id FROM actions a WHERE a.state='UNKNOWN' "
                "AND a.capability!='currency.quote' "
                "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.task_id=a.task_id "
                "AND e.kind='manual_review_acknowledged')"
            ).fetchall()
            for row in pending:
                if not any(result.task_id == row[0] for result in waiting):
                    print(
                        "Notepad actions are paused for an uncertain earlier outcome. "
                        f"Inspect Notepad, then /review {row[0]} manually-handled."
                    )
        if args.real:
            from jarvis.win_stop import StopHotkey

            with StopHotkey(broker.desktop.stop):
                chat_loop(Conversation(broker), sys.stdin)
        else:
            chat_loop(Conversation(broker), sys.stdin)
    finally:
        broker.store.close()
        provider.close()
