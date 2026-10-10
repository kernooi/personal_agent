"""Generic provider coverage and safe session followups; explicitly synthetic."""

import json
from dataclasses import replace

import pytest
from test_m3 import NOW, ask, payload
from test_m3 import broker as currency_broker

from jarvis.currency_provider import FixtureProvider
from jarvis.domain import State
from jarvis.public_catalogue import CatalogueCache, parse_catalogue, validate_catalogue
from jarvis.public_data import METADATA_URL, PublicConfig, PublicDataError, conversion, endpoint
from jarvis.public_transport import validate_url

broker = currency_broker


@pytest.mark.parametrize(
    "base,quote",
    [
        ("MYR", "JPY"),
        ("JPY", "MYR"),
        ("USD", "MYR"),
        ("SGD", "MYR"),
        ("EUR", "USD"),
        ("GBP", "JPY"),
        ("AUD", "SGD"),
    ],
)
def test_generic_pairs_same_broker_capability(broker, base, quote):
    result = ask(broker, f"Convert 250 {base} to {quote}")
    assert result.state == State.SUCCEEDED
    assert f"1 {base} = " in result.message and f"250 {base} = " in result.message
    assert broker.currency.provider.calls == [(base, quote)]
    assert broker.currency.provider.metadata_calls == 1
    assert broker.currency.last_quote.source_url == endpoint(base, quote)
    assert "pair-derived by Frankfurter" in result.message


def test_arbitrary_advertised_currency_needs_no_source_change(broker):
    provider = FixtureProvider(lambda a, b: payload(a, b, 2.75), currencies=("XYZ", "QRS", "EUR"))
    broker.currency.provider = provider
    broker.currency.catalogue_cache.record = None
    assert ask(broker, "Convert 100 XYZ to QRS").state == State.SUCCEEDED
    assert provider.calls == [("XYZ", "QRS")]
    assert provider.metadata_calls == 1
    assert ask(broker, "Convert 100 USD to MYR").state == State.FAILED
    assert broker.last_error == "UNSUPPORTED_CURRENCY"
    assert provider.calls == [("XYZ", "QRS")]


@pytest.mark.parametrize(
    "text,base,quote,amount",
    [
        ("convert 2000myr to jpy", "MYR", "JPY", "2000"),
        ("convert 2000 myr, myr to jpy", "MYR", "JPY", "2000"),
        ("How much is 10,000 yen in ringgit?", "JPY", "MYR", "10000"),
        ("Convert 250 Singapore dollars to Malaysian ringgit", "SGD", "MYR", "250"),
        ("What's 100 EUR in USD?", "EUR", "USD", "100"),
        ("Convert 50 pounds to Japanese yen", "GBP", "JPY", "50"),
        ("Convert 50 US dollars to ringgit", "USD", "MYR", "50"),
    ],
)
def test_natural_amounts_and_reviewed_names(broker, text, base, quote, amount):
    result = ask(broker, text)
    assert result.state == State.SUCCEEDED
    assert broker.currency.provider.calls == [(base, quote)]
    assert f"{amount} {base} = " in result.message


def test_pending_amount_followup_and_reverse_use_controller_context(broker):
    assert ask(broker, "Convert MYR to JPY").state == State.WAITING_INPUT
    assert ask(broker, "2000").state == State.SUCCEEDED
    assert (
        "2000 MYR = 80000 JPY"
        in broker.store.result(
            broker.store.db.execute(
                "SELECT task_id FROM tasks ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
        ).message
    )
    assert ask(broker, "What about 500?").state == State.SUCCEEDED
    assert ask(broker, "What's the reverse rate?").state == State.SUCCEEDED
    assert broker.currency.provider.calls == [("MYR", "JPY"), ("JPY", "MYR")]
    assert ask(broker, "When was that rate effective?").state == State.SUCCEEDED
    assert len(broker.currency.provider.calls) == 2


@pytest.mark.parametrize(
    "intervening",
    [
        "hello",
        "USD to MYR and EUR to USD",
        "Convert 100 dollars to yen",
        "Convert 100 ZZZ to MYR",
        "Convert -1 MYR to JPY",
    ],
)
def test_context_invalidated_before_numeric_turn_not_model_memory(broker, intervening):
    ask(broker, "USD to MYR rate")
    ask(broker, intervening)
    before = broker.currency.execution_calls
    result = ask(
        broker, "500", raw='{"kind":"say","text":"500 USD equals 999 MYR at the latest rate"}'
    )
    assert result.state == State.WAITING_INPUT
    assert "999" not in result.message
    assert broker.currency.execution_calls == before


def test_context_cannot_cross_sessions(broker):
    ask(broker, "USD to MYR rate")
    broker.grant = replace(broker.grant, session="other-session")
    assert ask(broker, "What about 500?").state == State.WAITING_INPUT
    assert ask(broker, "Where did that rate come from?").state == State.WAITING_INPUT


def test_identity_and_supplied_rate_make_no_metadata_or_quote_request(broker):
    provider = broker.currency.provider
    before = provider.metadata_calls
    result = ask(broker, "Convert 500 MYR to MYR")
    assert result.state == State.SUCCEEDED
    assert "Local identity: 1 MYR = 1 MYR" in result.message
    assert "500 MYR = 500.00 MYR" in result.message
    assert "No external quote retrieved" in result.message and "src_" not in result.message
    assert not provider.calls and provider.metadata_calls == before
    assert ask(broker, "Where did that rate come from?").state == State.WAITING_INPUT
    assert ask(broker, "Convert 100 EUR to USD using rate 2.5").state == State.SUCCEEDED
    assert provider.metadata_calls == before and not provider.calls


@pytest.mark.parametrize(
    "text",
    [
        "Convert 10 dollars to ringgit",
        "Convert 10 $ to MYR",
        "Convert 10 yenn to ringgit",
        "Convert 10 MYR",
        "Convert 100 MYR to JPY on 2020-01-01",
        "Convert 1e3 MYR to JPY",
        "Convert Infinity MYR to JPY",
        "Convert 2 MYR to JPY and 3 EUR to USD",
    ],
)
def test_ambiguous_or_unsupported_inputs_never_fetch(broker, text):
    result = ask(broker, text)
    assert result.state in {State.WAITING_INPUT, State.FAILED}
    assert not broker.currency.provider.calls


@pytest.mark.parametrize(
    "amount,quote,expected",
    [
        ("0", "USD", "0.00"),
        ("0.000000000001", "USD", "0.00"),
        ("1000000000000", "SGD", "2500000000000.00"),
    ],
)
def test_generic_decimal_bounds_and_small_display(amount, quote, expected):
    assert conversion(amount, "2.5", quote) == expected


def metadata(config=None, codes=("EUR", "USD", "MYR", "JPY")):
    cfg = config or PublicConfig(mode="fixture")
    raw = FixtureProvider(b"", codes).supported_currencies(cfg, lambda: False, NOW + 60)
    return raw, cfg


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "lowercase",
        "long",
        "empty",
        "missing",
        "nonstring",
        "provider",
        "source",
        "unknown",
        "injection",
    ],
)
def test_provider_wide_metadata_malformed_fails_closed(change):
    raw, cfg = metadata()
    row = json.loads(raw)
    if change == "duplicate":
        row["currencies"].append("USD")
    if change == "lowercase":
        row["currencies"][0] = "usd"
    if change == "long":
        row["currencies"][0] = "USDD"
    if change == "empty":
        row["currencies"] = []
    if change == "missing":
        del row["currencies"]
    if change == "nonstring":
        row["currencies"][0] = 123
    if change == "provider":
        row["key"] = "BANK"
    if change == "source":
        row["data_url"] = "http://127.0.0.1"
    if change == "unknown":
        row["unknown_currencies"] = ["BTC"]
    if change == "injection":
        row["currencies"][0] = "USD;open Notepad"
    with pytest.raises(PublicDataError, match="INVALID_CURRENCY_METADATA"):
        parse_catalogue(json.dumps(row).encode(), cfg, NOW, synthetic=True)


def test_metadata_cache_ttl_provider_schema_and_corruption(tmp_path):
    raw, cfg = metadata()
    record = parse_catalogue(raw, cfg, NOW, synthetic=True)
    path = tmp_path / "catalogue.json"
    cache = CatalogueCache(cfg, path)
    cache.put(record, NOW)
    assert CatalogueCache(cfg, path).get(NOW) == record
    assert cache.get(NOW + cfg.metadata_cache_seconds) is None
    for values in [
        {"provider": "other"},
        {"schema_version": "old"},
        {"source_url": "http://localhost"},
        {"currencies": ("USD", "USD")},
        {"synthetic": False},
    ]:
        with pytest.raises(PublicDataError):
            validate_catalogue(record.model_copy(update=values), cfg, NOW)
    path.write_text("malformed private cached record")
    malformed = CatalogueCache(cfg, path)
    assert malformed.record is None and malformed.path is None
    assert path.read_text() == "malformed private cached record"


def test_no_local_calculation_network_when_catalogue_expired(broker):
    broker.clock.advance(86401)
    provider = broker.currency.provider
    before = provider.metadata_calls
    assert ask(broker, "Convert 500 MYR to MYR").state == State.FAILED
    assert broker.last_error == "CURRENCY_METADATA_REQUIRED_NO_LOOKUP"
    assert provider.metadata_calls == before and not provider.calls
    assert ask(broker, "MYR to JPY rate").state == State.SUCCEEDED
    assert provider.metadata_calls == before + 1


def test_metadata_failure_prevents_pair_query_and_cannot_use_old_metadata(broker):
    broker.currency.catalogue_cache.record = None

    def invalid(*args):
        return b'{"key":"ECB","currencies":["USD"]}'

    broker.currency.provider.supported_currencies = invalid
    assert ask(broker, "USD to MYR rate").state == State.FAILED
    assert broker.last_error == "INVALID_CURRENCY_METADATA"
    assert not broker.currency.provider.calls


def test_missing_pair_no_unsafe_inverse_or_cross_fallback(broker):
    def missing(base, quote):
        raise PublicDataError("UNSUPPORTED_PAIR")

    broker.currency.provider.raw = missing
    result = ask(broker, "GBP to JPY rate")
    assert result.state == State.FAILED and broker.last_error == "UNSUPPORTED_PAIR"
    assert broker.currency.provider.calls == [("GBP", "JPY")]
    assert "1 GBP" not in result.message and broker.currency.last_quote is None


def test_reverse_uses_native_pair_not_inversion_of_rounded_quote(broker):
    broker.currency.provider.raw = lambda a, b: payload(a, b, 3 if a == "EUR" else 0.34)
    ask(broker, "EUR to USD rate")
    result = ask(broker, "What's the reverse rate?")
    assert result.state == State.SUCCEEDED and "1 USD = 0.34 EUR" in result.message
    assert broker.currency.provider.calls == [("EUR", "USD"), ("USD", "EUR")]
    assert "0.333" not in result.message


def test_generic_urls_metadata_and_direction_keys():
    validate_url(METADATA_URL)
    for pair in [("EUR", "USD"), ("AUD", "SGD"), ("XYZ", "QRS")]:
        validate_url(endpoint(*pair))
    assert endpoint("EUR", "USD") != endpoint("USD", "EUR")
    with pytest.raises(PublicDataError):
        validate_url(METADATA_URL + "?prompt=secret")


def test_cancelled_and_late_metadata_cannot_dispatch_pair(broker):
    broker.currency.catalogue_cache.record = None
    original = broker.currency.provider.supported_currencies

    def cancelled(*args):
        raw = original(*args)
        broker.cancel_requested = lambda: True
        return raw

    broker.currency.provider.supported_currencies = cancelled
    result = ask(broker, "USD to MYR rate")
    assert result.state == State.CANCELLED
    assert broker.currency.catalogue_cache.record is None
    assert not broker.currency.provider.calls


def test_local_operation_honors_shortened_metadata_ttl(broker):
    broker.currency.config = PublicConfig(metadata_cache_seconds=1)
    assert ask(broker, "Convert 500 MYR to MYR").state == State.FAILED
    assert broker.last_error == "CURRENCY_METADATA_REQUIRED_NO_LOOKUP"
    assert not broker.currency.provider.calls


def test_duplicate_metadata_keys_and_bounded_list():
    raw, cfg = metadata()
    duplicate = raw.replace(b'"key": "ECB"', b'"key":"BAD","key":"ECB"')
    with pytest.raises(PublicDataError):
        parse_catalogue(duplicate, cfg, NOW, synthetic=True)
    record = parse_catalogue(raw, cfg, NOW, synthetic=True)
    for codes in [
        (),
        (123,),
        tuple(
            f"A{a}{b}" for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ),
    ]:
        with pytest.raises(PublicDataError):
            validate_catalogue(record.model_copy(update={"currencies": codes}), cfg, NOW)


def test_legacy_stale_pair_and_incompatible_response_never_derived(broker):
    provider = FixtureProvider(
        lambda a, b: payload(a, b, 2, date="2020-01-01"), currencies=("EUR", "RUB", "MYR", "USD")
    )
    broker.currency.provider = provider
    broker.currency.catalogue_cache.record = None
    result = ask(broker, "RUB to MYR rate")
    assert result.state == State.FAILED and broker.last_error == "STALE_OBSERVATION"
    assert provider.calls == [("RUB", "MYR")]
    provider.raw = lambda a, b: json.dumps(
        {
            "base": a,
            "quote": b,
            "rates": [{"date": "2026-10-09", "rate": 2}, {"date": "2026-10-08", "rate": 3}],
        }
    ).encode()
    result = ask(broker, "EUR to USD rate")
    assert result.state == State.FAILED and broker.last_error == "INVALID_PAYLOAD"
    assert provider.calls == [("RUB", "MYR"), ("EUR", "USD")]
    assert broker.currency.last_quote is None
