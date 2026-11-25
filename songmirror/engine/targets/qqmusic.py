"""Read QQ Music playlists by ID using Tencent Music's documented skill API."""

import os

from .base import ReadOnlyPlaylistTarget, TargetCapabilityError
from .music_server import MusicApi, integer, rows


def _playlist_id(value):
    parsed = integer(value)
    if not parsed or parsed > 2**63 - 1:
        raise ValueError("Expected a positive QQ Music playlist ID.")
    return parsed


class QQMusicTarget(ReadOnlyPlaylistTarget):
    name = "QQ Music"
    tag = source = "qqmusic"
    supports_playlist_library = False
    no_playlists_note = "its documented playlist endpoint can only read a playlist by ID."

    def __init__(self, api_key=None, *, session=None):
        api_key = api_key or os.getenv("QQMUSIC_API_KEY")
        if not api_key:
            raise RuntimeError("QQ Music is not configured.")
        self._api = MusicApi(self.name, "https://a.y.qq.com", session=session,
                             headers={"Authorization": f"Bearer {api_key}"})

    def list_playlists(self):
        raise TargetCapabilityError("Paste a QQ Music playlist link to read its tracks.")

    def find_playlist(self, playlist_id):
        return None

    def _call(self, path, *, missing=False, **params):
        body = self._api.request("POST", path, missing=missing, json={
            "params": params, "comm": {"skill_version": "0.0.3"},
        })
        if body is not None and any(body.get(key) not in (None, 0, "0") for key in ("ret", "sub_ret")):
            raise RuntimeError("QQ Music rejected the request.")
        return body

    def validate_connection(self):
        self._call("/discover/search", keyword="music", type="0")

    def _page(self, playlist_id, page, *, missing=False):
        body = self._call("/playlists/detail", missing=missing, dissId=playlist_id, page=page)
        if body is not None and (
            integer(body.get("dissId")) != playlist_id or integer(body.get("totalNum")) is None
        ):
            raise RuntimeError("QQ Music returned an invalid playlist.")
        return body

    def fetch_playlist(self, playlist_id):
        body = self._page(_playlist_id(playlist_id), 0, missing=True)
        if body is None:
            return None
        artwork = body.get("picUrl")
        return {
            "id": str(body["dissId"]), "name": body.get("dissName") or "",
            "description": body.get("desc") or "", "count": integer(body["totalNum"]),
            "images": [{"url": artwork}] if artwork else [],
        }

    def playlist_count(self, playlist):
        return playlist.get("count")

    def track_id(self, track):
        return track.get("id")

    def playlist_tracks(self, playlist):
        playlist_id = _playlist_id(playlist["id"])
        result, count, page = [], None, 0
        while True:
            body = self._page(playlist_id, page)
            total = integer(body["totalNum"])
            if count is not None and total != count:
                raise RuntimeError("QQ Music playlist size changed during the read.")
            count = total
            tracks = rows(body.get("trackList", []), "QQ Music returned invalid playlist entries.")
            for row in tracks:
                song_id = row.get("songMid")
                if not isinstance(song_id, str) or not song_id:
                    raise RuntimeError("QQ Music returned a track without an ID.")
                artist = row.get("singerName") or ""
                result.append({"id": song_id, "name": row.get("songName") or "",
                               "artist": artist, "artists": [artist] if artist else []})
            more = body.get("hasMore")
            if more is False and len(result) == count:
                return result
            if more is not True or not tracks or len(result) >= count:
                raise RuntimeError("QQ Music returned an incomplete playlist.")
            page += 1
