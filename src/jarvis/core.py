"""One bounded planner turn and one action, with durable and independent checks."""

import hashlib
from collections.abc import Callable
from dataclasses import replace
from uuid import uuid4

from jarvis.domain import (
    AdmissionRejected,
    Approval,
    Clock,
    Decision,
    Denied,
    Desktop,
    Grant,
    PreparedAction,
    Scope,
    State,
    UserRequest,
)
from jarvis.models import (
    Message,
    ModelReply,
    ModelRequest,
    Provider,
    ProviderError,
    TextProfile,
    parse_decision,
)
from jarvis.policy import authorize
from jarvis.prompts import context_messages
from jarvis.storage import Store, encode
from jarvis.tools import Registry


class Broker:
    def __init__(
        self,
        store: Store,
        clock: Clock,
        provider: Provider,
        desktop: Desktop,
        registry: Registry,
        profile: TextProfile,
        grant: Grant,
    ):
        self.store = store
        self.clock = clock
        self.provider = provider
        self.desktop = desktop
        self.registry = registry
        self.profile = profile
        self.grant = grant
        self.before_admission: Callable[[], None] = lambda: None
        self.after_intent: Callable[[], None] = lambda: None
        self.approve: Callable[[PreparedAction], Approval | None] = lambda action: None
        self.busy = False
        self.cancel_requested: Callable[[], bool] = lambda: False
        self.last_decision: Decision | None = None
        self.last_error: str | None = None
        self.last_reply: ModelReply | None = None

    def submit(self, request: UserRequest):
        text = request.text.strip().rstrip(".").casefold()
        if text != "open my registered text editor":
            raise Denied("M0 requires the explicit registered-editor alias; clarify target")
        return self._submit(request, Scope(request.session, "text_editor"))

    def converse(self, request: UserRequest, history: tuple[Message, ...] = ()):
        return self._submit(
            request, self.registry.scope_for(request.session, request.text), history
        )

    def _submit(self, request: UserRequest, scope: Scope, history: tuple[Message, ...] = ()):
        # A narrow trusted alias, not a scope inferred from the provider's proposal.
        if request.source != "owner_cli" or not request.request_key or not request.session:
            raise Denied("Missing authenticated request identity")
        if len(request.request_key) > 128 or len(request.session) > 128:
            raise Denied("Request identity too long")
        profile = self.profile  # Freeze selection for this task; switches affect the next task.
        if len(request.text.encode()) > 4096 or len(request.untrusted_context.encode()) > 8192:
            raise Denied("Request context too large")
        fingerprint = hashlib.sha256(
            encode(
                {
                    "text": request.text,
                    "source": request.source,
                    "context": request.untrusted_context,
                }
            ).encode()
        ).hexdigest()
        task, fresh = self.store.accept(
            request.request_key,
            scope,
            fingerprint,
            self.clock.now() + profile.task_seconds,
            profile.model_dump(exclude={"reply"}),
        )
        if not fresh:
            return self.store.result(task.task_id)
        if self.busy:
            self.store.transition(task.task_id, State.FAILED, "SIMULATED: planner is busy.")
            return self.store.result(task.task_id)
        self.busy = True
        self.last_decision = None
        self.last_error = None
        self.last_reply = None
        try:
            self.store.transition(task.task_id, State.PLANNING)
            task = self.store.get(task.task_id)
            if self._cancelled(task.task_id):
                return self.store.result(task.task_id)
            if self.registry.needs_live_retrieval(request.text):
                return self._non_action(
                    task.task_id,
                    Decision(
                        "unsupported",
                        text="I need live retrieval to verify current information. "
                        "Live retrieval is not available in M1.",
                    ),
                )
            messages = context_messages(
                profile,
                scope,
                request.text,
                request.untrusted_context,
                history,
                self.registry.schema(),
            )
            model_request = ModelRequest(
                str(uuid4()),
                task.task_id,
                task.revision,
                profile,
                self.registry.schema(),
                task.deadline,
                messages,
            )
            reply = self.provider.generate(model_request, lambda: self._cancelled(task.task_id))
            self.last_reply = reply
            self._cancelled(task.task_id)
            current = self.store.get(task.task_id)
            if (
                current.cancelled
                or current.revision != task.revision
                or reply.request_id != model_request.request_id
                or reply.task_id != task.task_id
                or reply.revision != task.revision
                or self.clock.now() >= task.deadline
            ):
                raise Denied("Late or obsolete model reply")
            if len(reply.raw) > profile.max_output_bytes:
                raise Denied("Model reply budget exceeded")
            decision = parse_decision(reply.raw)
            self.last_decision = decision
            if decision.proposal is None:
                return self._non_action(task.task_id, decision)
            action = self.registry.prepare(task, decision.proposal, self.grant)
            self.registry.validate(action)
            approval = self.approve(action)
            authorize(self.store.get(task.task_id), action, self.grant, approval, self.clock.now())
            self.store.transition(task.task_id, State.READY)
            self.dispatch(action, approval)
        except (Denied, ValueError) as exc:
            self.last_error = exc.code if isinstance(exc, ProviderError) else "DENIED_OR_INVALID"
            current = self.store.get(task.task_id)
            if current.state in (State.RECEIVED, State.PLANNING, State.READY):
                self.store.transition(
                    task.task_id,
                    State.FAILED,
                    "SIMULATED: request denied or invalid; zero execution."
                    + (f" Inference error: {exc.code}." if isinstance(exc, ProviderError) else ""),
                )
        finally:
            self.busy = False
        return self.store.result(task.task_id)

    def _cancelled(self, task_id: str) -> bool:
        if self.cancel_requested():
            self.store.cancel(task_id)
        return self.store.get(task_id).cancelled

    def _non_action(self, task_id: str, decision: Decision):
        self.last_decision = decision
        state = {
            "say": State.ANSWERED,
            "clarify": State.WAITING_INPUT,
            "unsupported": State.FAILED,
        }[decision.kind]
        self.store.transition(
            task_id,
            state,
            f"SIMULATED: {decision.kind}; no action verified. Text is not persisted.",
        )
        return replace(
            self.store.result(task_id),
            message=f"SIMULATED: {decision.kind}; no action verified. {decision.text}",
            decision_kind=decision.kind,
        )

    def dispatch(self, action: PreparedAction, approval: Approval | None = None):
        self.registry.validate(action)
        auth = authorize(
            self.store.get(action.task_id), action, self.grant, approval, self.clock.now()
        )
        action_id = self.store.intent(action, auth)
        self.after_intent()
        self.before_admission()
        self._cancelled(action.task_id)
        self.registry.validate(action)
        authorize(self.store.get(action.task_id), action, self.grant, approval, self.clock.now())
        attempt = self.store.admit(action_id, action, approval)
        try:

            def gate():
                try:
                    self._cancelled(action.task_id)
                    self.registry.validate(action)
                    self.store.gate(action)
                    authorize(
                        self.store.get(action.task_id),
                        action,
                        self.grant,
                        approval,
                        self.clock.now(),
                    )
                except Denied as exc:
                    raise AdmissionRejected("Adapter admission gate closed") from exc

            self.desktop.execute(action, gate)
        except AdmissionRejected:
            # The fake adapter's gate rejected before mutation, so absence of effect is known.
            current = self.store.get(action.task_id)
            self.store.transition(action.task_id, State.VERIFYING)
            self.store.complete(
                action_id,
                "FAILED",
                None,
                State.CANCELLED if current.cancelled else State.FAILED,
                "SIMULATED: adapter gate rejected; zero execution.",
            )
            return self.store.result(action.task_id)
        except Exception:
            self.store.complete(
                action_id,
                "UNKNOWN",
                None,
                State.NEEDS_REVIEW,
                "SIMULATED: execution outcome unknown; no replay.",
            )
            return self.store.result(action.task_id)
        self.store.transition(action.task_id, State.VERIFYING)
        try:
            evidence = self.desktop.observe(action)
        except Exception:
            evidence = None
        current = self.store.get(action.task_id)
        matches = (
            evidence is not None
            and evidence.target_identity == action.target_identity
            and evidence.session == action.session
            and evidence.observed_at <= self.clock.now()
            and evidence.observed_at >= attempt.admitted_at
            and evidence.source == "fake-state-observer-v1"
            and evidence.kind == "fake_api_state"
            and evidence.authority == "tool_output"
        )
        if not matches or evidence.running is None:
            self.store.complete(
                action_id,
                "UNKNOWN",
                evidence,
                State.NEEDS_REVIEW,
                "SIMULATED: postcondition unverified; outcome unknown; no replay.",
            )
        elif evidence.running is not True:
            self.store.complete(
                action_id,
                "FAILED",
                evidence,
                State.FAILED,
                "SIMULATED: verification failed; editor is not observed running.",
            )
        else:
            self.store.complete(
                action_id,
                "VERIFIED",
                evidence,
                State.CANCELLED if current.cancelled else State.SUCCEEDED,
                "SIMULATED: registered text editor observed running in fake state."
                + (
                    " Cancellation arrived after the effect; no rollback."
                    if current.cancelled
                    else ""
                ),
            )
        return self.store.result(action.task_id)

    def recover(self):
        # Recovery never executes, even when an admitted effect appears absent.
        rows = self.store.db.execute(
            "SELECT * FROM actions WHERE state IN ('DISPATCHING','INTENT_RECORDED')"
        ).fetchall()
        recovered = []
        for row in rows:
            task = self.store.get(row["task_id"])
            valid = True
            try:
                action = self.store.load_action(row["prepared_json"])
                self.registry.validate(action)
                if action.task_id != task.task_id or action.digest != row["prepared_digest"]:
                    raise Denied("Corrupt action binding")
            except ValueError:
                valid = False
            if row["state"] == "DISPATCHING":
                self.store.complete(
                    row["action_id"],
                    "UNKNOWN",
                    None,
                    State.NEEDS_REVIEW,
                    "SIMULATED: recovered admitted attempt with unknown outcome; "
                    "manual review required; no replay."
                    + (" Invalid stored action." if not valid else ""),
                )
            elif task.state == State.READY:
                self.store.transition(
                    task.task_id,
                    State.NEEDS_REVIEW,
                    "SIMULATED: unadmitted intent pending; reauthorization required.",
                )
            recovered.append(self.store.result(task.task_id))
        # A crash during planning or before intent admission carries no action to retry.
        for row in self.store.db.execute(
            "SELECT task_id FROM tasks WHERE state IN "
            "('RECEIVED','PLANNING','READY','WAITING_INPUT')"
        ).fetchall():
            task = self.store.get(row["task_id"])
            self.store.transition(
                task.task_id, State.FAILED, "SIMULATED: interrupted before admission; no replay."
            )
            recovered.append(self.store.result(task.task_id))
        return recovered

    def revoke_grant(self):
        self.grant = replace(self.grant, revoked=True, version=self.grant.version + 1)
