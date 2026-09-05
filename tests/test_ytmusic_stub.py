"""YT browser-session lifetime: keep it rotated, and never let an expired one
read as "no playlists / empty playlist"."""

import json

import pytest

from songmirror.engine.targets import ytmusic
from songmirror.engine.targets.base import TargetAuthError
from songmirror.engine.targets.ytmusic import (
    YTMusicBrowserTarget,
    _expired,
    _normalized_data_api_playlist_item,
    _normalized_youtubei_playlist_track,
    rotate_browser_cookie,
)


def _data_api_item(title, channel="BLOK3"):
    return {
        "id": "playlist-item-1",
        "contentDetails": {"videoId": "video-1"},
        "snippet": {
            "title": title,
            "videoOwnerChannelTitle": channel,
            "publishedAt": "2026-08-01T00:00:00Z",
        },
    }


@pytest.mark.parametrize(
    ("title", "channel", "expected"),
    [
        ("BLOK3 - KAYIP KALP (Official Music Video)", "BLOK3", "KAYIP KALP"),
        ("BLOK3 – KAYIP KALP [Official Video]", "BLOK3", "KAYIP KALP"),
        ("BLOK3: KAYIP KALP | Official Audio", "BLOK3", "KAYIP KALP"),
        ("BLOK3 | KAYIP KALP [4K]", "BLOK3", "KAYIP KALP"),
        ("BLOK3 - KAYIP KALP (Lyric Video)", "BLOK3", "KAYIP KALP"),
        ("BLOK3 - KAYIP KALP (Prod. by Worry)", "BLOK3", "KAYIP KALP"),
        ("BLOK3 - KAYIP KALP [4K · Official MV · UHD]", "BLOK3", "KAYIP KALP"),
        ("BLOK3 - KAYIP KALP (Official Video)", "BLOK3VEVO", "KAYIP KALP"),
        (
            "BLOK3 — KAYIP KALP (Official Visualizer) [4K]",
            "BLOK3 Official Channel",
            "KAYIP KALP",
        ),
        (
            "Emir Can İğrek - Ali Cabbar (Official Video)",
            "Emir Can İğrek - Topic",
            "Ali Cabbar",
        ),
    ],
)
def test_data_api_playlist_titles_strip_channel_prefixes_and_video_noise(
    title, channel, expected
):
    track = _normalized_data_api_playlist_item(_data_api_item(title, channel))

    assert track["name"] == expected


@pytest.mark.parametrize(
    "title",
    [
        "BLOK3 - KAYIP KALP (Acoustic)",
        "BLOK3 - KAYIP KALP (Live at Zorlu PSM)",
        "BLOK3 - KAYIP KALP (feat. Ati242)",
        "BLOK3 - KAYIP KALP (Official Remix)",
        "BLOK3 - KAYIP KALP [Remastered 2024]",
    ],
)
def test_data_api_playlist_titles_preserve_recording_qualifiers(title):
    track = _normalized_data_api_playlist_item(_data_api_item(title))

    assert track["name"] == title.removeprefix("BLOK3 - ")


@pytest.mark.parametrize(
    ("title", "channel", "expected"),
    [
        ("Love - Hate (Official Video)", "Some Channel", "Love - Hate"),
        ("BLOK3", "BLOK3", "BLOK3"),
        ("BLOK3 - Official Video", "BLOK3", "Official Video"),
        ("BLOK3 - KAYIP-KALP [From the Album]", "BLOK3", "KAYIP-KALP [From the Album]"),
    ],
)
def test_data_api_playlist_title_cleanup_is_conservative(title, channel, expected):
    track = _normalized_data_api_playlist_item(_data_api_item(title, channel))

    assert track["name"] == expected


def test_native_youtubei_titles_are_not_reparsed_as_raw_video_titles():
    title = "BLOK3 - KAYIP KALP (Official Music Video)"

    track = _normalized_youtubei_playlist_track({
        "videoId": "video-1",
        "title": title,
        "artists": [{"name": "BLOK3"}],
    })

    assert track["name"] == title


def _auth_file(tmp_path, ts="old"):
    p = tmp_path / "browser.json"
    p.write_text(json.dumps({"user-agent": "UA",
                             "cookie": f"SAPISID=sign; __Secure-1PSIDTS={ts}; PREF=f6=4&tz=UTC"}))
    return p


def _fake_post(status, issued):
    class R:
        status_code = status
        cookies = type("C", (), {"get_dict": lambda self: issued})()
    return lambda *a, **k: R()


def test_rotation_writes_the_new_cookie(tmp_path, monkeypatch):
    p = _auth_file(tmp_path)
    monkeypatch.setattr(ytmusic.requests, "post", _fake_post(200, {"__Secure-1PSIDTS": "new"}))
    assert rotate_browser_cookie(str(p)) is True
    cookie = json.loads(p.read_text())["cookie"]
    assert "__Secure-1PSIDTS=new" in cookie
    assert "SAPISID=sign" in cookie and "PREF=f6=4&tz=UTC" in cookie  # rest of the session intact


def test_rate_limited_rotation_leaves_the_working_cookie_alone(tmp_path, monkeypatch):
    p = _auth_file(tmp_path)
    before = p.read_text()
    monkeypatch.setattr(ytmusic.requests, "post", _fake_post(429, {}))
    assert rotate_browser_cookie(str(p)) is False
    assert p.read_text() == before


def test_unchanged_value_is_not_a_rotation(tmp_path, monkeypatch):
    p = _auth_file(tmp_path)
    monkeypatch.setattr(ytmusic.requests, "post", _fake_post(200, {"__Secure-1PSIDTS": "old"}))
    assert rotate_browser_cookie(str(p)) is False


def test_network_failure_is_survivable(tmp_path, monkeypatch):
    p = _auth_file(tmp_path)
    before = p.read_text()

    def boom(*a, **k):
        raise ytmusic.requests.RequestException("offline")

    monkeypatch.setattr(ytmusic.requests, "post", boom)
    assert rotate_browser_cookie(str(p)) is False  # a pass must still run on the stored cookie
    assert p.read_text() == before


def test_logged_out_keyerror_becomes_an_auth_error():
    assert _expired(lambda: ["ok"], "x") == ["ok"]
    with pytest.raises(TargetAuthError, match="session expired"):
        # what ytmusicapi's nav() raises when the response has no 'contents'
        _expired(lambda: (_ for _ in ()).throw(KeyError("contents")), "x")


def _target(library, alive):
    t = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)  # skip the network-touching __init__
    t._api = type("A", (), {
        "get_library_playlists": lambda self, limit=None: library,
        "get_account_info": lambda self: {"accountName": "me"} if alive else {},
    })()
    return t


def test_empty_library_on_dead_session_is_fatal_not_empty():
    # Returning {} here would make the runner recreate every playlist.
    with pytest.raises(TargetAuthError):
        _target([], alive=False).list_playlists()


def test_empty_library_on_live_session_is_honest():
    assert _target([], alive=True).list_playlists() == {}


def test_library_maps_by_casefolded_title():
    got = _target([{"title": "Chai & Chill", "playlistId": "p1", "count": 3}], alive=True).list_playlists()
    assert got["chai & chill"]["playlistId"] == "p1"


def test_topic_channel_reads_as_the_plain_artist():
    # youtubei returns either shape for the same video across passes; both must
    # normalize to one artist string or the track's canonical id flaps, and a
    # re-keyed entry is indistinguishable from a deletion.
    t = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    t._api = type("A", (), {"get_playlist": lambda self, pid, limit=None: {"tracks": [
        {"videoId": "v1", "setVideoId": "s1", "title": "Linger", "duration_seconds": 267,
         "artists": [{"name": "The Cranberries - Topic"}]},
        {"videoId": "v2", "setVideoId": "s2", "title": "Linger", "duration_seconds": 267,
         "artists": [{"name": "The Cranberries"}]},
    ]}})()
    a, b = t.playlist_tracks({"playlistId": "p1"})
    assert a["artist"] == b["artist"] == "The Cranberries"
    assert a["artists"] == b["artists"] == ["The Cranberries"]


def test_browser_adds_tracks_one_at_a_time_in_order(monkeypatch):
    calls = []
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = type("Api", (), {
        "add_playlist_items": lambda self, playlist_id, track_ids, duplicates: calls.append(
            (playlist_id, track_ids, duplicates)
        ),
    })()
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda _: None)

    target.add({"playlistId": "playlist-1"}, ["video-1", "video-2", "video-3"])

    assert calls == [
        ("playlist-1", ["video-1"], True),
        ("playlist-1", ["video-2"], True),
        ("playlist-1", ["video-3"], True),
    ]
