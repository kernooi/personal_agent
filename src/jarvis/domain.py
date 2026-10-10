"""Standard-library contracts; authority never comes from model output."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class State(StrEnum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    WAITING_INPUT = "WAITING_INPUT"
    ANSWERED = "ANSWERED"


TRANSITIONS = {
    State.RECEIVED: {State.PLANNING, State.CANCELLED, State.FAILED},
    State.PLANNING: {
        State.READY,
        State.WAITING_INPUT,
        State.FAILED,
        State.CANCELLED,
        State.ANSWERED,
    },
    State.READY: {State.RUNNING, State.CANCELLED, State.FAILED, State.NEEDS_REVIEW},
    State.RUNNING: {State.VERIFYING, State.NEEDS_REVIEW},
    State.VERIFYING: {State.SUCCEEDED, State.FAILED, State.CANCELLED, State.NEEDS_REVIEW},
    State.WAITING_INPUT: {State.CANCELLED, State.FAILED},
}


class Clock(Protocol):
    def now(self) -> float: ...


@dataclass(frozen=True)
class UserRequest:
    request_key: str
    session: str
    text: str
    source: str = "owner_cli"
    untrusted_context: str = ""


@dataclass(frozen=True)
class Scope:
    session: str
    app_id: str
    effect: str = "open"
    window_ref: str = ""


@dataclass(frozen=True)
class Task:
    task_id: str
    revision: int
    state: State
    scope: Scope
    deadline: float
    cancelled: bool


@dataclass(frozen=True)
class Proposal:
    capability: str
    app_id: str
    window_ref: str = ""


@dataclass(frozen=True)
class Decision:
    kind: str
    text: str = ""
    proposal: Proposal | None = None


@dataclass(frozen=True)
class PreparedAction:
    task_id: str
    revision: int
    capability: str
    app_id: str
    target_identity: str
    session: str
    effects: tuple[str, ...]
    adapter_version: str
    policy_version: str
    grant_id: str
    grant_version: int
    expires_at: float
    digest: str
    window_ref: str = ""


@dataclass(frozen=True)
class Grant:
    grant_id: str
    session: str
    apps: frozenset[str]
    expires_at: float
    version: int = 1
    revoked: bool = False
    effects: frozenset[str] = frozenset({"open"})
    issuer: str = "owner"


@dataclass(frozen=True)
class Approval:
    approval_id: str
    digest: str
    revision: int
    session: str
    expires_at: float
    approved: bool = True
    issuer: str = "owner"


@dataclass(frozen=True)
class Evidence:
    target_identity: str
    session: str
    observed_at: float
    running: bool | None
    source: str = "fake-state-observer-v1"
    authority: str = "tool_output"
    sensitivity: str = "synthetic"
    kind: str = "fake_api_state"
    postcondition: bool | None = None
    window_ref: str = ""
    observed_identity: str = ""


@dataclass(frozen=True)
class ExecutionAttempt:
    attempt_id: str
    action_id: str
    attempt_number: int
    admitted_at: float
    status: str = "ADMITTED"


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    state: State
    message: str
    simulated: bool = True
    decision_kind: str = ""
    display_message: str | None = None


class Desktop(Protocol):
    def execute(self, action: PreparedAction, admission_gate: Callable[[], None]) -> None: ...
    def observe(self, action: PreparedAction) -> Evidence: ...


class Denied(ValueError):
    """Safe normalized policy/validation rejection."""


class AdmissionRejected(Denied):
    """Raised only by the last broker gate, before the adapter mutates fake state."""


class Handoff(Denied):
    """A trusted adapter requires user handling before an effect can be admitted."""


class SimulatedCrash(BaseException):
    """Fault injection representing process loss, deliberately not a normal error."""
