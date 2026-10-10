"""Small session public-only caches; query text/history/credentials are not stored."""

from collections import OrderedDict


class ResearchCache:
    def __init__(self, config):
        self.config = config
        self.searches = OrderedDict()
        self.documents = OrderedDict()

    def get(self, section, key, now):
        values = getattr(self, section)
        value = values.get(key)
        if value is None or now < value[0] or now >= value[0] + self.config.cache_seconds:
            return None
        values.move_to_end(key)
        return value[1]

    def put(self, section, key, value, now):
        values = getattr(self, section)
        values[key] = (now, value)
        values.move_to_end(key)
        while len(values) > 8:
            values.popitem(last=False)

    def clear(self):
        self.searches.clear()
        self.documents.clear()

    def inspect(self):
        return {
            "search_entries": len(self.searches),
            "document_entries": len(self.documents),
            "ttl_seconds": self.config.cache_seconds,
            "persistent": False,
        }
