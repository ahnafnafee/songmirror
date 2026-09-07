"""Source metadata failures reproduced from public music-video playlists."""

from types import SimpleNamespace

import pytest

from songmirror.engine.targets import ytmusic
from songmirror.engine.targets.ytmusic import (
    YTMusicTarget,
    _normalized_data_api_playlist_item,
    _normalized_youtubei_playlist_track,
)


def video_item(title, channel, video_id="video-1"):
    return {
        "id": "playlist-entry-1",
        "contentDetails": {"videoId": video_id},
        "snippet": {
            "title": title,
            "videoOwnerChannelTitle": channel,
            "publishedAt": "2026-09-01T12:00:00Z",
        },
    }


@pytest.mark.parametrize(
    ("title", "channel", "name", "artists"),
    [
        (
            "BLOK3 x POİZİ - ÇOK GÜZEL GÜLÜYORSUN (Official Music Video)",
            "Blok3", "ÇOK GÜZEL GÜLÜYORSUN", ["BLOK3", "POİZİ"],
        ),
        (
            "ALLAME x SAGOPA KAJMER - BİR ŞANSIM DAHA OLSA",
            "Allame Official", "BİR ŞANSIM DAHA OLSA", ["ALLAME", "SAGOPA KAJMER"],
        ),
        (
            "Tan Taşçı - Gidişat (Resmi Müzik Videosu)",
            "Tan Taşçı", "Gidişat", ["Tan Taşçı"],
        ),
        (
            "Sezen Aksu - Firuze (Lyrics | Şarkı Sözleri)",
            "Sezen Aksu", "Firuze", ["Sezen Aksu"],
        ),
        (
            "Motive & UZI - ANAKONDA'S (Official Visualizer)",
            "S.O.S", "ANAKONDA'S", ["Motive", "UZI"],
        ),
        (
            "Enis Arıkan - Lafı Mı Olur (Official Video)",
            "Poll Production", "Lafı Mı Olur", ["Enis Arıkan"],
        ),
        (
            "AURA - PES (Official Music Video)",
            "AURA GIRLS", "PES", ["AURA"],
        ),
        (
            "Murat Ceylan Wish | İYİ KÖPEK (Official Music Video)",
            "MuratCeylanWish", "İYİ KÖPEK", ["Murat Ceylan Wish"],
        ),
    ],
)
def test_video_metadata_uses_confirmed_credits_and_removes_production_labels(
    title, channel, name, artists,
):
    track = _normalized_data_api_playlist_item(video_item(title, channel))

    assert track["name"] == name
    assert track["artists"] == artists
    assert track["playlistItemId"] == "playlist-entry-1"


def test_browser_playlist_video_metadata_can_still_need_cleanup():
    track = _normalized_youtubei_playlist_track({
        "videoId": "video-1", "setVideoId": "entry-1",
        "title": "Pau - Kehanet", "artists": [{"name": "Pau"}],
    })

    assert track["name"] == "Kehanet"
    assert track["artists"] == ["Pau"]
    assert track["setVideoId"] == "entry-1"


@pytest.mark.parametrize(
    ("title", "channel", "name", "artists"),
    [
        ("Hadise - Ara Beni | Official Visualizer", "Hadise Acikgoz", "Ara Beni", ["Hadise"]),
        ("Can Demir - Gel Dedim Geldin", "netd müzik", "Gel Dedim Geldin", ["Candemirtheater"]),
    ],
)
def test_data_api_playlist_uses_music_credits_for_the_same_video(
    title, channel, name, artists,
):
    target = YTMusicTarget.__new__(YTMusicTarget)
    target._paged = lambda *_args: iter([video_item(title, channel)])
    target._ytm = SimpleNamespace(get_playlist=lambda *_args, **_kwargs: {
        "tracks": [{
            "videoId": "video-1", "title": name,
            "artists": [{"name": artist} for artist in artists],
        }],
    })

    tracks = target.playlist_tracks({"playlistId": "public-chart"})

    assert len(tracks) == 1
    assert tracks[0]["name"] == name
    assert tracks[0]["artists"] == artists
    assert tracks[0]["playlistItemId"] == "playlist-entry-1"
    assert tracks[0]["added_at"] == "2026-09-01T12:00:00Z"


@pytest.mark.parametrize(
    ("title", "artist", "name", "artists"),
    [
        ("Earth, Wind & Fire - September (Official Video)", "Earth, Wind & Fire", "September", ["Earth, Wind & Fire"]),
        ("Love - Hate (Official Video)", "Roxy Music", "Love - Hate", ["Roxy Music"]),
        ("Queen of Hearts", "Queen", "Queen of Hearts", ["Queen"]),
        ("BLOK3 - KAYIP KALP (Live at Wembley) [4K]", "BLOK3", "KAYIP KALP (Live at Wembley)", ["BLOK3"]),
        ("Tan Taşçı - Gidişat (Version 2.0 - Resmi Müzik Videosu)", "Tan Taşçı", "Gidişat (Version 2.0)", ["Tan Taşçı"]),
    ],
)
def test_cleanup_preserves_bands_titles_and_recording_versions(title, artist, name, artists):
    track = _normalized_data_api_playlist_item(video_item(title, artist))
    assert track["name"] == name
    assert track["artists"] == artists


@pytest.mark.parametrize("metadata", [
    {"videoId": "other-video", "title": "Another song", "artists": [{"name": "Another artist"}]},
    {"videoId": "video-1", "title": "Another song", "artists": [None]},
    {"videoId": "video-1", "title": 42, "artists": [{"name": "Another artist"}]},
    {"videoId": "video-1", "title": "Another song", "artists": []},
])
def test_unrelated_or_malformed_music_metadata_does_not_replace_the_video(metadata):
    item = video_item("BLOK3 - KAYIP KALP (Official Music Video)", "BLOK3")
    assert _normalized_data_api_playlist_item(item, metadata) == _normalized_data_api_playlist_item(item)


@pytest.mark.parametrize("qualifier", [
    "Live at Wembley", "Akustik", "Dub", "Club Mix", "First DJ Remix", "feat. Guest",
])
def test_music_metadata_cannot_erase_an_explicit_recording_variant(qualifier):
    track = _normalized_data_api_playlist_item(
        video_item(f"BLOK3 - KAYIP KALP ({qualifier})", "BLOK3"),
        {"videoId": "video-1", "title": "Kayıp Kalp", "artists": [{"name": "BLOK3"}]},
    )
    assert track["name"] == f"KAYIP KALP ({qualifier})"


def test_music_metadata_cannot_replace_a_named_remix_with_another_remix():
    track = _normalized_data_api_playlist_item(
        video_item("Artist - Song (First DJ Remix)", "Artist"),
        {"videoId": "video-1", "title": "Song (Second DJ Remix)", "artists": [{"name": "Artist"}]},
    )
    assert track["name"] == "Song (First DJ Remix)"


def test_featured_artist_prefix_preserves_the_featured_recording():
    track = _normalized_data_api_playlist_item(video_item("Artist feat. Guest - Song (Official Audio)", "Artist"))
    assert track["name"] == "Song (feat. Guest)"
    assert track["artists"] == ["Artist", "Guest"]


@pytest.mark.parametrize(("title", "expected"), [
    ("kozzy (prod. Artz & Bugy)", "kozzy"),
    ("Song [Visualizer Music Video]", "Song"),
    ("Song (Live) [Official Performance Video]", "Song (Live)"),
])
def test_production_credits_are_not_recording_variants(title, expected):
    track = _normalized_data_api_playlist_item(video_item(title, "Artist"))
    assert track["name"] == expected


def test_private_playlist_keeps_the_authenticated_read_when_public_metadata_fails():
    target = YTMusicTarget.__new__(YTMusicTarget)
    target._paged = lambda *_args: iter([video_item("BLOK3 - KAYIP KALP", "BLOK3")])

    def unavailable(*_args, **_kwargs):
        raise KeyError("contents")

    target._ytm = SimpleNamespace(get_playlist=unavailable)
    assert target.playlist_tracks({"playlistId": "private"})[0]["name"] == "KAYIP KALP"


def test_progressive_data_api_read_bounds_metadata_and_matches_video_ids():
    item = video_item("Hadise - Ara Beni", "Hadise Acikgoz")
    item["snippet"]["position"] = 500
    calls = []

    def metadata(playlist_id, *, limit):
        calls.append((playlist_id, limit))
        return {"tracks": [
            {"videoId": "unrelated", "title": "Wrong song", "artists": [{"name": "Wrong artist"}]},
            {"videoId": "video-1", "title": "Ara Beni", "artists": [{"name": "Hadise"}]},
        ]}

    target = YTMusicTarget.__new__(YTMusicTarget)
    target._request = lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {
        "items": [item], "nextPageToken": "next-page",
    })
    target._ytm = SimpleNamespace(get_playlist=metadata)
    tracks, cursor = target.playlist_tracks_page({"playlistId": "chart"}, "previous-page")

    assert calls == [("chart", 501)]
    assert cursor == "next-page"
    assert len(tracks) == 1
    assert tracks[0]["name"] == "Ara Beni"
    assert tracks[0]["playlistItemId"] == "playlist-entry-1"


def test_authenticated_data_api_failure_is_not_hidden_by_public_metadata():
    target = YTMusicTarget.__new__(YTMusicTarget)

    def denied(*_args, **_kwargs):
        raise ytmusic.TargetAuthError("expired")

    target._paged = denied
    target._ytm = SimpleNamespace(get_playlist=lambda *_args, **_kwargs: pytest.fail("must not replace the failed source read"))
    with pytest.raises(ytmusic.TargetAuthError, match="expired"):
        target.playlist_tracks({"playlistId": "chart"})
