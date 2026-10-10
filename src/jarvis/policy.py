"""Authorization checks resolved effects, never natural-language model assurances."""

from jarvis.domain import Approval, Denied, Grant, PreparedAction, Task

POLICY_VERSION = "m0-policy-v1"


def authorize(
    task: Task, action: PreparedAction, grant: Grant, approval: Approval | None, now: float
) -> str:
    if task.cancelled or now >= task.deadline or action.revision != task.revision:
        raise Denied("Cancelled, expired, or stale task")
    if (
        action.task_id != task.task_id
        or action.app_id != task.scope.app_id
        or action.session != task.scope.session
        or action.effects != (task.scope.effect,)
        or (action.capability, action.effects)
        not in {
            ("apps.open", ("open",)),
            ("windows.focus", ("focus",)),
            ("windows.close", ("close",)),
        }
        or action.window_ref != task.scope.window_ref
        or action.policy_version != POLICY_VERSION
        or now >= action.expires_at
    ):
        raise Denied("Action outside task scope or expired")
    if (
        grant.revoked
        or grant.issuer != "owner"
        or now >= grant.expires_at
        or grant.session != task.scope.session
        or action.grant_id != grant.grant_id
        or action.grant_version != grant.version
        or action.app_id not in grant.apps
        or not set(action.effects) <= grant.effects
    ):
        raise Denied("No current scoped grant")
    if approval is not None:
        if (
            not approval.approved
            or approval.issuer != "owner"
            or approval.digest != action.digest
            or approval.revision != task.revision
            or approval.session != task.scope.session
            or now >= approval.expires_at
            or approval.expires_at > action.expires_at
        ):
            raise Denied("Invalid exact-action approval")
        return approval.approval_id
    return grant.grant_id
