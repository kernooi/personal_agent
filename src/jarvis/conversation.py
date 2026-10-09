"""Session-only text history; model text never authorizes a target."""

from dataclasses import replace
from uuid import uuid4

from jarvis.core import Broker
from jarvis.domain import State, TaskResult, UserRequest
from jarvis.models import Message


def conversational_text(result: TaskResult) -> str:
    """Keep broker diagnostics out of non-action replies and model history."""
    text = result.message
    if result.decision_kind in {"say", "clarify", "unsupported"}:
        prefixes = tuple(
            f"SIMULATED: {kind}; no action verified. " for kind in ("say", "clarify", "unsupported")
        )
        while text.startswith(prefixes):
            prefix = next(prefix for prefix in prefixes if text.startswith(prefix))
            text = text.removeprefix(prefix)
    return text


class Conversation:
    def __init__(self, broker: Broker):
        self.broker = broker
        self.history: list[Message] = []
        self.pending_open = False

    def submit(self, text: str, request_key: str | None = None):
        normalized = text.strip().casefold().rstrip(".!?")
        resolved = text
        if self.pending_open and normalized == "text editor":
            resolved = "Open my text editor."
        request = UserRequest(request_key or str(uuid4()), self.broker.grant.session, resolved)
        if self.broker.registry.scope_for(request.session, resolved).app_id == "text_editor":
            self.broker.grant = replace(
                self.broker.grant,
                expires_at=self.broker.clock.now() + self.broker.profile.task_seconds,
            )
        result = self.broker.converse(request, tuple(self.history))
        self.pending_open = result.state == State.WAITING_INPUT and normalized in {
            "open my editor",
            "open an editor",
            "open editor",
            "open an app",
            "launch an app",
        }
        if result.state != State.CANCELLED:
            self.history.extend(
                (Message("owner", text), Message("assistant", conversational_text(result)))
            )
            self.history = self.history[-16:]
        return result
