"""Reviewed extensions to the frozen v1 owner grammar."""

import re

from jarvis.notepad_intent import Intent
from jarvis.notepad_intent import interpret as previous


def interpret(text):
    value = " ".join(text.casefold().strip().rstrip(".!?").split())
    bare = {"close": "close", "minimize": "minimize", "minimise": "minimize", "focus": "focus"}
    if value in bare:
        return Intent(bare[value], "selected")
    # A repetition modifier never broadens the effect or target.
    if value.endswith(" again") and re.match(
        r"(?:please )?(?:bring|focus|activate|switch|put) ", value
    ):
        value = value.removesuffix(" again")
    value = re.sub(r"\bthe (?:registered )?text editor(?: window)?\b", "notepad", value)
    if re.search(r"\bminimi[sz]e\b", value):
        minimized = previous(re.sub(r"\bminimi[sz]e\b", "focus", value))
        if minimized and minimized.effect == "focus":
            return Intent("minimize", minimized.target)
    intent = previous(value)
    if intent and intent.target == "unregistered":
        if re.fullmatch(
            r"(?:bring|focus(?: on)?) (?:a |the )?window(?: to (?:the )?front)?", value
        ):
            return Intent(intent.effect, "ambiguous")
    return intent


def selected_followup(text):
    return " ".join(text.casefold().strip().rstrip(".!?").split()) in {
        "the only one that is open now",
        "the selected one",
        "that one",
        "the notepad one",
    }
