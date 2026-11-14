"""Manual references must identify a track on the intended service."""

import pytest

from songmirror.engine.targets import provider_ids, target_class
from songmirror.engine.track_references import normalize_track_reference


REFERENCES = [
    ("spotify", "https://open.spotify.com/track/6pHtgTMzsmP6ccN2ocv7XN?si=share", "6pHtgTMzsmP6ccN2ocv7XN"),
    ("ytmusic", "https://music.youtube.com/watch?v=c8i1Qpcnsa8&list=PLu-I-_7z66I6Az1Jj2a9P1Yj7QtT0Yl6-", "c8i1Qpcnsa8"),
    ("tidal", "https://tidal.com/browse/track/123456", "123456"),
    ("qobuz", "https://open.qobuz.com/track/123456", "123456"),
    ("deezer", "https://www.deezer.com/en/track/123456", "123456"),
    ("apple", "https://music.apple.com/us/album/my-album/1000?i=123456", "123456"),
    ("amazon", "https://music.amazon.com/albums/B08GBBC5MV/?trackAsin=B08G9TMYCZ", "B08G9TMYCZ"),
    ("lastfm", "https://www.last.fm/music/Black/_/Amar+Prithibi", "Black\u241fAmar Prithibi"),
    ("listenbrainz", "https://musicbrainz.org/recording/8f3471b5-7e6a-48da-86a9-c1c07a0f47ae", "mbid:8f3471b5-7e6a-48da-86a9-c1c07a0f47ae"),
]


def test_every_registered_target_has_reference_coverage():
    catalogs = {
        provider for provider in provider_ids()
        if getattr(target_class(provider), "catalog_ids_global", True)
        and getattr(target_class(provider), "supports_favorite_writes", True)
    }
    assert catalogs == {provider for provider, _, _ in REFERENCES}


def test_local_providers_keep_their_reference_contracts():
    assert target_class("subsonic").normalize_manual_track_id("local-song-id") == "local-song-id"
    with pytest.raises(ValueError):
        target_class("subsonic").normalize_manual_track_id("https://server.example/track/123")


@pytest.mark.parametrize("provider,reference,expected", REFERENCES)
def test_target_normalizes_links_and_raw_ids(provider, reference, expected):
    cls = target_class(provider)
    assert cls.normalize_manual_track_id(reference) == expected
    assert cls.normalize_manual_track_id(f"  {expected}  ") == expected


@pytest.mark.parametrize("provider,reference,expected", REFERENCES)
def test_legacy_manual_links_are_repaired_without_catalog_search(provider, reference, expected):
    target = target_class(provider).__new__(target_class(provider))
    cache = {"search": {"amar prithibi|black": reference}, "manual": {"amar prithibi|black"},
             "isrc": {"TEST": [{"id": "automatic-id", "name": "Amar Prithibi", "artist": "Black"}]}}
    track = {"name": "Amar Prithibi", "artists": ["Black"], "duration_ms": None, "isrc": "TEST"}
    assert target.resolve(track, cache)[0] == expected
    assert cache["search"]["amar prithibi|black"] == expected
    assert cache["dirty"] is True


@pytest.mark.parametrize("provider,reference,expected", REFERENCES)
def test_invalid_legacy_manual_reference_does_not_fall_back_to_automatic_match(provider, reference, expected):
    target = target_class(provider).__new__(target_class(provider))
    value = "https://wrong-service.example/track/123"
    cache = {"search": {"song|artist": value}, "manual": {"song|artist"}, "isrc": {}}
    with pytest.raises(ValueError):
        target.resolve({"name": "Song", "artists": ["Artist"], "duration_ms": None}, cache)
    assert cache["search"]["song|artist"] == value


@pytest.mark.parametrize("browser", [False, True])
def test_youtube_manual_link_reaches_both_writers_as_video_id_and_sync_is_idempotent(tmp_path, monkeypatch, browser):
    from types import SimpleNamespace
    from songmirror.engine import archive
    from songmirror.engine.targets import ytmusic
    from songmirror.engine.targets.base import mirror_pair

    cls = ytmusic.YTMusicBrowserTarget if browser else ytmusic.YTMusicTarget
    target = cls.__new__(cls)
    contents, sent = [], []
    target.playlist_tracks = lambda playlist: list(contents)
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda _: None)

    def added(video_id):
        sent.append(video_id)
        contents.append({"videoId": video_id, "name": "Amar Prithibi", "artist": "Black",
                         "duration_ms": 240000, "playlistItemId": "entry", "setVideoId": "entry"})

    def browser_add(playlist_id, ids, **kwargs):
        for video_id in ids:
            added(video_id)
        return {"status": "STATUS_SUCCEEDED"}

    def api_add(method, resource, **kwargs):
        assert (method, resource) == ("POST", "playlistItems")
        added(kwargs["json_body"]["snippet"]["resourceId"]["videoId"])

    if browser:
        target._api = SimpleNamespace(add_playlist_items=browser_add)
    else:
        target._request = api_add
    source = [{"id": "source-id", "name": "Amar Prithibi", "artists": ["Black"], "duration_ms": 240000}]
    cache = {"search": {"amar prithibi|black": REFERENCES[1][1]}, "manual": {"amar prithibi|black"}, "isrc": {}}
    songs = archive.connect(str(tmp_path / "songs.db"))
    archive.set_links(songs, "ytmusic", {"source-id": "oldVideo123"})
    try:
        for expected_added in (1, 0):
            result = mirror_pair(target, source, {"name": "Bangla Jatra"}, {"playlistId": "destination", "_owned": True},
                                 cache, songs, execute=True, max_removals=200, max_adds=200)
            assert result["added"] == expected_added
            assert result["removed"] == 0
        assert sent == ["c8i1Qpcnsa8"]
    finally:
        songs.close()


@pytest.mark.parametrize("provider,reference,_expected", REFERENCES)
@pytest.mark.parametrize("bad", ["not a track", "https://example.org/track/123", True, {}, "abc\n123"])
def test_all_providers_reject_invalid_manual_values(provider, reference, _expected, bad):
    with pytest.raises(ValueError):
        target_class(provider).normalize_manual_track_id(bad)


@pytest.mark.parametrize("provider,reference", [
    ("spotify", "spotify:album:6pHtgTMzsmP6ccN2ocv7XN"),
    ("spotify", "shortid"),
    ("spotify", "https://open.spotify.com/album/6pHtgTMzsmP6ccN2ocv7XN"),
    ("ytmusic", "https://music.youtube.com/playlist?list=PLtest"),
    ("ytmusic", "https://music.youtube.com/watch?v=c8i1Qpcnsa8&v=c8i1Qpcnsa8"),
    ("ytmusic", "https://youtu.be/shortid"),
    ("apple", "https://music.apple.com/us/album/some-album/123"),
    ("apple", "https://music.apple.com/us/album/some-album/123?i=456&i=789"),
    ("apple", "https://music.apple.com/library/playlist/pl.test"),
    ("amazon", "https://music.amazon.com/albums/B08GBBC5MV"),
    ("amazon", "https://music.amazon.com/albums/B08GBBC5MV?trackAsin=B08G9TMYCZ&trackAsin=B08GBBC5MV"),
    ("amazon", "https://music.amazon.com.evil.org/tracks/B08G9TMYCZ"),
    ("tidal", "https://tidal.com/browse/album/123"),
    ("qobuz", "https://open.qobuz.com/album/123"),
    ("deezer", "https://example.com/track/123"),
    ("deezer", "https://link.deezer.com/?dest=https%3A%2F%2Fevil.org%2Ftrack%2F123"),
    ("lastfm", "https://www.last.fm/music/Black"),
    ("lastfm", "Black\u241f"),
    ("lastfm", "https://www.last.fm/music/Black/_/%0ATitle"),
])
def test_wrong_resource_or_ambiguous_reference_is_rejected(provider, reference):
    with pytest.raises(ValueError):
        normalize_track_reference(provider, reference)


@pytest.mark.parametrize("provider,reference,expected", REFERENCES)
def test_untrusted_url_authorities_are_rejected(provider, reference, expected):
    host = reference.split("/")[2]
    for bad_host in (host + ".evil.org", "attacker@" + host, host + ":8000"):
        with pytest.raises(ValueError):
            normalize_track_reference(provider, reference.replace(host, bad_host, 1))


@pytest.mark.parametrize("provider,reference,expected", [
    ("spotify", "spotify:track:6pHtgTMzsmP6ccN2ocv7XN", "6pHtgTMzsmP6ccN2ocv7XN"),
    ("spotify", "open.spotify.com/intl-de/embed/track/6pHtgTMzsmP6ccN2ocv7XN", "6pHtgTMzsmP6ccN2ocv7XN"),
    ("ytmusic", "https://youtu.be/c8i1Qpcnsa8?si=shared", "c8i1Qpcnsa8"),
    ("ytmusic", "https://www.youtube.com/shorts/c8i1Qpcnsa8", "c8i1Qpcnsa8"),
    ("qobuz", "https://play.qobuz.com/#/track/123456", "123456"),
    ("apple", "https://music.apple.com/us/song/my-song/123456", "123456"),
    ("apple", "https://music.apple.com/song/123456", "123456"),
    ("amazon", "https://music.amazon.co.uk/tracks/B08G9TMYCZ", "B08G9TMYCZ"),
    ("amazon", "b08g9tmycz", "B08G9TMYCZ"),
    ("lastfm", "https://www.last.fm/music/AC%2FDC/_/Rock+%26+Roll", "AC/DC\u241fRock & Roll"),
])
def test_other_track_link_forms(provider, reference, expected):
    assert normalize_track_reference(provider, reference) == expected
