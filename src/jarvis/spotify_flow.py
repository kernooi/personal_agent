"""Named Spotify song/playlist workflow, reusing the broker-bound media phases."""

import re

from jarvis.media_language import named_media_request
from jarvis.youtube_flow import YouTubeFlow


def named_spotify_request(text):
    meaning = named_media_request(text)
    return (meaning.goal, meaning.query) if meaning and meaning.service == "spotify" else None


class SpotifyFlow(YouTubeFlow):
    service = "spotify"
    service_name = "Spotify"
    noun = "song or playlist"
    named_request = staticmethod(named_spotify_request)

    def resolve_named(self, text):
        # Spotify desktop is the sole registered playlist-search capability.
        # Default only for explicitly named playlists, never arbitrary bare media.
        config = self.chat.broker.media.config
        default = (
            "spotify"
            if (
                config.enabled
                and config.spotify
                and config.spotify_backend == "desktop"
                and re.search(r"(?i)\bplaylist\b", text)
            )
            else None
        )
        meaning = named_media_request(text, default_service=default)
        return (meaning.goal, meaning.query) if meaning and meaning.service == "spotify" else None

    def matching_candidates(self, query, results):
        title = re.sub(r"(?i)^playlist ", "", query)
        parts = re.split(r"(?i)\s+by\s+", title)
        title = " by ".join(parts[:-1]) if len(parts) > 1 else title
        exact = [
            i
            for i, item in enumerate(results, 1)
            if " ".join(title.split()).casefold() == " ".join(item.title.split()).casefold()
            and self.matches_item(query, item)
        ]
        return exact or super().matching_candidates(query, results)

    def matches_item(self, query, item):
        query = re.sub(r"(?i)^playlist ", "", query)
        parts = re.split(r"(?i)\s+by\s+", query)
        if len(parts) > 1:
            title, creator = " by ".join(parts[:-1]), parts[-1]

            def normalize(value):
                return " ".join(value.split()).casefold()

            return normalize(title) == normalize(item.title) and normalize(creator) == normalize(
                item.creator
            )
        return super().matches_item(query, item)

    def matching_words(self, query):
        query = re.sub(r"(?i)^playlist ", "", query)
        return set(re.findall(r"\w+", query.casefold())) - {"by"}
