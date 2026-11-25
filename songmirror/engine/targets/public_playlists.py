"""Read public playlists from the services' own web players."""

import json
import os
import re
import secrets
from html import unescape

import requests

from .base import ReadOnlyPlaylistTarget, TargetAuthError, TargetCapabilityError
from .music_server import MusicApi, counted_pages, integer, rows
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


class WebPlaylistAccountTarget(PublicPlaylistTarget):
    """An authenticated playlist library alongside the anonymous link reader."""

    supports_playlist_library = True
    account_id_pattern = None

    @classmethod
    def session_key(cls):
        return f"{cls.source.upper()}_PLAYLIST_WEB_SESSION"

    @classmethod
    def library_configured(cls, get=os.getenv):
        return bool(get(cls.session_key()))

    def __init__(self, *, session=None, web_session=None):
        super().__init__(session=session)
        if web_session is None:
            try:
                web_session = json.loads(os.getenv(self.session_key()) or "{}")
            except ValueError:
                raise TargetAuthError(f"Reconnect the {self.name} browser session.") from None
        if not isinstance(web_session, dict):
            raise TargetAuthError(f"Reconnect the {self.name} browser session.")
        self.web_session = web_session
        self._signed_api = MusicApi(self.name, self.api_url, session=session)
        self._library = None

    def _requires_session(self):
        if not self.web_session:
            raise TargetCapabilityError(f"Connect a signed-in {self.name} session or paste a public playlist link.")

    def browse_playlists(self):
        self._requires_session()
        self._library = {row["id"]: row for row in self._read_directory()}
        return list(self._library.values())

    def list_playlists(self):
        result = {}
        for playlist in self.browse_playlists():
            result.setdefault(playlist["name"].strip().casefold(), playlist)
        return result

    def find_playlist(self, playlist_id):
        if not self.web_session:
            return None
        if self._library is None:
            self.browse_playlists()
        return self._library.get(str(playlist_id))

    def playlist_tracks(self, playlist):
        if playlist.get("_account_playlist") is not True:
            return super().playlist_tracks(playlist)
        owned = self.find_playlist(playlist["id"])
        if owned is None:
            raise TargetCapabilityError(f"The playlist is no longer visible in this {self.name} account.")
        result = self._read_account_playlist(owned)
        if result is None:
            raise TargetCapabilityError(f"The playlist is no longer visible in this {self.name} account.")
        return result["_tracks"]

    def _account_playlist(self, identifier, title, count, image=None, **extra):
        identifier = str(identifier or "")
        if not (self.account_id_pattern or self.id_pattern).fullmatch(identifier) or not text(title):
            raise RuntimeError(f"{self.name} returned an invalid playlist directory entry.")
        artwork = text(image)
        return {"id": identifier, "name": text(title), "count": integer(count), "_account_playlist": True,
                "images": [{"url": artwork}] if artwork.startswith("https://") else [], **extra}


class _LineStylePlaylistTarget(WebPlaylistAccountTarget):
    # LINE MUSIC and VIBE expose the same playlist envelope and track fields.
    def _read(self, key, *, signed=False):
        request = self._account_request if signed else self._api.request
        body = request("GET", self.playlist_path.format(key), params=self.playlist_params, missing=True)
        if body is None:
            return None
        playlist = self._result(body).get("playlist")
        if not isinstance(playlist, dict):
            raise RuntimeError(f"{self.name} did not return a playlist.")
        if str(playlist.get("plId")) != key or (playlist.get("isPublic") is not True
                                                and not (signed and playlist.get("isMine") is True)):
            return None
        count = playlist.get("tracksTotalCount")
        if signed and self.source == "linemusic" and playlist.get("isMine") is True and integer(count):
            tracks = self._account_request("GET", f"/api2/user/me/myAlbum/{key}/tracks.v1")
            tracks = self._result(tracks).get("tracks")
        else:
            tracks = playlist.get("tracks")
        tracks = [self._music_track(row) for row in self._check_rows(tracks, count)]
        return self._playlist(key, playlist.get("title"), tracks, count=count,
                              image=(playlist.get("image") or {}).get("baseImageUrl"),
                              description=playlist.get("desc") or playlist.get("subTitle"))

    def _account_request(self, method, path, **kwargs):
        return self._signed_api.request(method, path, headers=self._account_headers(), **kwargs)

    def _result(self, body):
        result = (body.get("response") or {}).get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"{self.name} did not return playlist data.")
        return result

    @staticmethod
    def _music_track(row):
        return track(row.get("trackId"), row.get("trackTitle"),
                     [artist.get("artistName") for artist in (row.get("artists") or [])],
                     album=(row.get("album") or {}).get("albumTitle"), seconds=row.get("playTime"))

    def _library_rows(self, entries):
        return [self._account_playlist(row.get("id"), row.get("title"), row.get("trackCount"), row.get("imageUrl"),
                                       _library_type=text(row.get("type")).upper()) for row in entries
                if text(row.get("type")).upper() in {"PLAYLIST", "MYLIST"}]


class LineMusicTarget(_LineStylePlaylistTarget):
    name = "LINE MUSIC"
    tag = source = "linemusic"
    api_url = "https://music.line.me"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,120}")
    playlist_path = "/api2/playlist/{}.v2"
    playlist_params = None

    def _account_headers(self):
        return {"Cookie": self.web_session["cookie"], "Origin": self.api_url, "Referer": self.api_url + "/webapp/",
                "X-Lang": "ja", "X-Requested-With": "XMLHttpRequest",
                **({"X-LM-DID": self.web_session["deviceid"]} if self.web_session.get("deviceid") else {})}

    def _read_directory(self):
        result = self._result(self._account_request("GET", "/api2/user/me/libraries.v1"))
        return self._library_rows(self._check_rows(result.get("libraries"), result.get("totalCount")))

    def _read_account_playlist(self, playlist):
        return self._read(playlist["id"], signed=True)


class VibeTarget(_LineStylePlaylistTarget):
    name = "Naver Vibe"
    tag = source = "vibe"
    api_url = "https://apis.naver.com"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,120}")
    playlist_path = "/vibeWeb/musicapiweb/vibe/v3/playlist/{}"
    playlist_params = {"includeOthersMix": "false"}
    _prefix = "/vibeWeb/musicapiweb"

    def _account_headers(self):
        return {"Cookie": self.web_session["cookie"], "Origin": "https://vibe.naver.com",
                "Referer": "https://vibe.naver.com/"}

    def _read_directory(self):
        path = self._prefix + "/vibe/v2/library/PLAYLIST/libraries"
        entries = counted_pages(lambda start: self._library_page(path, start), self.name)
        return self._library_rows(entries)

    def _library_page(self, path, start):
        result = self._result(self._account_request("GET", path, params={"start": start + 1, "display": 20}))
        return result.get("libraries"), result.get("totalCount")

    def _read_account_playlist(self, playlist):
        key = playlist["id"]
        if playlist["_library_type"] != "MYLIST":
            return self._read(key, signed=True)
        body = self._account_request("GET", f"{self._prefix}/myMusic/myAlbums/{key}", missing=True)
        if body is None:
            return None
        matches = self._result(body).get("myAlbums")
        album, = self._check_rows(matches, 1)
        if str(album.get("myAlbumId")) != key or not (album.get("isMine") is True or album.get("isPublic") is True):
            return None
        count = integer(album.get("trackCount"))
        if count is None or count > 10_000:
            raise RuntimeError("Naver Vibe returned an invalid playlist track count.")
        tracks = []
        for offset in range(0, count, 100):
            page = self._account_request("GET", f"{self._prefix}/myMusic/myAlbum/{key}/tracks",
                                         params={"start": offset + 1, "display": 100})
            tracks.extend(self._music_track(row) for row in self._check_rows(
                self._result(page).get("tracks"), min(100, count - offset)))
        return self._playlist(key, album.get("title"), tracks, count=count,
                              image=album.get("imageUrl"), description=album.get("desc"))


class GaanaTarget(WebPlaylistAccountTarget):
    name = "Gaana"
    tag = source = "gaana"
    api_url = "https://api.gaana.com"
    id_pattern = re.compile(r"[A-Za-z0-9_-]{1,160}")

    def _headers(self, signed=False):
        return {"Referer": "https://gaana.com/", "Origin": "https://gaana.com",
                "deviceType": "GaanaWapApp", "deviceId": self.web_session.get("deviceid", "website") if signed else "website",
                "appVersion": "V6", "gaanaAppVersion": "gaanaAndroid-8.60.2",
                **({"COUNTRY": self.web_session["country"]} if signed and self.web_session.get("country") else {})}

    def _read_directory(self):
        body = self._signed_api.request("GET", "/user.php", headers=self._headers(signed=True), params={
            "type": "myplaylists", "subtype": "myplaylists", "token": self.web_session["token"],
        })
        if integer(body.get("user_token_status")) == 0 or "login needed" in text(body.get("msg")).lower():
            raise TargetAuthError("Sign in again on Gaana and import a fresh playlist request.")
        return [self._account_playlist(row.get("playlist_id"), row.get("title") or row.get("name"),
                                       row.get("trackcount"), row.get("atw"))
                for row in rows(body.get("playlist"), "Gaana did not return a signed-in playlist directory.")]

    def _read_account_playlist(self, playlist):
        return self._read(playlist["id"], signed=True)

    def _read(self, key, *, signed=False):
        api = self._signed_api if signed else self._api
        body = api.request("GET", "/playlist/detail", missing=True, headers=self._headers(signed), params={
            ("playlist_id" if signed else "seokey"): key, "request_type": "playlist",
            **({"token": self.web_session["token"]} if signed else {}),
        })
        if body is None:
            return None
        playlist = body.get("playlist")
        if signed and (integer(body.get("user_token_status")) == 0 or "login needed" in text(body.get("msg")).lower()):
            raise TargetAuthError("Sign in again on Gaana and import a fresh playlist request.")
        if not isinstance(playlist, dict):
            if integer(body.get("error_code")) == 1002:
                return None
            raise RuntimeError(f"{self.name} did not return a playlist.")
        # Editorial playlists also use is_public=0. A matching playlist and ordered
        # track IDs returned without authentication are the public view.
        if str(playlist.get("playlist_id") if signed else playlist.get("seokey")) != key:
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


class JioSaavnTarget(WebPlaylistAccountTarget):
    name = "JioSaavn"
    tag = source = "jiosaavn"
    api_url = "https://www.jiosaavn.com"
    id_pattern = re.compile(r"(?:featured/[\w.,!~()'%-]{1,200}|s/playlist/[\w.,!~()'%-]{1,160}/[\w.,!~()'%-]{1,200})/[A-Za-z0-9_,=-]{1,100}")
    account_id_pattern = re.compile(r"[1-9][0-9]{0,18}")
    page_size = 50

    def _account_call(self, method, **params):
        body = self._signed_api.request("GET", "/api.php", headers={
            "Cookie": self.web_session["cookie"], "Origin": self.api_url, "Referer": self.api_url + "/my-music",
        }, params={"__call": method, "api_version": 4, "_format": "json", "_marker": 0, "ctx": "web6dot0", **params})
        error = body.get("error")
        if isinstance(error, dict) and error.get("code") == "LOGIN_REQUIRED":
            raise TargetAuthError("Sign in again on JioSaavn and import a fresh library request.")
        if error or body.get("status") == "failure":
            raise RuntimeError("JioSaavn rejected the account playlist request.")
        return body

    def _read_directory(self):
        result = self._account_call("library.getAll")
        entries = []
        for row in rows(result.get("playlist"), "JioSaavn did not return its playlist library."):
            identifier = str(row.get("id") or "")
            if not self.account_id_pattern.fullmatch(identifier):
                raise RuntimeError("JioSaavn returned an invalid library playlist ID.")
            if not text(row.get("title")) or integer(row.get("list_count")) is None:
                row = self._account_call("playlist.getDetails", listid=identifier, p=1, n=1)
                if str(row.get("id")) != identifier:
                    raise RuntimeError("JioSaavn returned a different library playlist.")
            entries.append(self._account_playlist(identifier, row.get("title"), row.get("list_count"), row.get("image")))
        return entries

    def _read_account_playlist(self, playlist):
        key = playlist["id"]
        body = self._account_call("playlist.getDetails", listid=key)
        count = integer(body.get("list_count"))
        if (str(body.get("id")) != key or body.get("type") != "playlist" or count is None or count > 10_000):
            return None
        entries = self._check_rows(body.get("list"), count)
        return self._playlist(key, body.get("title"), [self._jio_track(row) for row in entries], count=count,
                              image=body.get("image"), description=body.get("header_desc"))

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
        tracks = [self._jio_track(row) for row in entries]
        return self._playlist(key, first.get("title"), tracks, count=count,
                              image=first.get("image"), description=first.get("header_desc"))

    @staticmethod
    def _jio_track(row):
        if row.get("type") not in (None, "song"):
            raise RuntimeError("JioSaavn returned a playlist entry that was not a song.")
        info = row.get("more_info") or {}
        artist_map = info.get("artistMap") or {}
        performers = (artist_map.get("primary_artists") or []) + (artist_map.get("featured_artists") or [])
        if not performers:
            performers = [artist for artist in (artist_map.get("artists") or []) if artist.get("role") == "singer"]
        return track(row.get("id"), row.get("title"), [artist.get("name") for artist in performers],
                     album=info.get("album"), seconds=info.get("duration"))


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


class PandoraTarget(WebPlaylistAccountTarget):
    name = "Pandora"
    tag = source = "pandora"
    api_url = "https://www.pandora.com"
    id_pattern = re.compile(r"PL:[0-9]{1,24}:[0-9]{1,24}")
    page_size = 100

    def __init__(self, *, session=None, web_session=None, signed_session=None):
        super().__init__(session=signed_session, web_session=web_session)
        self._make_session = requests.Session if session is None else session
        self._listener = None

    def _account_headers(self):
        return {"Origin": self.api_url, "Referer": self.api_url + "/collection/playlists",
                "X-AuthToken": self.web_session["authorization"], "X-CsrfToken": self.web_session["csrf"],
                "Cookie": "csrftoken=" + self.web_session["csrf"]}

    def _read_directory(self):
        offset, total, entries, seen = 0, None, [], set()
        headers = self._account_headers()
        while total is None or offset < total:
            reply = self._signed_api.request("POST", "/api/v6/collections/getSortedPlaylists", headers=headers,
                                             json={"request": {"sortOrder": "MOST_RECENT_MODIFIED", "offset": offset,
                                                               "limit": 100, "annotationLimit": 100},
                                                   "isRecentModifiedPlaylists": False, "allowedTypes": ["TR"]})
            listener = integer(reply.get("listenerId"))
            if not listener or reply.get("listenerPandoraId") != f"LI:{listener}":
                raise TargetAuthError("Pandora did not recognize the browser session.")
            count = integer(reply.get("totalCount"))
            if (count is None or count > 10_000 or integer(reply.get("offset")) != offset
                    or (total is not None and (count != total or listener != self._listener))):
                raise RuntimeError("Pandora returned an incomplete playlist directory.")
            self._listener, total = listener, count
            if count == 0:
                return []
            items = reply.get("items")
            if not isinstance(items, list) or not items or len(items) > total - offset:
                raise RuntimeError("Pandora returned an incomplete playlist directory.")
            annotations = reply.get("annotations") or {}
            for row in items:
                data = row if isinstance(row, dict) else {}
                key = data.get("pandoraId") or (row if isinstance(row, str) else "")
                if not isinstance(key, str) or not self.id_pattern.fullmatch(key) or key in seen:
                    raise RuntimeError("Pandora returned an invalid collection playlist ID.")
                seen.add(key)
                details = annotations.get(key) or data
                if not text(details.get("name")) or integer(details.get("totalTracks")) is None:
                    details = self._get_page(self._signed_api, key, headers, 0, 0, 1)
                    if not self._check_visibility(details, key, signed=True):
                        raise TargetCapabilityError("Pandora did not confirm access to a collection playlist.")
                entries.append(self._account_playlist(key, details.get("name"), details.get("totalTracks")))
            offset += len(items)
        return entries

    def _read_account_playlist(self, playlist):
        return self._read_pages(self._signed_api, playlist["id"], self._account_headers(), signed=True)

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
            return self._read_pages(api, key, {"X-AuthToken": auth})

    @staticmethod
    def _get_page(api, key, headers, version, offset, size):
        return api.request("POST", "/api/v7/playlists/getTracks", headers=headers, missing=True,
                           json={"request": {"pandoraId": key, "playlistVersion": version, "offset": offset,
                                             "limit": size, "annotationLimit": size,
                                             "allowedTypes": ["TR"], "bypassPrivacyRules": False}})

    def _check_visibility(self, page, key, *, signed):
        if page is None:
            return False
        if integer(page.get("errorCode")) == 99000:
            raise RuntimeError("The Pandora playlist changed during the read.")
        if page.get("pandoraId") != key or type(page.get("isPrivate")) is not bool:
            raise RuntimeError("Pandora did not return the expected playlist.")
        private = page["isPrivate"] or page.get("secret") is True
        return not private or (signed and integer(page.get("listenerId")) == self._listener)

    def _read_pages(self, api, key, headers, *, signed=False):
        tracks, count, version, first = [], None, None, None
        while count is None or len(tracks) < count:
            offset = len(tracks)
            page = self._get_page(api, key, headers, version or 0, offset, self.page_size)
            if not self._check_visibility(page, key, signed=signed):
                if first is None:
                    return None
                raise RuntimeError("The Pandora playlist changed during the read.")
            total, current_version = integer(page.get("totalTracks")), integer(page.get("version"))
            if (total is None or total > 10_000 or current_version is None or integer(page.get("offset")) != offset):
                raise RuntimeError("Pandora did not return a complete playlist page.")
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


class NetEaseTarget(WebPlaylistAccountTarget):
    name = "NetEase Cloud Music"
    tag = source = "netease"
    api_url = "https://music.163.com"
    id_pattern = re.compile(r"[1-9][0-9]{0,18}")

    def _account_request(self, method, path, **kwargs):
        headers = {"Cookie": self.web_session["cookie"], "Origin": self.api_url, "Referer": self.api_url + "/"}
        return self._signed_api.request(method, path, headers=headers, **kwargs)

    def _read_directory(self):
        body = self._account_request("POST", "/api/nuser/account/get")
        uid = integer((body.get("account") or {}).get("id"))
        if integer(body.get("code")) != 200 or not uid:
            raise TargetAuthError("Sign in again on NetEase Cloud Music and import a fresh playlist request.")
        entries = []
        for _ in range(200):
            page = self._account_request("GET", "/api/user/playlist", params={
                "uid": uid, "offset": len(entries), "limit": 50,
            })
            if integer(page.get("code")) != 200:
                raise RuntimeError("NetEase Cloud Music did not return the account playlist directory.")
            current = rows(page.get("playlist"), "NetEase Cloud Music returned an invalid playlist directory.")
            more = page.get("more")
            entries.extend(current)
            if more is False:
                return [self._account_playlist(row.get("id"), row.get("name"), row.get("trackCount"),
                                               row.get("coverImgUrl")) for row in entries]
            if more is not True or not current:
                break
        raise RuntimeError("NetEase Cloud Music returned an incomplete playlist directory.")

    def _read_account_playlist(self, playlist):
        return self._read(playlist["id"], signed=True)

    def _read(self, key, *, signed=False):
        request = self._account_request if signed else self._api.request
        body = request("GET", "/api/v6/playlist/detail", params={"id": key, "n": 1000}, missing=True)
        if body is None or integer(body.get("code")) == 404:
            return None
        playlist = body.get("playlist")
        if not isinstance(playlist, dict) or integer(body.get("code")) != 200:
            raise RuntimeError("NetEase Cloud Music did not return a playlist.")
        if integer(playlist.get("id")) != int(key) or (not signed and integer(playlist.get("privacy")) != 0):
            return None
        count = playlist.get("trackCount")
        ordered_ids = [integer(row.get("id")) for row in self._check_rows(playlist.get("trackIds"), count)]
        if not all(ordered_ids):
            raise RuntimeError("NetEase Cloud Music returned an invalid playlist track ID.")
        supplied = rows(playlist.get("tracks"), "NetEase Cloud Music returned invalid tracks.")
        by_id = {integer(row.get("id")): row for row in supplied}
        for batch in chunks([track_id for track_id in dict.fromkeys(ordered_ids) if track_id not in by_id], 100):
            body = request("GET", "/api/v3/song/detail", params={"c": json.dumps([{"id": track_id} for track_id in batch])})
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
