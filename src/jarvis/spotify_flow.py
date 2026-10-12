"""Named Spotify song/playlist workflow, reusing the broker-bound media phases."""

import re

from jarvis.youtube_flow import YouTubeFlow


def named_spotify_request(text):
    value = text.strip().rstrip(".!?")
    value = re.sub(r"(?i)^(?:please |(?:can|could|would) you (?:please )?)", "", value)
    services = {s.casefold() for s in re.findall(r"(?i)\b(youtube|spotify|netflix)\b", value)}
    if services != {"spotify"} or re.search(
        r"(?i)^(?:do not|don't|how (?:do|can)|explain|like|follow|subscribe|upload|download|"
        r"buy|click|type|delete|remove|save|add)\b|\b(?:password|javascript)\b",
        value,
    ):
        return None
    for goal, pattern in [
        ("play", r"(?:search|open) spotify and play (.+)"),
        ("play", r"(?:search|find) (?:on )?spotify for (.+?) (?:and|then) play(?: it)?"),
        ("play", r"play (.+?) (?:on|in) spotify"),
        ("play", r"play (?:on )?spotify (.+)"),
        ("search", r"(?:search|find) (?:on )?spotify for (.+)"),
    ]:
        match = re.fullmatch(pattern, value, re.I)
        if not match:
            continue
        query = match[1].strip()
        if re.fullmatch(
            r"(?i)(?:it|music|a song|a playlist|the song|the playlist|this|that)", query
        ):
            return None
        if re.search(
            r"(?i)\b(?:and|then)\s+(?:open|play|pause|resume|search|close|buy)\b|;", query
        ):
            return None
        query = re.sub(r"(?i)^(?:a |the )?(?:song|track) (?:called |named )?", "", query)
        query = re.sub(r"(?i)^(?:my |the |a )?playlist (?:called |named )?", "playlist ", query)
        return goal, query
    return None


class SpotifyFlow(YouTubeFlow):
    service = "spotify"
    service_name = "Spotify"
    noun = "song or playlist"
    named_request = staticmethod(named_spotify_request)

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
