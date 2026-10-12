"""Start the documented attended combined session using this PC's private setup.

This helper does not provision software or change settings. The normal JARVIS
startup validates every configuration and qualification before enabling effects.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Attended real JARVIS chat with all configured capabilities"
    )
    parser.add_argument(
        "--print-command", action="store_true", help="Print arguments without starting chat"
    )
    args = parser.parse_args()
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
        "--media-report": root / "docs/evaluations/m4-spotify-admission-browser-v2-r2.json",
        "--windows-media-report": root / "docs/evaluations/m4-spotify-admission-desktop-v1-r2.json",
    }
    missing = [str(path) for path in pairs.values() if not path.is_file()]
    if missing:
        parser.error("Missing local setup or qualification files: " + ", ".join(missing))
    command = [sys.executable, "-m", "jarvis", "chat"]
    for option, path in pairs.items():
        command.extend([option, str(path)])
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
    if args.print_command:
        print(subprocess.list2cmdline(command))
        return 0
    print(
        "Starting attended real Windows control. You may keep using other apps; "
        "Ctrl+Alt+Shift+F10 stops new effects.",
        flush=True,
    )
    return subprocess.call(command, cwd=root, shell=False)


if __name__ == "__main__":
    raise SystemExit(main())
