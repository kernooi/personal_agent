"""Runnable, visibly simulated scenarios. No arbitrary natural-language executor."""

import argparse
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from jarvis.bootstrap import ManualClock, build, load_profile
from jarvis.domain import SimulatedCrash, UserRequest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JARVIS M0 — SIMULATED scripted provider/fake desktop"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="SIMULATED scenarios only")
    demo.add_argument(
        "--scenario",
        choices=["open-editor", "denied", "cancelled", "recovery-unknown"],
        required=True,
    )
    demo.add_argument("--profile", type=Path, default=Path("config/defaults.toml"))
    args = parser.parse_args()
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
