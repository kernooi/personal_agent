"""Optional currency routing never captures unrelated chat or controller requests."""

import pytest
from test_m3 import ask
from test_m3 import broker as currency_broker

from jarvis.conversation import Conversation
from jarvis.currency_router import route
from jarvis.domain import State

broker = currency_broker

NON_CURRENCY = [
    "how much potential muscle gain did i lose by sleeping 6 hours instead of 8",
    "How much protein do I need?",
    "How much RAM does my PC have?",
    "How much muscle in pounds can I gain?",
    "Convert 7 hours to minutes",
    "Convert 50 pounds to kg",
    "How to fix my mouse?",
    "What about sleeping 8 hours?",
    "What about the moon?",
    "I'm not asking about a currency question",
    "This is not a currency question",
    "Stop asking me about currency",
    "Why did you reply Please specify one source and one destination currency, such as USD to MYR?",
    "Explain what MYR and JPY stand for",
    "What is currency?",
    "Why do exchange rates change?",
    "Don't convert 100 USD to MYR",
    "I didn't ask you to convert USD to MYR",
    "What is the total for 40 tickets at 40 each?",
]


@pytest.mark.parametrize("text", NON_CURRENCY)
def test_non_currency_text_is_ordinary_even_after_a_conversion(text):
    assert route(text).kind == "ordinary"
    assert route(text, context=("USD", "MYR")).kind == "ordinary"


def test_reported_loop_exits_and_never_fetches_or_asks_for_a_pair(broker):
    chat = Conversation(broker)
    for text in [NON_CURRENCY[0], NON_CURRENCY[9], "I'm asking a question", NON_CURRENCY[12]]:
        result = chat.submit(text)
        assert result.state == State.ANSWERED
        assert "specify" not in result.message.casefold()
        assert broker.registry.context is None
        assert broker.currency.provider.calls == []
    assert broker.currency.execution_calls == 0


@pytest.mark.parametrize("first", ["Convert USD to MYR", "Convert 100 USD to MYR"])
@pytest.mark.parametrize("unrelated", NON_CURRENCY[:13])
def test_pending_or_completed_conversion_is_released_by_a_new_topic(broker, first, unrelated):
    ask(broker, first)
    assert broker.registry.context == ("USD", "MYR")
    before = len(broker.currency.provider.calls)
    result = ask(broker, unrelated)
    assert result.state == State.ANSWERED
    assert broker.registry.context is None and broker.currency.last_quote is None
    number = ask(broker, "500")
    assert number.state == State.WAITING_INPUT
    assert "currenc" not in number.message.casefold()
    assert len(broker.currency.provider.calls) == before


def test_explicit_conversion_still_works_after_corrections(broker):
    ask(broker, "I'm not asking about currency")
    assert ask(broker, "Convert 100 MYR to JPY").state == State.SUCCEEDED
    assert ask(broker, "What about 500?").state == State.SUCCEEDED
    assert broker.currency.provider.calls == [("MYR", "JPY")]


def test_rejected_app_request_still_ends_the_old_currency_topic(broker):
    from jarvis.application_data import ApplicationsConfig
    from jarvis.application_fake import FakeApplicationPlatform
    from jarvis.application_tools import attach

    ask(broker, "Convert USD to MYR")
    broker.assistant_memory = {"amount": "100", "session": broker.grant.session}
    platform = FakeApplicationPlatform()
    platform.add_app("Studio Note")
    chat = attach(broker, ApplicationsConfig(enabled=True), platform=platform)
    chat.submit("Open Studio Note")
    assert broker.registry.context is None and broker.assistant_memory is None
    before = broker.currency.execution_calls
    assert chat.submit("500").state == State.WAITING_INPUT
    assert broker.currency.execution_calls == before


@pytest.mark.parametrize("version", ["assistant-v1", "assistant-v2"])
def test_numeric_topic_change_cannot_inherit_semantic_currency_operands(broker, version):
    from test_assistant import install, install_fast, meaning

    chat = (install_fast if version == "assistant-v2" else install)(broker, meaning("n0"))
    assert chat.submit("Convert 100 SGD to USD").state == State.SUCCEEDED
    assert broker.assistant_memory is not None
    calls = broker.currency.execution_calls

    def ordinary(data):
        assert data["currency_context"] is None
        assert data["followup_operands"] == {}
        assert data["previous_amount"] is None
        return {"kind": "say", "text": "A precise loss cannot be inferred from sleep hours alone."}

    broker.provider.meaning = ordinary
    assert chat.submit(NON_CURRENCY[0]).state == State.ANSWERED
    assert broker.assistant_memory is None and broker.registry.context is None
    assert broker.currency.execution_calls == calls


def test_model_currency_misclassification_cannot_authorize_an_unrelated_lookup(broker):
    from test_assistant import install, meaning

    chat = install(broker, meaning())
    result = chat.submit(NON_CURRENCY[0])
    assert result.state == State.FAILED
    assert broker.currency.execution_calls == 0 and not broker.currency.provider.calls


def test_lowercase_generic_codes_can_use_provider_metadata_for_routing():
    routed = route("Convert 100 czk to huf", known_codes=("CZK", "HUF"))
    assert routed.kind == "currency"
    assert (routed.arguments.base, routed.arguments.quote) == ("CZK", "HUF")


def test_ordinary_question_schema_allows_explanation_without_tool_failure(broker):
    scope = broker.registry.scope_for(broker.grant.session, "How much RAM does my PC have?")
    schema = broker.registry.schema_for(scope)
    assert set(schema["discriminator"]["mapping"]) == {"say", "clarify"}
    scope = broker.registry.scope_for(broker.grant.session, "Type secret text into Notepad")
    assert "unsupported" in broker.registry.schema_for(scope)["discriminator"]["mapping"]
