"""Read QQ Music playlists by ID using Tencent Music's documented skill API."""

import os
import re

from .base import TargetAuthError
from .music_server import MusicApi, integer, rows
from .public_playlists import WebPlaylistAccountTarget

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


class QQMusicTarget(WebPlaylistAccountTarget):
    name = "QQ Music"
    tag = source = "qqmusic"
    api_url = _WEB_HOST
    id_pattern = re.compile(r"[1-9][0-9]{0,18}")
    no_playlists_note = "its playlist integration is read-only."

    def __init__(self, api_key=None, *, web=None, session=None, web_session=None):
        if (api_key is not None or web is not None) and web_session is None:
            web_session = {}
        super().__init__(session=session, web_session=web_session)
        self._web = bool(self.web_session) or (browser_mode() if web is None and api_key is None else bool(web))
        if self._web:
            self._api = MusicApi(self.name, _WEB_HOST, headers=_WEB_HEADERS, session=session)
            return
        api_key = api_key or os.getenv("QQMUSIC_API_KEY")
        if not api_key:
            raise RuntimeError("QQ Music is not configured.")
        self._api = MusicApi(self.name, "https://a.y.qq.com", session=session,
                             headers={"Authorization": f"Bearer {api_key}"})

    def _signed_request(self, module, method, params):
        credentials = self.web_session
        return self._signed_api.request("POST", "/cgi-bin/musicu.fcg", headers={
            **_WEB_HEADERS, "Cookie": credentials["cookie"],
        }, json={"comm": {"uin": credentials["uin"], "authst": credentials["authst"],
                           "ct": 19, "cv": 0, "format": "json"},
                 "req_0": {"module": module, "method": method, "param": params}})

    def _read_directory(self):
        body = self._signed_request("music.musicasset.PlaylistBaseRead", "GetPlaylistByUin",
                                    {"uin": self.web_session["uin"]})
        reply = body.get("req_0") or {}
        if integer(reply.get("code")) == 80030:
            raise TargetAuthError("Sign in again on QQ Music and import a fresh playlist request.")
        if integer(body.get("code")) != 0 or integer(reply.get("code")) != 0:
            raise RuntimeError("QQ Music did not return the signed-in playlist directory.")
        data = reply.get("data") or {}
        if data.get("bFinish") is False or data.get("bFinish") == 0:
            raise RuntimeError("QQ Music returned an incomplete account playlist directory.")
        entries = self._check_rows(data.get("v_playlist"), data.get("total"))
        return [self._account_playlist(row.get("tid"), row.get("dirName"), row.get("songNum"), row.get("dirPicUrl"))
                for row in entries if integer(row.get("tid"))]

    def _call(self, path, *, missing=False, **params):
        body = self._api.request("POST", path, missing=missing, json={
            "params": params, "comm": {"skill_version": "0.0.3"},
        })
        if body is not None and any(body.get(key) not in (None, 0, "0") for key in ("ret", "sub_ret")):
            raise RuntimeError("QQ Music rejected the request.")
        return body

    def validate_connection(self):
        self._call("/discover/search", keyword="music", type="0")

    def _page(self, playlist_id, page, *, missing=False, signed=False):
        if self._web:
            return self._web_page(playlist_id, page, missing=missing, signed=signed)
        body = self._call("/playlists/detail", missing=missing, dissId=playlist_id, page=page)
        if body is not None and (
            integer(body.get("dissId")) != playlist_id or integer(body.get("totalNum")) is None
        ):
            raise RuntimeError("QQ Music returned an invalid playlist.")
        return body

    def _web_page(self, playlist_id, page, *, missing, signed=False):
        if page >= 334:
            raise RuntimeError("QQ Music exceeded the playlist page limit.")
        begin = page * _WEB_PAGE_SIZE
        module, method = "music.srfDissInfo.aiDissInfo", "uniform_get_Dissinfo"
        params = {"disstid": playlist_id, "song_begin": begin, "song_num": _WEB_PAGE_SIZE, "onlysong": 0}
        body = (self._signed_request(module, method, params) if signed else
                self._api.request("POST", "/cgi-bin/musicu.fcg", missing=missing,
                                  json={"req_0": {"module": module, "method": method, "param": params}}))
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
        if signed and integer(directory.get("dir_show")) == 2 and integer(directory.get("owndir")) != 1:
            raise TargetAuthError("QQ Music did not confirm access to that private playlist.")
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
        signed = playlist.get("_account_playlist") is True
        if signed:
            playlist = self.find_playlist(playlist["id"])
            if playlist is None:
                raise TargetAuthError("That playlist is no longer visible in this QQ Music account.")
        playlist_id = _playlist_id(playlist["id"])
        result, count, page = [], None, 0
        while True:
            body = self._page(playlist_id, page, signed=signed)
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
