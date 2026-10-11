"""M4 strict semantic contracts. Browser state is evidence, never authority."""

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, field_validator, model_validator

from jarvis.domain import Denied
from jarvis.models import StrictRecord, reject_constant, unique_object

Service = Literal["youtube", "spotify", "netflix"]
Operation = Literal[
    "search", "open", "play", "pause", "resume", "current", "login", "devices", "next", "previous"
]
VERSION = "media-adapter-v1"
ORIGINS = {
    "youtube": frozenset({"www.youtube.com"}),
    "netflix": frozenset({"www.netflix.com"}),
    "spotify": frozenset({"api.spotify.com"}),
}


class MediaError(Denied):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class MediaConfig(StrictRecord):
    schema_version: Literal[1] = 1
    enabled: bool = False
    youtube: bool = True
    netflix: bool = False
    spotify: bool = False
    spotify_backend: Literal["api", "windows"] = "api"
    result_limit: int = Field(default=5, ge=1, le=5)
    operation_seconds: int = Field(default=20, ge=2, le=30)
    reference_seconds: int = Field(default=300, ge=10, le=600)


def load_media_config(path):
    return MediaConfig.model_validate(tomllib.loads(Path(path).read_text(encoding="utf-8-sig")))


def canonical(value):
    data = value.model_dump()
    # Original M4 journal scopes predate backend selection. API is their only
    # meaning; preserve that exact binding/digest without rewriting the journal.
    # Windows scopes always carry the explicit new backend field.
    if data.get("backend") == "api":
        del data["backend"]
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def text_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def safe_media_query(value):
    from jarvis.web_data import safe_query

    value = safe_query(value)
    if re.search(r"https?://|file:|localhost|127\.0\.0|cookie|password|token=", value, re.I):
        raise MediaError("PRIVATE_OR_URL_QUERY")
    return value


def media_url(service, url):
    """Exact service top-level destinations, never model-selected URLs."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ORIGINS[service]
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or "\\" in url
    ):
        raise MediaError("UNEXPECTED_DESTINATION")
    return parsed


def item_id(service, url):
    parsed = media_url(service, url)
    if service == "youtube":
        values = parse_qs(parsed.query)
        if parsed.path == "/watch" and re.fullmatch(r"[A-Za-z0-9_-]{11}", values.get("v", [""])[0]):
            return values["v"][0]
    elif service == "netflix":
        match = re.fullmatch(r"/title/(\d{1,12})", parsed.path)
        if match:
            return match[1]
    raise MediaError("INVALID_MEDIA_IDENTITY")


class MediaArguments(StrictRecord):
    service: Service
    operation: Operation
    backend: Literal["api", "windows"] = "api"
    query_hash: str = Field(default="", pattern=r"^(?:|[0-9a-f]{64})$")
    reference: str = Field(default="", pattern=r"^(?:|media_[0-9a-f]{32})$")
    device_ref: str = Field(default="", pattern=r"^(?:|device_[0-9a-f]{32})$")
    generation: int = Field(default=0, ge=0)
    session_ref: str = Field(pattern=r"^browser_[0-9a-f]{32}$")

    @model_validator(mode="after")
    def exact_operation(self):
        if bool(self.query_hash) != (self.operation == "search"):
            raise ValueError("Only searches have query hashes")
        if self.operation == "open" and not self.reference:
            raise ValueError("Opening requires a runtime reference")
        if self.service == "netflix" and self.operation in {"play", "pause", "resume", "devices"}:
            raise ValueError("Netflix protected playback is unsupported")
        if self.service != "spotify" and (self.device_ref or self.operation == "devices"):
            raise ValueError("Devices belong to Spotify")
        if self.operation in {"next", "previous"} and self.service != "spotify":
            raise ValueError("Track skipping belongs to Spotify Windows media")
        return self


class MediaItem(StrictRecord):
    reference: str = Field(pattern=r"^media_[0-9a-f]{32}$")
    item_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    creator: str = Field(default="", max_length=160)
    duration: str = Field(default="", max_length=32)
    url: str = Field(default="", max_length=400)

    @field_validator("title", "creator", "duration")
    @classmethod
    def inert_labels(cls, value):
        if any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
            raise ValueError("Control characters in external labels")
        return value


class PlaybackDevice(StrictRecord):
    reference: str = Field(pattern=r"^device_[0-9a-f]{32}$")
    name: str = Field(max_length=100)
    active: bool
    restricted: bool

    @field_validator("name")
    @classmethod
    def inert_name(cls, value):
        return MediaItem.inert_labels(value)


class MediaObservation(StrictRecord):
    session_ref: str = Field(pattern=r"^browser_[0-9a-f]{32}$")
    service: Service
    generation: int = Field(ge=0)
    observed_at: float
    state: Literal[
        "ready",
        "results",
        "opened",
        "playing",
        "paused",
        "ad",
        "loading",
        "login_required",
        "age_restricted",
        "region_restricted",
        "plan_restricted",
        "challenge",
        "error",
        "unknown",
    ]
    item_id: str = Field(default="", max_length=64)
    title: str = Field(default="", max_length=240)
    creator: str = Field(default="", max_length=160)
    results: list[MediaItem] = Field(default_factory=list, max_length=5)
    devices: list[PlaybackDevice] = Field(default_factory=list, max_length=10)
    device_ref: str = Field(default="", max_length=48)
    progress_ms: int | None = Field(default=None, ge=0)
    authenticated: bool | None = None
    downloads_blocked: int = Field(default=0, ge=0)

    @field_validator("title", "creator")
    @classmethod
    def inert_labels(cls, value):
        return MediaItem.inert_labels(value)


class WorkerRequest(StrictRecord):
    version: Literal[1] = 1
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    command: Literal["execute", "observe", "snapshot", "shutdown"]
    arguments: MediaArguments
    query: str = Field(default="", max_length=256)
    deadline: float
    result_limit: int = Field(default=5, ge=1, le=5)

    @model_validator(mode="after")
    def query_binding(self):
        if self.command == "execute" and self.arguments.operation == "search":
            if (
                safe_media_query(self.query) != self.query
                or text_hash(self.query) != self.arguments.query_hash
            ):
                raise ValueError("Query scope changed")
        elif self.query:
            raise ValueError("No query allowed")
        return self


def parse_record(raw, record):
    if not raw or len(raw) > 32768:
        raise MediaError("WORKER_MESSAGE_LIMIT")
    return record.model_validate(
        json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant),
        strict=True,
    )


def effect(args):
    return "media_read" if args.operation in {"search", "current", "devices"} else "media_visible"


class BrowserProvider(Protocol):
    real: bool

    def call(self, request: WorkerRequest, cancel) -> MediaObservation: ...
    def close(self) -> None: ...
