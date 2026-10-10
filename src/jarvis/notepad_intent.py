"""Reviewed owner-command grammar; proposals/history never create task scope.

Match a whole, single request. Composable politeness, verbs and targets accept
paraphrases without substring matching arbitrary prose or compound operations.
"""

import re
from dataclasses import dataclass

RESOLVER_VERSION = "notepad-intent-v1"


@dataclass(frozen=True)
class Intent:
    effect: str
    target: str  # notepad, selected, ambiguous, unregistered


def interpret(text: str) -> Intent | None:
    value = " ".join(text.casefold().strip().rstrip(".!?").split())
    value = re.sub(r"^(?:hey )?jarvis[, ]+", "", value)
    value = re.sub(r"^(?:can|could|would|will) you (?:please )?", "", value)
    value = re.sub(r"^(?:i want|i'd like|i would like) you to ", "", value)
    value = re.sub(r"^please ", "", value)
    value = re.sub(r",? please$", "", value)
    patterns = (
        ("open", r"(?:open|launch|start) (.+)"),
        ("close", r"(?:close|exit) (.+)"),
        ("focus", r"(?:focus(?: on)?|activate|switch to) (.+)"),
        ("focus", r"bring (.+) (?:to (?:the )?front|forward|up)"),
        ("focus", r"put (.+) (?:in (?:the )?foreground|in front)"),
    )
    for effect, pattern in patterns:
        match = re.fullmatch(pattern, value)
        if not match:
            continue
        target = match[1]
        if re.fullmatch(
            r"(?:(?:the |my |that |this )?(?:selected )?notepad(?: window)?"
            r"|my (?:registered )?text editor(?: window)?)",
            target,
        ):
            return Intent(effect, "notepad")
        if target in {
            "it",
            "that",
            "this",
            "that window",
            "this window",
            "the window",
            "the selected window",
            "selected window",
        }:
            return Intent(effect, "selected")
        if target in {"my editor", "an editor", "editor", "an app", "app", "a window", "window"}:
            return Intent(effect, "ambiguous")
        return Intent(effect, "unregistered")
    return None
