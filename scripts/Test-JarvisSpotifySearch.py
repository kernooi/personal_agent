"""Explicit attended native Spotify search/song/playlist regression; no account setup."""

import argparse
import json
import os
import threading
from pathlib import Path
from uuid import uuid4

from jarvis.bootstrap import SystemClock, build, load_profile
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import State
from jarvis.media_data import MediaConfig
from jarvis.media_evaluation import qualified
from jarvis.ollama import OllamaProvider
from jarvis.spotify_desktop import SpotifyDesktopProvider
from jarvis.win_stop import StopHotkey


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--language-report", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved")
    clock = SystemClock()
    profile = load_profile(args.profile, allow_ollama=True)
    model = OllamaProvider(clock)
    metadata = model.inspect(profile)
    if not qualified(args.model_report, profile, metadata, spotify_desktop=True):
        model.close()
        parser.error("Current passed actual-local-model Spotify desktop gate required")
    if args.language_report:
        from jarvis.language_evaluation import qualified as language_gate

        if not language_gate(args.language_report, profile, metadata):
            model.close()
            parser.error("Matching passed wording gate required")
    stop = threading.Event()
    config = MediaConfig(
        enabled=True, spotify=True, spotify_backend="desktop", operation_seconds=30
    )
    native = SpotifyDesktopProvider(clock, config, stop)
    journal = (
        Path(os.environ["LOCALAPPDATA"])
        / "Jarvis"
        / ("spotify-search-lab-" + uuid4().hex + ".sqlite")
    )
    broker = build(
        journal, profile, clock, provider=model, media_config=config, browser_provider=native
    )
    broker.cancel_requested = stop.is_set
    broker.language_qualified = args.language_report is not None
    chat = Conversation(broker)
    rows, passed = [], False

    def submit(text, operation):
        result = chat.submit(text)
        observed = broker.media.observation
        rows.append(
            {
                "operation": operation,
                "state": result.state,
                "observed_state": observed.state if observed else None,
                "content_id": observed.item_id if observed else None,
                "result_count": len(observed.results) if observed else None,
                "error": broker.last_error,
            }
        )
        print("JARVIS: " + conversational_text(result), flush=True)
        if result.state != State.SUCCEEDED:
            raise ValueError("Unverified result; no automatic retry")
        return observed

    def choose_if_needed(observed, title, creator):
        if observed.state != "results":
            return observed
        matches = [
            i
            for i, item in enumerate(broker.media.results, 1)
            if item.title.casefold() == title.casefold()
            and item.creator.casefold() == creator.casefold()
        ]
        if not matches:
            raise ValueError("Expected public lab result not observed; no guessed selection")
        # Attended lab scope permits the first exact title/creator edition.
        return submit("Open the " + str(matches[0]) + " result", "select-and-play")

    try:
        with StopHotkey(stop):
            observed = submit(
                "Could you put Never Gonna Give You Up by Rick Astley on for me using Spotify?"
                if args.language_report
                else "Play Never Gonna Give You Up by Rick Astley on Spotify",
                "song-request",
            )
            observed = choose_if_needed(observed, "Never Gonna Give You Up", "Rick Astley")
            if (
                observed.state != "playing"
                or observed.title != "Never Gonna Give You Up"
                or observed.creator != "Rick Astley"
            ):
                raise ValueError("Song playback unverified")
            submit("Stop Spotify for me" if args.language_report else "Pause Spotify", "pause-song")
            submit(
                "Continue Spotify for me" if args.language_report else "Resume Spotify",
                "resume-song",
            )
            observed = submit(
                "Could you put the playlist Deep Focus by Spotify on for me using Spotify?"
                if args.language_report
                else "Play playlist Deep Focus by Spotify on Spotify",
                "playlist-request",
            )
            observed = choose_if_needed(observed, "Deep Focus", "Spotify")
            if (
                observed.state != "playing"
                or observed.title != "Deep Focus"
                or observed.creator != "Spotify"
            ):
                raise ValueError("Playlist context/playback unverified")
            submit("Pause Spotify", "pause-playlist")
            before = broker.media.execution_calls
            stop.set()
            result = chat.submit("Resume Spotify")
            blocked = result.state == State.CANCELLED
            zero = broker.media.execution_calls == before
            if not blocked or not zero:
                raise ValueError("Stop boundary failed")
            passed = True
            rows.append({"operation": "stop", "blocked": blocked, "zero_new_admissions": zero})
    except (ValueError, RuntimeError, OSError):
        print(
            "Lab stopped; failed evidence retained. Inspect any uncertain outcome manually.",
            flush=True,
        )
    finally:
        broker.media.close()  # Only the owned Python worker; never closes Spotify.
        broker.store.close()
        model.close()
        report = {
            "version": "spotify-desktop-windows-v1",
            "passed": passed,
            "records": rows,
            "audio_audibility_verified": False,
            "ordinary_apps_controlled": False,
            "spotify_left_open": True,
            "language_report": args.language_report.name if args.language_report else None,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({"passed": passed, "records": len(rows)}), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
