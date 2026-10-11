"""Semantic plans remain proposals; these tests use no network or Windows effects."""

import json
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest
from test_m1 import Runtime
from test_m2 import broker as desktop_fixture
from test_m3 import broker as currency_broker
from test_web import Model as WebModel
from test_web import system as web_stack

from jarvis.assistant import calculate, operands, parse
from jarvis.conversation import Conversation, conversational_text
from jarvis.domain import Denied, Scope, State, UserRequest
from jarvis.models import ModelReply, ProviderError
from jarvis.public_data import CurrencyArguments

broker = currency_broker
stack = web_stack
notepad_broker = desktop_fixture


@pytest.mark.parametrize(
    "owner,reply,state",
    [
        ("close notepad", {"kind": "clarify", "question": "Which window?"}, State.WAITING_INPUT),
        ("open my editor", {"kind": "clarify", "question": "Which editor?"}, State.WAITING_INPUT),
    ],
)
def test_unresolved_notepad_intent_keeps_controller_path(notepad_broker, owner, reply, state):
    notepad_broker.profile = notepad_broker.profile.model_copy(
        update={
            "assistant_version": "assistant-v1",
            "prompt_version": "planner-m2-v10",
            "reply": json.dumps(reply),
        }
    )
    notepad_broker.registry.conversational = True
    notepad_broker.registry.extended = True
    result = Conversation(notepad_broker).submit(owner)
    assert result.state == state
    assert notepad_broker.registry.intent is not None
    assert notepad_broker.model_turns == 1
    assert notepad_broker.desktop.execution_calls == 0


class SemanticModel:
    def __init__(self, meaning, mutate=None):
        self.meaning, self.mutate = meaning, mutate
        self.requests = []

    def close(self):
        pass

    def generate(self, request, cancel):
        self.requests.append(request)
        data = (
            json.loads(
                request.messages[
                    -2
                    if request.decision_boundary
                    in {
                        "assistant-plan-v1",
                        "assistant-repair-v1",
                        "assistant-intent-v1",
                        "assistant-check-v1",
                    }
                    else -1
                ].text
            )
            if request.decision_boundary != "currency-decision-v1"
            else {}
        )
        if request.decision_boundary in {
            "assistant-intent-v1",
            "assistant-plan-v1",
            "assistant-repair-v1",
            "assistant-check-v1",
        }:
            data["owner_request"] = request.messages[-1].text
        if request.decision_boundary == "assistant-intent-v1":
            planned = self.meaning(data) if callable(self.meaning) else self.meaning
            value = {
                "kind": "assistant_intent",
                "route": "currency" if planned["kind"] == "currency" else "conversation",
            }
        elif request.decision_boundary in {"assistant-plan-v1", "assistant-repair-v1"}:
            data["owner_request"] = request.messages[-1].text
            value = self.meaning(data) if callable(self.meaning) else self.meaning
        elif request.decision_boundary == "currency-decision-v1":
            value = {
                "kind": "propose_action",
                "action": {
                    "capability": "currency.quote",
                    "arguments": {
                        k: v["const"]
                        for k, v in request.schema["$defs"]["CurrencyArguments"][
                            "properties"
                        ].items()
                    },
                },
            }
        elif request.decision_boundary == "assistant-answer-v1":
            value = {"kind": "assistant_answer", "text": data["verified_answer"]}
        elif request.decision_boundary == "assistant-check-v1":
            value = {"kind": "calculation_check", "supported": True, "question": ""}
        else:
            raise AssertionError(request.decision_boundary)
        reply = ModelReply(
            request.request_id,
            request.task_id,
            request.revision,
            json.dumps(value).encode(),
            "synthetic-semantic",
        )
        return self.mutate(request, reply) if self.mutate else reply


class SemanticWebModel(WebModel):
    def generate(self, request, cancel):
        if request.decision_boundary == "assistant-intent-v1":
            self.requests.append(request)
            return ModelReply(
                request.request_id,
                request.task_id,
                request.revision,
                b'{"kind":"assistant_intent","route":"research"}',
                "synthetic-semantic",
            )
        return super().generate(request, cancel)


def install(broker, meaning, mutate=None):
    broker.profile = broker.profile.model_copy(update={"assistant_version": "assistant-v1"})
    broker.provider = SemanticModel(meaning, mutate)
    return Conversation(broker)


def meaning(expression="n0*n0", **kwargs):
    return {"kind": "currency", "base": "SGD", "quote": "USD", "expression": expression, **kwargs}


@pytest.mark.parametrize(
    "expression,values,total",
    [
        ("n0*n1*(1-n2/100)", {"n0": "40", "n1": "35", "n2": "20"}, "1120.0"),
        ("(n0*n1+n2)/n3", {"n0": "40", "n1": "35", "n2": "20", "n3": "4"}, "355"),
        ("n0+n1", {"n0": "0.1", "n1": "0.2"}, "0.3"),
    ],
)
def test_bounded_decimal_arithmetic(expression, values, total):
    actual, ledger = calculate(expression, values)
    assert Decimal(actual) == Decimal(total)
    assert ledger


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('calc')",
        "n0.real",
        "n0[0]",
        "n0**2",
        "n0//1",
        "1600",
        "n999",
        "[n0]",
        "True",
        "n0/(n0-n0)",
        "n0*1000000000000",
    ],
)
def test_expression_cannot_execute_or_invent_operands(expression):
    with pytest.raises((Denied, ValueError, ArithmeticError)):
        calculate(expression, {"n0": "40"})


def test_quantity_discount_goes_through_broker(broker):
    chat = install(broker, meaning("n1*n2*(1-n3/100)"))
    result = chat.submit("Forty is written 40: buy 40 tickets priced 35 SGD, less 20%, in USD")
    assert result.state == State.SUCCEEDED, result
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert Decimal(args.amount) == 1120
    assert broker.currency.provider.calls == [("SGD", "USD")]
    assert broker.desktop.execution_calls == 0
    assert broker.model_turns == 5
    assert "28.00 USD" in conversational_text(result)


def test_unknown_wording_reaches_semantic_model_before_old_clarification(broker):
    chat = install(broker, meaning())
    result = chat.submit(
        "if i buy 40 tickets each worth 40 sgd. how much would 40 tickets worth in usd"
    )
    assert result.state == State.SUCCEEDED
    assert "1600 SGD" in conversational_text(result)
    assert broker.provider.requests[0].decision_boundary == "assistant-intent-v1"


def test_invented_currency_or_operand_is_denied_without_lookup(broker):
    for plan in [meaning("n0*n9"), meaning("n0", quote="JPY")]:
        chat = install(broker, plan)
        assert chat.submit("40 SGD in USD").state == State.FAILED
    assert not broker.currency.provider.calls


def test_answer_hallucination_falls_back_without_replaying_lookup(broker):
    def mutate(request, reply):
        if request.decision_boundary == "assistant-answer-v1":
            return replace(reply, raw=b'{"kind":"assistant_answer","text":"You paid 999 USD."}')
        return reply

    result = install(broker, meaning(), mutate).submit("40 tickets at 40 SGD each in USD")
    assert result.state == State.SUCCEEDED
    assert "999" not in conversational_text(result)
    assert "1600 SGD" in conversational_text(result)
    assert len(broker.currency.provider.calls) == 1


def test_duplicate_delivery_does_not_reinterpret_or_lookup(broker):
    install(broker, meaning())
    request = UserRequest("same", broker.grant.session, "40 tickets at 40 SGD in USD")
    first = broker.converse(request)
    assert first.state == State.SUCCEEDED
    assert broker.converse(request).state == State.SUCCEEDED
    assert len(broker.provider.requests) == 5
    assert len(broker.currency.provider.calls) == 1


@pytest.mark.parametrize("fault", ["revision", "identity", "cancel"])
def test_obsolete_interpretation_cannot_bind_or_execute(broker, fault):
    def mutate(request, reply):
        if fault == "revision":
            broker.store.revise(request.task_id)
        elif fault == "cancel":
            broker.store.cancel(request.task_id)
        else:
            reply = replace(reply, task_id="wrong")
        return reply

    result = install(broker, meaning(), mutate).submit("40 SGD in USD")
    assert result.state in {State.FAILED, State.CANCELLED}
    assert not broker.currency.provider.calls
    assert broker.store.get(result.task_id).scope.app_id == "none"


def test_memory_is_session_bound_and_cleared_by_unrelated_chat(broker):
    chat = install(broker, meaning())
    assert chat.submit("40 tickets at 40 SGD in USD").state == State.SUCCEEDED
    assert broker.assistant_memory["amount"] == "1600"
    broker.provider.meaning = {"kind": "say", "text": "Hello!"}
    assert chat.submit("Hello").state == State.ANSWERED
    assert broker.assistant_memory is None
    assert broker.registry.context is None


def test_scope_binding_cannot_escalate_to_windows(broker):
    task, _ = broker.store.accept(
        "bind", Scope(broker.grant.session, "none"), "f", broker.clock.now() + 10
    )
    broker.store.transition(task.task_id, State.PLANNING)
    with pytest.raises(Denied):
        broker.store.bind_read_scope(
            task.task_id, task.revision, Scope(task.scope.session, "notepad")
        )
    assert broker.store.get(task.task_id).revision == 1


def test_strict_whole_plan_has_no_authorization_fields():
    with pytest.raises(ValueError):
        parse('{"kind":"research","grant":"all"}', "assistant-plan-v1")
    assert operands("40 tickets at 40 SGD to USD") == {"n0": "40", "n1": "40"}


def test_ordinary_conversation_receives_recent_local_history(broker):
    chat = install(broker, {"kind": "say", "text": "An exchange rate compares currencies."})
    assert chat.submit("Explain an exchange rate.").state == State.ANSWERED
    assert chat.submit("Give me a simpler example.").state == State.ANSWERED
    data = json.loads(broker.provider.requests[-1].messages[-2].text)
    assert any("exchange rate" in item["text"] for item in data["conversation"])
    assert not broker.currency.provider.calls


def test_followup_operands_keep_original_ids_and_require_updated_input(broker):
    chat = install(broker, meaning("n0/n1"))
    assert chat.submit("Split 800 SGD between 4 people in USD").state == State.SUCCEEDED

    def revised(data):
        if data.get("owner_request"):
            assert data["current_operands"] == {"n2": "5"}
            assert data["followup_operands"] == {"n0": "800", "n1": "4", "n2": "5"}
            assert data["previous_expression"] == "n0/n1"
        return meaning("n0/n2", use_context=True)

    broker.provider.meaning = revised
    result = chat.submit("What if there are 5 people instead?")
    assert result.state == State.SUCCEEDED
    assert (
        CurrencyArguments.model_validate_json(
            broker.store.get(result.task_id).scope.window_ref
        ).amount
        == "160"
    )


def test_omitted_amount_or_fee_cannot_be_looked_up(broker):
    for expression in (None, "n0"):
        chat = install(broker, meaning(expression))
        assert chat.submit("40 SGD plus a 5 SGD fee in USD").state == State.FAILED
    assert not broker.currency.provider.calls
    assert broker.model_turns == 4  # Classify plus at most three rejected interpretations.


def test_shared_turn_budget_prevents_another_provider_call(broker):
    chat = install(broker, meaning())
    broker.profile = broker.profile.model_copy(update={"max_model_turns": 4})
    result = chat.submit("40 tickets at 40 SGD each in USD")
    assert result.state == State.SUCCEEDED
    assert broker.model_turns == len(broker.provider.requests) == 4
    assert len(broker.currency.provider.calls) == 1
    assert "1600 SGD" in conversational_text(result)


def test_binding_deadline_is_measured_from_acceptance_and_rolls_back(broker):
    from jarvis.public_data import canonical

    args = CurrencyArguments(base="SGD", quote="USD", amount="40")
    task, _ = broker.store.accept(
        "expired-read", Scope(broker.grant.session, "none"), "f", broker.clock.now() + 100
    )
    broker.store.transition(task.task_id, State.PLANNING)
    broker.clock.advance(11)
    with pytest.raises(Denied):
        broker.store.bind_read_scope(
            task.task_id,
            task.revision,
            Scope(task.scope.session, "currency", "public_read", canonical(args)),
            task_seconds=10,
        )
    assert broker.store.get(task.task_id).scope.app_id == "none"
    assert broker.store.get(task.task_id).revision == 1


def test_missing_price_review_cannot_deliver_a_quote(broker):
    def review(request, reply):
        if request.decision_boundary == "assistant-check-v1":
            return replace(
                reply,
                raw=(
                    b'{"kind":"calculation_check","supported":false,'
                    b'"question":"What is each ticket price in SGD?"}'
                ),
            )
        return reply

    result = install(broker, meaning("n0"), review).submit(
        "40 tickets cost how much in USD if priced in SGD?"
    )
    assert result.state == State.WAITING_INPUT
    assert "ticket price" in conversational_text(result)
    assert not broker.currency.provider.calls


def test_rate_only_memory_has_no_operand_collision_on_amount_followup(broker):
    chat = install(broker, meaning(None))
    assert chat.submit("What is the SGD to USD rate?").state == State.SUCCEEDED
    broker.provider.meaning = meaning("n0", use_context=True)
    result = chat.submit("What about 500?")
    assert result.state == State.SUCCEEDED
    assert (
        CurrencyArguments.model_validate_json(
            broker.store.get(result.task_id).scope.window_ref
        ).amount
        == "500"
    )


def test_profile_stage_options_do_not_change_effects_or_legacy_defaults():
    from jarvis.models import OllamaProfile

    base = dict(
        profile_name="stage-test",
        model_identity="qwen3:8b",
        provider="ollama",
        network_mode="local_model_only",
    )
    legacy = OllamaProfile(**base)
    assert legacy.stage_options == {} and legacy.assistant_version == "legacy"
    staged = OllamaProfile(**base, stage_options={"assistant-plan-v1": {"think": True}})
    assert staged.stage_options["assistant-plan-v1"].think is True
    with pytest.raises(ValueError):
        OllamaProfile(**base, stage_options={"shell.execute": {"think": True}})


def test_supplied_rate_cannot_be_applied_twice(broker):
    chat = install(broker, meaning("n0*n1*n2", operation="supplied", supplied_operand="n2"))
    result = chat.submit("40 tickets at 40 SGD each using supplied rate 0.75 USD per SGD")
    assert result.state == State.FAILED
    assert not broker.currency.provider.calls
    assert broker.currency.execution_calls == 0


def test_rate_question_is_corrected_before_asking_the_owner(broker):
    chat = install(broker, meaning("n0"))

    def mutate(request, reply):
        if (
            request.decision_boundary == "assistant-plan-v1"
            and sum(r.decision_boundary == "assistant-plan-v1" for r in broker.provider.requests)
            == 1
        ):
            return replace(
                reply,
                raw=b'{"kind":"clarify","question":"What is the exchange rate from SGD to USD?"}',
            )
        return reply

    broker.provider.mutate = mutate
    result = chat.submit("40 SGD in USD")
    assert result.state == State.SUCCEEDED
    assert len(broker.currency.provider.calls) == 1
    assert broker.model_turns == 6


def test_unsupported_reason_remains_visible_in_natural_chat(broker):
    chat = install(broker, {"kind": "unsupported", "message": "Purchases are unavailable."})
    result = chat.submit("Buy the tickets and charge my card")
    assert result.state == State.FAILED
    assert conversational_text(result) == "Purchases are unavailable."
    assert not broker.currency.provider.calls


def test_complete_new_purchase_does_not_inherit_previous_amount(broker):
    def plan(data):
        if len(data["current_operands"]) == 2:
            return meaning("n0*n1")
        assert data["previous_amount"] is None
        assert data["previous_expression"] is None
        assert data["followup_operands"] == {}
        return meaning("(n0*n1*(1-n2/100)+n3)/n4")

    chat = install(broker, plan)
    assert chat.submit("40 tickets at 40 SGD each in USD").state == State.SUCCEEDED
    result = chat.submit(
        "20 tickets at 30 SGD each, 10% discount then 20 SGD fee, split among 4 in USD"
    )
    assert result.state == State.SUCCEEDED
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert Decimal(args.amount) == Decimal("140")


def test_incorrect_plan_review_repairs_before_any_retrieval(broker):
    chat = install(broker, meaning("n0+n1"))

    def mutate(request, reply):
        if request.decision_boundary == "assistant-check-v1":
            data = json.loads(request.messages[-2].text)
            if data["computed_arguments"]["amount"] == "55":
                assert broker.currency.execution_calls == 0
                return replace(
                    reply,
                    raw=json.dumps(
                        {
                            "kind": "calculation_check",
                            "supported": False,
                            "issue": "incorrect_plan",
                            "question": "Multiply quantity by price instead of adding them.",
                        }
                    ).encode(),
                )
        if (
            request.decision_boundary == "assistant-plan-v1"
            and "REJECTED" in request.messages[0].text
        ):
            return replace(reply, raw=json.dumps(meaning("n0*n1")).encode())
        return reply

    broker.provider.mutate = mutate
    result = chat.submit("20 tickets at 35 SGD each in USD")
    assert result.state == State.SUCCEEDED
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert args.amount == "700"
    assert broker.currency.execution_calls == 1


def test_quote_evidence_and_reverse_rate_keep_controller_scope(broker):
    chat = install(broker, meaning("n0"))
    assert chat.submit("100 SGD in USD").state == State.SUCCEEDED
    before = len(broker.currency.provider.calls)
    result = chat.submit("When was that rate published, and where did it come from?")
    assert result.state == State.SUCCEEDED
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert args.operation == "source"
    assert len(broker.currency.provider.calls) == before
    result = chat.submit("What's the reverse rate?")
    assert result.state == State.SUCCEEDED
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert (args.base, args.quote, args.amount) == ("USD", "SGD", None)


def test_missing_amount_retains_explicit_pair_for_numeric_reply(broker):
    def plan(data):
        values = data["current_operands"]
        return meaning(next(iter(values), "n0"), use_context=bool(data["currency_context"]))

    chat = install(broker, plan)
    assert chat.submit("Convert SGD to USD").state == State.WAITING_INPUT
    assert not broker.currency.provider.calls
    result = chat.submit("2000")
    assert result.state == State.SUCCEEDED
    args = CurrencyArguments.model_validate_json(broker.store.get(result.task_id).scope.window_ref)
    assert (args.base, args.quote, args.amount) == ("SGD", "USD", "2000")


def test_explicit_new_pair_clears_old_context_and_ambiguous_symbol_cannot_inherit(broker):
    def plan(data):
        if "EUR" in data["owner_request"]:
            assert data["currency_context"] is None
            assert data["previous_amount"] is None
            return meaning("n0", base="EUR", quote="USD")
        return meaning("n0", use_context=bool(data["currency_context"]))

    chat = install(broker, plan)
    assert chat.submit("100 SGD in USD").state == State.SUCCEEDED
    assert chat.submit("50 EUR to USD").state == State.SUCCEEDED
    before = len(broker.currency.provider.calls)
    result = chat.submit("Convert $100 to USD")
    assert result.state == State.WAITING_INPUT
    assert len(broker.currency.provider.calls) == before


def test_historical_and_multiple_pairs_cannot_be_silently_replaced(broker):
    chat = install(broker, meaning("n0", base="EUR"))
    result = chat.submit("Convert 100 EUR to USD on 2020-01-01")
    assert result.state == State.FAILED and result.decision_kind == "unsupported"
    assert not broker.provider.requests
    broker.provider.meaning = meaning(None, base="USD", quote="MYR")
    assert chat.submit("USD to MYR and EUR to USD").state == State.WAITING_INPUT
    assert not broker.currency.provider.calls


@pytest.mark.parametrize("repair_fails", [False, True])
def test_output_limit_repair_has_one_attempt_before_effects(broker, repair_fails):
    def mutate(request, reply):
        boundary = request.decision_boundary
        if boundary == "assistant-plan-v1" or (boundary == "assistant-repair-v1" and repair_fails):
            assert broker.currency.execution_calls == 0
            raise ProviderError("INVALID_RESPONSE", output_limit=True)
        return reply

    chat = install(broker, meaning("n0"), mutate)
    result = chat.submit("40 SGD in USD")
    assert result.state == (State.FAILED if repair_fails else State.SUCCEEDED)
    assert sum(r.decision_boundary == "assistant-repair-v1" for r in broker.provider.requests) == 1
    assert broker.model_turns == (3 if repair_fails else 6)
    assert broker.currency.execution_calls == (0 if repair_fails else 1)


@pytest.mark.parametrize("interrupt", ["cancel", "revision", "transport"])
def test_plan_repair_cannot_bypass_cancellation_revision_or_transport(broker, interrupt):
    def mutate(request, reply):
        if request.decision_boundary == "assistant-plan-v1":
            if interrupt == "cancel":
                broker.store.cancel(request.task_id)
            elif interrupt == "revision":
                broker.store.revise(request.task_id)
            raise ProviderError(
                "RUNTIME_UNAVAILABLE" if interrupt == "transport" else "INVALID_RESPONSE",
                output_limit=interrupt != "transport",
            )
        return reply

    chat = install(broker, meaning("n0"), mutate)
    result = chat.submit("40 SGD in USD")
    assert result.state == (State.CANCELLED if interrupt == "cancel" else State.FAILED)
    assert not any(r.decision_boundary == "assistant-repair-v1" for r in broker.provider.requests)
    assert broker.currency.execution_calls == 0
    assert not broker.currency.provider.calls


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({}, True),
        ({"model": "different"}, False),
        ({"done": False}, False),
        ({"message": {"role": "assistant", "content": "", "tool_calls": [{}]}}, False),
    ],
)
def test_only_valid_local_envelope_marks_output_limit(extra, expected):
    from pathlib import Path

    from jarvis.bootstrap import ManualClock, load_profile
    from jarvis.models import Message, ModelRequest
    from jarvis.ollama import OllamaProvider

    profile = load_profile(Path("config/examples/assistant.toml"), allow_ollama=True).model_copy(
        update={"cloud_disabled_verified": True, "cloud_disabled_evidence": "Synthetic fixture"}
    )
    runtime = Runtime(profile)
    runtime.show["model_info"]["synthetic.context_length"] = profile.context_tokens
    runtime.response_update = {"done_reason": "length", **extra}
    clock = ManualClock()
    provider = OllamaProvider(clock, httpx.MockTransport(runtime.handle))
    request = ModelRequest(
        "request",
        "task",
        0,
        profile,
        {},
        clock.now() + 30,
        (Message("owner", "fixture"),),
        decision_boundary="assistant-plan-v1",
    )
    try:
        with pytest.raises(ProviderError) as error:
            provider.generate(request, lambda: False)
        assert error.value.code == "INVALID_RESPONSE"
        assert error.value.output_limit is expected
    finally:
        provider.close()


def test_web_summary_bound_to_retrieved_excerpts(stack):
    broker, chat, old, search, fetch = stack
    broker.profile = broker.profile.model_copy(update={"assistant_version": "assistant-v1"})

    def mutate(request, value):
        boundary = request.decision_boundary
        if boundary == "assistant-plan-v1":
            return {"kind": "research"}
        data = json.loads(request.messages[-1].text)
        if boundary == "web-summary-v1":
            e = data["untrusted_evidence"][0]
            return {
                "kind": "research_summary",
                "claims": [
                    {
                        "text": "Version 3.0 was released.",
                        "source_id": e["source_id"],
                        "excerpt_index": e["excerpt_index"],
                    }
                ],
            }
        if boundary == "web-summary-check-v1":
            return {"kind": "summary_check", "supported": True}
        return value

    broker.provider = SemanticWebModel(mutate)
    result = chat.submit("Search for the public project's release")
    assert result.state == State.SUCCEEDED, result
    assert conversational_text(result) == "Version 3.0 was released."
    assert broker.model_turns == 6
    assert len(search.calls) <= broker.web.config.max_searches
    assert broker.desktop.execution_calls == 0


@pytest.mark.parametrize("preserve_metric", [False, True])
def test_popularity_metric_cannot_become_world_ranking(stack, preserve_metric):
    broker, chat, old, search, fetch = stack
    broker.profile = broker.profile.model_copy(update={"assistant_version": "assistant-v1"})
    original = fetch.fetch

    def page(*args):
        data, receipt = original(*args)
        data["chunks"] = (
            "Athlete is a Malaysian badminton player. In this site's popularity ranking, "
            "Athlete is the 81st most popular badminton player.",
        )
        return data, receipt

    fetch.fetch = page

    def mutate(request, value):
        if request.decision_boundary == "web-summary-v1":
            evidence = json.loads(request.messages[-1].text)["untrusted_evidence"][0]
            binding = {
                "source_id": evidence["source_id"],
                "excerpt_index": evidence["excerpt_index"],
            }
            return {
                "kind": "research_summary",
                "claims": [
                    {**binding, "text": "Athlete is a Malaysian badminton player."},
                    {
                        **binding,
                        "text": "Athlete is the 81st most popular badminton player."
                        if preserve_metric
                        else "Athlete ranks 81 in the world.",
                    },
                ],
            }
        if request.decision_boundary == "web-summary-check-v1":
            # Even an over-permissive model review must not erase a known metric.
            return {"kind": "summary_check", "supported": True}
        return value

    broker.provider = SemanticWebModel(mutate)
    result = chat.submit("Search for Athlete's biography")
    assert result.state == State.SUCCEEDED
    answer = conversational_text(result)
    assert "Malaysian badminton player" in answer
    assert "ranks 81 in the world" not in answer
    assert ("81st most popular" in answer) == preserve_metric
    assert len(broker.web.summary.claims) == (2 if preserve_metric else 1)


def test_classifier_cannot_send_recognized_conversion_amounts_to_search(stack):
    broker, chat, old, search, fetch = stack
    broker.profile = broker.profile.model_copy(update={"assistant_version": "assistant-v1"})
    broker.provider = SemanticWebModel()  # Proposes research even for a conversion.
    result = chat.submit("Convert 1234 SGD to USD")
    assert result.state == State.FAILED
    assert not search.calls and not fetch.calls
    assert broker.desktop.execution_calls == 0


@pytest.mark.parametrize(
    "owner", ["Search http://127.0.0.1:11434/", "Search my API key secret_token"]
)
def test_private_query_never_reaches_search(stack, owner):
    broker, chat, old, search, fetch = stack
    broker.profile = broker.profile.model_copy(update={"assistant_version": "assistant-v1"})
    broker.provider = SemanticWebModel(
        lambda r, v: {"kind": "research"} if r.decision_boundary == "assistant-plan-v1" else v
    )
    assert chat.submit(owner).state == State.FAILED
    assert not search.calls and not fetch.calls
