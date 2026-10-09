"""Reviewed capability and target registry; no model-selected paths or commands."""

import hashlib
import json
from dataclasses import asdict, dataclass

from jarvis.domain import Denied, Grant, PreparedAction, Proposal, Scope, Task
from jarvis.models import BOUNDARY
from jarvis.policy import POLICY_VERSION


@dataclass(frozen=True)
class RegisteredApp:
    app_id: str
    identity: str
    display_name: str


class Registry:
    capability = "apps.open"
    adapter_version = "fake-desktop-v1"
    retry_class = "conditionally_repeatable"

    def __init__(self):
        self.apps = {
            "text_editor": RegisteredApp("text_editor", "fake:editor:v1", "Registered text editor"),
            "other_editor": RegisteredApp("other_editor", "fake:other:v1", "Other editor fixture"),
        }

    def schema(self) -> dict:
        # The reviewed registry has exactly one capability, using these same boundary types.
        return BOUNDARY.json_schema()

    def scope_for(self, session: str, text: str) -> Scope:
        normalized = text.strip().casefold().rstrip(".!?")
        aliases = {
            "open my registered text editor",
            "open my text editor",
            "open text editor",
            "launch my text editor",
            "please open my text editor",
        }
        return Scope(session, "text_editor" if normalized in aliases else "none")

    def needs_live_retrieval(self, text: str) -> bool:
        value = text.casefold()
        return (
            ("myr" in value and "jpy" in value)
            or any(word in value for word in ("exchange rate", "weather", "latest news"))
            or (
                any(word in value for word in ("current", "today", "now", "latest"))
                and any(word in value for word in ("price", "rate", "news", "president"))
            )
        )

    def prepare(self, task: Task, proposal: Proposal, grant: Grant) -> PreparedAction:
        if proposal.capability != self.capability or proposal.app_id not in self.apps:
            raise Denied("Unknown capability or target")
        app = self.apps[proposal.app_id]
        action = PreparedAction(
            task.task_id,
            task.revision,
            proposal.capability,
            app.app_id,
            app.identity,
            task.scope.session,
            ("open",),
            self.adapter_version,
            POLICY_VERSION,
            grant.grant_id,
            grant.version,
            min(task.deadline, grant.expires_at),
            "",
        )
        return PreparedAction(**{**asdict(action), "digest": digest(action)})

    def validate(self, action: PreparedAction) -> None:
        if (
            action.capability != self.capability
            or action.app_id not in self.apps
            or self.apps[action.app_id].identity != action.target_identity
            or action.adapter_version != self.adapter_version
            or digest(action) != action.digest
        ):
            raise Denied("Prepared target or action changed")


def digest(action: PreparedAction) -> str:
    payload = asdict(action)
    payload.pop("digest")
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
