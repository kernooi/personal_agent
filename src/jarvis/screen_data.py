"""M5 boundaries. Pixels and recognized text are private, untrusted evidence."""

import json
import tomllib
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from jarvis.companion import CompanionConfig
from jarvis.domain import Denied
from jarvis.models import reject_constant, unique_object


class Record(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ScreenConfig(Record):
    version: Literal[1] = 1
    enabled: bool = False
    companion: CompanionConfig = Field(default_factory=CompanionConfig)
    default_capture_scope: Literal["primary_display", "foreground_window"] = "primary_display"
    vision_model: str = Field(default="", max_length=120, pattern=r"^[a-zA-Z0-9:._/-]*$")
    allowed_executables: list[str] = Field(default_factory=list, max_length=100)
    excluded_executables: list[str] = Field(
        default_factory=lambda: ["1password.exe", "keepass.exe", "keepassxc.exe", "bitwarden.exe"],
        max_length=100,
    )
    excluded_title_terms: list[str] = Field(
        default_factory=lambda: [
            "incognito",
            "inprivate",
            "private browsing",
            "password",
            "banking",
        ],
        max_length=100,
    )
    watch_enabled: bool = False
    watch_seconds: int = Field(default=120, ge=10, le=300)
    sample_seconds: int = Field(default=10, ge=5, le=60)
    max_samples: int = Field(default=24, ge=1, le=60)
    max_pixels: int = Field(default=4_194_304, ge=4096, le=8_294_400)
    max_image_bytes: int = Field(default=8_388_608, ge=4096, le=16_777_216)
    capture_seconds: int = Field(default=8, ge=1, le=20)
    inference_seconds: int = Field(default=90, ge=5, le=180)
    freshness_seconds: int = Field(default=30, ge=1, le=120)
    context_tokens: int = Field(default=4096, ge=2048, le=8192)
    output_tokens: int = Field(default=1536, ge=256, le=4096)
    cpu_retry_on_incomplete: bool = True
    cpu_retry_max_pixels: int = Field(default=147456, ge=4096, le=1048576)
    chat_answer_enabled: bool = True
    chat_answer_seconds: int = Field(default=30, ge=5, le=60)
    word_list: str = Field(default="", max_length=2048)


def load_config(path):
    return ScreenConfig.model_validate(
        tomllib.loads(path.read_text(encoding="utf-8-sig")), strict=True
    )


class Target(Record):
    reference: str = Field(pattern=r"^screen_[a-f0-9]{32}$")
    kind: Literal["window", "display", "desktop"]
    identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    application: str = Field(max_length=256)
    bounds: tuple[int, int, int, int]
    dpi: int = Field(ge=48, le=768)
    native: dict  # Trusted adapter-private binding; never accepted from the model.


class Frame(Record):
    artifact: str = Field(pattern=r"^image_[a-f0-9]{32}$")
    target_identity: str
    generation: int = Field(ge=1)
    captured_at: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    bounds: tuple[int, int, int, int]
    png: bytes = Field(repr=False)
    pixel_digest: str


class WordleRow(Record):
    letters: str = Field(pattern=r"^[a-z?]{5}$")
    feedback: list[Literal["correct", "present_elsewhere", "absent", "unknown"]] = Field(
        min_length=5, max_length=5
    )


class WordleBoard(Record):
    columns: Literal[5]
    rows: Literal[6]
    guesses: list[WordleRow] = Field(max_length=6)
    incomplete: str = Field(default="", pattern=r"^[a-z?]{0,5}$")


class WordleLetters(Record):
    letters: str = Field(pattern=r"^[a-z?]{5}$")


class WordleRead(Record):
    rows: list[WordleLetters] = Field(min_length=1, max_length=6)
    uncertainty: list[str] = Field(max_length=10)


class Interpretation(Record):
    description: str = Field(min_length=1, max_length=2400)
    visible_text: list[str] = Field(default_factory=list, max_length=20)
    objects: list[str] = Field(default_factory=list, max_length=20)
    activity_candidates: list[str] = Field(default_factory=list, max_length=5)
    uncertainty: list[str] = Field(default_factory=list, max_length=10)
    unreadable_regions: list[str] = Field(default_factory=list, max_length=10)
    wordle: WordleBoard | None = None


class Observation(Record):
    observation_id: str
    artifact: str
    target_identity: str
    application: str
    capture_scope: Literal["window", "display", "desktop"]
    captured_at: float
    generation: int
    bounds: tuple[int, int, int, int]
    image_dimensions: tuple[int, int]
    analyzed_regions: list[tuple[int, int, int, int]] = Field(default_factory=list, max_length=4)
    model: str
    model_digest: str
    adapter_version: Literal["local-vision-v1"] = "local-vision-v1"
    interpretation: Interpretation
    sensitivity: Literal["private"] = "private"
    authority: Literal["untrusted_visual_inference"] = "untrusted_visual_inference"


class VisionProvider(Protocol):
    def inspect(self, cancel, deadline) -> dict: ...

    def analyze(self, frame: Frame, question: str, context: dict, cancel, deadline): ...


def parse_interpretation(raw):
    if not raw or len(raw) > 32768:
        raise Denied("VISION_OUTPUT_LIMIT")
    data = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    result = Interpretation.model_validate(data, strict=True)
    for items in (
        result.visible_text,
        result.objects,
        result.activity_candidates,
        result.uncertainty,
        result.unreadable_regions,
    ):
        if any(len(value) > 1500 for value in items):
            raise Denied("VISION_OUTPUT_LIMIT")
    return result
