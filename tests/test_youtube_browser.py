"""YouTube video libraries and full transfers must not use Music's filtered IDs."""

import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from songmirror.engine import youtube_browser as web
from songmirror.engine.targets import AccountBoundTarget, ytmusic
from songmirror.engine.targets.base import TargetAuthError, TargetTransientError
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.services.transfers import transfer


def _video(video_id):
    return {"lockupViewModel": {
        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO", "contentId": video_id,
        "metadata": {"lockupMetadataViewModel": {
            "title": {"content": "A video {with braces}"},
            "metadata": {"contentMetadataViewModel": {"metadataRows": [
                {"metadataParts": [{"text": {"content": "Uploader"}}]},
            ]}},
        }},
    }}


def _playlist(playlist_id, title, owned):
    return {"lockupViewModel": {
        "contentType": "LOCKUP_CONTENT_TYPE_PLAYLIST", "contentId": playlist_id,
        "contentImage": {"thumbnailBadgeViewModel": {"text": "1,250 videos"}},
        "metadata": {"lockupMetadataViewModel": {
            "title": {"content": title},
            "menuButton": {"deletePlaylistEndpoint": {"playlistId": playlist_id}} if owned else {},
        }},
    }}


def _continuation(token):
    return {"continuationItemViewModel": {"onVisible": {
        "innertubeCommand": {"continuationCommand": {"token": token}},
    }}}


def _page(items, total, token=None, hidden=False):
    return {
        "responseContext": {"mainAppWebResponseContext": {"loggedOut": False}},
        "contents": {"sectionListRenderer": {"contents": [
            {"itemSectionRenderer": {"contents": items + ([_continuation(token)] if token else [])}},
            _continuation("recommendations-must-not-be-read"),
        ]}},
        "sidebar": {"playlistSidebarPrimaryInfoRenderer": {"stats": [{"simpleText": f"{total} videos"}]}},
        "alerts": [{"alertWithButtonRenderer": {"text": {"simpleText": "Unavailable videos are hidden"}}}] if hidden else [],
    }


def _next(items, token=None):
    return {
        # Real continuations also include a skeletal, unusable contents tree.
        "contents": {"twoColumnBrowseResultsRenderer": {"tabs": []}},
        "onResponseReceivedActions": [{"appendContinuationItemsAction": {
            "continuationItems": items + ([_continuation(token)] if token else []),
        }}],
    }


class _Response:
    status_code = 200

    def __init__(self, payload, *, html=False):
        self.payload = payload
        self.text = "" if not html else (
            'ytcfg.set({"unrelated":true}); ytcfg.set(' + json.dumps({
                "INNERTUBE_CONTEXT": {"client": {"clientName": "WEB", "clientVersion": "test"}},
            }) + '); var ytInitialData = ' + json.dumps(payload) + ";"
        )

    def json(self):
        return self.payload


def _api(handler, account="0"):
    return SimpleNamespace(
        headers={"cookie": "private-session", "x-goog-authuser": account,
                 "authorization": "music-origin-signature"},
        sapisid="session-secret",
        _session=SimpleNamespace(request=handler),
    )


def test_video_library_pages_keep_duplicate_names_and_ownership(monkeypatch):
    calls = []
    monkeypatch.setattr(web.time, "time", lambda: 100)

    def request(method, url, **kwargs):
        calls.append((method, url))
        assert url.startswith(web.ORIGIN + "/")
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] > 0
        headers = kwargs["headers"]
        assert headers["x-goog-authuser"] == "2"
        assert headers["cookie"] == "private-session"
        assert headers["origin"] == headers["x-origin"] == web.ORIGIN
        signature = hashlib.sha1(b"100 session-secret https://www.youtube.com").hexdigest()
        assert headers["authorization"] == "SAPISIDHASH 100_" + signature
        if method == "GET":
            return _Response({"contents": {"richGridRenderer": {"contents": [
                _playlist("one", "Same name", True), _continuation("more-library"),
            ]}}}, html=True)
        assert kwargs["json"]["continuation"] == "more-library"
        assert kwargs["json"]["context"]["client"]["clientName"] == "WEB"
        return _Response(_next([_playlist("two", "Same name", False)]))

    library = web.YouTubeBrowser(_api(request, account="2")).playlists()
    assert [(row["playlistId"], row["title"], row["_owned"], row["count"]) for row in library] == [
        ("one", "Same name", True, 1250), ("two", "Same name", False, 1250),
    ]
    assert len(calls) == 2


def test_transfer_reads_all_795_entries_and_skips_existing_videos(monkeypatch, tmp_path):
    # Music would return three video IDs and null IDs for the other videos.
    # Regular YouTube supplies 791 playable entries and explicitly hides four.
    source_ids = [f"video-{i}" for i in range(791)]
    destination_ids = [source_ids[1], source_ids[300], source_ids[700]]
    writes, continuations = [], []
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda *_: None)

    def request(method, url, **kwargs):
        if method == "GET":
            playlist_id = parse_qs(urlparse(url).query)["list"][0]
            ids = source_ids if playlist_id == "old" else destination_ids
            return _Response(_page(
                [_video(video_id) for video_id in ids[:100]],
                795 if playlist_id == "old" else len(ids),
                "old-100" if playlist_id == "old" else ("new-100" if len(ids) > 100 else None),
                hidden=playlist_id == "old",
            ), html=True)
        token = kwargs["json"]["continuation"]
        continuations.append(token)
        kind, offset = token.split("-")
        offset = int(offset)
        ids = source_ids if kind == "old" else destination_ids
        return _Response(_next([_video(video_id) for video_id in ids[offset:offset + 100]],
                               f"{kind}-{offset + 100}" if offset + 100 < len(ids) else None))

    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    targets = []
    for label in ("Old", "New"):
        profile = profiles.create("ytmusic", label)
        target = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)
        target.cache_file = str(tmp_path / f"{profile.id}.json")
        target._api = _api(request)
        target._api.get_playlist = lambda *_args, **_kwargs: {"tracks": []}

        def add(playlist_id, video_ids, duplicates):
            assert playlist_id == "new"
            destination_ids.extend(video_ids)
            writes.extend(video_ids)
            return {"status": "STATUS_SUCCEEDED"}

        target._api.add_playlist_items = add
        target._youtube = web.YouTubeBrowser(target._api)
        targets.append(AccountBoundTarget(target, profile, profiles))
    progress = []
    cache = {"search": {}, "isrc": {}, "dirty": False}

    def copy():
        return transfer(*targets, {"playlistId": "old"}, {"playlistId": "new", "_owned": True}, cache,
                        execute=True, max_adds=3,
                        on_progress=lambda *values: progress.append(values))

    result = copy()
    assert result["completed"] is True
    assert result["added"] == 788
    assert result["unavailable"] == 4
    assert result["not_found"] == []
    assert progress[-1] == (795, 795, 788)
    assert writes == [video_id for video_id in source_ids if video_id not in source_ids[1:2] + source_ids[300:301] + source_ids[700:701]]
    assert set(destination_ids) == set(source_ids)
    writes.clear()
    assert copy()["added"] == 0
    assert writes == []
    assert "new-700" in continuations  # Dedup must read all destination pages too.


@pytest.mark.parametrize("problem", ["short", "loop", "empty", "logged-out", "malformed"])
def test_incomplete_reads_never_look_like_completed_transfers(problem):
    def request(method, _url, **_kwargs):
        if method == "GET":
            page = _page([_video("one")], 2, token="more" if problem in {"loop", "empty"} else None)
            if problem == "logged-out":
                page["responseContext"]["mainAppWebResponseContext"]["loggedOut"] = True
            if problem == "malformed":
                page["contents"] = {"unknownRenderer": {}}
            return _Response(page, html=True)
        return _Response(_next([_video("two")], "more") if problem == "loop" else _next([]))

    with pytest.raises((TargetAuthError, TargetTransientError)):
        web.YouTubeBrowser(_api(request)).tracks("playlist")


def test_empty_playlist_is_a_successful_zero_count_read():
    page = _page([], 0)
    page["sidebar"]["playlistSidebarPrimaryInfoRenderer"]["stats"][0] = {"simpleText": "No videos"}
    page["contents"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"] = [
        {"messageRenderer": {"text": {"simpleText": "No videos in this playlist yet"}}},
    ]
    client = web.YouTubeBrowser(_api(lambda *_args, **_kwargs: _Response(page, html=True)))
    assert client.tracks("empty") == []


def test_browser_picker_includes_video_only_playlists_without_changing_sync_library():
    target = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_library_playlists=lambda limit: [
        {"playlistId": "music", "title": "Mix", "count": 3},
    ])
    target._youtube = SimpleNamespace(playlists=lambda: [
        {"playlistId": "music", "title": "Mix", "count": 795, "_owned": False},
        {"playlistId": "videos", "title": "Mix", "count": 100, "_owned": True},
    ])
    assert [(p["playlistId"], p["count"], p["_owned"]) for p in target.browse_playlists()] == [
        ("music", 795, False), ("videos", 100, True),
    ]
    assert list(target.list_playlists()) == ["mix"]
    assert target.list_playlists()["mix"]["count"] == 3
    assert target.list_playlists()["mix"]["_owned"] is False
    assert target.is_editable(target.list_playlists()["mix"]) is False


def test_playlist_api_preserves_music_priority_and_category(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService

    target = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_library_playlists=lambda limit: [
        {"playlistId": "music", "title": "Zulu music", "count": 3},
    ])
    target._youtube = SimpleNamespace(playlists=lambda: [
        {"playlistId": "music", "title": "Zulu music", "count": 3, "_owned": False},
        {"playlistId": "videos", "title": "Alpha videos", "count": 100, "_owned": True},
    ])
    monkeypatch.setattr(PlaylistService, "_target", lambda *_: target)
    rows = PlaylistService(SettingsStore(dir=tmp_path)).browse("ytmusic")
    assert [(r["id"], r["library_kind"], r["owned"]) for r in rows] == [
        ("music", "music", False), ("videos", "video", True),
    ]


def test_same_named_music_playlists_both_keep_music_priority():
    target = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)
    target._api = SimpleNamespace(get_library_playlists=lambda limit: [
        {"playlistId": "first", "title": "Mix", "count": 3},
        {"playlistId": "second", "title": "Mix", "count": 4},
    ])
    target._youtube = SimpleNamespace(playlists=lambda: [
        {"playlistId": "second", "title": "Mix", "_owned": False},
        {"playlistId": "videos", "title": "Videos", "_owned": True},
    ])
    assert [(p["playlistId"], p["_library_kind"]) for p in target.browse_playlists()] == [
        ("first", "music"), ("second", "music"), ("videos", "video"),
    ]
    # Automatic sync still uses its name-keyed Music directory.
    assert len(target.list_playlists()) == 1


@pytest.mark.parametrize("status", [302, 401, 403, 429, 500])
def test_failed_http_reads_do_not_return_a_partial_library(status):
    response = _Response({})
    response.status_code = status
    client = web.YouTubeBrowser(_api(lambda *_args, **_kwargs: response))
    with pytest.raises((TargetAuthError, TargetTransientError)):
        client.playlists()


def test_empty_library_continuation_is_not_silently_accepted():
    def request(method, _url, **_kwargs):
        if method == "GET":
            return _Response({"contents": {"richGridRenderer": {"contents": [
                _playlist("one", "First page", True), _continuation("missing-page"),
            ]}}}, html=True)
        return _Response(_next([]))

    with pytest.raises(TargetTransientError):
        web.YouTubeBrowser(_api(request)).playlists()


@pytest.mark.parametrize("result", [None, {}, {"status": "STATUS_FAILED"}])
def test_unconfirmed_video_add_stops_before_later_writes(result):
    calls = []
    target = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)

    def add(playlist_id, video_ids, duplicates):
        calls.extend(video_ids)
        return result

    target._api = SimpleNamespace(add_playlist_items=add)
    with pytest.raises(TargetTransientError, match="did not confirm adding a video"):
        target.add({"playlistId": "destination", "_owned": True}, ["first", "second"])
    assert calls == ["first"]
