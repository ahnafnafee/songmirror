"""Provider playlist-link parsing and track-link building."""

import pytest

from songmirror.services.playlist_links import (
    PlaylistLinkError, external_url, parse_playlist_link, track_url,
)


@pytest.mark.parametrize("text, expected", [
    # Spotify: web link, localized web link, share query, and the desktop URI.
    ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
     ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
    ("https://open.spotify.com/intl-de/playlist/37i9dQZF1DXcBWIGoYBM5M",
     ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
    ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123",
     ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
    ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
    # Apple: a public link carries a catalog id, not a library one.
    ("https://music.apple.com/us/playlist/todays-hits/pl.f4d106fed2bd41149aaacabb233eb5eb",
     ("apple", "pl.f4d106fed2bd41149aaacabb233eb5eb")),
    ("https://music.apple.com/gb/playlist/my-mix/pl.u-8aAveKJudDdMqW",
     ("apple", "pl.u-8aAveKJudDdMqW")),
    # YouTube Music: the id is a query parameter, on either host.
    ("https://music.youtube.com/playlist?list=PLabc123def", ("ytmusic", "PLabc123def")),
    ("https://www.youtube.com/playlist?list=PLabc123def", ("ytmusic", "PLabc123def")),
    ("https://music.youtube.com/browse/VLPLabc123def", ("ytmusic", "PLabc123def")),
    # TIDAL: uuid, on the marketing host, the browse route, or the web player.
    ("https://tidal.com/playlist/dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f",
     ("tidal", "dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f")),
    ("https://tidal.com/browse/playlist/dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f",
     ("tidal", "dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f")),
    ("https://listen.tidal.com/playlist/dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f",
     ("tidal", "dcb0f8f9-1c0b-4b6a-9f0e-1a2b3c4d5e6f")),
    # Deezer: numeric, with or without the language segment.
    ("https://www.deezer.com/playlist/1234567890", ("deezer", "1234567890")),
    ("https://www.deezer.com/en/playlist/1234567890", ("deezer", "1234567890")),
    ("https://deezer.com/us/playlist/1234567890", ("deezer", "1234567890")),
    # Qobuz: numeric, on either web player host.
    ("https://open.qobuz.com/playlist/12345678", ("qobuz", "12345678")),
    ("https://play.qobuz.com/playlist/12345678", ("qobuz", "12345678")),
    # Amazon: one host per marketplace, two playlist routes.
    ("https://music.amazon.com/user-playlists/abc123def456", ("amazon", "abc123def456")),
    ("https://music.amazon.co.uk/playlists/abc123def456", ("amazon", "abc123def456")),
    # A bare host with no scheme still parses.
    ("open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
     ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
])
def test_parses_every_provider(text, expected):
    assert parse_playlist_link(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "   ",
    "not a link at all",
    "https://example.com/playlist/123",       # unknown service
    "https://soundcloud.com/user/sets/mix",   # unsupported service
])
def test_unknown_input_is_not_a_link(text):
    assert parse_playlist_link(text) is None


@pytest.mark.parametrize("text", [
    "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3",
    "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
    "https://music.apple.com/us/album/some-album/1440746552",
    "https://www.deezer.com/en/album/1234567",
    "https://tidal.com/browse/album/12345678",
    "https://music.amazon.com/albums/B000000000",
])
def test_known_service_but_not_a_playlist_is_reported(text):
    # Worth distinguishing from "unknown link": the user pasted the right
    # service and the wrong page, and the message can say so.
    with pytest.raises(PlaylistLinkError):
        parse_playlist_link(text)


def test_deezer_share_link_follows_one_redirect():
    calls = []

    def fake_redirect(url):
        calls.append(url)
        return "https://www.deezer.com/en/playlist/1234567890"

    assert parse_playlist_link(
        "https://link.deezer.com/s/30abcDEF", resolve_redirect=fake_redirect
    ) == ("deezer", "1234567890")
    assert calls == ["https://link.deezer.com/s/30abcDEF"]


def test_deezer_share_link_that_does_not_resolve_is_reported():
    with pytest.raises(PlaylistLinkError):
        parse_playlist_link(
            "https://link.deezer.com/s/30abcDEF", resolve_redirect=lambda url: None
        )


@pytest.mark.parametrize("provider, expected", [
    ("spotify", "https://open.spotify.com/track/ID"),
    ("ytmusic", "https://music.youtube.com/watch?v=ID"),
    ("tidal", "https://listen.tidal.com/track/ID"),
    ("deezer", "https://www.deezer.com/track/ID"),
    ("qobuz", "https://open.qobuz.com/track/ID"),
    ("amazon", "https://music.amazon.com/tracks/ID"),
    ("apple", "https://music.apple.com/song/ID"),
])
def test_track_url_per_provider(provider, expected):
    assert track_url(provider, "ID") == expected


@pytest.mark.parametrize("provider, track_id", [
    ("spotify", ""),      # an unmatched cache entry has no id to link to
    ("spotify", None),
    ("jellyfin", "ID"),   # browse-only service, no track pages
])
def test_track_url_is_empty_without_a_linkable_id(provider, track_id):
    assert track_url(provider, track_id) == ""


def test_external_url_covers_playlists_too():
    assert external_url("spotify", "playlist", "PID") == "https://open.spotify.com/playlist/PID"
    assert external_url("apple", "playlist", "p.PID") == "https://music.apple.com/library/playlist/p.PID"
    assert external_url("ytmusic", "playlist", "PID") == "https://music.youtube.com/playlist?list=PID"
