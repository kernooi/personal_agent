"""Controller-owned public research contracts. No model or desktop authority."""

import hashlib
import json
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from jarvis.models import StrictRecord
from jarvis.public_data import PublicDataError
from jarvis.public_transport import public_address


class WebError(PublicDataError):
    def __init__(self, code, *, downloaded_bytes=None):
        self.downloaded_bytes = downloaded_bytes
        super().__init__(code)


class WebConfig(StrictRecord):
    enabled: bool = False
    provider: str = Field(default="searxng", pattern=r"^[a-z][a-z0-9_-]{0,30}$")
    search_endpoint: str = "http://127.0.0.1:8080/search"
    local_search_authorized: bool = False
    max_searches: int = Field(default=2, ge=1, le=3)
    result_limit: int = Field(default=5, ge=1, le=10)
    max_pages: int = Field(default=3, ge=1, le=5)
    max_response_bytes: int = Field(default=524288, ge=4096, le=2097152)
    max_total_bytes: int = Field(default=1572864, ge=4096, le=5242880)
    max_text_chars: int = Field(default=12000, ge=1000, le=40000)
    max_model_turns: int = Field(default=4, ge=3, le=6)
    timeout_seconds: float = Field(default=12.0, gt=0, le=30)
    task_seconds: float = Field(default=100.0, gt=0, le=120)
    redirects: int = Field(default=2, ge=0, le=3)
    cache_seconds: int = Field(default=600, ge=0, le=3600)
    timezone: str = "Asia/Kuala_Lumpur"

    @model_validator(mode="after")
    def endpoint_policy(self):
        # The infrastructure exception is exclusively this configured search API.
        p = urlsplit(self.search_endpoint)
        if (
            p.scheme != "http"
            or p.hostname != "127.0.0.1"
            or p.username
            or p.password
            or p.query
            or p.fragment
            or p.path != "/search"
            or p.port is None
            or p.port in {11434, 0}
            or p.netloc != f"127.0.0.1:{p.port}"
        ):
            raise ValueError("SearXNG must use an exact numeric loopback HTTP /search endpoint")
        from zoneinfo import ZoneInfo

        ZoneInfo(self.timezone)
        return self


def load_web_config(path: Path):
    return WebConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8-sig")))


def canonical(value):
    return json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))


def stamp(now):
    return datetime.fromtimestamp(now, UTC).isoformat()


def public_url(value):
    """Strict syntax first; DNS/public socket binding is independently required."""
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\s\\\x00-\x1f\x7f]", value):
        raise WebError("URL_DENIED")
    try:
        p = urlsplit(value)
        host = p.hostname
        if (
            p.scheme != "https"
            or not host
            or p.username
            or p.password
            or p.port not in {None, 443}
            or "%" in p.netloc
            or host.endswith(".")
            or p.fragment
        ):
            raise ValueError()
        host = host.encode("idna").decode("ascii").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(
            (".localhost", ".local", ".internal", ".lan", ".home", ".test", ".invalid")
        ):
            raise ValueError()
        # Deny ambiguous numeric spellings before libc can reinterpret them.
        if ":" in host or re.fullmatch(r"[0-9.]+|0[xX][0-9a-fA-F]+", host):
            public_address(host)
        elif not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or "." not in host:
            raise ValueError()
        if re.search(r"(?:token|api[_-]?key|password|secret|session|auth)=", p.query, re.I):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise WebError("URL_DENIED") from None


def safe_query(text):
    """No history, files, memory, desktop state, or source text enters query egress."""
    if len(text) > 600 or re.search(
        r"[A-Za-z]:[\\/]|\\\\|/(?:Users|home|etc)/|@|"
        r"\b(?:password|secret|api[_ -]?key|cookie|token|private|confidential)\b|"
        r"[A-Za-z0-9+/=_-]{40,}",
        text,
        re.I,
    ):
        raise WebError("PRIVATE_QUERY_DENIED")
    # Strip conversational scaffolding. All remaining terms belong to this owner turn.
    words = re.findall(r"[\w.+-]+", text, flags=re.UNICODE)
    stop = {
        "please",
        "search",
        "web",
        "internet",
        "online",
        "look",
        "up",
        "research",
        "find",
        "verify",
        "check",
        "me",
        "my",
        "you",
        "can",
        "could",
        "the",
        "a",
        "an",
        "for",
        "what",
        "is",
        "are",
        "why",
        "how",
        "about",
        "this",
        "that",
        "information",
    }
    query = " ".join(w for w in words if w.casefold() not in stop)
    if not query or len(query) > 256:
        raise WebError("QUERY_SCOPE_EMPTY_OR_TOO_LARGE")
    return query


class SearchRequest(StrictRecord):
    query: str = Field(min_length=1, max_length=256)
    result_limit: int = Field(ge=1, le=10)
    recency: Literal["day", "month", "year"] | None = None
    domains: tuple[str, ...] = ()


class SearchResult(StrictRecord):
    result_id: str
    provider: str
    title: str
    url: str
    domain: str
    snippet: str = ""
    published_at: str | None = None
    retrieved_at: str
    rank: int


class Source(StrictRecord):
    source_id: str
    search_result_id: str
    provider: str
    url: str
    canonical_url: str | None = None
    domain: str
    title: str
    author: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    retrieved_at: str
    content_type: str
    extraction_version: Literal["public-extract-v1"] = "public-extract-v1"
    chunks: tuple[str, ...]
    headings: tuple[str, ...] = ()
    task_id: str
    query_hash: str
    provenance: str = "public HTTPS, independently fetched; external content is untrusted"
    freshness: str = "publication time unknown"
    reliability_notes: str = "Source assertions are evidence, not independently established truth."


class WebArguments(StrictRecord):
    query_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    operation: Literal["research", "sources", "followup"] = "research"
    refresh: bool = False
    consider: bool = False


def query_hash(query):
    return hashlib.sha256(query.encode()).hexdigest()


class SearchProvider(Protocol):
    name: str

    def search(self, request: SearchRequest, config: WebConfig, cancel, deadline): ...


class PageFetcher(Protocol):
    def fetch(self, url: str, config: WebConfig, cancel, deadline): ...
