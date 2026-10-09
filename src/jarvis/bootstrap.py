"""Explicit composition root. No hidden clients and no real adapter paths."""

import time
import tomllib
from pathlib import Path

from jarvis.adapters import FakeDesktop
from jarvis.core import Broker
from jarvis.domain import Clock, Grant
from jarvis.models import FakeProvider, Profile
from jarvis.storage import Store
from jarvis.tools import Registry


class SystemClock:
    def now(self) -> float:
        return time.time()


class ManualClock:
    def __init__(self, value: float = 1000):
        self.value = value

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Clock cannot go backwards")
        self.value += seconds


def load_profile(path: Path) -> Profile:
    with path.open("rb") as stream:
        return Profile.model_validate(tomllib.load(stream), strict=True)


def build(path: Path, profile: Profile, clock: Clock | None = None) -> Broker:
    clock = clock or SystemClock()
    store = Store(path, clock)
    provider = FakeProvider(clock)
    desktop = FakeDesktop(clock)
    grant = Grant(
        "fixture-owner-grant", "demo-session", frozenset({"text_editor"}), clock.now() + 60
    )
    return Broker(store, clock, provider, desktop, Registry(), profile, grant)
