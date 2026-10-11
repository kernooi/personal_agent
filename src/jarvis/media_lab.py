"""Explicit attended real-Chrome/local-model lab. No fake/browser substitution."""

import json
import os
import platform
import threading
import time
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.browser_transport import BrowserWorkerProvider
from jarvis.chrome_identity import load_registration
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import State
from jarvis.media_data import MediaArguments, MediaConfig
from jarvis.media_evaluation import contract_hash, qualified
from jarvis.ollama import OllamaProvider
from jarvis.win_stop import StopHotkey


def run_lab(args):
    if args.report.exists():
        raise ValueError("Existing live result preserved; choose a new report path")
    profile = load_profile(args.profile, allow_ollama=True)
    clock = SystemClock()
    provider = OllamaProvider(clock)
    metadata = provider.inspect(profile)
    if not qualified(args.media_report, profile, metadata):
        provider.close()
        raise ValueError("A matching passed M4 local-model/fake-media report is required")
    identity = load_registration(args.browser_registration)
    stop = threading.Event()
    browser = BrowserWorkerProvider(
        clock, args.browser_registration, MediaConfig(enabled=True), stop
    )
    home = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    journal = home / f"m4-lab-{uuid4().hex}.sqlite"
    broker = build(
        journal,
        profile,
        clock,
        provider=provider,
        session=uuid4().hex,
        media_config=MediaConfig(enabled=True),
        browser_provider=browser,
    )
    broker.cancel_requested = stop.is_set
    chat = Conversation(broker)
    report = {
        "version": "m4-windows-lab-v1",
        "mode": "real local model -> Conversation -> broker -> installed Chrome",
        "profile": profile.model_dump(),
        "metadata": metadata,
        "contract_sha256": contract_hash(),
        "windows_version": platform.platform(),
        "chrome_version": identity.version,
        "chrome_sha256": identity.sha256,
        "automation_library": "Playwright",
        "automation_version": version("playwright"),
        "profile_classification": (
            "dedicated private JARVIS profile outside Git; normal Chrome excluded"
        ),
        "service": "youtube",
        "adapter_version": "media-adapter-v1",
        "records": [],
        "spotify": "NOT RUN / OAuth setup pending",
        "netflix": "NOT RUN / manual login pending",
        "passed": False,
    }

    def submit(text, expected_state=State.SUCCEEDED):
        started = time.monotonic()
        result = chat.submit(text)
        observed = broker.media.observation
        row = {
            "public_owner_request": text,
            "state": result.state,
            "error": broker.last_error,
            "latency_seconds": round(time.monotonic() - started, 3),
            "verified": result.state == expected_state,
            "observed_video_id": observed.item_id if observed else "",
            "observed_state": observed.state if observed else "unknown",
            "observed_public_title": observed.title if observed else "",
            "candidates": [
                {"id": r.item_id, "title": r.title, "creator": r.creator} for r in observed.results
            ]
            if observed
            else [],
            "desktop_calls": broker.desktop.execution_calls,
        }
        report["records"].append(row)
        print("JARVIS: " + conversational_text(result), flush=True)
        return row

    print(
        "ATTENDED M4 LAB: installed Chrome, dedicated JARVIS profile, YouTube only. "
        "No login/account edits. Ctrl+Alt+Shift+F10 stops new effects. "
        "Owned test Chrome context closes at the end; ordinary Chrome is excluded.",
        flush=True,
    )
    try:
        with StopHotkey(stop):
            first = submit("Search YouTube for Rick Astley Never Gonna Give You Up")
            if not first["verified"]:
                return report, 1
            candidates = broker.media.results
            selected = next(
                (i for i, r in enumerate(candidates, 1) if r.item_id == "dQw4w9WgXcQ"), None
            )
            if selected is None:
                report["limitation"] = (
                    "The pinned harmless public lab video was not in the bounded results; "
                    "no arbitrary selection."
                )
                return report, 1
            ordinal = ["first", "second", "third", "fourth", "fifth"][selected - 1]
            opened = submit(f"Open the {ordinal} result")
            if not opened["verified"] or opened["observed_video_id"] != "dQw4w9WgXcQ":
                return report, 1
            wait_until = time.monotonic() + 90
            snapshots = []
            while broker.media.observation.state in {"ad", "loading"}:
                if stop.is_set() or time.monotonic() >= wait_until:
                    report["limitation"] = "Ad/loading did not clear naturally within 90 seconds."
                    return report, 1
                print(
                    "WAITING_FOR_PLAYER: read-only wait; no ad skip or playback click.", flush=True
                )
                if stop.wait(5):
                    return report, 1
                observed = broker.media.call(
                    "snapshot",
                    MediaArguments(
                        service="youtube",
                        operation="current",
                        session_ref=broker.media.session_ref,
                        generation=broker.media.generation,
                    ),
                )
                snapshots.append({"state": observed.state, "video_id": observed.item_id})
                broker.media.observation = observed
                if observed.item_id != "dQw4w9WgXcQ":
                    report["limitation"] = "Player identity changed during read-only wait."
                    return report, 1
            report["read_only_player_wait"] = snapshots
            for text in (
                "Play it",
                "Pause the video",
                "Resume it",
                "What video is currently open on YouTube?",
            ):
                if not submit(text)["verified"]:
                    report["limitation"] = (
                        "Player state/restriction did not verify; no retry or bypass."
                    )
                    return report, 1
            if args.interactive:
                print(
                    "WAITING_FOR_GLOBAL_STOP: focus the dedicated test Chrome manually and press "
                    "Ctrl+Alt+Shift+F10. No new action will be sent while waiting (120 seconds).",
                    flush=True,
                )
                if not stop.wait(120):
                    report["stop"] = "NOT RUN / hotkey not observed"
                    return report, 1
                before = broker.media.execution_calls
                stopped = submit("Pause the video", State.CANCELLED)
                report["stop"] = {
                    "native_hotkey_observed": True,
                    "cancelled": stopped["verified"],
                    "new_admissions": broker.media.execution_calls - before,
                }
                if not stopped["verified"] or broker.media.execution_calls != before:
                    return report, 1
            else:
                report["stop"] = "NOT RUN / physical hotkey requires --interactive"
            report["passed"] = args.interactive
            return report, 0 if report["passed"] else 1
    except Exception as exc:
        report["error"] = getattr(exc, "code", "LIVE_BROWSER_LAB_FAILED")
        return report, 1
    finally:
        browser.close()
        broker.store.close()
        provider.close()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
