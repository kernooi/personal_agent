"""Model prose is not an action receipt. Never promote prose into execution."""

import re


def unverified_completion(text):
    value = text.casefold().replace("’", "'")
    return bool(
        re.search(
            r"\b(?:i(?:'ve| have| just)?|we(?:'ve| have)?)\s+(?:(?:successfully|already|just)\s+)?"
            r"(?:opened|closed|launched|focused|activated|brought|moved|switched|cleared|saved|discarded)\b"
            r"|\b(?:notepad|(?:the |your |selected )?(?:window|text editor))\s+"
            r"(?:has been|was|is now)\s+"
            r"(?:opened|closed|focused|launched|activated|in the foreground)\b"
            r"|\b(?:notepad(?: window)?|(?:the |your |selected )*"
            r"(?:notepad )?(?:window|text editor))\s+"
            r"is\s+(?:(?:already|now)\s+)?(?:open|closed|focused|running|in the foreground)\b",
            value,
        )
    )


def non_action_text(decision, intent):
    if decision.kind == "say" and intent is not None:
        return (
            "I haven't performed that operation. "
            "Please specify the selected Notepad window and the action."
        )
    if unverified_completion(decision.text):
        return (
            "I haven't performed an action for that message. "
            "Please ask me to open, focus or close the selected Notepad."
        )
    return decision.text
