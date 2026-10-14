"""Explicit attended real YouTube workflow regression; dedicated context only."""

import argparse
import json
import os
import re
import threading
import time
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.browser_transport import BrowserWorkerProvider
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import State
from jarvis.media_data import MediaArguments, MediaConfig
from jarvis.media_evaluation import qualified
from jarvis.ollama import OllamaProvider
from jarvis.win_stop import StopHotkey


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--media-report", type=Path, required=True)
    parser.add_argument("--language-report", type=Path)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved")
    clock = SystemClock()
    profile = load_profile(args.profile, allow_ollama=True)
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    if not qualified(args.media_report, profile, metadata):
        parser.error("Current passed actual-local-model media gate required")
    if args.language_report:
        from jarvis.language_evaluation import qualified as language_gate

        if not language_gate(args.language_report, profile, metadata):
            model.close()
            parser.error("Matching passed wording gate required")
    stop = threading.Event()
    config = MediaConfig(enabled=True)
    browser = BrowserWorkerProvider(clock, args.registration, config, stop)
    journal = (
        Path(os.environ["LOCALAPPDATA"])
        / "Jarvis"
        / ("youtube-flow-lab-" + uuid4().hex + ".sqlite")
    )
    broker = build(
        journal, profile, clock, provider=model, media_config=config, browser_provider=browser
    )
    broker.cancel_requested = stop.is_set
    broker.language_qualified = args.language_report is not None
    chat = Conversation(broker)
    rows, passed = [], False
    native_error = [None]
    original_call = browser.call

    def observed_call(request, cancel):
        try:
            return original_call(request, cancel)
        except Exception as error:
            code = getattr(error, "code", str(error))
            native_error[0] = (
                code if re.fullmatch(r"[A-Z0-9_]{1,80}", code) else type(error).__name__
            )
            raise

    browser.call = observed_call

    def submit(text):
        result = chat.submit(text)
        observed = broker.media.observation
        row = {
            "state": result.state,
            "player_state": observed.state if observed else None,
            "video_id": observed.item_id if observed else None,
            "error": broker.last_error,
            "native_error": native_error[0],
        }
        rows.append(row)
        print("JARVIS: " + conversational_text(result), flush=True)
        if result.state != State.SUCCEEDED:
            raise ValueError("Unverified result; no retry")
        return observed

    try:
        with StopHotkey(stop):
            observed = submit(
                "Could you put Never Gonna Give You Up by Rick Astley on YouTube for me?"
                if args.language_report
                else "Search YouTube and play Rick Astley Never Gonna Give You Up"
            )
            if observed.state == "results":
                choices = [
                    i for i, r in enumerate(broker.media.results, 1) if r.item_id == "dQw4w9WgXcQ"
                ]
                if len(choices) != 1:
                    raise ValueError("Pinned public lab video absent or ambiguous")
                observed = submit("Open the " + str(choices[0]) + " result")
            if observed.item_id != "dQw4w9WgXcQ":
                raise ValueError("Lab video identity differs; no further effect")
            until = time.monotonic() + 90
            while observed.state in {"ad", "loading"} and time.monotonic() < until:
                if stop.wait(2):
                    raise ValueError("Stopped during read-only wait")
                observed = broker.media.call(
                    "snapshot",
                    MediaArguments(
                        service="youtube",
                        operation="current",
                        session_ref=broker.media.session_ref,
                        generation=broker.media.generation,
                    ),
                )
                broker.media.observation = observed
                broker.media.update_generation(observed)
                if observed.item_id != "dQw4w9WgXcQ":
                    raise ValueError("Player changed; no replay")
            if observed.state in {"ad", "loading"}:
                raise ValueError("Ad/loading did not clear naturally")
            observed = submit("What video is currently open on YouTube?")
            if observed.item_id != "dQw4w9WgXcQ":
                raise ValueError("Read-only reobservation found a different video")
            if observed.state != "playing":
                observed = submit("Play it")
            if observed.state != "playing":
                raise ValueError("Playback unverified")
            if (
                submit("Pause it for me" if args.language_report else "Pause the video").state
                != "paused"
            ):
                raise ValueError("Pause unverified")
            if (
                submit("Continue YouTube for me" if args.language_report else "Resume it").state
                != "playing"
            ):
                raise ValueError("Resume unverified")
            before = broker.media.execution_calls
            stop.set()
            result = chat.submit("Pause the video")
            blocked = result.state == State.CANCELLED and broker.media.execution_calls == before
            rows.append(
                {
                    "stop_blocked": blocked,
                    "zero_new_admissions": broker.media.execution_calls == before,
                }
            )
            passed = blocked
    except Exception as exc:
        rows.append({"error_type": type(exc).__name__, "passed": False})
        print("Lab paused; failed evidence retained. No replay.", flush=True)
    finally:
        browser.close()
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "version": "youtube-flow-native-v1",
                    "passed": passed,
                    "mode": "real local model -> Conversation -> broker -> dedicated Chrome",
                    "model_report": args.media_report.name,
                    "language_report": args.language_report.name if args.language_report else None,
                    "metadata": metadata,
                    "records": rows,
                    "journal_retained": True,
                },
                stream,
                indent=2,
            )
            stream.write("\n")
        broker.store.close()
        model.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
