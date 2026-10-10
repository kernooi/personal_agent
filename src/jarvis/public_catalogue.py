"""Validated provider-wide coverage, separate from pair availability and quote TTL."""

import json
import re
from datetime import datetime

from pydantic import Field

from jarvis.models import StrictRecord, reject_constant, unique_object
from jarvis.public_data import METADATA_URL, SOURCE, PublicDataError, utc


class Catalogue(StrictRecord):
    schema_version: str = Field(pattern=r"^ecb-currencies-v1$")
    provider: str = Field(pattern=r"^frankfurter_ecb$")
    source_url: str = Field(pattern=r"^https://api\.frankfurter\.dev/v2/providers/ecb$")
    currencies: tuple[str, ...] = Field(min_length=1, max_length=256)
    retrieved_at_utc: str
    expires_at_utc: str
    synthetic: bool = False


def validate_catalogue(record, config, now):
    if (
        record.schema_version != "ecb-currencies-v1"
        or record.provider != "frankfurter_ecb"
        or record.source_url != METADATA_URL
    ):
        raise PublicDataError("INVALID_CURRENCY_METADATA")
    codes = record.currencies
    if (
        not 1 <= len(codes) <= 256
        or any(not isinstance(c, str) or not re.fullmatch(r"[A-Z]{3}", c) for c in codes)
        or len(set(codes)) != len(codes)
    ):
        raise PublicDataError("INVALID_CURRENCY_METADATA")
    try:
        start = datetime.fromisoformat(record.retrieved_at_utc)
        end = datetime.fromisoformat(record.expires_at_utc)
        if start.utcoffset().total_seconds() or end.utcoffset().total_seconds():
            raise ValueError("Not UTC")
        if (
            start.timestamp() > now + 1
            or not 0 < (end - start).total_seconds() <= config.metadata_cache_seconds
        ):
            raise ValueError("Invalid TTL")
        if now >= end.timestamp():
            raise PublicDataError("EXPIRED_CURRENCY_METADATA")
        if record.synthetic != (config.mode == "fixture"):
            raise PublicDataError("CURRENCY_METADATA_MODE_MISMATCH")
    except (ValueError, AttributeError) as exc:
        if isinstance(exc, PublicDataError):
            raise
        raise PublicDataError("INVALID_CURRENCY_METADATA") from exc
    return record


def parse_catalogue(raw, config, now, *, synthetic=False):
    if len(raw) > config.max_response_bytes:
        raise PublicDataError("OVERSIZED_PAYLOAD")
    try:
        row = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        if (
            not isinstance(row, dict)
            or row.get("key") != "ECB"
            or row.get("name") != "European Central Bank"
            or row.get("rate_type") != "reference rate"
            or row.get("data_url") != SOURCE
            or row.get("pivot_currency") != "EUR"
            or row.get("unknown_currencies") != []
        ):
            raise ValueError("Unreviewed provider metadata")
        if not isinstance(row["currencies"], list):
            raise ValueError("Currency list required")
        record = Catalogue(
            schema_version="ecb-currencies-v1",
            provider="frankfurter_ecb",
            source_url=METADATA_URL,
            currencies=tuple(row["currencies"]),
            retrieved_at_utc=utc(now),
            expires_at_utc=utc(now + config.metadata_cache_seconds),
            synthetic=synthetic,
        )
        return validate_catalogue(record, config, now)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        if isinstance(exc, PublicDataError):
            raise
        raise PublicDataError("INVALID_CURRENCY_METADATA") from exc


class CatalogueCache:
    def __init__(self, config, path=None):
        self.config, self.path, self.record = config, path, None
        if path and path.exists():
            try:
                if path.stat().st_size > 16384:
                    raise ValueError("Oversized cache")
                row = json.loads(
                    path.read_bytes(),
                    object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )
                self.record = Catalogue.model_validate_json(json.dumps(row))
            except (ValueError, OSError, TypeError, RecursionError):
                self.path = None  # Preserve malformed existing evidence; do not overwrite it.

    def get(self, now):
        if self.record is not None:
            try:
                return validate_catalogue(self.record, self.config, now)
            except PublicDataError:
                return None
        return None

    def put(self, record, now):
        validate_catalogue(record, self.config, now)
        self.record = record
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(record.model_dump_json(), encoding="utf-8")
            temporary.replace(self.path)
