"""Restricted research model boundaries: queries, result IDs, exact evidence excerpts."""

import json
from typing import Literal
from uuid import uuid4

from pydantic import Field

from jarvis.domain import Decision
from jarvis.models import Message, ModelRequest, StrictRecord, reject_constant, unique_object
from jarvis.web_data import WebError


class ResearchPlan(StrictRecord):
    kind: Literal["research_plan"]
    queries: list[str] = Field(min_length=1, max_length=3)


class ResearchSelection(StrictRecord):
    kind: Literal["research_selection"]
    result_ids: list[str] = Field(min_length=1, max_length=5)


class ResearchRoute(StrictRecord):
    kind: Literal["research_route"]
    need_evidence: bool
    static_answer: str = Field(max_length=1500)


class CitedExcerpt(StrictRecord):
    source_id: str = Field(max_length=64)
    excerpt_index: int = Field(ge=0, le=255)


class ResearchAnswer(StrictRecord):
    kind: Literal["research_answer"]
    excerpts: list[CitedExcerpt] = Field(max_length=6)
    assessment: Literal["supported", "conflicting", "insufficient"]


BOUNDARIES = {
    "web-route-v1": ResearchRoute,
    "web-plan-v1": ResearchPlan,
    "web-select-v1": ResearchSelection,
    "web-answer-v1": ResearchAnswer,
}


def query_candidates(topic):
    """Reviewed purpose refinements disclose only the owner topic plus fixed terms."""
    import re

    candidates = [topic]
    parts = re.split(r"\s+(?:and|versus|vs)\s+", topic, flags=re.I)
    if len(parts) == 2:
        candidates.extend(parts)
    if topic.casefold().startswith("who ") and len(topic) <= 238:
        candidates.append(topic + " biography profile")
    return candidates


def parse(raw, boundary):
    return BOUNDARIES[boundary].model_validate(
        json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    )


def gateway_parse(raw, boundary):
    parse(raw, boundary)
    return Decision("say", text="Structured research result; not an action receipt.")


def generate(adapter, action, boundary, instructions, data):
    broker = adapter.broker
    adapter.model_turns += 1
    if adapter.model_turns > adapter.config.max_model_turns:
        raise WebError("MODEL_TURN_BUDGET")
    adapter.check(action)
    schema = BOUNDARIES[boundary].model_json_schema()
    if boundary == "web-plan-v1":
        topic = data["authorized_public_topic"]
        # Model selects from controller-approved topic-only refinements. Its
        # generated query cannot incorporate source instructions or private context.
        candidates = query_candidates(topic)
        schema["properties"]["queries"]["items"] = {"type": "string", "enum": candidates}
    messages = (Message("system", instructions), Message("owner", json.dumps(data)))
    # Explicit conservative gateway context limit; evidence is trimmed before this call.
    import math

    from jarvis.models import OllamaProfile

    size = len(json.dumps({"messages": [m.__dict__ for m in messages], "schema": schema}).encode())
    profile = broker.profile
    if size + 512 > profile.context_bytes or (
        isinstance(profile, OllamaProfile)
        and math.ceil(size / 3) + profile.max_output_tokens + profile.safety_tokens
        > profile.context_tokens
    ):
        raise WebError("CONTEXT_LIMIT")
    task = broker.store.get(action.task_id)
    request = ModelRequest(
        str(uuid4()),
        task.task_id,
        task.revision,
        profile,
        schema,
        min(task.deadline, adapter.until),
        messages,
        decision_boundary=boundary,
    )
    reply = broker.provider.generate(request, adapter.cancel)
    broker.last_reply = reply
    adapter.check(action)
    current = broker.store.get(action.task_id)
    if (
        current.revision != task.revision
        or reply.request_id != request.request_id
        or reply.task_id != task.task_id
        or reply.revision != task.revision
        or len(reply.raw) > profile.max_output_bytes
    ):
        raise WebError("LATE_OR_INVALID_RESEARCH_REPLY")
    return parse(reply.raw, boundary)


def validate_answer(answer, sources):
    known = {source.source_id: source for source in sources}
    if answer.assessment == "supported" and not answer.excerpts:
        raise WebError("INSUFFICIENT_EVIDENCE")
    if answer.assessment == "conflicting" and len({e.source_id for e in answer.excerpts}) < 2:
        raise WebError("CONFLICT_REQUIRES_TWO_SOURCES")
    for item in answer.excerpts:
        source = known.get(item.source_id)
        if source is None or item.excerpt_index >= len(source.chunks):
            raise WebError("UNSUPPORTED_CITATION_OR_CLAIM")
        if len(source.chunks[item.excerpt_index]) < 20:
            raise WebError("EXCERPT_TOO_SHORT_TO_SUPPORT_CLAIM")
    return answer


def plan_owner(broker, task):
    """Model-assisted niche routing inside an already controller-scoped owner task."""
    from jarvis.domain import Proposal
    from jarvis.web_data import WebArguments

    args = WebArguments.model_validate_json(task.scope.window_ref)
    adapter = broker.web
    adapter.routing_turns = 0
    if adapter.route_error:
        raise WebError(adapter.route_error)
    if args.operation == "sources" and (
        not adapter.sources or adapter.session != task.scope.session
    ):
        return Decision("say", text="I haven't retrieved any web sources in this session.")
    if args.consider:
        adapter.cancel = lambda: broker._cancelled(task.task_id)
        adapter.until = min(task.deadline, broker.clock.now() + adapter.config.task_seconds)
        adapter.model_turns = 0
        action = broker.registry.prepare(
            task, Proposal("web.research", "web", task.scope.window_ref), broker.grant
        )
        route = generate(
            adapter,
            action,
            "web-route-v1",
            "Classify this owner factual topic. Return research_route JSON. "
            "Use need_evidence=true for specialized, obscure, niche or changeable "
            "facts needing external verification. Otherwise give a brief static "
            "general-knowledge answer in static_answer and need_evidence=false. "
            "Confidence is not authority. No permissions, actions, URLs or secrets. "
            "The controller independently owns the scope and networking policy.",
            {"owner_public_topic": adapter.pending["query"]},
        )
        adapter.routing_turns = 1
        if not route.need_evidence:
            return Decision(
                "say", text=route.static_answer or "Please specify the factual question."
            )
    return Decision(
        "propose_action", proposal=Proposal("web.research", "web", task.scope.window_ref)
    )
