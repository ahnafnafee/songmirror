"""Transfer progress must reflect confirmed writes, with control between videos."""

from types import SimpleNamespace

import pytest

from songmirror.engine.targets import ytmusic
from songmirror.services.transfers import transfer


@pytest.fixture
def youtube_copy(monkeypatch):
    monkeypatch.setattr(ytmusic, "polite_sleep", lambda *_: None)
    tracks = [{"id": str(i), "videoId": str(i), "name": f"Video {i}", "artists": ["Uploader"]}
              for i in range(3)]
    source = SimpleNamespace(source="ytmusic", playlist_tracks=lambda _: tracks,
                             track_id=lambda track: track["id"])
    destination = ytmusic.YTMusicBrowserTarget.__new__(ytmusic.YTMusicBrowserTarget)
    destination.playlist_tracks = lambda _: []
    return source, destination


def test_progress_never_counts_a_youtube_video_before_its_write(youtube_copy):
    source, destination = youtube_copy
    progress, written = [], []

    def add(_playlist, ids, duplicates):
        assert progress[-1][2] == len(written), "Queued videos must not count as added"
        written.extend(ids)
        return {"status": "STATUS_SUCCEEDED"}

    destination._api = SimpleNamespace(add_playlist_items=add)
    result = transfer(source, destination, {}, {"playlistId": "copy", "_owned": True}, {}, execute=True, max_adds=100,
                      on_progress=lambda *values: progress.append(values))
    assert result["added"] == 3
    assert [added for _, _, added in progress if added] == [1, 2, 3]


@pytest.mark.parametrize("control", ["pause", "stop"])
def test_youtube_transfer_polls_control_between_confirmed_writes(youtube_copy, control):
    source, destination = youtube_copy
    written = []

    def add(_playlist, ids, duplicates):
        written.extend(ids)
        return {"status": "STATUS_SUCCEEDED"}

    destination._api = SimpleNamespace(add_playlist_items=add)
    result = transfer(source, destination, {}, {"playlistId": "copy", "_owned": True}, {}, execute=True, max_adds=100,
                      should_continue=lambda: control if written else "run")
    assert written == ["0"]
    assert result["added"] == 1
    assert result["completed"] is False
    assert result["not_found"] == []
