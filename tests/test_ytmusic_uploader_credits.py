"""Regressions from the post-#55 issue #44 report."""

import pytest
from types import SimpleNamespace

from songmirror.engine.targets import ytmusic
from songmirror.engine.matching import score_candidate
from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget, _normalized_data_api_playlist_item


@pytest.mark.parametrize(("title", "channel", "music_title", "expected_artists"), [
    ("Can Demir - Gel Dedim Geldin", "netd müzik", "Gel Dedim Geldin", ["Can Demir"]),
    ("Semicenk - Sende Kalmış", "Eva Records", "Sende Kalmış", ["Semicenk"]),
    ("Ebru Yaşar & Burak Bulut - Kehribar", "Mahzen Fabrick", "Kehribar", ["Ebru Yaşar", "Burak Bulut"]),
    ("Shakira, Burna Boy - Dai Dai", "shakiraVEVO", "Dai Dai", ["Shakira", "Burna Boy"]),
    ("Tame Impala - Loser", "tameimpalaVEVO", "Loser", ["Tame Impala"]),
    ("Yıldız Tilbe - Bende Kalmadı", "Avrupa Müzik", "Bende Kalmadı", ["Yıldız Tilbe"]),
    ("Rixton - Me And My Broken Heart (Official Video)", "push baby", "Me And My Broken Heart", ["Rixton"]),
])
def test_public_music_uploader_credit_cannot_overwrite_the_video_artist(
    title, channel, music_title, expected_artists,
):
    item = {"id": "occurrence", "contentDetails": {"videoId": "video"}, "snippet": {
        "title": title, "videoOwnerChannelTitle": channel,
    }}
    music = {"videoId": "video", "title": music_title, "artists": [{"name": channel}]}
    track = _normalized_data_api_playlist_item(item, music)
    assert track["name"] == music_title
    assert track["artists"] == expected_artists


@pytest.mark.parametrize("reader", ["playlist_tracks", "playlist_tracks_page", "favorite_tracks"])
def test_browser_reads_recover_original_video_credits_and_versions(monkeypatch, reader):
    rows = [{
        "videoId": "abcdefghijk", "setVideoId": "entry-1", "title": "Song",
        "artists": [{"name": "Publisher"}], "duration_seconds": 180,
        "videoType": "MUSIC_VIDEO_TYPE_OMV", "dateAdded": "2026-09-01",
    }]
    calls = []

    def video_details(video_id):
        calls.append(video_id)
        return {"title": "Artist - Song (Live at Wembley)", "author_name": "Publisher"}

    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = SimpleNamespace(
        get_playlist=lambda *_args, **_kwargs: {"tracks": rows},
        get_liked_songs=lambda **_kwargs: {"tracks": rows},
    )
    monkeypatch.setattr(ytmusic, "_public_video_metadata", video_details, raising=False)
    monkeypatch.setattr(ytmusic, "_youtubei_playlist_page", lambda *_a, **_k: (rows, "next"))
    if reader == "favorite_tracks":
        tracks = target.favorite_tracks()
    elif reader == "playlist_tracks_page":
        tracks, cursor = target.playlist_tracks_page({"playlistId": "private"})
        assert cursor == "next"
    else:
        tracks = target.playlist_tracks({"playlistId": "private"})
    assert tracks[0]["name"] == "Song (Live at Wembley)"
    assert tracks[0]["artists"] == ["Artist"]
    assert tracks[0]["setVideoId"] == "entry-1"
    assert tracks[0]["duration_ms"] == 180000
    assert tracks[0]["added_at"] == "2026-09-01"
    assert calls == ["abcdefghijk"]
    target.playlist_tracks({"playlistId": "private"})
    assert calls == ["abcdefghijk"]  # Same video on another read uses the local cache.


@pytest.mark.parametrize(("title", "channel", "expected_name", "expected_artists"), [
    ("Can Demir - Gel Dedim Geldin - netd müzik", "netd müzik", "Gel Dedim Geldin", ["Can Demir"]),
    ("Semicenk - Sende Kalmış - Eva Records", "Eva Records", "Sende Kalmış", ["Semicenk"]),
    ("Mahşer [Official Video] - Gökhan Türkmen #Mahşer", "Gökhan Türkmen", "Mahşer", ["Gökhan Türkmen"]),
    ("Yalın - Son Aşkım #EllerineSağlık", "YALIN", "Son Aşkım", ["Yalın"]),
    ("Senle Zor", "Yener Çevik Official", "Senle Zor", ["Yener Çevik"]),
])
def test_video_metadata_fallback_does_not_search_for_publishers_or_hashtags(
    title, channel, expected_name, expected_artists,
):
    item = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": title, "videoOwnerChannelTitle": channel,
    }}
    track = _normalized_data_api_playlist_item(item)
    assert track["name"] == expected_name
    assert track["artists"] == expected_artists


@pytest.mark.parametrize(("title", "channel", "name", "artists"), [
    ("Selcan - Senden Adam Olmaz (Prod. Yusuf Tomakin)", "OfficialYusufTomakin", "Senden Adam Olmaz", ["Selcan"]),
    ("Pınar Soykan - Sakla (Erhan Boraer Remix)", "Erhan Boraer", "Sakla (Erhan Boraer Remix)", ["Pınar Soykan"]),
    ("BLOK3 x POİZİ - ÇOK GÜZEL GÜLÜYORSUN", "Blok3", "ÇOK GÜZEL GÜLÜYORSUN", ["BLOK3", "POİZİ"]),
    ("manifest X Ajda Pekkan - Hileli", "manifest", "Hileli", ["manifest", "Ajda Pekkan"]),
    ("Sibel Can & Eypio - KIYAMAM", "Sibel Can", "KIYAMAM", ["Sibel Can", "Eypio"]),
    ("Mabel Matiz - Ha Leylim", "mabelmatiz", "Ha Leylim", ["Mabel Matiz"]),
    ("ALLAME x SAGOPA KAJMER - BİR ŞANSIM DAHA OLSA", "Allame Official", "BİR ŞANSIM DAHA OLSA", ["ALLAME", "SAGOPA KAJMER"]),
    ("Gökhan Doğanay - Kala Kala Kaldım (Diyemedim) [2026 Official Audio]", "Gökhan Doğanay Resmi", "Kala Kala Kaldım (Diyemedim)", ["Gökhan Doğanay"]),
    ("Yalın - Akşamüstü", "YALIN", "Akşamüstü", ["Yalın"]),
    ("Eva Simons - Policeman (Official Video)", "Default.1", "Policeman", ["Eva Simons"]),
])
def test_same_video_title_recovers_collaborators_and_producer_uploads(title, channel, name, artists):
    item = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": title, "videoOwnerChannelTitle": channel,
    }}
    music = {"videoId": "video", "title": name, "artists": [{"name": channel}]}
    track = _normalized_data_api_playlist_item(item, music)
    assert track["name"] == name
    assert track["artists"] == artists


def test_browser_public_metadata_failure_keeps_the_authenticated_occurrence(monkeypatch):
    raw = {
        "videoId": "abcdefghijk", "setVideoId": "entry-1", "title": "Song (Dub)",
        "artists": [{"name": "Artist"}], "videoType": "MUSIC_VIDEO_TYPE_OMV",
    }
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_playlist=lambda *_a, **_k: {"tracks": [raw]})
    monkeypatch.setattr(ytmusic, "_public_video_metadata", lambda _vid: None)
    tracks = target.playlist_tracks({"playlistId": "private"})
    assert tracks[0]["name"] == "Song (Dub)"
    assert tracks[0]["setVideoId"] == "entry-1"


def test_browser_art_tracks_do_not_fetch_video_metadata(monkeypatch):
    target = YTMusicBrowserTarget.__new__(YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_playlist=lambda *_a, **_k: {"tracks": [{
        "videoId": "abcdefghijk", "title": "Song", "artists": [{"name": "Artist"}],
        "videoType": "MUSIC_VIDEO_TYPE_ATV",
    }]})
    monkeypatch.setattr(ytmusic, "_public_video_metadata", lambda _vid: pytest.fail("catalog art track"))
    assert target.playlist_tracks({"playlistId": "playlist"})[0]["name"] == "Song"


def test_a_title_separator_and_unknown_channel_do_not_invent_an_artist():
    raw = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": "Love - Hate (Official Video)", "videoOwnerChannelTitle": "Some Channel",
    }}
    music = {"videoId": "video", "title": "Love - Hate", "artists": [{"name": "Some Channel"}]}
    track = _normalized_data_api_playlist_item(raw, music)
    assert track["name"] == "Love - Hate"
    assert track["artists"] == ["Some Channel"]


def test_unseparated_credit_does_not_duplicate_case_variants_of_the_artist():
    raw = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": "ADANALI AYHAN Silah Sıkarım Havaya", "videoOwnerChannelTitle": "ADANALI AYHAN",
    }}
    music = {"videoId": "video", "title": "Silah Sıkarım Havaya", "artists": [{"name": "Adanalı Ayhan"}]}
    track = _normalized_data_api_playlist_item(raw, music)
    assert track["name"] == "Silah Sıkarım Havaya"
    assert track["artists"] == ["ADANALI AYHAN"]


def test_a_recording_year_and_literal_hashtag_title_are_preserved():
    for title in ["Song (2026)", "#SELFIE"]:
        raw = {"contentDetails": {"videoId": "video"}, "snippet": {
            "title": title, "videoOwnerChannelTitle": "Artist",
        }}
        assert _normalized_data_api_playlist_item(raw)["name"] == title


@pytest.mark.parametrize(("tag", "qualifier"), [
    ("Acoustic", "Acoustic"), ("Live", "Live"), ("Dub", "Dub"), ("Remix", "Remix"),
    ("SpedUp", "Sped Up"), ("Radio_Edit", "Radio Edit"), ("feat_Guest", "feat Guest"),
])
def test_recording_hashtags_cannot_become_studio_matches(tag, qualifier):
    raw = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": f"Artist - Song #{tag} #Promotion", "videoOwnerChannelTitle": "Artist",
    }}
    music = {"videoId": "video", "title": "Song", "artists": [{"name": "Artist"}]}
    track = _normalized_data_api_playlist_item(raw, music)
    assert track["name"] == f"Song ({qualifier})"
    assert score_candidate(track["name"], track["artist"], 180000, "Song", "Artist", 180000) == (0.0, False)
    assert score_candidate(track["name"], track["artist"], 180000, f"Song ({qualifier})", "Artist", 180000)[1]


def test_featured_collaborators_separated_by_x_match_catalog_guest_lists():
    raw = {"contentDetails": {"videoId": "video"}, "snippet": {
        "title": "TUĞRUL BEKTAŞ ft. ORTAQ x CASH FLOW x KAISA NATRON - BURDA GECELER [Visualizer Music Video]",
        "videoOwnerChannelTitle": "Tuğrul Bektaş",
    }}
    name = "BURDA GECELER (feat. Ortaq, Cash Flow & Kaisa Natron)"
    music = {"videoId": "video", "title": name, "artists": [{"name": "Tuğrul Bektaş"}]}
    track = _normalized_data_api_playlist_item(raw, music)
    assert track["artists"] == ["TUĞRUL BEKTAŞ", "ORTAQ", "CASH FLOW", "KAISA NATRON"]
    assert score_candidate(track["name"], track["artist"], 249000, name, "Tuğrul Bektaş", 249000)[1]
