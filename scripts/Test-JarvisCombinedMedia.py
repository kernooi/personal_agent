"""Attended media regression using the exact shared GUI/terminal composition."""

import argparse
import json
import os
import runpy
import sys
import time
from pathlib import Path
from uuid import uuid4

from jarvis import cli
from jarvis.conversation import conversational_text
from jarvis.domain import State
from jarvis.media_data import MediaArguments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attended", action="store_true", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manual-ad", action="store_true")
    for name in (
        "model-report",
        "conversation-report",
        "applications-report",
        "language-report",
        "media-report",
        "windows-media-report",
    ):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Existing evidence preserved; choose a new report")
    launcher = runpy.run_path(str(Path(__file__).with_name("Chat-JarvisAll.py")))
    command = launcher["chat_command"](real=True)
    for name in (
        "model-report",
        "conversation-report",
        "applications-report",
        "language-report",
        "media-report",
        "windows-media-report",
    ):
        path = getattr(args, name.replace("-", "_"))
        if path:
            command[command.index("--" + name) + 1] = str(path)
    journal = (
        Path(os.environ["LOCALAPPDATA"])
        / "Jarvis"
        / ("combined-media-lab-" + uuid4().hex + ".sqlite")
    )
    report = {
        "version": "combined-media-windows-v1",
        "mode": "shared GUI/terminal CLI -> actual local model -> broker -> native media",
        "passed": False,
        "journal": journal.name,
        "records": [],
        "audible_sound_verified": False,
        "ordinary_chrome_excluded": True,
        "spotify_left_open": True,
    }
    ad_signal = journal.with_suffix(".ad-ready")
    original_build = cli.build
    original_loop = cli.chat_loop if hasattr(cli, "chat_loop") else None
    from jarvis import terminal

    original_terminal_loop = terminal.chat_loop
    original_argv = sys.argv

    def isolated_build(path, *values, **settings):
        return original_build(journal, *values, **settings)

    def lab_loop(chat, stream):
        broker, media = chat.broker, chat.broker.media
        # terminal.chat_loop normally supplies this callback. The lab replaces
        # that interactive loop, so preserve its global-stop cancellation wiring.
        broker.cancel_requested = broker.desktop.stop.is_set
        report["qualification"] = {
            name: Path(command[command.index("--" + name) + 1]).name
            for name in (
                "model-report",
                "conversation-report",
                "applications-report",
                "language-report",
                "media-report",
                "windows-media-report",
            )
        }

        def submit(text, label):
            started = time.monotonic()
            result = chat.submit(text)
            observed = media.observation
            report["records"].append(
                {
                    "check": label,
                    "task_id": result.task_id,
                    "state": result.state,
                    "service": observed.service if observed else None,
                    "observed_state": observed.state if observed else None,
                    "generation": observed.generation if observed else None,
                    "error": broker.last_error,
                    "latency_seconds": round(time.monotonic() - started, 3),
                }
            )
            print("JARVIS: " + conversational_text(result), flush=True)
            if result.state != State.SUCCEEDED:
                raise ValueError("Unverified result; no retry")
            return observed

        def song():
            observed = submit(
                "Play Never Gonna Give You Up by Rick Astley on Spotify", "spotify-song"
            )
            if observed.state == "results":
                matches = [
                    index
                    for index, item in enumerate(media.results, 1)
                    if item.title.casefold() == "never gonna give you up"
                    and item.creator.casefold() == "rick astley"
                ]
                if not matches:
                    raise ValueError("Approved song not in retrieved results")
                observed = submit("Open the " + str(matches[0]) + " result", "spotify-select")
            if (
                observed.state != "playing"
                or observed.title.casefold() != "never gonna give you up"
                or observed.creator.casefold() != "rick astley"
            ):
                raise ValueError("Approved song/context not verified")

        song()
        if submit("Pause Spotify", "spotify-pause").state != "paused":
            raise ValueError("Pause not verified")
        if submit("Resume Spotify", "spotify-resume").state != "playing":
            raise ValueError("Resume not verified")
        submit("Pause Spotify", "spotify-before-youtube")
        observed = submit("Play Never Gonna Give You Up by Rick Astley on YouTube", "youtube-song")
        if observed.state == "results":
            matches = [
                index
                for index, item in enumerate(media.results, 1)
                if item.item_id == "dQw4w9WgXcQ"
            ]
            if len(matches) != 1:
                raise ValueError("Approved official video absent or ambiguous")
            observed = submit("Open the " + str(matches[0]) + " result", "youtube-select")
        if observed.item_id != "dQw4w9WgXcQ":
            raise ValueError("Approved video identity differs")
        until = time.monotonic() + 90
        if observed.state in {"ad", "loading"} and args.manual_ad:
            print("WAITING_FOR_OPERATOR_AD_HANDOFF: " + str(ad_signal), flush=True)
            until = time.monotonic() + 180
            while not ad_signal.exists():
                if broker.desktop.stop.wait(0.1) or time.monotonic() >= until:
                    report["limitation"] = "OPERATOR_HANDOFF_NOT_COMPLETED"
                    raise ValueError("Operator handoff not completed")
            ad_signal.unlink()
            observed = submit("What video is currently open on YouTube?", "operator-reobserve")
            report["operator_ad_handoff"] = True
            if observed.item_id != "dQw4w9WgXcQ":
                report["limitation"] = "VIDEO_CHANGED_AFTER_HANDOFF"
                raise ValueError("Video changed after handoff")
            until = time.monotonic() + 90
        if observed.state in {"ad", "loading"}:
            print(
                "Waiting for the advertisement/loading to finish naturally. "
                "Please leave the dedicated test Chrome window untouched.",
                flush=True,
            )
        while observed.state in {"ad", "loading"} and time.monotonic() < until:
            if broker.desktop.stop.wait(2):
                raise ValueError("Stopped during observation")
            observed = media.call(
                "snapshot",
                MediaArguments(
                    service="youtube",
                    operation="current",
                    session_ref=media.session_ref,
                    generation=media.generation,
                ),
            )
            media.observation = observed
            media.update_generation(observed)
            if observed.item_id != "dQw4w9WgXcQ":
                raise ValueError("Video changed while waiting")
        if observed.state not in {"playing", "paused"}:
            report["limitation"] = "AD_OR_LOADING_DID_NOT_FINISH_90_SECONDS"
            raise ValueError("Ad/loading did not finish naturally")
        # No extra current-state command to mask stale-generation/takeover bugs.
        if observed.state != "playing":
            observed = submit("Play it on YouTube", "youtube-play")
        if submit("Pause YouTube", "youtube-pause").state != "paused":
            raise ValueError("YouTube pause not verified")
        if submit("Resume YouTube", "youtube-resume").state != "playing":
            raise ValueError("YouTube resume not verified")
        song()  # A second fresh search after switching back to the native worker.
        submit("Pause Spotify", "spotify-final-pause")
        if submit("Pause YouTube", "youtube-after-spotify").state != "paused":
            raise ValueError("Returning to selected YouTube video failed")
        before = media.execution_calls
        broker.desktop.stop.set()
        result = chat.submit("Resume Spotify")
        blocked = result.state == State.CANCELLED and media.execution_calls == before
        report["records"].append(
            {
                "check": "stop",
                "blocked": blocked,
                "zero_new_admissions": media.execution_calls == before,
            }
        )
        report["passed"] = blocked

    try:
        cli.build = isolated_build
        terminal.chat_loop = lab_loop
        sys.argv = ["jarvis", *command[3:]]
        cli.main()
    except (Exception, SystemExit) as error:
        report["error_type"] = type(error).__name__
        print("Combined test stopped; evidence retained. No automatic replay.", flush=True)
    finally:
        cli.build = original_build
        if original_loop is not None:
            cli.chat_loop = original_loop
        terminal.chat_loop = original_terminal_loop
        sys.argv = original_argv
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(
            json.dumps({"passed": report["passed"], "records": len(report["records"])}), flush=True
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
