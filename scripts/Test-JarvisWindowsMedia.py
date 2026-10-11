"""Explicit attended Spotify lab: local model -> broker -> Windows session."""

import argparse
import json
import os
import threading
import time
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.domain import State, UserRequest
from jarvis.media_data import MediaConfig
from jarvis.media_evaluation import qualified
from jarvis.ollama import OllamaProvider
from jarvis.win_stop import StopHotkey
from jarvis.windows_media import WindowsMediaProvider


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing report preserved; use a new filename")
    clock, stop = SystemClock(), threading.Event()
    profile = load_profile(args.profile, allow_ollama=True)
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    if not qualified(args.model_report, profile, metadata, windows_media=True):
        parser.error("Matching passed Windows media model qualification required")
    config = MediaConfig(enabled=True, youtube=False, spotify=True, spotify_backend="windows")
    native = WindowsMediaProvider(clock, config, stop)
    rows = []
    passed = False
    try:
        directory = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
        directory.mkdir(parents=True, exist_ok=True)
        broker = build(
            directory / ("spotify-lab-" + uuid4().hex + ".sqlite"),
            profile,
            clock,
            provider=model,
            media_config=config,
            browser_provider=native,
        )
        broker.cancel_requested = stop.is_set
        try:
            with StopHotkey(stop):
                for text in [
                    "What is playing on Spotify?",
                    "Pause Spotify",
                    "Resume Spotify",
                    "Next track on Spotify",
                    "Previous track on Spotify",
                ]:
                    started = time.monotonic()
                    result = broker.converse(
                        UserRequest(str(len(rows)), broker.grant.session, text)
                    )
                    observed = broker.media.observation
                    row = {
                        "operation": text,
                        "state": result.state,
                        "playback_state": observed.state if observed else None,
                        "item_fingerprint": observed.item_id if observed else None,
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "error": broker.last_error,
                    }
                    rows.append(row)
                    print(json.dumps(row), flush=True)
                    if result.state != State.SUCCEEDED:
                        break
                if len(rows) == 5 and all(r["state"] == State.SUCCEEDED for r in rows):
                    print(
                        "WAITING_FOR_PHYSICAL_STOP: focus Spotify and press Ctrl+Alt+Shift+F10",
                        flush=True,
                    )
                    stopped = stop.wait(120)
                    admissions = broker.media.execution_calls
                    result = broker.converse(
                        UserRequest("stopped", broker.grant.session, "Pause Spotify")
                    )
                    rows.append(
                        {
                            "operation": "pause-after-global-stop",
                            "state": result.state,
                            "physical_stop_observed": stopped,
                            "zero_worker_delivery": stopped
                            and broker.media.execution_calls == admissions,
                        }
                    )
                    passed = (
                        stopped
                        and result.state == State.CANCELLED
                        and broker.media.execution_calls == admissions
                    )
        finally:
            native.close()
            broker.store.close()
            model.close()
    except Exception as exc:
        rows.append({"error": getattr(exc, "code", type(exc).__name__)})
    report = {
        "mode": "attended_local_model_windows_spotify",
        "passed": passed,
        "model_report": str(args.model_report),
        "records": rows,
        "audible_sound_verified": False,
        "desktop_input_calls": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({"passed": passed, "report": str(args.report)}), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
