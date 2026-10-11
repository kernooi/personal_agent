"""Portable application contracts and whole-request intent; no per-app alias list."""

import hashlib
import json
import re
from typing import Literal, Protocol

from pydantic import Field

from jarvis.domain import Decision, Proposal
from jarvis.models import StrictRecord, reject_constant, unique_object


class Application(StrictRecord):
    app_id: str = Field(pattern=r"^app_[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=160)
    launch_id: str = Field(min_length=1, max_length=512)
    kind: Literal["exe", "package"]
    executable: str = Field(min_length=1, max_length=32768)
    package: str = Field(default="", max_length=512)


class ApplicationsConfig(StrictRecord):
    version: Literal["applications-v1"] = "applications-v1"
    enabled: bool = False
    platform: Literal["windows"] = "windows"
    maximum_apps: int = Field(default=512, ge=1, le=1024)
    maximum_windows: int = Field(default=128, ge=1, le=256)
    operation_seconds: float = Field(default=15.0, ge=5, le=30)


class ApplicationPlatform(Protocol):
    """Each host implements bounded discovery, observation and gated effects."""

    def call(self, operation: str, payload=None, gate=None): ...


def app_id(launch_id):
    return "app_" + hashlib.sha256(launch_id.encode("utf-8")).hexdigest()[:32]


def valid_runtime_proof(observed, target):
    """Validate persisted launch/runtime linkage, separate from window identity."""
    if observed.get("exe_sha256") == target["exe_sha256"]:
        return True
    proof = observed.get("association")
    if not isinstance(proof, dict) or (
        proof.get("launch_id") != target["app"]["launch_id"]
        or proof.get("launch_sha256") != target["exe_sha256"]
        or proof.get("runtime_sha256") != observed.get("exe_sha256")
        or not re.fullmatch(r"[0-9a-f]{64}", proof.get("runtime_sha256", ""))
    ):
        return False
    if proof.get("method") == "os-application-id":
        return bool(
            target["app"]["package"]
            and proof.get("package") == target["app"]["package"] == observed.get("package")
        )
    if (
        target["app"]["kind"] != "exe"
        or observed.get("package")
        or not isinstance(proof.get("publisher_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", proof["publisher_sha256"])
    ):
        return False
    if proof.get("method") == "signed-versioned-runtime":
        return True
    if proof.get("method") != "signed-descendant-runtime":
        return False
    chain = proof.get("ancestry")
    keys = {"pid", "created", "os_session", "owner_sid", "exe", "package", "exe_sha256"}
    if not isinstance(chain, list) or not 2 <= len(chain) <= 8:
        return False
    seen = set()
    for p in chain:
        if (
            not isinstance(p, dict)
            or set(p) != keys
            or any(type(p[k]) is not int or p[k] <= 0 for k in ("pid", "created"))
            or p["pid"] in seen
            or type(p["os_session"]) is not int
            or p["os_session"] < 0
            or p["os_session"] != observed.get("os_session")
            or not isinstance(p["owner_sid"], str)
            or p["owner_sid"] != observed.get("owner_sid")
            or p["package"]
            or not isinstance(p["exe"], str)
            or not isinstance(p["exe_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", p["exe_sha256"])
        ):
            return False
        seen.add(p["pid"])
    return (
        all(chain[0][k] == observed.get(k) for k in ("pid", "created", "exe_sha256"))
        and chain[-1]["exe_sha256"] == target["exe_sha256"]
        and chain[-1]["exe"].casefold() == target["app"]["executable"].casefold()
        and all(
            parent["created"] <= child["created"]
            for child, parent in zip(chain, chain[1:], strict=False)
        )
    )


def normalized(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def resolve_app(text, apps):
    value = normalized(text)
    exact = [
        a
        for a in apps
        if value
        in {
            normalized(a.name),
            normalized(a.launch_id),
            normalized(a.executable.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".exe")),
        }
    ]
    if exact:
        return exact
    # Whole label words, never edit-distance guessing or first-match selection.
    words = value.split()
    if not words:
        return []
    return [
        a
        for a in apps
        if any(
            normalized(a.name).split()[i : i + len(words)] == words
            for i in range(len(normalized(a.name).split()))
        )
    ]


def owner_intent(text):
    value = " ".join(text.strip().rstrip(".!?").split())
    value = re.sub(r"(?i)^(?:hey )?jarvis[, ]+", "", value)
    value = re.sub(r"(?i)^(?:can|could|would|will) you (?:please )?", "", value)
    value = re.sub(r"(?i)^(?:i want|i'd like|i would like) you to ", "", value)
    value = re.sub(r"(?i)^please ", "", value)
    value = re.sub(r"(?i),? please$", "", value)
    bare = {"close": "close", "minimize": "minimize", "minimise": "minimize", "focus": "focus"}
    if value.casefold() in bare:
        return bare[value.casefold()], "it"
    patterns = [
        ("open", r"(?:open|launch|start) (.+)"),
        ("close", r"(?:close|exit) (.+)"),
        ("minimize", r"minimi[sz]e (.+)"),
        ("focus", r"(?:focus(?: on)?|activate|switch to) (.+)"),
        ("focus", r"bring (.+) (?:to (?:the )?front|forward|up)(?: again)?"),
    ]
    for effect, pattern in patterns:
        match = re.fullmatch(pattern, value, re.I)
        if match:
            target = match[1]
            # Never interpret a chain, path, URL, arguments or quoted executable as a name.
            if re.search(r'[\\/:;`"<>|]|\b(?:and|then)\b|(?:^|\s)--?\w', target, re.I):
                return ("unsupported", "")
            target = re.sub(r"(?i)^(?:the |my )", "", target)
            target = re.sub(r"(?i) (?:app|application|window)$", "", target)
            return effect, target
    return None


class ApplicationChoice(StrictRecord):
    kind: Literal["application_choice"]
    capability: Literal["apps.open", "windows.focus", "windows.minimize", "windows.close"]
    app_id: str = Field(pattern=r"^app_[0-9a-f]{32}$")
    window_ref: str = Field(default="", pattern=r"^(?:|win_[0-9a-f]{32})$")


def parse_choice(raw):
    parsed = ApplicationChoice.model_validate(
        json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant),
        strict=True,
    )
    return Decision(
        "propose_action", proposal=Proposal(parsed.capability, parsed.app_id, parsed.window_ref)
    )
