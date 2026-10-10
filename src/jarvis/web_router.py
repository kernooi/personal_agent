"""Owner-only routing; freshness is independent of model confidence."""

import re


def is_identity_question(text):
    """Assistant self-identification belongs to local chat, not public evidence."""
    value = text.strip().casefold().replace("’", "'")
    value = re.sub(r"\s+", " ", value).rstrip(".!?")
    return bool(
        re.fullmatch(
            r"(?:please )?(?:"
            r"(?:what is|what's|whats) your (?:name|identity)|"
            r"who (?:are you|is jarvis)|"
            r"(?:what should|what can|how should) i call you|"
            r"(?:tell me|can you tell me) your name|"
            r"introduce yourself"
            r")(?: please)?",
            value,
        )
    )


def wants_web(text):
    return bool(
        re.search(
            r"\b(?:search|research|latest|current|today|recent|recently|new|newest|news|"
            r"prices?|pricing|releases?|released|announced|compare|leadership|"
            r"versions?|availability|schedules?|ceo|president|documentation|scientific)\b|"
            r"\b(?:this week|this month|look this up|look up|check online|find sources|"
            r"verify this|find documentation|find information)\b|https://",
            text,
            re.I,
        )
    )


def recency(text):
    if re.search(r"\b(?:today|24 hours)\b", text, re.I):
        return "day"
    if re.search(r"\b(?:recent|week|month|newer|latest|newest)\b", text, re.I):
        return "month"
    return None


def eligible_factual_question(text):
    """Owner purpose permits consideration, not a confidence-based network grant."""
    if is_identity_question(text):
        return False
    value = text.strip().casefold()
    if re.search(r"\b(?:recursion|rewrite|paragraph|provided code|this function)\b", value):
        return False
    if re.fullmatch(r"what is [0-9\s+*/().?-]+", value):
        return False
    return bool(re.match(r"(?:what (?:is|are)|who (?:is|are)|when (?:did|was)|where is)\b", value))
