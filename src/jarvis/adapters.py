"""In-memory desktop only; execution receipt is deliberately not verification."""

from collections.abc import Callable

from jarvis.domain import Clock, Evidence, PreparedAction, SimulatedCrash


class FakeDesktop:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.running: set[tuple[str, str]] = set()
        self.execution_calls = 0
        self.effect_count = 0
        self.observation_calls = 0
        self.apply_effect = True
        self.observation_available = True
        self.crash = "none"
        self.before_effect: Callable[[], None] = lambda: None
        self.after_effect: Callable[[], None] = lambda: None

    def execute(self, action: PreparedAction, admission_gate: Callable[[], None]) -> None:
        self.before_effect()
        admission_gate()  # Last check immediately before this bounded fake mutation.
        self.execution_calls += 1
        if self.crash == "before_effect":
            raise SimulatedCrash()
        target = (action.session, action.target_identity)
        if self.apply_effect and target not in self.running:
            self.running.add(target)
            self.effect_count += 1
        self.after_effect()
        if self.crash == "after_effect":
            raise SimulatedCrash()

    def observe(self, action: PreparedAction) -> Evidence:
        self.observation_calls += 1
        running = (
            (action.session, action.target_identity) in self.running
            if self.observation_available
            else None
        )
        return Evidence(action.target_identity, action.session, self.clock.now(), running)
