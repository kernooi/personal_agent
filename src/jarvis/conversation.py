"""Session-only text history; model text never authorizes a target."""

from dataclasses import replace
from uuid import uuid4

from jarvis.core import Broker
from jarvis.domain import State, UserRequest
from jarvis.models import Message


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
            self.history.extend((Message("owner", text), Message("assistant", result.message)))
            self.history = self.history[-16:]
        return result
