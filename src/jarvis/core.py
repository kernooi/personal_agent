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
    Handoff,
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
    ProviderOptions,
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
        self.model_turns = 0
        self.model_metrics = []
        self.assistant_memory = None
        self.assistant_pending_memory = None
        self.active_profile = None
        self.currency = getattr(registry, "currency", None)
        self.web = getattr(registry, "web", None)
        self.media = getattr(registry, "media", None)
        if self.web is not None:
            self.web.broker = self

    def submit(self, request: UserRequest):
        text = request.text.strip().rstrip(".").casefold()
        if text != "open my registered text editor":
            raise Denied("M0 requires the explicit registered-editor alias; clarify target")
        return self._submit(request, Scope(request.session, "text_editor"))

    def converse(self, request: UserRequest, history: tuple[Message, ...] = ()):
        prior = self.store.db.execute(
            "SELECT task_id FROM tasks WHERE session=? AND request_key=?",
            (request.session, request.request_key),
        ).fetchone()
        if prior:
            return self._submit(request, self.store.get(prior["task_id"]).scope, history)
        scope = self.registry.scope_for(request.session, request.text)
        controller_read = False
        if scope.app_id == "currency":
            import re

            from jarvis.currency_router import NUM
            from jarvis.public_data import CurrencyArguments

            arguments = CurrencyArguments.model_validate_json(scope.window_ref)
            controller_read = arguments.operation == "source" or (
                arguments.amount is None and re.search(NUM, request.text) is None
            )
        if (
            self.profile.assistant_version in {"assistant-v1", "assistant-v2"}
            and getattr(self.registry, "intent", None) is None
            and not controller_read
            and scope.app_id not in {"notepad", "text_editor", "media"}
        ):
            # Explicit evidence inspection stays controller routed. All other read
            # requests are interpreted before binding a capability.
            from jarvis.web_data import WebArguments

            if scope.app_id != "web" or (
                self.profile.assistant_version == "assistant-v1"
                and WebArguments.model_validate_json(scope.window_ref).operation == "research"
            ):
                scope = Scope(request.session, "none")
        return self._submit(request, scope, history)

    def generate_model(self, request, cancel):
        if request.profile.assistant_version in {"assistant-v1", "assistant-v2"}:
            if cancel() or self.clock.now() >= request.deadline:
                raise ProviderError("CANCELLED_OR_EXPIRED")
            if self.model_turns >= request.profile.max_model_turns:
                raise ProviderError("MODEL_TURN_BUDGET")
            self.model_turns += 1
            with self.store.db:
                self.store.event(
                    request.task_id,
                    "model_turn",
                    payload={
                        "ordinal": self.model_turns,
                        "boundary": request.decision_boundary or "planner",
                    },
                )
        options = getattr(request.profile, "stage_options", {}).get(request.decision_boundary)
        if options is not None:
            request = replace(
                request,
                profile=request.profile.model_copy(
                    update={
                        "provider_options": ProviderOptions.model_validate(
                            options.model_dump(exclude={"max_output_tokens"})
                        ),
                        "max_output_tokens": options.max_output_tokens
                        or request.profile.max_output_tokens,
                        "stage_options": {},
                    }
                ),
            )
        if request.profile.assistant_version != "assistant-v2":
            return self.provider.generate(request, cancel)
        started = self.clock.now()
        reply = None
        error = None
        try:
            reply = self.provider.generate(request, cancel)
            return reply
        except ProviderError as exc:
            error = exc.code
            raise
        finally:
            # Session-only numeric measurements; no messages, outputs or reasoning.
            self.model_metrics.append(
                {
                    "boundary": request.decision_boundary or "planner",
                    "elapsed_seconds": round(max(0.0, self.clock.now() - started), 4),
                    "tokens": reply.tokens if reply else None,
                    "load_seconds": reply.runtime_load_seconds if reply else None,
                    "error": error,
                }
            )

    def _submit(self, request: UserRequest, scope: Scope, history: tuple[Message, ...] = ()):
        # A narrow trusted alias, not a scope inferred from the provider's proposal.
        if request.source != "owner_cli" or not request.request_key or not request.session:
            raise Denied("Missing authenticated request identity")
        if len(request.request_key) > 128 or len(request.session) > 128:
            raise Denied("Request identity too long")
        if scope.app_id in {"currency", "web", "media"}:
            self.grant = replace(
                self.grant, expires_at=self.clock.now() + self.profile.task_seconds
            )
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
            self.clock.now()
            + (
                min(profile.task_seconds, self.web.config.task_seconds)
                if scope.app_id == "web"
                else profile.task_seconds
            ),
            {
                **profile.model_dump(exclude={"reply"}),
                "execution_mode": "windows"
                if getattr(self.desktop, "real", False)
                else "simulation",
            },
        )
        if not fresh:
            return self._result(task.task_id)
        if self.busy:
            self.store.transition(task.task_id, State.FAILED, "SIMULATED: planner is busy.")
            return self._result(task.task_id)
        self.busy = True
        self.active_profile = profile
        self.last_decision = None
        self.last_error = None
        self.last_reply = None
        self.model_turns = 0
        self.model_metrics = []
        self.assistant_pending_memory = None
        currency_route = getattr(self.registry, "route", None) if self.currency else None
        try:
            self.store.transition(task.task_id, State.PLANNING)
            task = self.store.get(task.task_id)
            if self._cancelled(task.task_id):
                return self._result(task.task_id)
            if (
                profile.assistant_version in {"assistant-v1", "assistant-v2"}
                and scope.app_id == "none"
                and getattr(self.registry, "intent", None) is None
                and getattr(currency_route, "unavailable_operation", None) is None
            ):
                from jarvis.assistant import bind_scope, interpret

                meaning, research = interpret(self, task, request, history)
                if isinstance(meaning, Decision):
                    if meaning.kind != "clarify" or not getattr(
                        currency_route, "pending_pair", None
                    ):
                        currency_route = None
                    return self._non_action(task.task_id, meaning)
                scope, currency_route = bind_scope(self, task, request, meaning, research)
                task = self.store.bind_read_scope(
                    task.task_id,
                    task.revision,
                    scope,
                    task_seconds=self.web.config.task_seconds if scope.app_id == "web" else None,
                )
                self.grant = replace(self.grant, expires_at=task.deadline)
            route = currency_route
            if scope.app_id != "web" and route and route.kind in {"clarify", "unsupported"}:
                return self._non_action(task.task_id, Decision(route.kind, text=route.message))
            if scope.app_id == "media":
                from jarvis.media_tools import plan_media

                decision = plan_media(self, task, request)
                task = self.store.get(task.task_id)
                scope = task.scope
            elif scope.app_id == "web":
                # The owner router binds the public topic. Local model planning and
                # source selection happen inside the admitted, bounded read adapter.
                from jarvis.web_decisions import plan_owner

                decision = plan_owner(self, task)
            elif scope.app_id == "currency":
                from jarvis.currency_decisions import plan

                decision = plan(self, task, request)
            else:
                if self.currency is None and self.registry.needs_live_retrieval(request.text):
                    return self._non_action(
                        task.task_id,
                        Decision(
                            "unsupported",
                            text="I need live retrieval to verify current information. "
                            "Live retrieval is not available in M1.",
                        ),
                    )
                candidate_schema = (
                    self.registry.schema_for(scope)
                    if profile.prompt_version
                    in {"planner-m2-v7", "planner-m2-v8", "planner-m2-v9", "planner-m2-v10"}
                    else self.registry.schema()
                )
                messages = context_messages(
                    profile,
                    scope,
                    request.text,
                    request.untrusted_context,
                    history,
                    candidate_schema,
                    self.registry.planner_context()
                    if profile.prompt_version
                    in {
                        "planner-m2-v5",
                        "planner-m2-v6",
                        "planner-m2-v7",
                        "planner-m2-v8",
                        "planner-m2-v9",
                        "planner-m2-v10",
                    }
                    else None,
                )
                model_request = ModelRequest(
                    str(uuid4()),
                    task.task_id,
                    task.revision,
                    profile,
                    candidate_schema,
                    task.deadline,
                    messages,
                )
                reply = self.generate_model(model_request, lambda: self._cancelled(task.task_id))
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
                decision = parse_decision(reply.raw, profile.decision_version)
            self.last_decision = decision
            if getattr(self.registry, "m2", False) or scope.app_id == "currency":
                with self.store.db:
                    self.store.event(
                        task.task_id,
                        "model_decision",
                        payload={
                            "kind": decision.kind,
                            "capability": decision.proposal.capability
                            if decision.proposal
                            else None,
                        },
                    )
            if decision.proposal is None:
                return self._non_action(task.task_id, decision)
            action = self.registry.prepare(task, decision.proposal, self.grant)
            self.registry.validate(action)
            approval = self.approve(action)
            authorize(self.store.get(task.task_id), action, self.grant, approval, self.clock.now())
            self.store.transition(task.task_id, State.READY)
            result = self.dispatch(action, approval)
            if (
                profile.assistant_version in {"assistant-v1", "assistant-v2"}
                and scope.app_id == "currency"
                and result.state == State.SUCCEEDED
            ):
                from jarvis.assistant import finish_currency

                result = finish_currency(self, self.store.get(task.task_id), result)
            elif (
                profile.assistant_version in {"assistant-v1", "assistant-v2"}
                and scope.app_id == "web"
                and result.state == State.SUCCEEDED
            ):
                from jarvis.assistant import finish_web
                from jarvis.web_data import WebArguments

                if WebArguments.model_validate_json(scope.window_ref).operation != "sources":
                    result = finish_web(self, self.store.get(task.task_id), result)
            return result
        except Handoff as exc:
            self.last_error = "MANUAL_HANDOFF"
            self.store.transition(task.task_id, State.WAITING_INPUT, str(exc))
        except (Denied, ValueError) as exc:
            from jarvis.public_data import PublicDataError

            self.last_error = (
                exc.code
                if isinstance(exc, (ProviderError, PublicDataError))
                else "DENIED_OR_INVALID"
            )
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
            self.active_profile = None
            if self.currency is not None:
                self.registry.completed(self.store.get(task.task_id), currency_route)
            if profile.assistant_version in {"assistant-v1", "assistant-v2"}:
                finished = self.store.get(task.task_id)
                self.assistant_memory = (
                    self.assistant_pending_memory
                    if finished.scope.app_id == "currency" and finished.state == State.SUCCEEDED
                    else None
                )
        return self._result(task.task_id)

    def _result(self, task_id: str):
        result = self.store.result(task_id)
        if self.store.get(task_id).scope.app_id == "media":
            if result.state == State.CANCELLED:
                result = replace(
                    result,
                    display_message="Stopped. No further media action will be sent.",
                )
            if result.state == State.NEEDS_REVIEW:
                self.media.blocked_unknown = True
                result = replace(
                    result,
                    message=self.media.review_notice(self.store.get(task_id)),
                )
            if result.state == State.FAILED and result.message.startswith(
                "SIMULATED: request denied or invalid; zero execution."
            ):
                result = replace(
                    result,
                    display_message="I couldn't validate that media request. "
                    "No media action was sent.",
                )
            elif (
                result.state == State.FAILED
                and result.message == "SIMULATED: adapter gate rejected; zero execution."
            ):
                result = replace(
                    result,
                    display_message=self.media.admission_failure_message(self.last_error),
                )
            return replace(result, simulated=not self.media.real)
        if getattr(self.registry, "conversational", False):
            task = self.store.get(task_id)
            if task.scope.app_id == "notepad":
                self.desktop.last_outcome = {
                    "effect": task.scope.effect,
                    "state": result.state,
                    "verified": result.state == State.SUCCEEDED,
                }
        if (
            result.state == State.NEEDS_REVIEW
            and getattr(self.registry, "m2", False)
            and self.store.get(task_id).scope.app_id not in {"currency", "web"}
        ):
            self.desktop.review_task_id = task_id
            result = replace(
                result,
                message=(
                    getattr(self.desktop, "verification_note", "")
                    + "The operation's outcome is uncertain; new actions are paused. "
                    "Inspect Notepad manually, then enter "
                    f"/review {task_id} manually-handled. I will not repeat the operation."
                ),
            )
        if self.store.get(task_id).scope.app_id == "web":
            if result.state == State.FAILED:
                result = replace(
                    result,
                    message="I could not complete web research ("
                    + (self.last_error or "RESEARCH_FAILED")
                    + "). No unverified factual answer is supplied.",
                )
            return replace(result, simulated=False)
        if self.store.get(task_id).scope.app_id == "currency":
            if result.state == State.FAILED:
                result = replace(
                    result,
                    message="Currency information is unavailable ("
                    + (self.last_error or "LOOKUP_FAILED")
                    + "). No current rate is supplied.",
                )
            return replace(result, simulated=False)
        if getattr(self.desktop, "real", False):
            return replace(
                result, simulated=False, message=result.message.removeprefix("SIMULATED: ")
            )
        if (
            self.profile.assistant_version in {"assistant-v1", "assistant-v2"}
            and result.state == State.FAILED
        ):
            return replace(
                result,
                display_message="I couldn't reliably interpret that request. No action was taken.",
            )
        return result

    def _cancelled(self, task_id: str) -> bool:
        if self.cancel_requested():
            self.store.cancel(task_id)
        return self.store.get(task_id).cancelled

    def _non_action(self, task_id: str, decision: Decision):
        self.last_decision = decision
        if getattr(self.registry, "m2", False):
            from jarvis.action_language import non_action_text

            decision = replace(
                decision, text=non_action_text(decision, getattr(self.registry, "intent", None))
            )
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
            self._result(task_id),
            message=f"SIMULATED: {decision.kind}; no action verified. {decision.text}",
            decision_kind=decision.kind,
            display_message=decision.text
            if self.profile.assistant_version in {"assistant-v1", "assistant-v2"}
            else None,
        )

    def dispatch(self, action: PreparedAction, approval: Approval | None = None):
        adapter = (
            self.screen
            if action.capability == "screen.observe"
            else self.currency
            if action.capability == "currency.quote"
            else self.web
            if action.capability == "web.research"
            else self.media
            if action.capability == "media.control"
            else self.desktop
        )
        if action.capability in {
            "currency.quote",
            "web.research",
            "media.control",
            "screen.observe",
        }:
            adapter.cancel = lambda: self._cancelled(action.task_id)
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

            adapter.execute(action, gate)
        except AdmissionRejected as exc:
            if action.capability == "media.control":
                self.last_error = self.media.admission_error_code(exc)
                with self.store.db:
                    self.store.event(
                        action.task_id,
                        "media_admission_rejected",
                        action_id=action_id,
                        payload={"code": self.last_error},
                    )
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
            return self._result(action.task_id)
        except Exception as exc:
            if action.capability in {"currency.quote", "web.research", "screen.observe"}:
                from jarvis.public_data import PublicDataError

                self.last_error = (
                    exc.code if isinstance(exc, PublicDataError) else "PUBLIC_READ_FAILED"
                )
                self.store.transition(action.task_id, State.VERIFYING)
                self.store.complete(
                    action_id,
                    "FAILED",
                    None,
                    State.CANCELLED if self.store.get(action.task_id).cancelled else State.FAILED,
                    "Currency lookup failed; no answer published.",
                )
                return self._result(action.task_id)
            if action.capability == "media.control":
                self.last_error = self.media.diagnostic_error_code(exc)
                with self.store.db:
                    self.store.event(
                        action.task_id,
                        "media_execution_error",
                        action_id=action_id,
                        payload={"code": self.last_error, "stage": "execute"},
                    )
            self.store.complete(
                action_id,
                "UNKNOWN",
                None,
                State.NEEDS_REVIEW,
                "SIMULATED: execution outcome unknown; no replay.",
            )
            return self._result(action.task_id)
        self.store.transition(action.task_id, State.VERIFYING)
        try:
            evidence = adapter.observe(action)
        except Exception as exc:
            if action.capability in {"currency.quote", "web.research", "screen.observe"}:
                from jarvis.public_data import PublicDataError

                self.last_error = (
                    exc.code if isinstance(exc, PublicDataError) else "INVALID_EVIDENCE"
                )
                self.store.complete(
                    action_id,
                    "FAILED",
                    None,
                    State.CANCELLED if self.store.get(action.task_id).cancelled else State.FAILED,
                    "Currency evidence could not be validated; no answer published.",
                )
                return self._result(action.task_id)
            evidence = None
            if action.capability == "media.control":
                self.last_error = self.media.diagnostic_error_code(exc)
                with self.store.db:
                    self.store.event(
                        action.task_id,
                        "media_execution_error",
                        action_id=action_id,
                        payload={"code": self.last_error, "stage": "observe"},
                    )
        current = self.store.get(action.task_id)
        matches = (
            evidence is not None
            and evidence.target_identity == action.target_identity
            and evidence.session == action.session
            and evidence.observed_at <= self.clock.now()
            and evidence.observed_at >= attempt.admitted_at
            and evidence.source == getattr(adapter, "evidence_source", "fake-state-observer-v1")
            and evidence.kind == getattr(adapter, "evidence_kind", "fake_api_state")
            and evidence.authority == "tool_output"
        )
        observed = (
            evidence.postcondition
            if evidence
            and (
                getattr(self.registry, "m2", False)
                or action.capability
                in {"currency.quote", "web.research", "media.control", "screen.observe"}
            )
            else evidence.running
            if evidence
            else None
        )
        if not matches or observed is None:
            self.store.complete(
                action_id,
                "FAILED"
                if action.capability in {"currency.quote", "web.research", "screen.observe"}
                else "UNKNOWN",
                evidence,
                State.FAILED
                if action.capability in {"currency.quote", "web.research", "screen.observe"}
                else State.NEEDS_REVIEW,
                "SIMULATED: postcondition unverified; outcome unknown; no replay.",
            )
        elif observed is not True:
            self.store.complete(
                action_id,
                "FAILED",
                evidence,
                State.FAILED,
                adapter.failure_message(action)
                if action.capability == "media.control"
                else getattr(
                    self.desktop,
                    "failure_message",
                    "SIMULATED: verification failed; editor is not observed running.",
                ),
            )
        else:
            self.store.complete(
                action_id,
                "VERIFIED",
                evidence,
                State.CANCELLED if current.cancelled else State.SUCCEEDED,
                (
                    "Currency lookup cancelled; no answer published."
                    " A request already sent cannot be retracted."
                    if current.cancelled and action.capability in {"currency.quote", "web.research"}
                    else (
                        (
                            "Media action verified; private labels omitted from journal."
                            if action.capability == "media.control"
                            else adapter.success_message(action)
                        )
                        if hasattr(adapter, "success_message")
                        else "SIMULATED: registered text editor observed running in fake state."
                    )
                )
                + (
                    " Cancellation arrived after the effect; no rollback."
                    if current.cancelled
                    else ""
                ),
            )
        result = self._result(action.task_id)
        if action.capability == "media.control" and result.state == State.SUCCEEDED:
            result = replace(result, display_message=adapter.success_message(action))
        if result.state == State.SUCCEEDED and hasattr(adapter, "concise_message"):
            result = replace(result, display_message=adapter.concise_message(action))
        return result

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
                if row["capability"] in {"currency.quote", "web.research", "screen.observe"}:
                    if task.state == State.RUNNING:
                        self.store.transition(task.task_id, State.VERIFYING)
                    self.store.complete(
                        row["action_id"],
                        "FAILED",
                        None,
                        State.FAILED,
                        "Interrupted public lookup; no answer published and no automatic replay.",
                    )
                    recovered.append(self._result(task.task_id))
                    continue
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
                    State.FAILED if row["capability"] == "screen.observe" else State.NEEDS_REVIEW,
                    "SIMULATED: unadmitted intent pending; reauthorization required.",
                )
            recovered.append(self._result(task.task_id))
        # A crash during planning or before intent admission carries no action to retry.
        for row in self.store.db.execute(
            "SELECT task_id FROM tasks WHERE state IN "
            "('RECEIVED','PLANNING','READY','WAITING_INPUT')"
        ).fetchall():
            task = self.store.get(row["task_id"])
            self.store.transition(
                task.task_id, State.FAILED, "SIMULATED: interrupted before admission; no replay."
            )
            recovered.append(self._result(task.task_id))
        if hasattr(self.desktop, "blocked_unknown"):
            self.desktop.blocked_unknown = (
                self.store.db.execute(
                    "SELECT a.task_id FROM actions a WHERE a.state='UNKNOWN' "
                    "AND a.capability NOT IN ('currency.quote','web.research','media.control') "
                    "AND NOT EXISTS "
                    "(SELECT 1 FROM events e WHERE e.task_id=a.task_id "
                    "AND e.kind='manual_review_acknowledged')"
                ).fetchone()
                is not None
            )
        if self.media is not None:
            self.media.blocked_unknown = (
                self.store.db.execute(
                    "SELECT 1 FROM actions a WHERE a.capability='media.control' "
                    "AND a.state='UNKNOWN' "
                    "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.task_id=a.task_id "
                    "AND e.kind='manual_review_acknowledged')"
                ).fetchone()
                is not None
            )
        return recovered

    def revoke_grant(self):
        self.grant = replace(self.grant, revoked=True, version=self.grant.version + 1)
