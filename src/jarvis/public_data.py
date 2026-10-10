"""Reviewed public-data policy, normalized evidence and decimal calculations."""

import json
import re
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field

from jarvis.models import StrictRecord, reject_constant, unique_object

VERSION = "frankfurter-ecb-v2"
HOST = "api.frankfurter.dev"
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
METADATA_URL = f"https://{HOST}/v2/providers/ecb"
SOURCE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"


class PublicDataError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PublicConfig(StrictRecord):
    mode: Literal["disabled", "fixture", "enabled"] = "disabled"
    provider: Literal["frankfurter_ecb"] = "frankfurter_ecb"
    display_timezone: Literal["Asia/Kuala_Lumpur"] = "Asia/Kuala_Lumpur"
    timeout_seconds: float = Field(default=12.0, ge=1, le=20)
    max_response_bytes: int = Field(default=8192, ge=256, le=16384)
    cache_seconds: int = Field(default=3600, ge=0, le=86400)
    max_observation_days: int = Field(default=7, ge=1, le=14)
    stale_cache_seconds: int = Field(default=86400, ge=0, le=604800)
    allow_stale_cache: bool = False
    max_cache_entries: int = Field(default=8, ge=1, le=32)
    metadata_cache_seconds: int = Field(default=86400, ge=1, le=604800)


class CurrencyArguments(StrictRecord):
    base: CurrencyCode
    quote: CurrencyCode
    amount: str | None = Field(default=None, max_length=40)
    operation: Literal["latest", "supplied", "source", "identity"] = "latest"
    supplied_rate: str | None = Field(default=None, max_length=40)
    refresh: bool = False


def number(value, *, rate=False):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise PublicDataError("INVALID_RATE" if rate else "INVALID_AMOUNT")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise PublicDataError("INVALID_AMOUNT") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1000000000000"):
        raise PublicDataError("INVALID_AMOUNT")
    if rate and result <= 0:
        raise PublicDataError("INVALID_RATE")
    if len(result.as_tuple().digits) > 24 or result.as_tuple().exponent < -12:
        raise PublicDataError("EXCESS_PRECISION")
    return result


def canonical(arguments):
    values = arguments.model_dump()
    if arguments.refresh and arguments.operation != "latest":
        raise PublicDataError("INVALID_REFRESH")
    if arguments.operation == "source" and arguments.amount is not None:
        raise PublicDataError("INVALID_SOURCE_ARGUMENT")
    if values["amount"] is not None:
        values["amount"] = format(number(values["amount"]).normalize(), "f")
    if (arguments.base == arguments.quote) != (arguments.operation == "identity"):
        raise PublicDataError("INVALID_IDENTITY_OPERATION")
    if arguments.operation == "supplied":
        if arguments.supplied_rate is None:
            raise PublicDataError("MISSING_RATE")
        values["supplied_rate"] = format(
            number(arguments.supplied_rate, rate=True).normalize(), "f"
        )
    elif arguments.supplied_rate is not None:
        raise PublicDataError("UNEXPECTED_RATE")
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def endpoint(base, quote):
    if (
        not all(isinstance(c, str) and re.fullmatch(r"[A-Z]{3}", c) for c in (base, quote))
        or base == quote
    ):
        raise PublicDataError("UNSUPPORTED_PAIR")
    return f"https://{HOST}/v2/providers/ecb/rate/{base.lower()}/{quote.lower()}"


class Quote(StrictRecord):
    source_id: str = Field(pattern=r"^src_[0-9a-f]{32}$")
    adapter_version: Literal["frankfurter-ecb-v2"] = VERSION
    provider: Literal["Frankfurter v2 / ECB"] = "Frankfurter v2 / ECB"
    provenance: Literal["ECB reference rates, served and pair-derived by Frankfurter"] = (
        "ECB reference rates, served and pair-derived by Frankfurter"
    )
    source_url: str
    original_source_url: Literal[SOURCE] = SOURCE
    base: CurrencyCode
    quote: CurrencyCode
    rate: str
    unit_base: Literal[1] = 1
    basis: Literal["daily reference estimate; provider-derived pair"] = (
        "daily reference estimate; provider-derived pair"
    )
    effective_date: str
    effective_precision: Literal["date"] = "date"
    retrieved_at_utc: str
    expires_at_utc: str
    freshness: Literal["latest_available_daily", "dated_stale"]
    validation: Literal["validated"] = "validated"
    sensitivity: Literal["public", "synthetic"] = "public"


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def validate_quote(quote, config, now, *, permit_old=False):
    if quote.source_url != endpoint(quote.base, quote.quote):
        raise PublicDataError("SOURCE_MISMATCH")
    number(quote.rate, rate=True)
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", quote.effective_date):
            raise ValueError("Not a date-only ISO observation")
        effective = date.fromisoformat(quote.effective_date)
        fetched = datetime.fromisoformat(quote.retrieved_at_utc)
        expires = datetime.fromisoformat(quote.expires_at_utc)
        if fetched.utcoffset() != timedelta(0) or expires.utcoffset() != timedelta(0):
            raise ValueError("Not UTC")
        if fetched.timestamp() > now + 1 or expires < fetched:
            raise ValueError("Invalid retrieval time")
        if (expires - fetched).total_seconds() > config.cache_seconds:
            raise ValueError("Invalid cache lifetime")
    except ValueError as exc:
        raise PublicDataError("INVALID_DATE") from exc
    age = (datetime.fromtimestamp(now, UTC).date() - effective).days
    if age < 0:
        raise PublicDataError("FUTURE_DATE")
    if age > config.max_observation_days and not permit_old:
        raise PublicDataError("STALE_OBSERVATION")
    return quote


def parse_quote(raw, base, quote, config, now, *, synthetic=False):
    if len(raw) > config.max_response_bytes:
        raise PublicDataError("OVERSIZED_PAYLOAD")
    try:
        row = json.loads(
            raw,
            parse_float=Decimal,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        if not isinstance(row, dict) or set(row) != {"date", "base", "quote", "rate"}:
            raise ValueError("Unexpected fields")
        if row["base"] != base or row["quote"] != quote:
            raise PublicDataError("PAIR_MISMATCH")
        if isinstance(row["rate"], bool) or not isinstance(row["rate"], (Decimal, int)):
            raise ValueError("Invalid rate type")
        numeric = Decimal(row["rate"])
        if (
            not numeric.is_finite()
            or numeric <= 0
            or numeric > Decimal("1000000000000")
            or len(numeric.as_tuple().digits) > 24
            or numeric.as_tuple().exponent < -12
        ):
            raise PublicDataError("INVALID_RATE")
        rate = format(numeric, "f")
        observation = Quote(
            source_id="src_" + uuid4().hex,
            source_url=endpoint(base, quote),
            base=base,
            quote=quote,
            rate=rate,
            effective_date=row["date"],
            retrieved_at_utc=utc(now),
            expires_at_utc=utc(now + config.cache_seconds),
            freshness="latest_available_daily",
            sensitivity="synthetic" if synthetic else "public",
        )
        return validate_quote(observation, config, now)
    except PublicDataError:
        raise
    except (ValueError, TypeError, KeyError, InvalidOperation, RecursionError) as exc:
        raise PublicDataError("INVALID_PAYLOAD") from exc


def conversion(amount, rate, quote):
    with localcontext() as context:
        context.prec = 64  # Two accepted 24-digit inputs need up to 48 exact product digits.
        result = number(amount) * number(rate, rate=True)
        return format(
            result.quantize(
                Decimal("1") if quote == "JPY" else Decimal("0.01"), rounding=ROUND_HALF_EVEN
            ),
            "f",
        )


def render(arguments, observation=None, *, status="live", failure=None):
    if arguments.operation == "identity":
        rate = "1"
        text = (
            f"Local identity: 1 {arguments.base} = 1 {arguments.quote}. "
            "No external quote retrieved."
        )
    elif arguments.operation == "supplied":
        rate = format(number(arguments.supplied_rate, rate=True).normalize(), "f")
        text = (
            f"User-supplied rate: 1 {arguments.base} = {rate} {arguments.quote}. "
            "No internet lookup."
        )
    else:
        if observation is None:
            raise PublicDataError("UNKNOWN_CITATION")
        rate = observation.rate
        fetched = datetime.fromisoformat(observation.retrieved_at_utc)
        display = fetched.astimezone(timezone(timedelta(hours=8), "Asia/Kuala_Lumpur")).isoformat()
        text = (
            f"[{status.upper()}] Latest available daily reference rate: "
            f"1 {arguments.base} = {rate} {arguments.quote}.\n"
            f"Source-effective date: {observation.effective_date} "
            "(date only; publication time unavailable).\n"
            f"Retrieved: {observation.retrieved_at_utc} UTC ({display}, Asia/Kuala_Lumpur).\n"
            f"Source [{observation.source_id}]: {observation.provider}; {observation.provenance}.\n"
            f"{observation.source_url}\nOriginal source: {observation.original_source_url}\n"
        )
        if status == "stale cache":
            text = text.replace(
                "Latest available daily reference rate", "Dated cached reference rate"
            )
            text += f"A new quote could not be checked ({failure}); not verified current.\n"
        if arguments.operation == "source":
            text = text.replace(
                "Latest available daily reference rate", "Recorded daily reference rate"
            )
        if status == "dated session evidence":
            text += "This is previously recorded evidence, not verified current.\n"
    if arguments.amount is not None and arguments.operation != "source":
        converted = conversion(arguments.amount, rate, arguments.quote)
        text += f"\n{arguments.amount} {arguments.base} = {converted} {arguments.quote}."
    return (
        text + "\nReference estimate only; bank/card/cash rates and fees may differ. "
        "No transaction performed."
    )
