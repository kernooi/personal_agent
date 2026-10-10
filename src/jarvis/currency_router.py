"""Trusted currency normalization and a single unambiguous session pair."""

import re
from dataclasses import dataclass

from jarvis.public_data import CurrencyArguments, PublicDataError, canonical

NUM = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
# Language aliases are not a support list: provider metadata remains authoritative.
ALIASES = {
    "malaysian ringgit": "MYR",
    "ringgit": "MYR",
    "japanese yen": "JPY",
    "yen": "JPY",
    "us dollars": "USD",
    "us dollar": "USD",
    "american dollars": "USD",
    "singapore dollars": "SGD",
    "singapore dollar": "SGD",
    "british pounds": "GBP",
    "british pound": "GBP",
    "pounds": "GBP",
    "euros": "EUR",
    "euro": "EUR",
    "australian dollars": "AUD",
    "australian dollar": "AUD",
}


@dataclass(frozen=True)
class Route:
    kind: str = "ordinary"
    arguments: CurrencyArguments | None = None
    message: str = ""
    pending_pair: tuple[str, str] | None = None


def resolved(base, quote, amount=None, supplied=None, refresh=False):
    try:
        args = CurrencyArguments(
            base=base,
            quote=quote,
            amount=amount,
            operation="identity" if base == quote else "supplied" if supplied else "latest",
            supplied_rate=supplied,
            refresh=refresh,
        )
        canonical(args)
        return Route("currency", args)
    except (PublicDataError, ValueError):
        return Route(
            "clarify",
            message="Use a finite nonnegative amount up to 1,000,000,000,000 "
            "and a positive rate, with at most 12 decimal places.",
        )


def route(text, previous=None, context=None):
    value = " ".join(text.strip().casefold().rstrip(".!?").split())
    if len(value) > 4096:
        return Route("unsupported", message="The request is too long.")
    cited = re.findall(r"\bsrc_[a-z0-9]+\b", value)
    if cited:
        if previous is None or cited != [previous.source_id]:
            return Route("unsupported", message="That source ID is not known in this session.")
        return Route(
            "currency",
            CurrencyArguments(base=previous.base, quote=previous.quote, operation="source"),
        )
    source = "that rate" in value and any(
        w in value for w in ("source", "published", "where", "date", "effective")
    )
    refresh = value in {"refresh that rate", "refresh the rate", "refresh"}
    reverse = bool(re.fullmatch(r"(?:what(?:'s| is) (?:the )?)?reverse rate", value))
    if source or refresh or reverse:
        pair = context or ((previous.base, previous.quote) if previous else None)
        if pair is None or (source and previous is None):
            return Route(
                "clarify", message="Which currency pair do you mean? Please name both currencies."
            )
        if source:
            return Route(
                "currency",
                CurrencyArguments(base=previous.base, quote=previous.quote, operation="source"),
            )
        return resolved(*(tuple(reversed(pair)) if reverse else pair), refresh=refresh)
    followup = re.fullmatch(rf"(?:what about\s+)?({NUM})", value)
    if followup:
        if context is None:
            return Route(
                "clarify", message="Which currencies should I convert that amount between?"
            )
        return resolved(*context, amount=followup[1].replace(",", ""))
    if value.startswith("what about ") or (
        context is not None and re.fullmatch(r"[-+0-9.,]+|nan|inf|infinity", value)
    ):
        return Route(
            "clarify",
            message="Please specify a valid finite amount and an unambiguous currency pair.",
        )
    if re.search(r"\b(?:what is|explain|define) (?:an? |the )?exchange rate\b", value) and not any(
        w in value for w in ("now", "today", "current", " to ", " in ")
    ):
        return Route()
    for name in sorted(ALIASES, key=len, reverse=True):
        value = re.sub(rf"\b{re.escape(name)}\b", ALIASES[name].lower(), value)
    currency_like = any(
        w in value for w in ("convert", "exchange rate", "currency", "how much", "myr", "jpy")
    ) or bool(re.search(r"(?:[0-9]\s*|\b)[a-z]{3}\s*(?:to|in|/|->)\s*[a-z]{3}\b", value))
    if currency_like:
        if re.fullmatch(r"(?:what is|explain) [a-z]{3}", value):
            return Route()
        if ";" in value or re.search(r"\band\s+(?:open|close|run|send|fetch)\b", value):
            return Route(
                "clarify", message="Please request one currency pair or conversion at a time."
            )
        if any(symbol in value for symbol in ("$", "£", "¥")) or re.search(r"\bdollars?\b", value):
            return Route(
                "clarify",
                message="Please name both currencies; "
                "dollar and currency symbols can be ambiguous.",
            )
        if re.search(
            r"\b(?:on|in|as of)\s+(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{4})\b"
            r"|\b(?:historical|yesterday|last year)\b",
            value,
        ):
            return Route(
                "unsupported",
                message="Historical-date retrieval is not implemented; "
                "request the latest available daily reference rate.",
            )
        pairs = re.findall(r"(?<![a-z])([a-z]{3})\s*(?:to|in|/|->)\s*([a-z]{3})(?![a-z])", value)
        if len(set(pairs)) != 1:
            return Route(
                "clarify",
                message="Please specify one source and one destination currency, "
                "such as USD to MYR.",
            )
        base, quote = (s.upper() for s in pairs[0])
        if re.search(
            r"\b(?:nan|infinity|inf)\b|[+-][0-9]|[0-9]e[+-]?[0-9]|(?<![0-9])\.[0-9]", value
        ):
            return Route(
                "clarify", message="Use a finite nonnegative amount, at most 1,000,000,000,000."
            )
        for token in re.findall(r"[0-9][0-9,.]*", value):
            if not re.fullmatch(NUM, token):
                return Route(
                    "clarify",
                    message="Please write the amount with valid comma grouping and decimals.",
                )
        amount_matches = list(
            re.finditer(rf"(?<![a-z0-9.,+-])({NUM})\s*{base.lower()}\b(?!\s*=)", value)
        )
        amount_values = {m[1].replace(",", "") for m in amount_matches}
        if len(amount_values) > 1:
            return Route("clarify", message="Please specify a single conversion amount.")
        amount = next(iter(amount_values), None)
        equation = re.search(rf"\b1\s*([a-z]{{3}})\s*=\s*({NUM})\s*([a-z]{{3}})\b", value)
        if equation and (equation[1].upper(), equation[3].upper()) != (base, quote):
            return Route(
                "clarify", message="Supply the rate in the same direction as the conversion."
            )
        supplied = re.search(rf"(?:at|using) (?:a |the )?(?:rate (?:of )?)?({NUM})(?:\s|$)", value)
        supplied_rate = (
            equation[2].replace(",", "")
            if equation
            else supplied[1].replace(",", "")
            if supplied
            else None
        )
        if "=" in value and equation is None:
            return Route(
                "clarify",
                message="Supply a positive rate as 1 base currency = rate quote currency.",
            )
        if any(w in value for w in ("convert", "how much")) and amount is None:
            return Route(
                "clarify", message="What amount should I convert?", pending_pair=(base, quote)
            )
        return resolved(base, quote, amount, supplied_rate)
    if any(w in value for w in ("weather", "latest news", "current news", "forecast")) or (
        any(w in value for w in ("current", "today", "now", "latest", "who is"))
        and any(
            w in value
            for w in ("price", "president", "prime minister", "ceo", "news", "version", "schedule")
        )
    ):
        return Route(
            "unsupported",
            message="I can't verify that current information. "
            "M3 implements public currency retrieval only.",
        )
    return Route()
