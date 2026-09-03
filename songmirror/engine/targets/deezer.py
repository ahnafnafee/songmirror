"""Deezer playlist peer through the web player or documented REST API."""

import os
import random
import re
import time
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from ...deezer_web import (
    DEFAULT_WEB_SESSION_FILE,
    DeezerWebAuthError,
    DeezerWebClient,
    ENDPOINT as WEB_ENDPOINT,
)
from ...oauth import read_token, token_path
from ..config import REQUEST_TIMEOUT, polite_sleep
from ..matching import normalize_text, romanized, track_key
from .base import MirrorTarget, TargetAuthError
from .provider_utils import best_candidate, source_playlist_details

API = "https://api.deezer.com"
DEFAULT_TOKEN_FILE = "data/deezer_oauth.json"
_TRACK_PATH_RE = re.compile(r"(?:^|/)track/(\d+)(?=$|[/?#])", re.IGNORECASE)
SHARE_LINK_HOSTS = {"link.deezer.com"}


def _track_id_from_reference(value):
    decoded = unquote(str(value).strip())
    if re.fullmatch(r"\d+", decoded):
        return decoded
    match = _TRACK_PATH_RE.search(decoded)
    return match.group(1) if match else None


def _normalized_track(track):
    raw_contributors = track.get("contributors") or []
    if isinstance(raw_contributors, dict):
        raw_contributors = [edge.get("node") or {} for edge in raw_contributors.get("edges") or []]
    contributors = [a.get("name", "") for a in raw_contributors if a.get("name")]
    primary = (track.get("artist") or {}).get("name", "")
    artists = contributors or ([primary] if primary else [""])
    duration = track.get("duration")
    album = track.get("album") or {}
    cover = album.get("cover")
    if isinstance(cover, dict):
        image = next((url for url in reversed(cover.get("urls") or []) if url), "")
    else:
        image = next((album.get(key) for key in ("cover_medium", "cover_big", "cover_xl", "cover")
                      if isinstance(album.get(key), str) and album.get(key)), "")
    return {
        "id": str(track.get("id")) if track.get("id") is not None else None,
        "name": track.get("title", ""),
        "artist": ", ".join(artists),
        "artists": artists,
        "album": album.get("title") or album.get("displayTitle"),
        "album_position": track.get("track_position"),
        "duration_ms": int(duration * 1000) if isinstance(duration, (int, float)) else None,
        "isrc": track.get("isrc"),
        "added_at": str(track.get("time_add") or ""),
        "image": image,
    }


class DeezerTarget(MirrorTarget):
    name = "Deezer"
    tag = "deezer"
    source = "deezer"
    favorite_tracks_name = "Favorite Tracks"

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("DEEZER_CACHE_FILE", "deezer_resolve_cache.json")

    def __init__(self):
        self.cache_file = self.resolve_cache_path()
        self._web = None
        web_headers = (os.getenv("DEEZER_WEB_HEADERS") or "").strip()
        refresh_token = (os.getenv("DEEZER_REFRESH_TOKEN") or "").strip()
        if web_headers or refresh_token:
            try:
                self._web = DeezerWebClient(
                    web_headers,
                    refresh_token=refresh_token,
                    token_file=token_path("DEEZER_WEB_SESSION_FILE", DEFAULT_WEB_SESSION_FILE),
                    endpoint=os.getenv("DEEZER_WEB_ENDPOINT") or WEB_ENDPOINT,
                )
            except ValueError as exc:
                raise RuntimeError(f"Invalid DEEZER_WEB_HEADERS: {exc}") from exc
            self._token = None
        else:
            self._token_file = token_path("DEEZER_TOKEN_FILE", DEFAULT_TOKEN_FILE)
            self._token = read_token(self._token_file).get("access_token")
            if not self._token:
                raise RuntimeError("Missing Deezer web session or OAuth token; connect Deezer in Accounts")
        self._session = requests.Session()
        self._user = None

    def _request(self, method, path, *, params=None):
        url = path if str(path).startswith("http") else f"{API}/{str(path).lstrip('/')}"
        query = dict(params or {})
        query["access_token"] = self._token
        attempts = 4
        for attempt in range(attempts):
            try:
                response = self._session.request(method, url, params=query, timeout=REQUEST_TIMEOUT)
            except requests.RequestException:
                if method == "GET" and attempt < attempts - 1:
                    time.sleep(min(2**attempt, 12) + random.uniform(0, 1))
                    continue
                raise
            if response.status_code == 429 and attempt < attempts - 1:
                time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0.5, 1.5))
                continue
            response.raise_for_status()
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if error:
                code = error.get("code")
                message = error.get("message") or error.get("type") or "API error"
                if code in (200, 300) or error.get("type") in ("OAuthException", "PermissionsException"):
                    raise TargetAuthError(f"Deezer authorization was rejected ({message}); reconnect in Accounts.")
                raise RuntimeError(f"Deezer API error {code}: {message}")
            return body
        raise RuntimeError("Deezer request retry budget exhausted")

    def _catalog_get(self, path, *, params=None):
        """Use Deezer's unauthenticated catalog reads in browser-session mode."""

        if self._web is None:
            return self._request("GET", path, params=params)
        url = path if str(path).startswith("http") else f"{API}/{str(path).lstrip('/')}"
        for attempt in range(4):
            try:
                response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            except requests.RequestException:
                if attempt < 3:
                    time.sleep(min(2**attempt, 12) + random.uniform(0, 1))
                    continue
                raise
            if (response.status_code == 429 or response.status_code >= 500) and attempt < 3:
                time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0, 1))
                continue
            response.raise_for_status()
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if error:
                raise RuntimeError(f"Deezer catalog API error: {error.get('message', error)}")
            return body
        raise RuntimeError("Deezer catalog request retry budget exhausted")

    def _pages(self, path, params=None):
        next_url, next_params = path, dict(params or {})
        while next_url:
            body = self._request("GET", next_url, params=next_params)
            yield body
            next_url = body.get("next") if isinstance(body, dict) else None
            next_params = None

    def _me(self):
        if self._user is None:
            if self._web is not None:
                self._user = {"id": self._web.validate()}
            else:
                self._user = self._request("GET", "user/me")
        return self._user

    def _all_playlists(self):
        if self._web is not None:
            try:
                user_id, rows = self._web.list_playlists()
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
            self._user = {"id": user_id}
            return [{**playlist, "_owned": True} for playlist in rows]
        rows = []
        me = str(self._me().get("id"))
        for body in self._pages("user/me/playlists", {"limit": 100}):
            for playlist in body.get("data") or []:
                owner = str((playlist.get("creator") or {}).get("id") or "")
                rows.append({**playlist, "_owned": not owner or owner == me})
        return rows

    def list_playlists(self):
        out = {}
        for playlist in self._all_playlists():
            key = (playlist.get("title") or "").strip().casefold()
            if key and (key not in out or (playlist.get("_owned") and not out[key].get("_owned"))):
                out[key] = playlist
        return out

    def browse_playlists(self):
        return self._all_playlists()

    def is_editable(self, playlist):
        if "_owned" in playlist:
            return bool(playlist["_owned"])
        owner = str((playlist.get("creator") or {}).get("id") or "")
        return not owner or owner == str(self._me().get("id"))

    def create(self, source_playlist):
        name, description = source_playlist_details(source_playlist)
        if self._web is not None:
            try:
                playlist = self._web.create(name, description)
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
            if not playlist.get("id"):
                raise RuntimeError("Deezer did not return the created playlist id")
            polite_sleep(0.4)
            return playlist
        result = self._request("POST", "user/me/playlists", params={"title": name})
        playlist_id = result.get("id") if isinstance(result, dict) else result
        if not playlist_id:
            raise RuntimeError(f"Deezer did not return the created playlist id ({result!r})")
        polite_sleep(0.4)
        return self._request("GET", f"playlist/{playlist_id}")

    def fetch_playlist(self, playlist_id):
        """A playlist by id, public ones included. Deezer's playlist endpoint is
        not scoped to the caller's library, so one GET covers both."""
        try:
            playlist = self._request("GET", f"playlist/{playlist_id}")
        except Exception:
            return None
        return playlist if isinstance(playlist, dict) and playlist.get("id") is not None else None

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "id": str(playlist_id),
            "title": "",
            "description": "",
            "nb_tracks": expected_count,
            "_owned": True,
        }

    def playlist_tracks_page(self, playlist, cursor=None):
        if self._web is not None:
            try:
                rows, next_cursor = self._web.playlist_tracks_page(
                    str(playlist["id"]),
                    cursor=cursor,
                    limit=20,
                )
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
            return [_normalized_track(track) for track in rows], next_cursor

        try:
            offset = 0 if cursor is None else int(cursor)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Deezer playlist cursor is not a valid offset") from exc
        if offset < 0:
            raise RuntimeError("Deezer playlist cursor is not a valid offset")
        body = self._request(
            "GET",
            f"playlist/{playlist['id']}/tracks",
            params={"limit": 20, "index": offset},
        )
        rows = body.get("data") or []
        next_offset = offset + len(rows)
        next_cursor = None
        next_url = body.get("next")
        if next_url:
            values = parse_qs(urlsplit(str(next_url)).query).get("index") or []
            try:
                advertised = int(values[0]) if values else next_offset
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Deezer returned an invalid playlist continuation") from exc
            if not rows or advertised <= offset:
                raise RuntimeError("Deezer returned a non-advancing playlist cursor")
            next_cursor = str(advertised)
        else:
            total = body.get("total")
            if total is not None and next_offset < int(total):
                if not rows:
                    raise RuntimeError(
                        f"Deezer playlist read incomplete: stopped at {offset} of {int(total)} tracks"
                    )
                next_cursor = str(next_offset)
        return [
            _normalized_track(track)
            for track in rows
            if track.get("id") is not None
        ], next_cursor

    def playlist_tracks(self, playlist):
        if self._web is not None:
            try:
                return [_normalized_track(track) for track in self._web.playlist_tracks(str(playlist["id"]))]
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
        tracks = []
        for body in self._pages(f"playlist/{playlist['id']}/tracks", {"limit": 100}):
            tracks.extend(_normalized_track(track) for track in body.get("data") or [] if track.get("id"))
        return tracks

    def favorite_tracks(self):
        if self._web is not None:
            try:
                return [_normalized_track(track) for track in self._web.favorite_tracks()]
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
        tracks = []
        for body in self._pages("user/me/tracks", {"limit": 100}):
            tracks.extend(
                _normalized_track(track)
                for track in body.get("data") or []
                if track.get("id") is not None
            )
        return tracks

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            normalized = self.normalize_manual_track_id(target_id)
            try:
                if self._web is not None:
                    self._web.add_favorite_track(normalized)
                else:
                    self._request("POST", "user/me/tracks", params={"songs": normalized})
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
            polite_sleep(0.25)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if not target_id:
            return
        try:
            if self._web is not None:
                self._web.remove_favorite_track(target_id)
            else:
                self._request("DELETE", "user/me/tracks", params={"songs": target_id})
        except DeezerWebAuthError as exc:
            raise TargetAuthError(str(exc)) from exc
        polite_sleep(0.25)

    def track_id(self, track):
        return str(track.get("id")) if track.get("id") is not None else None

    @classmethod
    def normalize_manual_track_id(cls, value):
        """Extract Deezer's numeric catalog id from a pasted id or track URL."""
        raw = super().normalize_manual_track_id(value)
        track_id = _track_id_from_reference(raw)
        if track_id:
            return track_id

        try:
            parts = urlsplit(raw)
        except ValueError:
            parts = None
        is_share_link = (
            parts
            and parts.scheme == "https"
            and (parts.hostname or "").lower() in SHARE_LINK_HOSTS
        )
        if is_share_link:
            try:
                response = requests.head(
                    raw,
                    allow_redirects=False,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise ValueError(
                    "Could not resolve that Deezer share link; paste its full track URL or numeric ID."
                ) from exc
            track_id = _track_id_from_reference(response.headers.get("Location", ""))
            if track_id:
                return track_id
            raise ValueError("That Deezer share link does not point to a track.")

        raise ValueError("Paste a numeric Deezer track ID or a Deezer track URL.")

    def playlist_count(self, playlist):
        return playlist.get("nb_tracks", playlist.get("estimatedTracksCount"))

    def playlist_name(self, playlist):
        return playlist.get("title", "")

    def playlist_description(self, playlist):
        return playlist.get("description", "") or ""

    def prefetch(self, source_tracks, cache):
        for isrc in sorted({t.get("isrc") for t in source_tracks if t.get("isrc")}):
            if isrc in cache["isrc"]:
                continue
            try:
                raw = self._catalog_get(f"track/isrc:{isrc}")
                candidate = _normalized_track(raw) if raw.get("id") else None
            except RuntimeError:
                candidate = None
            cache["isrc"][isrc] = [candidate] if candidate else []
            cache["dirty"] = True
            polite_sleep(0.15)

    def native_isrc_map(self, cache):
        return {
            str(candidate["id"]): isrc
            for isrc, candidates in cache.get("isrc", {}).items()
            for candidate in candidates
            if candidate and candidate.get("id")
        }

    def expected_ids(self, source_tracks, links, cache):
        out = {}
        for track in source_tracks:
            ids = {
                str(c["id"])
                for c in cache["isrc"].get(track.get("isrc") or "", [])
                if c and c.get("id")
            }
            if links.get(track.get("id")):
                ids.add(str(links[track["id"]]))
            if ids:
                out[track.get("id")] = ids
        return out

    def resolve(self, track, cache):
        candidates = [c for c in cache["isrc"].get(track.get("isrc") or "", []) if c]
        if candidates:
            return best_candidate(track, candidates) or str(candidates[0]["id"]), "isrc"
        key = track_key(track.get("name", ""), " ".join(track.get("artists") or []))
        if key in cache["search"]:
            cached = cache["search"][key]
            if cached is None:
                return None, "search"
            normalized = self.normalize_manual_track_id(cached)
            if normalized != cached:
                cache["search"][key] = normalized
                cache["dirty"] = True
            return normalized, "search"
        primary = (track.get("artists") or [""])[0]
        queries = [f"{track.get('name', '')} {primary}".strip()]
        roman = f"{romanized(track.get('name'))} {romanized(primary)}".strip()
        if roman and roman != normalize_text(queries[0]):
            queries.append(roman)
        best = None
        for query in queries:
            body = self._catalog_get("search/track", params={"q": query, "limit": 10})
            best = best_candidate(track, [_normalized_track(c) for c in body.get("data") or []])
            if best:
                break
        cache["search"][key] = best
        cache["dirty"] = True
        polite_sleep(0.2)
        return best, "search"

    def add(self, playlist, target_ids):
        if self._web is not None:
            try:
                for target_id in target_ids:
                    self._web.add(
                        str(playlist["id"]),
                        [self.normalize_manual_track_id(target_id)],
                    )
                    polite_sleep(0.25)
                return
            except DeezerWebAuthError as exc:
                raise TargetAuthError(str(exc)) from exc
        for target_id in target_ids:
            self._request(
                "POST",
                f"playlist/{playlist['id']}/tracks",
                params={"songs": self.normalize_manual_track_id(target_id)},
            )
            polite_sleep(0.25)

    def remove(self, playlist, track):
        target_id = self.track_id(track)
        if target_id:
            if self._web is not None:
                try:
                    self._web.remove(str(playlist["id"]), [target_id])
                except DeezerWebAuthError as exc:
                    raise TargetAuthError(str(exc)) from exc
                polite_sleep(0.25)
                return
            self._request("DELETE", f"playlist/{playlist['id']}/tracks", params={"songs": target_id})
            polite_sleep(0.25)

    def remove_occurrences(self, playlist, positioned):
        # Deezer deletes by catalog track id rather than entry id. Preserve any
        # unflagged copies by deleting once and re-appending their count.
        current = self.playlist_tracks(playlist)
        totals = {}
        for track in current:
            tid = self.track_id(track)
            totals[tid] = totals.get(tid, 0) + 1
        flagged = {}
        for _, track in positioned:
            tid = self.track_id(track)
            flagged[tid] = flagged.get(tid, 0) + 1
        for tid, count in flagged.items():
            if not tid:
                continue
            self.remove(playlist, {"id": tid})
            keep = max(0, totals.get(tid, count) - count)
            if keep:
                self.add(playlist, [tid] * keep)

    # Deezer has no positional insert, and its delete addresses the catalog
    # track id, so an ordered repair would have to delete every copy of a song
    # and re-append a keeper. Its playlist reads also trail its own writes, so
    # that keeper count can be taken from a snapshot which has not indexed the
    # staged copies yet, retiring the song outright instead of reordering it.
    # Appending in source order is the only ordering write Deezer can survive.
    replay_chronology = None
