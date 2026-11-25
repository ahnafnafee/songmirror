"""Read QQ Music playlists by ID using Tencent Music's documented skill API."""

import os

from .base import ReadOnlyPlaylistTarget, TargetCapabilityError
from .music_server import MusicApi, integer, rows

_WEB_HOST = "https://u.y.qq.com"
_WEB_PAGE_SIZE = 30
_WEB_HEADERS = {
    "Origin": "https://y.qq.com", "Referer": "https://y.qq.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}


def browser_mode(get=os.getenv):
    return get("QQMUSIC_PREFER_BROWSER") == "1"


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

    def __init__(self, api_key=None, *, web=None, session=None):
        self._web = browser_mode() if web is None and api_key is None else bool(web)
        if self._web:
            self._api = MusicApi(self.name, _WEB_HOST, headers=_WEB_HEADERS, session=session)
            return
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
        if self._web:
            return self._web_page(playlist_id, page, missing=missing)
        body = self._call("/playlists/detail", missing=missing, dissId=playlist_id, page=page)
        if body is not None and (
            integer(body.get("dissId")) != playlist_id or integer(body.get("totalNum")) is None
        ):
            raise RuntimeError("QQ Music returned an invalid playlist.")
        return body

    def _web_page(self, playlist_id, page, *, missing):
        if page >= 334:
            raise RuntimeError("QQ Music exceeded the playlist page limit.")
        begin = page * _WEB_PAGE_SIZE
        body = self._api.request("POST", "/cgi-bin/musicu.fcg", json={"req_0": {
            "module": "music.srfDissInfo.aiDissInfo", "method": "uniform_get_Dissinfo",
            "param": {"disstid": playlist_id, "song_begin": begin, "song_num": _WEB_PAGE_SIZE, "onlysong": 0},
        }}, missing=missing)
        if body is None:
            return None
        if integer(body.get("code")) != 0 or not isinstance(body.get("req_0"), dict):
            raise RuntimeError("QQ Music's web player did not return a playlist response.")
        reply = body["req_0"]
        data = reply.get("data")
        directory = data.get("dirinfo") if isinstance(data, dict) else None
        if (integer(reply.get("code")) != 0 or not isinstance(directory, dict)
                or integer(directory.get("id")) != playlist_id):
            if missing:
                return None
            raise RuntimeError("QQ Music's web player could not reopen the public playlist.")
        total = integer(data.get("total_song_num", directory.get("songnum")))
        if total is None:
            raise RuntimeError("QQ Music's web player omitted the playlist size.")
        tracks = rows(data.get("songlist"), "QQ Music's web player returned invalid tracks.")
        if len(tracks) != min(_WEB_PAGE_SIZE, max(0, total - begin)):
            raise RuntimeError("QQ Music's web player returned an incomplete playlist page.")
        return {
            "dissId": playlist_id, "dissName": directory.get("title"), "desc": directory.get("desc"),
            "picUrl": directory.get("picurl"), "totalNum": total, "hasMore": begin + len(tracks) < total,
            "trackList": [{
                "songMid": track.get("mid") or str(integer(track.get("id")) or ""),
                "songName": track.get("name") or track.get("title"),
                "singerName": ", ".join(artist["name"] for artist in (track.get("singer") or [])
                                        if isinstance(artist, dict) and isinstance(artist.get("name"), str)),
                "album": (track.get("album") or {}).get("name") or "",
                "duration_ms": (integer(track.get("interval")) or 0) * 1000 or None,
            } for track in tracks],
        }

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
                               "artist": artist, "artists": [artist] if artist else [],
                               "album": row.get("album") or "", "duration_ms": row.get("duration_ms")})
            more = body.get("hasMore")
            if more is False and len(result) == count:
                return result
            if more is not True or not tracks or len(result) >= count:
                raise RuntimeError("QQ Music returned an incomplete playlist.")
            page += 1
