"""Start the documented attended combined session using this PC's private setup.

This helper does not provision software or change settings. The normal JARVIS
startup validates every configuration and qualification before enabling effects.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def chat_command(*, real=True):
    """Share this PC's existing configuration with terminal and desktop chat."""
    root = Path(__file__).resolve().parents[1]
    private = Path(os.environ["LOCALAPPDATA"]) / "Jarvis"
    pairs = {
        "--profile": private / "profiles/notepad-m2-concurrent-v1.toml",
        "--registration": private / "notepad-registration.json",
        "--model-report": root / "docs/evaluations/m2-spotify-admission-model-v1-r1.json",
        "--conversation-report": root
        / "docs/evaluations/m2-spotify-admission-conversation-v1-r1.json",
        "--applications-config": private / "applications.toml",
        "--applications-report": root
        / "docs/evaluations/applications-spotify-admission-v4-r1.json",
        "--public-data-config": private / "public-data.toml",
        "--web-config": private / "web.toml",
        "--media-config": private / "media-all-spotify-desktop-v1.toml",
        "--browser-registration": private / "chrome-registration.json",
        "--media-report": root / "docs/evaluations/m4-revert-compat-browser-v1-r1.json",
        "--windows-media-report": root / "docs/evaluations/m4-revert-compat-desktop-v1-r1.json",
    }
    if not real:
        for option in (
            "--registration",
            "--model-report",
            "--conversation-report",
            "--applications-report",
            "--browser-registration",
            "--media-report",
            "--windows-media-report",
        ):
            pairs.pop(option)
    missing = [str(path) for path in pairs.values() if not path.is_file()]
    if missing:
        raise ValueError("Missing local setup or qualification files: " + ", ".join(missing))
    command = [sys.executable, "-m", "jarvis", "chat"]
    for option, path in pairs.items():
        command.extend([option, str(path)])
    if real:
        command.extend(
            [
                "--real",
                "--attended",
                "--real-apps",
                "--apps-attended",
                "--real-browser",
                "--browser-attended",
                "--real-media",
                "--media-attended",
            ]
        )
    return command


def main():
    parser = argparse.ArgumentParser(
        description="Attended real JARVIS chat with all configured capabilities"
    )
    parser.add_argument(
        "--print-command", action="store_true", help="Print arguments without starting chat"
    )
    args = parser.parse_args()
    try:
        command = chat_command()
    except ValueError as exc:
        parser.error(str(exc))
    if args.print_command:
        print(subprocess.list2cmdline(command))
        return 0
    print(
        "Starting attended real Windows control. You may keep using other apps; "
        "Ctrl+Alt+Shift+F10 stops new effects.",
        flush=True,
    )
    return subprocess.call(command, cwd=Path(__file__).resolve().parents[1], shell=False)


if __name__ == "__main__":
    raise SystemExit(main())
