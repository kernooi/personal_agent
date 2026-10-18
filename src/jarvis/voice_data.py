"""Private local voice settings/contracts. No tool or model execution authority."""

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, field_validator

from jarvis.models import StrictRecord


class VoiceState(StrEnum):
    DISABLED = "DISABLED"
    IDLE = "IDLE"
    WAKE_LISTENING = "WAKE_LISTENING"
    WAKE_CHECKING = "WAKE_CHECKING"
    WAKE_ACKNOWLEDGING = "WAKE_ACKNOWLEDGING"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    SUBMITTING = "SUBMITTING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class VoiceConfig(StrictRecord):
    version: Literal[1] = 1
    enabled: bool = True
    interaction_mode: Literal["push_to_talk", "wake_word"] = "push_to_talk"
    wake_enabled: bool = True
    wake_call: str = Field(default="Jarvis", min_length=1, max_length=64)
    wake_provider: Literal["windows_sapi", "whisper"] = "windows_sapi"
    wake_session_seconds: int = Field(default=60, ge=15, le=120)
    wake_followup_seconds: int = Field(default=10, ge=3, le=20)
    wake_silence_seconds: float = Field(default=1.1, ge=0.4, le=3)
    wake_minimum_rms: int = Field(default=100, ge=50, le=1000)
    stt_provider: Literal["faster-whisper"] = "faster-whisper"
    model_directory: str = "speech/base.en"
    stt_beam_size: int = Field(default=5, ge=1, le=8)
    app_name_hints: bool = False
    recognition_terms: list[str] = Field(default_factory=list, max_length=64)
    language: str | None = Field(default="en", pattern=r"^[a-z]{2,3}$")
    input_device: str = Field(default="", max_length=512)
    recording_seconds: int = Field(default=20, ge=2, le=60)
    transcription_seconds: int = Field(default=45, ge=5, le=120)
    silence_seconds: float = Field(default=0, ge=0, le=5)
    speak_responses: bool = True
    tts_provider: Literal["windows_sapi", "kokoro"] = "windows_sapi"
    tts_model_directory: str = Field(default="speech/kokoro-v1.0", max_length=512)
    neural_voice: str = Field(default="am_michael", pattern=r"^[ab][mf]_[a-z]{1,32}$")
    voice: str = Field(default="", max_length=2048)
    output_device: str = Field(default="", max_length=2048)
    volume: int = Field(default=80, ge=0, le=100)
    rate: int = Field(default=0, ge=-5, le=5)
    speech_seconds: int = Field(default=90, ge=5, le=180)
    review_transcript: bool = False

    @field_validator("recognition_terms")
    @classmethod
    def validate_terms(cls, values):
        from jarvis.voice_vocabulary import MAX_HINT_CHARACTERS, valid_term

        if any(any(ord(c) < 32 or ord(c) == 127 for c in value) for value in values):
            raise ValueError("Names cannot contain control characters.")
        values = [" ".join(value.split()) for value in values]
        if (
            any(not valid_term(value) for value in values)
            or sum(len(value) + 2 for value in values) > MAX_HINT_CHARACTERS
        ):
            raise ValueError("Use short names/spellings only, up to 512 characters in total.")
        return list(dict.fromkeys(values))

    @field_validator("wake_call")
    @classmethod
    def validate_wake_call(cls, value):
        value = " ".join(value.split())
        words = value.split()
        if not 1 <= len(words) <= 5 or any(
            not re.fullmatch(r"[^\W_]+(?:['’-][^\W_]+)*", word) for word in words
        ):
            raise ValueError("Use one to five spoken words, without symbols or punctuation.")
        return value


def load_config(root):
    path = Path(root) / "voice.toml"
    if not path.is_file():
        return VoiceConfig()
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("language") == "":
        data["language"] = None
    return VoiceConfig.model_validate(data, strict=True)


@dataclass(frozen=True)
class Audio:
    pcm: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2

    def validate(self, maximum_seconds=60):
        if (
            self.sample_rate != 16000
            or self.channels != 1
            or self.sample_width != 2
            or not isinstance(self.pcm, bytes)
            or not 6400 <= len(self.pcm) <= maximum_seconds * 32000
            or len(self.pcm) % 2
        ):
            raise ValueError("INVALID_AUDIO")


class Transcript(StrictRecord):
    text: str = Field(max_length=4096)
    language: str = Field(max_length=20)
    uncertain: bool
    seconds: float = Field(ge=0, le=60)


class Device(StrictRecord):
    id: str = Field(max_length=2048)
    name: str = Field(max_length=512)
    index: int | None = Field(default=None, ge=0)


class Devices(StrictRecord):
    kind: Literal["devices"]
    inputs: list[Device] = Field(max_length=256)
    voices: list[Device] = Field(max_length=128)
    outputs: list[Device] = Field(max_length=128)
    app_names: list[str] = Field(default_factory=list, max_length=64)
    stt_ready: bool
    errors: list[str] = Field(max_length=10)

    @field_validator("app_names")
    @classmethod
    def validate_app_names(cls, values):
        return VoiceConfig.validate_terms(values)


class WakeSetupDiagnostic(StrictRecord):
    stage: Literal["CREATE", "ENGINE", "INPUT", "CONTEXT", "EVENTS", "GRAMMAR", "ACTIVATE", "STOP"]
    category: Literal["BINDING", "NATIVE", "SETUP"]
    hresult: int | None = Field(default=None, ge=-(2**31), le=2**31 - 1)


class STT(Protocol):
    def transcribe(self, audio: Audio, config: VoiceConfig, cancel): ...


class TTS(Protocol):
    def speak(self, text: str, config: VoiceConfig, cancel, started): ...


def request_text(text):
    """Remove only the optional spoken address, never invent or execute a command."""
    value = re.sub(r"(?i)^\s*jarvis\b[\s,.:!-]*", "", text).strip()
    if not value or len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("INVALID_TRANSCRIPT")
    return value


def needs_review(transcript, config):
    text = request_text(transcript.text)
    return (
        config.review_transcript
        or transcript.uncertain
        or text.startswith("/")
        or bool(
            re.fullmatch(
                r"(?i)(?:yes|confirm|approve|approved|confirmed|go ahead|do it)",
                text.rstrip(" .!?"),
            )
        )
    )


def spoken_text(text):
    """No extra LLM, invented summary, URLs or discarded late safety warnings."""
    if len(text) > 2200 or "```" in text or sum("|" in line for line in text.splitlines()) > 3:
        return "The full response is in the chat. Please read it, including any limitations."
    text = re.sub(r"\[([^\]]+)\]\(https?://[^\s)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|\[(?:\d+|[Ss]ource[^\]]*)\]", "", text)
    text = re.sub(r"[*`#]", "", text)
    return " ".join(text.split()).strip()
