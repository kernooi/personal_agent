"""Explicit composition root. No hidden clients and no real adapter paths."""

import time
import tomllib
from pathlib import Path

from jarvis.adapters import FakeDesktop
from jarvis.core import Broker
from jarvis.domain import Clock, Grant
from jarvis.models import FakeProvider, OllamaProfile, Profile, Provider, TextProfile
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


def load_profile(path: Path, *, allow_ollama: bool = False) -> TextProfile:
    # Windows PowerShell's UTF8 encoding may include a BOM.
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    if allow_ollama and data.get("provider") == "ollama":
        return OllamaProfile.model_validate(data, strict=True)
    return Profile.model_validate(data, strict=True)


def build(
    path: Path,
    profile: TextProfile,
    clock: Clock | None = None,
    provider: Provider | None = None,
    session: str = "demo-session",
) -> Broker:
    clock = clock or SystemClock()
    store = Store(path, clock)
    if provider is None:
        if isinstance(profile, OllamaProfile):
            from jarvis.ollama import OllamaProvider

            provider = OllamaProvider(clock)
        else:
            provider = FakeProvider(clock)
    desktop = FakeDesktop(clock)
    grant = Grant(
        "fixture-owner-grant",
        session,
        frozenset({"text_editor"}),
        clock.now() + profile.task_seconds + 60,
    )
    return Broker(store, clock, provider, desktop, Registry(), profile, grant)
