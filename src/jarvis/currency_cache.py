"""Bounded public-only cache. Amounts and conversation never enter cache records."""

import json
from datetime import datetime

from jarvis.public_data import VERSION, PublicDataError, Quote, validate_quote


class QuoteCache:
    def __init__(self, config, path=None):
        self.config, self.path = config, path
        self.entries = {}
        if path and path.exists():
            try:
                if path.stat().st_size > 262144:
                    raise ValueError("Cache too large")
                rows = json.loads(path.read_bytes())
                if not isinstance(rows, list) or len(rows) > config.max_cache_entries:
                    raise ValueError("Invalid cache")
                for row in rows:
                    observation = Quote.model_validate(row, strict=True)
                    self.entries[self.key(observation.base, observation.quote)] = observation
            except (ValueError, OSError):
                # Invalid cache is never served. Do not silently overwrite evidence.
                self.entries = {}
                self.path = None

    def key(self, base, quote):
        return (VERSION, self.config.provider, self.config.mode, "reference", "latest", base, quote)

    def get(self, base, quote, now, *, stale=False):
        observation = self.entries.get(self.key(base, quote))
        if observation is None:
            return None
        expected = "synthetic" if self.config.mode == "fixture" else "public"
        if observation.sensitivity != expected:
            return None
        try:
            validate_quote(observation, self.config, now)
        except PublicDataError:
            return None
        expires = datetime.fromisoformat(observation.expires_at_utc).timestamp()
        fetched = datetime.fromisoformat(observation.retrieved_at_utc).timestamp()
        if not stale and now >= expires:
            return None
        if stale and (
            not self.config.allow_stale_cache or now - fetched > self.config.stale_cache_seconds
        ):
            return None
        return observation

    def put(self, observation, now):
        validate_quote(observation, self.config, now)
        self.entries[self.key(observation.base, observation.quote)] = observation
        while len(self.entries) > self.config.max_cache_entries:
            self.entries.pop(next(iter(self.entries)))
        self._save()

    def clear(self):
        self.entries.clear()
        self._save()

    def _save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps([row.model_dump() for row in self.entries.values()], indent=2)
            )
            temporary.replace(self.path)

    def inspect(self):
        return [
            {
                "source_id": row.source_id,
                "base": row.base,
                "quote": row.quote,
                "effective_date": row.effective_date,
                "retrieved_at_utc": row.retrieved_at_utc,
                "expires_at_utc": row.expires_at_utc,
            }
            for row in self.entries.values()
        ]
