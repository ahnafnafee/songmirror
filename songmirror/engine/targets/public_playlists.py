"""Read public playlists from the services' own web players."""

import json
import re
import secrets
from html import unescape

import requests

from .base import ReadOnlyPlaylistTarget, TargetCapabilityError
from .music_server import MusicApi, integer, rows
from .provider_utils import chunks


def text(value):
    return unescape(value).strip() if isinstance(value, str) and value != "$undefined" else ""


def track(track_id, title, artists, *, album=None, seconds=None, isrc=None):
    track_id = text(track_id) or (str(track_id) if type(track_id) is int else "")
    title = text(title)
    if not track_id or not title:
        raise RuntimeError("The web player returned a track without an ID or title.")
    artists = list(dict.fromkeys(filter(None, map(text, artists))))
    return {"id": track_id, "name": title, "artist": ", ".join(artists), "artists": artists,
            "album": text(album), "duration_ms": (integer(seconds) or 0) * 1000 or None,
            "isrc": text(isrc) or None}


class PublicPlaylistTarget(ReadOnlyPlaylistTarget):
    supports_playlist_library = False
    no_playlists_note = "its web player reads public playlists by link."
    id_pattern: re.Pattern

    def __init__(self, *, session=None):
        self._api = MusicApi(self.name, self.api_url, session=session)

    def list_playlists(self):
        raise TargetCapabilityError(f"Paste a public {self.name} playlist link to read its tracks.")

    def find_playlist(self, playlist_id):
        return None

    def track_id(self, track):
        return track.get("id")

    def playlist_count(self, playlist):
        return playlist.get("count")

    def fetch_playlist(self, playlist_id):
        if not isinstance(playlist_id, str) or not self.id_pattern.fullmatch(playlist_id):
            raise ValueError(f"Expected a valid {self.name} playlist ID.")
        return self._read(playlist_id)

    def playlist_tracks(self, playlist):
        # The result returned by fetch_playlist already contains the ordered snapshot.
        if "_tracks" not in playlist:
            playlist = self.fetch_playlist(playlist["id"])
        if playlist is None:
            raise TargetCapabilityError(f"The {self.name} playlist is no longer public.")
        return playlist["_tracks"]

    def _check_rows(self, entries, count):
        error = f"{self.name} returned an incomplete playlist. Sync was stopped."
        entries = rows(entries, error)
        if len(entries) != integer(count):
            raise RuntimeError(error)
        return entries

    def _playlist(self, key, title, tracks, *, count, image=None, description=None):
        self._check_rows(tracks, count)
        if not text(title):
            raise RuntimeError(f"{self.name} returned a playlist without a title.")
        artwork = text(image)
        return {"id": key, "name": text(title), "count": len(tracks), "description": text(description),
                "images": [{"url": artwork}] if artwork.startswith("https://") else [], "_tracks": tracks}


class _LineStylePlaylistTarget(PublicPlaylistTarget):
    # LINE MUSIC and VIBE expose the same playlist envelope and track fields.
    def _read(self, key):
        body = self._api.request("GET", self.playlist_path.format(key), params=self.playlist_params, missing=True)
        if body is None:
            return None
        playlist = (body.get("response") or {}).get("result", {}).get("playlist")
        if not isinstance(playlist, dict):
            raise RuntimeError(f"{self.name} did not return a playlist.")
        if playlist.get("plId") != key or playlist.get("isPublic") is not True:
            return None
        count = playlist.get("tracksTotalCount")
        tracks = [track(row.get("trackId"), row.get("trackTitle"),
                        [artist.get("artistName") for artist in (row.get("artists") or [])],
                        album=(row.get("album") or {}).get("albumTitle"), seconds=row.get("playTime"))
                  for row in self._check_rows(playlist.get("tracks"), count)]
        return self._playlist(key, playlist.get("title"), tracks, count=count,
                              image=(playlist.get("image") or {}).get("baseImageUrl"),
                              description=playlist.get("desc") or playlist.get("subTitle"))


class LineMusicTarget(_LineStylePlaylistTarget):
    name = "LINE MUSIC"
    tag = source = "linemusic"
    api_url = "https://music.line.me"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,120}")
    playlist_path = "/api2/playlist/{}.v2"
    playlist_params = None


class VibeTarget(_LineStylePlaylistTarget):
    name = "Naver Vibe"
    tag = source = "vibe"
    api_url = "https://apis.naver.com"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,120}")
    playlist_path = "/vibeWeb/musicapiweb/vibe/v3/playlist/{}"
    playlist_params = {"includeOthersMix": "false"}


class GaanaTarget(PublicPlaylistTarget):
    name = "Gaana"
    tag = source = "gaana"
    api_url = "https://api.gaana.com"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,160}")

    def _read(self, key):
        body = self._api.request("GET", "/playlist/detail", missing=True,
                                 params={"seokey": key, "request_type": "playlist"}, headers={
                                     "Referer": "https://gaana.com/", "Origin": "https://gaana.com",
                                     "deviceType": "GaanaWapApp", "deviceId": "website", "appVersion": "V6",
                                     "gaanaAppVersion": "gaanaAndroid-8.60.2",
                                 })
        if body is None:
            return None
        playlist = body.get("playlist")
        if not isinstance(playlist, dict):
            if integer(body.get("error_code")) == 1002:
                return None
            raise RuntimeError(f"{self.name} did not return a playlist.")
        # Editorial playlists also use is_public=0. A matching playlist and ordered
        # track IDs returned without authentication are the public view.
        if playlist.get("seokey") != key:
            return None
        ordered_ids = [item.strip() for item in text(playlist.get("trackids")).split(",") if item.strip()]
        tracks = [track(row.get("track_id"), row.get("track_title"),
                        [artist.get("name") for artist in (row.get("artist") or [])],
                        album=row.get("album_title"), seconds=row.get("duration"), isrc=row.get("isrc"))
                  for row in self._check_rows(body.get("tracks"), body.get("count"))]
        if [item["id"] for item in tracks] != ordered_ids:
            raise RuntimeError(f"{self.name} returned tracks that do not match the playlist order.")
        return self._playlist(key, playlist.get("title"), tracks, count=len(ordered_ids),
                              image=playlist.get("atw") or playlist.get("artwork"))


class JioSaavnTarget(PublicPlaylistTarget):
    name = "JioSaavn"
    tag = source = "jiosaavn"
    api_url = "https://www.jiosaavn.com"
    id_pattern = re.compile(r"(?:featured/[\w.,!~()'%-]{1,200}|s/playlist/[\w.,!~()'%-]{1,160}/[\w.,!~()'%-]{1,200})/[A-Za-z0-9_,=-]{1,100}")
    page_size = 50

    def _page(self, key, page):
        return self._api.request("GET", "/api.php", missing=True, params={
            "__call": "webapi.get", "token": key.rsplit("/", 1)[-1], "type": "playlist", "p": page,
            "n": self.page_size, "includeMetaTags": 0, "ctx": "web6dot0", "api_version": 4,
            "_format": "json", "_marker": 0,
        })

    def _read(self, key):
        first = self._page(key, 1)
        if first is None or (first.get("type") == "playlist" and first.get("id") == ""):
            return None
        count = integer(first.get("list_count"))
        if first.get("type") != "playlist" or not text(first.get("id")) or count is None or count > 10_000:
            raise RuntimeError(f"{self.name} did not return a playlist with a usable track count.")
        entries = list(self._check_rows(first.get("list"), min(count, self.page_size)))
        signatures = {tuple(row.get("id") for row in entries)}
        for offset in range(self.page_size, count, self.page_size):
            page = self._page(key, offset // self.page_size + 1)
            if not page or page.get("id") != first.get("id") or integer(page.get("list_count")) != count:
                raise RuntimeError(f"{self.name} playlist changed during the read.")
            current = self._check_rows(page.get("list"), min(self.page_size, count - offset))
            signature = tuple(row.get("id") for row in current)
            if signature in signatures:
                raise RuntimeError(f"{self.name} repeated a playlist page. Sync was stopped.")
            signatures.add(signature)
            entries.extend(current)
        tracks = []
        for row in entries:
            info = row.get("more_info") or {}
            artist_map = info.get("artistMap") or {}
            performers = (artist_map.get("primary_artists") or []) + (artist_map.get("featured_artists") or [])
            if not performers:
                performers = [artist for artist in (artist_map.get("artists") or []) if artist.get("role") == "singer"]
            tracks.append(track(row.get("id"), row.get("title"), [artist.get("name") for artist in performers],
                                album=info.get("album"), seconds=info.get("duration")))
        return self._playlist(key, first.get("title"), tracks, count=count,
                              image=first.get("image"), description=first.get("header_desc"))


_FLIGHT_CHUNK = re.compile(r"self\.__next_f\.push\((\[1,.*?\])\)</script>", re.DOTALL)


def _audiomack_music(value, path):
    if isinstance(value, dict):
        music = value.get("music")
        if isinstance(music, dict) and music.get("type") == "playlist" and music.get("href") == path:
            return music
        values = value.values()
    elif isinstance(value, list):
        values = value
    else:
        return None
    return next((music for item in values if (music := _audiomack_music(item, path)) is not None), None)


class AudiomackTarget(PublicPlaylistTarget):
    name = "Audiomack"
    tag = source = "audiomack"
    api_url = "https://audiomack.com"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,150}/playlist/[A-Za-z0-9_-]{1,150}")

    def _read(self, key):
        path = "/" + key
        response = self._api.request("GET", path, headers={"Accept": "text/html"}, missing=True, expect_text=True)
        if response is None:
            return None
        flight = "".join(json.loads(match[1])[1] for match in _FLIGHT_CHUNK.finditer(response))
        for line in flight.split("\n"):
            _, _, payload = line.partition(":")
            if not payload.startswith(("[", "{")) or '"music"' not in payload:
                continue
            try:
                music = _audiomack_music(json.loads(payload), path)
            except (ValueError, RecursionError):
                continue
            if music is not None:
                break
        else:
            raise RuntimeError(f"{self.name} did not return public playlist data.")
        if music.get("isPrivate") is True:
            return None
        count = music.get("trackCount")
        tracks = [track(row.get("id"), row.get("title"), [row.get("artistName")],
                        seconds=row.get("duration"), isrc=row.get("isrc"))
                  for row in self._check_rows(music.get("tracks"), count)]
        return self._playlist(key, music.get("title"), tracks, count=count,
                              image=music.get("image"), description=music.get("description"))


class PandoraTarget(PublicPlaylistTarget):
    name = "Pandora"
    tag = source = "pandora"
    api_url = "https://www.pandora.com"
    id_pattern = re.compile(r"PL:[0-9]{1,24}:[0-9]{1,24}")
    page_size = 100

    def __init__(self, *, session=None):
        self._make_session = requests.Session if session is None else session

    def _read(self, key):
        # Start a fresh anonymous web session for each read. The guest token and
        # double-submit CSRF cookie are confined to this request sequence.
        with self._make_session() as session:
            csrf = secrets.token_hex(8)
            session.cookies.set("csrftoken", csrf, domain="www.pandora.com", path="/api")
            headers = {"Origin": self.api_url, "Referer": f"{self.api_url}/playlist/{key}", "X-CsrfToken": csrf}
            api = MusicApi(self.name, self.api_url, headers=headers, session=session)
            guest = api.request("POST", "/api/v1/auth/anonymousLogin", json={})
            auth = text(guest.get("authToken"))
            if not auth:
                raise RuntimeError("Pandora could not start an anonymous web session.")
            return self._read_pages(api, key, auth)

    def _read_pages(self, api, key, auth):
        tracks, count, version, first = [], None, None, None
        while count is None or len(tracks) < count:
            offset = len(tracks)
            page = api.request("POST", "/api/v7/playlists/getTracks", headers={"X-AuthToken": auth}, missing=True,
                               json={"request": {"pandoraId": key, "playlistVersion": version or 0, "offset": offset,
                                                 "limit": self.page_size, "annotationLimit": self.page_size,
                                                 "allowedTypes": ["TR"], "bypassPrivacyRules": False}})
            if page is None or page.get("isPrivate") is True or page.get("secret") is True:
                if first is None:
                    return None
                raise RuntimeError("The Pandora playlist changed during the read.")
            if integer(page.get("errorCode")) == 99000:
                raise RuntimeError("The Pandora playlist changed during the read.")
            total, current_version = integer(page.get("totalTracks")), integer(page.get("version"))
            if (page.get("pandoraId") != key or total is None or total > 10_000 or current_version is None
                    or integer(page.get("offset")) != offset or page.get("isPrivate") is not False):
                raise RuntimeError("Pandora did not return the expected public playlist.")
            if first is None:
                first, count, version = page, total, current_version
            elif (count, version) != (total, current_version):
                raise RuntimeError("The Pandora playlist changed during the read.")
            annotations = page.get("annotations") or {}
            for row in self._check_rows(page.get("tracks"), min(self.page_size, count - offset)):
                track_id = row.get("trackPandoraId") or row.get("pandoraId")
                info = annotations.get(track_id)
                if not isinstance(info, dict):
                    raise RuntimeError("Pandora omitted metadata for a playlist entry.")
                tracks.append(track(track_id, info.get("name"), [info.get("artistName")],
                                    album=info.get("albumName"), seconds=info.get("duration"), isrc=info.get("isrc")))
        return self._playlist(key, first.get("name"), tracks, count=count, description=first.get("description"))


class NetEaseTarget(PublicPlaylistTarget):
    name = "NetEase Cloud Music"
    tag = source = "netease"
    api_url = "https://music.163.com"
    id_pattern = re.compile(r"[1-9][0-9]{0,18}")

    def _read(self, key):
        body = self._api.request("GET", "/api/v6/playlist/detail", params={"id": key, "n": 1000}, missing=True)
        if body is None or integer(body.get("code")) == 404:
            return None
        playlist = body.get("playlist")
        if not isinstance(playlist, dict) or integer(body.get("code")) != 200:
            raise RuntimeError("NetEase Cloud Music did not return a playlist.")
        if integer(playlist.get("id")) != int(key) or integer(playlist.get("privacy")) != 0:
            return None
        count = playlist.get("trackCount")
        ordered_ids = [integer(row.get("id")) for row in self._check_rows(playlist.get("trackIds"), count)]
        if not all(ordered_ids):
            raise RuntimeError("NetEase Cloud Music returned an invalid playlist track ID.")
        supplied = rows(playlist.get("tracks"), "NetEase Cloud Music returned invalid tracks.")
        by_id = {integer(row.get("id")): row for row in supplied}
        for batch in chunks([track_id for track_id in dict.fromkeys(ordered_ids) if track_id not in by_id], 100):
            body = self._api.request("GET", "/api/v3/song/detail",
                                     params={"c": json.dumps([{"id": track_id} for track_id in batch])})
            if integer(body.get("code")) != 200:
                raise RuntimeError("NetEase Cloud Music could not supply all playlist tracks.")
            found = rows(body.get("songs"), "NetEase Cloud Music returned invalid tracks.")
            by_id.update({integer(row.get("id")): row for row in found})
        if not set(ordered_ids) <= by_id.keys():
            raise RuntimeError("NetEase Cloud Music could not supply all playlist tracks.")
        tracks = []
        for track_id in ordered_ids:
            row = by_id[track_id]
            item = track(track_id, row.get("name"), [artist.get("name") for artist in (row.get("ar") or [])],
                         album=(row.get("al") or {}).get("name"))
            item["duration_ms"] = integer(row.get("dt")) or None
            tracks.append(item)
        return self._playlist(key, playlist.get("name"), tracks, count=count,
                              image=playlist.get("coverImgUrl"), description=playlist.get("description"))


PUBLIC_PLAYLIST_TARGETS = {cls.source: cls for cls in (
    AudiomackTarget, GaanaTarget, JioSaavnTarget, LineMusicTarget, NetEaseTarget, PandoraTarget, VibeTarget,
)}
