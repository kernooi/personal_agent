"""Local spelling hints, never transcript replacement, identity or execution authority."""

import re
import tomllib

MAX_HINT_CHARACTERS = 512
TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 &'().+_-]{0,63}")


def valid_term(value):
    return (
        isinstance(value, str)
        and TERM.fullmatch(value) is not None
        and any(c.isalpha() for c in value)
    )


def vocabulary(configured, applications=()):
    """Explicit owner spellings first; shorter OS labels fit the bounded hint budget."""
    selected, seen, size = [], set(), 0
    for value in [
        *configured,
        *sorted(
            [value for value in applications if valid_term(value)],
            key=lambda value: (len(value.split()), len(value), value.casefold()),
        ),
    ]:
        if not valid_term(value):
            continue
        value = " ".join(value.split())
        if value.casefold() in seen or size + len(value) + 2 > MAX_HINT_CHARACTERS:
            continue
        selected.append(value)
        seen.add(value.casefold())
        size += len(value) + 2
        if len(selected) >= 64:
            break
    return selected


def installed_names(root):
    """Only the fixed, read-only catalog operation; no windows or effects are observed."""
    import threading

    from jarvis.application_data import Application, ApplicationsConfig
    from jarvis.application_windows import WindowsApplicationPlatform

    path = root / "applications.toml"
    if not path.is_file():
        return []
    if path.stat().st_size > 8192:
        raise ValueError("APP_VOCABULARY_UNAVAILABLE")
    config = ApplicationsConfig.model_validate(
        tomllib.loads(path.read_text(encoding="utf-8-sig")), strict=True
    )
    if not config.enabled:
        return []
    platform = WindowsApplicationPlatform(
        config.model_copy(update={"operation_seconds": 5.0}), threading.Event()
    )
    result = platform.call("catalog")
    if len(result["apps"]) > config.maximum_apps:
        raise ValueError("APP_VOCABULARY_UNAVAILABLE")
    records = [Application.model_validate(item, strict=True) for item in result["apps"]]
    return vocabulary([], [item.name for item in records])
