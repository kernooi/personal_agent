"""Strict decisions, profiles, shared provider contracts, and scripted provider."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from jarvis.domain import Clock, Decision, Proposal


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OpenArguments(StrictRecord):
    app_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")


class OpenAction(StrictRecord):
    capability: Literal["apps.open"]
    arguments: OpenArguments


class Say(StrictRecord):
    kind: Literal["say"]
    text: str = Field(min_length=1, max_length=2000)


class Clarify(StrictRecord):
    kind: Literal["clarify"]
    question: str = Field(min_length=1, max_length=1000)


class Unsupported(StrictRecord):
    kind: Literal["unsupported"]
    message: str = Field(min_length=1, max_length=1000)


class Propose(StrictRecord):
    kind: Literal["propose_action"]
    action: OpenAction


BOUNDARY = TypeAdapter(
    Annotated[Say | Clarify | Unsupported | Propose, Field(discriminator="kind")]
)
MAX_REPLY_BYTES = 32768


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def parse_decision(raw: bytes) -> Decision:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REPLY_BYTES:
        raise ValueError("Empty, non-byte, or oversized reply")
    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        parsed = BOUNDARY.validate_python(payload, strict=True)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid decision") from exc
    if isinstance(parsed, Propose):
        return Decision(parsed.kind, proposal=Proposal("apps.open", parsed.action.arguments.app_id))
    text = getattr(parsed, "text", getattr(parsed, "question", getattr(parsed, "message", "")))
    return Decision(parsed.kind, text=text)


class BaseProfile(StrictRecord):
    schema_version: Literal[1] = 1
    profile_name: str
    execution_mode: Literal["simulation"] = "simulation"
    model_identity: str
    role: Literal["primary_text"] = "primary_text"
    prompt_version: Literal["planner-v1", "planner-v2", "planner-v3", "planner-v4"] = "planner-v1"
    decision_version: Literal["decision-v1"] = "decision-v1"
    context_bytes: int = Field(default=16384, ge=1024, le=65536)
    max_output_bytes: int = Field(default=32768, ge=1, le=32768)
    task_seconds: int = Field(default=30, ge=1, le=120)


class Profile(BaseProfile):
    """The M0 fake-profile boundary remains deliberately separate."""

    provider: Literal["fake"] = "fake"
    network_mode: Literal["none"] = "none"
    reply: str = Field(max_length=32768)


class ProviderOptions(StrictRecord):
    think: bool | Literal["low", "medium", "high"] | None = None
    keep_alive: str = Field(default="2m", pattern=r"^(?:0|[1-9][0-9]?[sm])$")


class OllamaProfile(BaseProfile):
    prompt_version: Literal["planner-v1", "planner-v2", "planner-v3", "planner-v4"] = "planner-v4"
    provider: Literal["ollama"]
    network_mode: Literal["local_model_only"]
    base_url: Literal["http://127.0.0.1:11434"] = "http://127.0.0.1:11434"
    model_identity: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._/-]*(?::[a-z0-9][a-z0-9._-]*)?$"
    )
    response_mode: Literal["json_schema"] = "json_schema"
    context_tokens: int = Field(default=4096, ge=1024, le=16384)
    max_output_tokens: int = Field(default=512, ge=128, le=1024)
    safety_tokens: int = Field(default=256, ge=128, le=1024)
    connect_timeout_seconds: float = Field(default=5.0, gt=0, le=10)
    read_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
    max_envelope_bytes: int = Field(default=131072, ge=1024, le=262144)
    temperature: float = Field(default=0.0, ge=0, le=1)
    cloud_disabled_verified: bool = False
    cloud_disabled_evidence: str = Field(default="", max_length=512)
    provider_options: ProviderOptions = Field(default_factory=ProviderOptions)

    @model_validator(mode="after")
    def safe_profile(self):
        if "cloud" in self.model_identity.split(":")[-1]:
            raise ValueError("Cloud model identities are disabled")
        if self.max_output_tokens + self.safety_tokens >= self.context_tokens:
            raise ValueError("Output and safety reservations exhaust context")
        if self.cloud_disabled_verified and not self.cloud_disabled_evidence.strip():
            raise ValueError("User-verified local-only setup needs an evidence note")
        return self


TextProfile = Profile | OllamaProfile


class ProviderError(ValueError):
    """Normalized errors contain categories, never server bodies or prompts."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Message:
    role: str
    text: str


@dataclass(frozen=True)
class ModelRequest:
    request_id: str
    task_id: str
    revision: int
    profile: TextProfile
    schema: dict[str, Any]
    deadline: float
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class ModelReply:
    request_id: str
    task_id: str
    revision: int
    raw: bytes
    identity: str
    runtime_version: str | None = None
    tokens: int | None = None
    latency_seconds: float | None = None
    runtime_load_seconds: float | None = None


class Provider(Protocol):
    def inspect(self, profile: TextProfile) -> dict[str, Any]: ...
    def generate(self, request: ModelRequest, cancel: Callable[[], bool]) -> ModelReply: ...
    def close(self) -> None: ...


class FakeProvider:
    """Scripted output only. Hooks are deterministic test scheduling boundaries."""

    def __init__(self, clock: Clock, before_reply: Callable[[], None] = lambda: None):
        self.clock = clock
        self.before_reply = before_reply
        self.calls = 0
        self.closed = False

    def inspect(self, profile: Profile) -> dict[str, Any]:
        return {
            "available": True,
            "identity": profile.model_identity,
            "text_generation": "supported",
            "schema_constrained_output": "unsupported",
            "context_capacity": "unknown",
        }

    def generate(self, request: ModelRequest, cancel: Callable[[], bool]) -> ModelReply:
        if self.closed or cancel() or self.clock.now() >= request.deadline:
            raise ValueError("Provider unavailable or request stopped")
        self.calls += 1
        self.before_reply()
        # Deliberately permit a late reply: the broker must independently reject it.
        return ModelReply(
            request.request_id,
            request.task_id,
            request.revision,
            request.profile.reply.encode(),
            request.profile.model_identity,
        )

    def close(self) -> None:
        self.closed = True
