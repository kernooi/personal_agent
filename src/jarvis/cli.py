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
    sub.add_parser("inspect-apps", help="Read Windows app catalog; no app launch")
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
    chrome = sub.add_parser(
        "inspect-chrome", help="Observe installed stable Google Chrome; no launch"
    )
    chrome.add_argument("--registration", type=Path)
    register = sub.add_parser(
        "register-chrome", help="Create private dedicated-profile Chrome registration"
    )
    register.add_argument("--output", type=Path, required=True)
    spotify = sub.add_parser(
        "spotify-store-token", help="Explicit private OS credential setup; no model/network"
    )
    spotify.add_argument("--expires-in", type=int, choices=range(1, 3601), required=True)
    media_lab = sub.add_parser(
        "test-media", help="Explicit attended installed-Chrome/local-model YouTube lab"
    )
    media_lab.add_argument("--windows", action="store_true", required=True)
    media_lab.add_argument("--attended", action="store_true", required=True)
    media_lab.add_argument("--profile", type=Path, required=True)
    media_lab.add_argument("--browser-registration", type=Path, required=True)
    media_lab.add_argument("--media-report", type=Path, required=True)
    media_lab.add_argument("--report", type=Path, required=True)
    media_lab.add_argument("--interactive", action="store_true")
    for command in (
        "doctor",
        "chat",
        "eval",
        "eval-m2",
        "eval-m2-chat",
        "eval-m3",
        "eval-web",
        "eval-assistant",
        "eval-media",
        "eval-windows-media",
        "eval-spotify-desktop",
        "eval-apps",
    ):
        child = sub.add_parser(command, help=f"Local {command}; real chat requires explicit opt-in")
        child.add_argument("--profile", type=Path, required=True)
        if command in {"doctor", "chat", "eval-m3"}:
            child.add_argument("--public-data-config", type=Path, required=command == "eval-m3")
        if command in {"doctor", "chat", "eval-web"}:
            child.add_argument("--web-config", type=Path, required=command == "eval-web")
        if command in {"doctor", "chat"}:
            child.add_argument("--media-config", type=Path)
        if command == "eval-web":
            child.add_argument("--owner-url-only", action="store_true")
        if command == "doctor":
            child.add_argument("--evaluation-report", type=Path)
        if command == "chat":
            child.add_argument("--applications-config", type=Path)
            child.add_argument("--real-apps", action="store_true")
            child.add_argument("--apps-attended", action="store_true")
            child.add_argument("--applications-report", type=Path)
            child.add_argument("--real", action="store_true")
            child.add_argument("--attended", action="store_true")
            child.add_argument("--registration", type=Path)
            child.add_argument("--model-report", type=Path)
            child.add_argument("--conversation-report", type=Path)
            child.add_argument("--real-browser", action="store_true")
            child.add_argument("--real-media", action="store_true")
            child.add_argument("--media-attended", action="store_true")
            child.add_argument("--windows-media-report", type=Path)
            child.add_argument("--browser-attended", action="store_true")
            child.add_argument("--browser-registration", type=Path)
            child.add_argument("--media-report", type=Path)
        if command in {
            "eval",
            "eval-m2",
            "eval-m2-chat",
            "eval-m3",
            "eval-web",
            "eval-assistant",
            "eval-media",
            "eval-windows-media",
            "eval-spotify-desktop",
            "eval-apps",
        }:
            child.add_argument("--live", action="store_true", required=True)
            child.add_argument("--report", type=Path)
        if command == "eval":
            child.add_argument(
                "--corpus", type=Path, default=Path("tests/fixtures/m1-corpus-v1.json")
            )
            child.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    if args.command == "inspect-apps":
        import threading

        from jarvis.application_data import ApplicationsConfig
        from jarvis.application_windows import WindowsApplicationPlatform

        platform = WindowsApplicationPlatform(ApplicationsConfig(enabled=True), threading.Event())
        records = platform.call("catalog")
        print(
            json.dumps(
                {
                    "supported_count": len(records["apps"]),
                    "unsupported_count": records["unsupported_count"],
                    "applications": [
                        {"name": a["name"], "app_id": a["app_id"]} for a in records["apps"]
                    ],
                    "effects_sent": 0,
                },
                indent=2,
            )
        )
        return
    if args.command == "test-media":
        from jarvis.media_lab import run_lab

        try:
            report, code = run_lab(args)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
        raise SystemExit(code)
    if args.command in {"inspect-chrome", "register-chrome"}:
        from jarvis.chrome_identity import create_registration, discover_chrome, load_registration

        try:
            identity = (
                create_registration(args.output, Path.cwd())
                if args.command == "register-chrome"
                else load_registration(args.registration)
                if args.registration
                else discover_chrome()
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                {
                    **identity.model_dump(),
                    "browser_launched": False,
                    "profile_classification": "dedicated private JARVIS; ordinary Chrome excluded",
                },
                indent=2,
            )
        )
        return
    if args.command == "spotify-store-token":
        import getpass
        import time

        from jarvis.spotify_api import SCOPES, store_token

        if not sys.stdin.isatty():
            parser.error("Use an attended terminal; never pass tokens as command-line arguments")
        print(
            "Store only an authorized Spotify access token with the documented playback scopes. "
            "No refresh token or password is requested."
        )
        token = getpass.getpass("Authorized access token (hidden): ")
        store_token(token, SCOPES, time.time() + args.expires_in)
        print("Stored in Windows Credential Manager. Expiry still requires manual reauthorization.")
        return
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
    if args.command == "eval-apps":
        from jarvis.application_evaluation import evaluate

        if args.report is None:
            parser.error("eval-apps requires --report; preserve existing results")
        report, code = evaluate(profile, args.report)
        print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
        raise SystemExit(code)
    public_config = None
    web_config = None
    if getattr(args, "web_config", None) is not None:
        from jarvis.web_data import load_web_config

        try:
            web_config = load_web_config(args.web_config)
        except (OSError, ValueError):
            parser.error("Web research configuration unavailable or invalid")
    if args.command == "eval-assistant":
        from jarvis.assistant_evaluation import evaluate as evaluate_assistant

        if args.report is None:
            parser.error("eval-assistant requires --report; failed evidence is preserved")
        try:
            report, code = evaluate_assistant(profile, args.report)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
        raise SystemExit(code)
    if args.command in {"eval-media", "eval-windows-media", "eval-spotify-desktop"}:
        from jarvis.media_evaluation import evaluate as evaluate_media

        if args.report is None:
            parser.error("eval-media requires --report; existing reports are preserved")
        report, code = evaluate_media(
            profile,
            args.report,
            windows_media=args.command == "eval-windows-media",
            spotify_desktop=args.command == "eval-spotify-desktop",
        )
        print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))
        raise SystemExit(code)
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
                    "tests/fixtures/m2-conversation-v5.json"
                    if profile.prompt_version == "planner-m2-v10"
                    else "tests/fixtures/m2-conversation-v1.json"
                ),
                args.report,
            )
        else:
            report, code = evaluate_m2(
                profile,
                Path(
                    "tests/fixtures/m2-corpus-v2.json"
                    if profile.prompt_version == "planner-m2-v10"
                    else "tests/fixtures/m2-corpus-v1.json"
                ),
                args.report,
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
    media_config = None
    if getattr(args, "media_config", None):
        from jarvis.media_data import load_media_config

        try:
            media_config = load_media_config(args.media_config)
        except (OSError, ValueError):
            parser.error("Invalid media configuration")
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
        if profile.assistant_version in {"assistant-v1", "assistant-v2"} and args.evaluation_report:
            from jarvis.assistant_evaluation import qualification_summary as assistant_summary

            candidate = assistant_summary(args.evaluation_report, profile, metadata)
            if candidate["status"] == "passed":
                selected_summary = candidate
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
                    "media": media_config.model_dump() if media_config else {"enabled": False},
                    "browser_launched": False,
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
    browser_provider = None
    browser_stop = None
    if args.real_browser:
        import threading

        from jarvis.browser_transport import BrowserWorkerProvider
        from jarvis.media_evaluation import qualified as media_qualified

        if (
            not args.browser_attended
            or args.browser_registration is None
            or media_config is None
            or not media_config.enabled
            or args.media_report is None
            or not media_qualified(args.media_report, profile, metadata)
        ):
            parser.error(
                "Real Chrome requires enabled media config, --browser-attended, "
                "--browser-registration and matching passed --media-report"
            )
        browser_stop = threading.Event()
        browser_provider = BrowserWorkerProvider(
            SystemClock(), args.browser_registration, media_config, browser_stop
        )
    elif args.browser_attended or args.browser_registration or args.media_report:
        parser.error("Browser real-mode options require --real-browser")
    if args.real_media:
        import threading

        from jarvis.media_evaluation import qualified as media_qualified
        from jarvis.windows_media import MediaProviders, WindowsMediaProvider

        if (
            not args.media_attended
            or media_config is None
            or not media_config.enabled
            or not media_config.spotify
            or media_config.spotify_backend not in {"windows", "desktop"}
            or args.windows_media_report is None
            or not media_qualified(
                args.windows_media_report,
                profile,
                metadata,
                windows_media=media_config.spotify_backend == "windows",
                spotify_desktop=media_config.spotify_backend == "desktop",
            )
        ):
            parser.error(
                "Windows Spotify requires an enabled windows/desktop backend, --media-attended "
                "and matching passed --windows-media-report"
            )
        browser_stop = browser_stop or threading.Event()
        if media_config.spotify_backend == "desktop":
            from jarvis.spotify_desktop import SpotifyDesktopProvider

            native = SpotifyDesktopProvider(SystemClock(), media_config, browser_stop)
        else:
            native = WindowsMediaProvider(SystemClock(), media_config, browser_stop)
        browser_provider = MediaProviders(browser_provider, native, browser_stop)
    elif args.media_attended or args.windows_media_report:
        parser.error("Windows media real-mode options require --real-media")
    if (
        args.real_browser
        and media_config.spotify
        and media_config.spotify_backend in {"windows", "desktop"}
        and not args.real_media
    ):
        parser.error("Windows Spotify needs separate --real-media consent; no API fallback")
    mode = "WINDOWS" if args.real else "SIMULATED"
    applications_config = None
    if args.applications_config:
        import tomllib

        from jarvis.application_data import ApplicationsConfig

        applications_config = ApplicationsConfig.model_validate(
            tomllib.loads(args.applications_config.read_text(encoding="utf-8-sig")), strict=True
        )
    if args.real_apps:
        from jarvis.application_evaluation import qualified as applications_qualified

        if (
            not args.apps_attended
            or applications_config is None
            or not applications_config.enabled
            or args.applications_report is None
            or profile.decision_version != "decision-m2-v1"
            or not applications_qualified(args.applications_report, profile, metadata)
        ):
            parser.error(
                "Real applications require enabled config, --apps-attended and matching "
                "passed --applications-report; no application effect enabled"
            )
    elif args.apps_attended or args.applications_report:
        parser.error("Application real-mode options require --real-apps")
    targets = "notepad" if profile.decision_version == "decision-m2-v1" else "text_editor"
    print(
        f"JARVIS | model={profile.model_identity} | provider=ollama | "
        f"execution={mode} | targets={targets}"
    )
    if args.real:
        print("Attended Notepad only. Ctrl+Alt+Shift+F10 stops new effects globally.")
        print(
            "Ask naturally to open, focus, minimize or close Notepad. Unsaved work stays protected."
        )
    else:
        print("Notepad actions are simulated; local-mode evidence is user/operator verified.")
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
    if media_config:
        browser_label = (
            "installed Google Chrome / dedicated JARVIS profile"
            if args.real_browser
            else "SIMULATED browser"
        )
        spotify_label = (
            "Windows media controls / native Spotify search"
            if args.real_media and media_config.spotify_backend == "desktop"
            else "Windows media controls"
            if args.real_media
            else "setup required"
            if not browser_provider or not browser_provider.spotify_ready
            else "OAuth configured"
        )
        print(
            f"Media: {browser_label} | YouTube={media_config.youtube} | "
            f"Netflix={media_config.netflix} | Spotify={spotify_label}."
        )
        print(
            "Media controls: /media-status, /media-device <reference>, "
            "/review-media <task> manually-handled. "
            "Ctrl+Alt+Shift+F10 stops new real media actions."
        )
    try:
        broker = build(
            data_home
            / (
                "applications-journal.sqlite"
                if args.real_apps
                else "applications-simulation-journal.sqlite"
                if applications_config and applications_config.enabled
                else "m4-journal.sqlite"
                if args.real_browser or args.real_media
                else "m2-journal.sqlite"
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
            media_config=media_config,
            browser_provider=browser_provider,
        )
    except (OSError, sqlite3.Error, ValueError):
        provider.close()
        parser.exit(2, "Private JARVIS journal unavailable; no execution or fallback.\n")
    try:
        conversation = Conversation(broker)
        if applications_config and applications_config.enabled:
            from jarvis.application_tools import attach

            try:
                conversation = attach(
                    broker, applications_config, real=args.real_apps, attended=args.apps_attended
                )
            except (OSError, ValueError, RuntimeError):
                parser.exit(2, "Application catalog unavailable; no execution or fallback.\n")
            application_mode = "WINDOWS" if args.real_apps else "SIMULATED"
            print(
                f"Applications: device catalog | execution={application_mode} "
                f"| supported={len(conversation.desktop.apps)} "
                f"| unavailable={conversation.desktop.unsupported_count}."
            )
            print(
                "Ask to open, focus, minimize or close an app by name. "
                "A selected or sole verified window needs no extra confirmation. "
                "Notepad text, unsaved changes and unknown state stay protected."
            )
        recovered = broker.recover()
        waiting = [result for result in recovered if result.state == "NEEDS_REVIEW"]
        if recovered and len(recovered) != len(waiting):
            print("Earlier unfinished requests were ended safely; no actions were replayed.")
        for result in waiting:
            print(result.message)
        if broker.media:
            reported = {result.task_id for result in waiting}
            for task_id, message in broker.media.pending_reviews(broker.store):
                if task_id not in reported:
                    print(message)
        if args.real:
            pending = broker.store.db.execute(
                "SELECT DISTINCT a.task_id FROM actions a WHERE a.state='UNKNOWN' "
                "AND a.capability NOT IN ('currency.quote','web.research','media.control') "
                "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.task_id=a.task_id "
                "AND e.kind='manual_review_acknowledged')"
            ).fetchall()
            for row in pending:
                if not any(result.task_id == row[0] for result in waiting):
                    print(
                        "Notepad actions are paused for an uncertain earlier outcome. "
                        f"Inspect Notepad, then /review {row[0]} manually-handled."
                    )
        if args.real or args.real_browser or args.real_media or args.real_apps:
            from jarvis.win_stop import StopHotkey

            stop = getattr(broker.desktop, "stop", browser_stop)
            if browser_provider:
                browser_provider.stop = stop
            with StopHotkey(stop):
                chat_loop(conversation, sys.stdin)
        else:
            chat_loop(conversation, sys.stdin)
    finally:
        if broker.media:
            broker.media.close()
        broker.store.close()
        provider.close()
