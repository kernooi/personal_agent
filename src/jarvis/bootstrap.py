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
    *,
    real: bool = False,
    registration: Path | None = None,
    attended: bool = False,
    public_config=None,
    currency_provider=None,
    cache_path=None,
    web_config=None,
    search_provider=None,
    page_fetcher=None,
) -> Broker:
    if real and (
        not attended or registration is None or profile.decision_version != "decision-m2-v1"
    ):
        raise ValueError("Real mode requires M2 profile, registration and attended-session consent")
    if profile.decision_version == "decision-m2-v1" and profile.prompt_version not in {
        "planner-m2-v1",
        "planner-m2-v2",
        "planner-m2-v3",
        "planner-m2-v4",
        "planner-m2-v5",
        "planner-m2-v6",
        "planner-m2-v7",
        "planner-m2-v8",
        "planner-m2-v9",
        "planner-m2-v10",
    }:
        raise ValueError("M2 schema requires its versioned prompt")
    clock = clock or SystemClock()
    if provider is None:
        if isinstance(profile, OllamaProfile):
            from jarvis.ollama import OllamaProvider

            provider = OllamaProvider(clock)
        else:
            provider = FakeProvider(clock)
    if profile.decision_version == "decision-m2-v1":
        import os
        import threading

        from jarvis.notepad import (
            DesktopLease,
            NotepadDesktop,
            NotepadRegistry,
            WorkerTransport,
            load_registration,
        )

        if real:
            stop = threading.Event()
            transport = WorkerTransport(load_registration(registration), stop)
            lease = DesktopLease(Path(os.environ["LOCALAPPDATA"]) / "Jarvis/desktop-lease.lock")
        else:
            from jarvis.notepad_fake import FakeNotepadTransport

            transport = FakeNotepadTransport()
            lease = None
        desktop = NotepadDesktop(clock, transport, real=real, lease=lease)
        if real:
            desktop.stop = stop
        registry = NotepadRegistry(
            desktop,
            conversational=profile.prompt_version
            in {
                "planner-m2-v5",
                "planner-m2-v6",
                "planner-m2-v7",
                "planner-m2-v8",
                "planner-m2-v9",
                "planner-m2-v10",
            },
        )
    else:
        desktop = FakeDesktop(clock)
        registry = Registry()
    if public_config is not None:
        from jarvis.currency_tools import CurrencyAdapter, CurrencyRegistry

        registry = CurrencyRegistry(
            registry, CurrencyAdapter(clock, public_config, currency_provider, cache_path)
        )
    store = Store(path, clock)
    if getattr(registry, "m2", False):
        registry.extended = profile.prompt_version == "planner-m2-v10"
        if public_config is not None and hasattr(registry.underlying, "m2"):
            registry.underlying.extended = registry.extended
    if web_config is not None:
        from jarvis.web_tools import WebAdapter, WebRegistry

        registry = WebRegistry(
            registry, WebAdapter(clock, web_config, search_provider, page_fetcher)
        )
    grant = Grant(
        "fixture-owner-grant",
        session,
        frozenset({"notepad"})
        if profile.decision_version == "decision-m2-v1"
        else frozenset({"text_editor"}),
        clock.now() + profile.task_seconds + 60,
        effects=frozenset({"open", "focus", "close"})
        if profile.decision_version == "decision-m2-v1"
        else frozenset({"open"}),
    )
    if public_config is not None:
        from dataclasses import replace

        grant = replace(
            grant,
            apps=grant.apps | {"currency"},
            effects=grant.effects | {"public_read", "local_calculate", "read_evidence"},
        )
    if web_config is not None:
        from dataclasses import replace

        grant = replace(
            grant,
            apps=grant.apps | {"web"},
            effects=grant.effects | {"web_public_read", "web_evidence"},
        )
    if real:
        unresolved = store.db.execute(
            "SELECT a.task_id FROM actions a WHERE a.state='UNKNOWN' "
            "AND a.capability NOT IN ('currency.quote','web.research') AND NOT EXISTS "
            "(SELECT 1 FROM events e WHERE e.task_id=a.task_id "
            "AND e.kind='manual_review_acknowledged')"
        ).fetchone()
        desktop.blocked_unknown = unresolved is not None
        desktop.review_task_id = unresolved[0] if unresolved else ""
    return Broker(store, clock, provider, desktop, registry, profile, grant)
