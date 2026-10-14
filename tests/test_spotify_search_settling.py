"""Only read-only settling may repeat after Spotify URI navigation."""

import asyncio
from types import SimpleNamespace

import pytest

from jarvis.media_data import MediaError
from jarvis.spotify_accessibility import SpotifyAccessibility


def test_rebuilding_search_field_is_read_again_without_effect_delivery():
    ui = object.__new__(SpotifyAccessibility)
    reads = []
    ui.root = lambda: object()

    def read(root):
        reads.append(root)
        if len(reads) < 3:
            raise MediaError("SPOTIFY_SEARCH_CONTROL_UNAVAILABLE")
        return None, SimpleNamespace(CurrentValue="Synthetic query")

    ui.search_field = read
    assert asyncio.run(ui.settled_search_value(lambda: None)) == "Synthetic query"
    assert len(reads) == 3


@pytest.mark.parametrize("error", ["SPOTIFY_WINDOW_CHANGED", "SPOTIFY_WINDOW_MINIMIZED"])
def test_identity_or_window_errors_are_not_treated_as_transient_search_loading(error):
    ui = object.__new__(SpotifyAccessibility)
    ui.root = lambda: object()
    ui.search_field = lambda root: (_ for _ in ()).throw(MediaError(error))
    with pytest.raises(MediaError, match=error):
        asyncio.run(ui.settled_search_value(lambda: None))


def test_cancelled_or_expired_settling_never_returns_a_search_value():
    ui = object.__new__(SpotifyAccessibility)
    reads = []
    ui.root = lambda: object()

    def read(root):
        reads.append(root)
        raise MediaError("SPOTIFY_SEARCH_CONTROL_UNAVAILABLE")

    def gate():
        if reads:
            raise MediaError("SPOTIFY_DESKTOP_STOPPED_OR_EXPIRED")

    ui.search_field = read
    with pytest.raises(MediaError, match="SPOTIFY_DESKTOP_STOPPED_OR_EXPIRED"):
        asyncio.run(ui.settled_search_value(gate))
    assert len(reads) == 1
