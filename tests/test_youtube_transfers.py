"""YouTube account copies retain exact video identities across full playlist reads."""

import pytest

from songmirror.engine.targets import AccountBoundTarget, ytmusic
from songmirror.engine.targets.ytmusic import YTMusicBrowserTarget, YTMusicTarget
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.settings import SettingsStore
from songmirror.services.transfers import transfer


@pytest.mark.parametrize("browser", [False, True], ids=["oauth", "browser"])
@pytest.mark.parametrize("separate_accounts", [False, True], ids=["public-link", "two-accounts"])
def test_long_youtube_copy_uses_exact_ids_and_reads_every_page(
    monkeypatch, tmp_path, browser, separate_accounts,
):
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda _: None)
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    destination_profile = profiles.create("ytmusic", "New account")
    source_profile = profiles.create("ytmusic", "Old account") if separate_accounts else destination_profile
    reads, writes = [], []
    # Every video shares its display metadata. A metadata-based dedup would
    # silently discard most of this playlist instead of copying its video ids.
    source_ids = [f"video-{index}" for index in range(125)]
    playlists = {"old-playlist": source_ids + [source_ids[0]], "new-playlist": source_ids[:2]}

    def row(video_id, *, destination):
        return {
            "videoId": video_id,
            "title": "Changed title" if destination else "Same title",
            "artists": [{"name": "Same artist"}],
            "videoType": "MUSIC_VIDEO_TYPE_ATV",
        }

    class Response:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def request(method, path, params=None, json_body=None):
        assert path == "playlistItems"
        if method == "POST":
            snippet = json_body["snippet"]
            assert snippet["playlistId"] == "new-playlist"
            video_id = snippet["resourceId"]["videoId"]
            writes.append(video_id)
            playlists["new-playlist"].append(video_id)
            return Response({})
        assert method == "GET"
        playlist_id = params["playlistId"]
        offset = int(params.get("pageToken", "0"))
        size = params["maxResults"]
        reads.append((playlist_id, offset))
        ids = playlists[playlist_id]
        data = {"items": [
            {
                "id": f"entry-{offset + index}",
                "contentDetails": {"videoId": video_id},
                "snippet": {
                    "title": "Changed title" if playlist_id == "new-playlist" else "Same title",
                    "videoOwnerChannelTitle": "Same artist",
                },
            }
            for index, video_id in enumerate(ids[offset:offset + size])
        ]}
        if offset + size < len(ids):
            data["nextPageToken"] = str(offset + size)
        return Response(data)

    class BrowserAPI:
        def get_playlist(self, playlist_id, limit):
            assert limit is None, "A transfer must read the entire playlist"
            reads.append((playlist_id, limit))
            return {"tracks": [row(video_id, destination=playlist_id == "new-playlist")
                               for video_id in playlists[playlist_id]]}

        def add_playlist_items(self, playlist_id, video_ids, duplicates):
            assert playlist_id == "new-playlist"
            writes.extend(video_ids)
            playlists[playlist_id].extend(video_ids)
            return {"status": "STATUS_SUCCEEDED"}

    def target(profile):
        adapter = (YTMusicBrowserTarget if browser else YTMusicTarget).__new__(
            YTMusicBrowserTarget if browser else YTMusicTarget,
        )
        adapter.cache_file = str(tmp_path / f"{profile.id}.json")
        adapter._request = request
        adapter._api = BrowserAPI()

        def resolve(*_args):
            pytest.fail("YouTube-to-YouTube must copy original video ids without searching")

        adapter.resolve = resolve
        return AccountBoundTarget(adapter, profile, profiles)

    source, destination = target(source_profile), target(destination_profile)
    progress = []
    cache = {"search": {}, "isrc": {}, "dirty": False}

    def copy():
        return transfer(
            source, destination,
            {"playlistId": "old-playlist"}, {"playlistId": "new-playlist", "_owned": True},
            cache, execute=True, max_adds=3,
            on_progress=lambda *values: progress.append(values),
        )

    result = copy()

    assert result["completed"] is True
    assert result["added"] == 123  # The sync cap must not truncate a one-off copy.
    assert result["not_found"] == []
    assert playlists["new-playlist"] == source_ids
    assert writes == source_ids[2:]
    assert progress[-1] == (126, 126, 123)
    if not browser:
        assert reads[:3] == [("old-playlist", 0), ("old-playlist", 50), ("old-playlist", 100)]

    # A repeat after metadata changes must find all existing videos by id.
    writes.clear()
    assert copy()["added"] == 0
    assert writes == []
