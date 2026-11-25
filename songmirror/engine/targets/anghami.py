"""Read music playlists through the Anghami SDK's REST gateway."""

import hashlib
import os
from pathlib import Path
from threading import RLock
from urllib.parse import quote

from ...oauth import read_token, token_is_live, with_expiry
from ...services.private_files import write_private
from ..matching import normalize_isrc
from .base import ReadOnlyPlaylistTarget, TargetAuthError
from .music_server import MusicApi, integer, rows
from .provider_utils import chunks

API = "https://sdk.anghami.com"
TOKEN_FILE = "anghami_oauth.json"
_token_lock = RLock()


def _value(item):
    value = item.get("value") if isinstance(item, dict) else None
    return value if isinstance(value, str) else ""


class AnghamiApi:
    def __init__(self, client_id, token_file, *, session=None):
        self._client_id = client_id
        self._client_key = hashlib.sha256(client_id.encode()).hexdigest()
        self._token_file = Path(token_file)
        self._api = MusicApi("Anghami", API, session=session)

    def configured(self):
        tokens = read_token(self._token_file)
        return bool(tokens.get("refresh_token")) and tokens.get("client_key") == self._client_key

    def disconnect(self):
        with _token_lock:
            self._token_file.unlink(missing_ok=True)

    def _exchange(self, path, params, *, refresh=None):
        body = self._api.request("POST", path, json={"clientId": self._client_id, **params})
        # The gateway specification wraps TokenInfo. Accept the flat token
        # response also illustrated in the SDK's OAuth walkthrough.
        token = body.get("token", body)
        if not isinstance(token, dict):
            raise RuntimeError("Anghami returned an invalid OAuth response.")
        access = token.get("accessToken", token.get("access_token"))
        refresh = token.get("refreshToken", token.get("refresh_token")) or refresh
        expires = integer(token.get("expiresIn", token.get("expires_in")))
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or not expires:
            raise RuntimeError("Anghami returned incomplete OAuth credentials.")
        return with_expiry({"access_token": access, "refresh_token": refresh, "expires_in": expires,
                            "client_key": self._client_key})

    def authorize(self, code, verifier, redirect_uri):
        with _token_lock:
            tokens = self._exchange("/v1/auth/token", {
                "code": code, "codeVerifier": verifier, "redirectUri": redirect_uri,
            })
            self._api.request("GET", "/v1/playlists", params={"page_size": 1},
                              headers={"Authorization": f"Bearer {tokens['access_token']}"})
            write_private(self._token_file, tokens)

    def _access(self, rejected=None):
        with _token_lock:
            tokens = read_token(self._token_file)
            refresh = tokens.get("refresh_token")
            if not refresh or tokens.get("client_key") != self._client_key:
                raise TargetAuthError("Connect your Anghami account again.")
            if token_is_live(tokens, leeway=30) and tokens["access_token"] != rejected:
                return tokens["access_token"]
            tokens = self._exchange("/v1/auth/token/refresh", {"refreshToken": refresh}, refresh=refresh)
            write_private(self._token_file, tokens)
            return tokens["access_token"]

    def request(self, method, path, **kwargs):
        access = self._access()
        try:
            return self._api.request(method, path, headers={"Authorization": f"Bearer {access}"}, **kwargs)
        except TargetAuthError:
            access = self._access(rejected=access)
            return self._api.request(method, path, headers={"Authorization": f"Bearer {access}"}, **kwargs)


class AnghamiTarget(ReadOnlyPlaylistTarget):
    name = "Anghami"
    tag = source = "anghami"
    no_playlists_note = "its SDK can only read playlists."

    def __init__(self, client=None):
        if client is None:
            client_id = os.getenv("ANGHAMI_CLIENT_ID")
            if not client_id:
                raise RuntimeError("Anghami is not configured.")
            client = AnghamiApi(client_id, os.getenv("ANGHAMI_TOKEN_FILE") or TOKEN_FILE)
            if not client.configured():
                raise RuntimeError("Anghami is not connected.")
        self._api = client

    @staticmethod
    def _playlist(raw):
        playlist_id = _value(raw.get("id")) if isinstance(raw, dict) else ""
        if not playlist_id:
            raise RuntimeError("Anghami returned a playlist without an ID.")
        artwork = (raw.get("coverArtwork") or {}).get("url")
        return {
            "id": playlist_id, "name": _value(raw.get("name")), "description": _value(raw.get("description")),
            "count": integer(raw.get("itemCount")), "images": [{"url": artwork}] if artwork else [],
        }

    def _pages(self, path):
        params = {"page_size": 100}
        seen = set()
        while True:
            body = self._api.request("GET", path, params=params)
            yield body
            token = body.get("nextPageToken")
            if not token:
                return
            if not isinstance(token, str) or token in seen:
                raise RuntimeError("Anghami returned an invalid playlist page token.")
            seen.add(token)
            params = {**params, "page_token": token}

    def browse_playlists(self):
        return [self._playlist(item) for page in self._pages("/v1/playlists")
                for item in rows(page.get("playlists", []), "Anghami returned invalid playlist data.")]

    def list_playlists(self):
        return {item["name"].strip().casefold(): item for item in self.browse_playlists()}

    @staticmethod
    def _path(playlist_id):
        if not isinstance(playlist_id, str) or playlist_id in ("", ".", ".."):
            raise ValueError("Expected an Anghami playlist ID.")
        return f"/v1/playlists/{quote(str(playlist_id), safe='')}"

    def fetch_playlist(self, playlist_id):
        body = self._api.request("GET", self._path(playlist_id), params={"page_size": 1}, missing=True)
        if body is None:
            return None
        playlist = self._playlist(body.get("playlist"))
        if playlist["id"] != playlist_id:
            raise RuntimeError("Anghami returned a different playlist.")
        return playlist

    def playlist_count(self, playlist):
        return playlist.get("count")

    def track_id(self, track):
        return track.get("id")

    def playlist_tracks(self, playlist):
        items, count = [], None
        for page in self._pages(self._path(playlist["id"])):
            info = self._playlist(page.get("playlist"))
            if info["id"] != playlist["id"] or (count is not None and info["count"] != count):
                raise RuntimeError("Anghami returned a different playlist snapshot.")
            count = info["count"]
            items.extend(rows(page.get("items", []), "Anghami returned invalid playlist items."))
        if count is not None and count != len(items):
            raise RuntimeError("Anghami returned an incomplete playlist.")
        entries = []
        for position, item in enumerate(items):
            content = item.get("content")
            if not isinstance(content, dict) or integer(item.get("position", 0)) != position:
                raise RuntimeError("Anghami returned an invalid playlist entry.")
            if "songId" in content:
                song_id = _value(content["songId"])
                if not song_id:
                    raise RuntimeError("Anghami returned a song without an ID.")
                entries.append((song_id, item, content))
        songs = {}
        for batch in chunks(list(dict.fromkeys(song_id for song_id, _, _ in entries)), 100):
            body = self._api.request("POST", "/v1/music/songs:batchGet",
                                     json={"songIdList": [{"value": song_id} for song_id in batch]})
            results = body.get("results")
            if not isinstance(results, dict) or any(not isinstance(results.get(key), dict) for key in batch):
                raise RuntimeError("Anghami returned incomplete song metadata.")
            for key in batch:
                song = results[key].get("song")
                if song is None and isinstance(results[key].get("error"), dict):
                    song = {}
                elif not isinstance(song, dict) or _value(song.get("id")) != key:
                    raise RuntimeError("Anghami returned invalid song metadata.")
                songs[key] = song
        tracks = []
        for song_id, item, content in entries:
            song = songs[song_id]
            artists = [_value(artist.get("name")) for artist in song.get("artists", [])]
            artists = [artist for artist in artists if artist] or ([content["subtitle"]] if content.get("subtitle") else [])
            tracks.append({
                "id": song_id, "name": _value(song.get("title")) or content.get("title") or "",
                "artist": ", ".join(artists), "artists": artists, "duration_ms": integer(song.get("durationMs")),
                "isrc": normalize_isrc(song.get("isrc")) or None, "added_at": item.get("addedAt") or "",
            })
        return tracks
