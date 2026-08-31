"""Minimal Deezer web-player session for playlist operations.

Deezer's Pipe Bearer token is short-lived.  SongMirror therefore retains only
the dedicated ``refresh-token`` renewal cookie alongside the current Bearer,
rotates both through Deezer's own auth endpoint, and keeps unrelated browser
cookies and playback requests outside this transport.
"""

from __future__ import annotations

import json
import random
import time

import requests

from .browser_session import bearer_from, bearer_is_expired, header_pairs, jwt_expiry
from .engine.config import REQUEST_TIMEOUT
from .oauth import read_token, write_token

ENDPOINT = "https://pipe.deezer.com/api"
AUTH_ENDPOINT = "https://auth.deezer.com/login/renew?jo=p&rto=c&i=c"
DEFAULT_WEB_SESSION_FILE = "data/deezer_web_session.json"


class DeezerWebAuthError(RuntimeError):
    pass


def parse_web_headers(raw: str) -> dict[str, str]:
    token = bearer_from(raw)
    if bearer_is_expired(token):
        raise ValueError("the pasted Deezer web-player Bearer token is expired")
    return {"authorization": f"Bearer {token}"}


def serialize_web_headers(raw: str) -> str:
    return json.dumps(parse_web_headers(raw), separators=(",", ":"), sort_keys=True)


def parse_refresh_token(raw: str) -> str:
    """Extract only Deezer's dedicated renewal cookie from DevTools text."""

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("paste a Deezer auth.deezer.com renewal request or refresh-token value")

    candidates = []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if str(key).strip().casefold() in ("refresh-token", "refresh_token"):
                candidates.append(value)

    for name, value in header_pairs(raw):
        key = str(name).strip().casefold()
        if key in ("refresh-token", "refresh_token"):
            candidates.append(value)
        elif key == "cookie":
            for part in str(value).split(";"):
                cookie_name, separator, cookie_value = part.strip().partition("=")
                if separator and cookie_name.casefold() == "refresh-token":
                    candidates.append(cookie_value)

    # Firefox can copy the Cookie request header as its bare value rather
    # than as ``Cookie: ...``.  Accept that shape too, but still extract only
    # the one dedicated renewal cookie instead of retaining the whole jar.
    for part in raw.split(";"):
        cookie_name, separator, cookie_value = part.strip().partition("=")
        if separator and cookie_name.casefold() == "refresh-token":
            candidates.append(cookie_value)

    stripped = raw.strip()
    if not candidates and not any(char.isspace() for char in stripped) and ";" not in stripped and ":" not in stripped:
        candidates.append(stripped)

    token = str(candidates[-1] if candidates else "").strip()
    if not token or any(char.isspace() for char in token) or ";" in token:
        raise ValueError("missing or malformed refresh-token cookie")
    return token


def serialize_refresh_token(raw: str) -> str:
    return parse_refresh_token(raw)


ME_QUERY = """
query SongMirrorDeezerSession { me { id } }
"""

PLAYLISTS_QUERY = """
query SongMirrorDeezerPlaylists($first: Int, $after: String) {
  me {
    id
    playlists(first: $first, after: $after, sort: {by: LAST_MODIFICATION_DATE, order: DESC}) {
      edges {
        cursor
        node {
          id title description isPrivate isCollaborative estimatedTracksCount
          picture { urls(pictureRequest: {width: 256, height: 256}) }
          defaultPicture { urls(pictureRequest: {width: 256, height: 256}) }
          owner { id name }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

PLAYLIST_QUERY = """
query SongMirrorDeezerPlaylist($playlistId: String!) {
  playlist(playlistId: $playlistId) {
    id title description isPrivate isCollaborative estimatedTracksCount
    picture { urls(pictureRequest: {width: 256, height: 256}) }
    defaultPicture { urls(pictureRequest: {width: 256, height: 256}) }
    owner { id name }
  }
}
"""

PLAYLIST_TRACKS_QUERY = """
query SongMirrorDeezerPlaylistTracks($playlistId: String!, $first: Int!, $cursor: String) {
  playlist(playlistId: $playlistId) {
    id
    tracks(first: $first, after: $cursor) {
      edges {
        cursor
        node {
          id title duration
          album {
            id displayTitle
            cover { urls(pictureRequest: {width: 128, height: 128}) }
          }
          contributors { edges { node { ... on Artist { id name } } } }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

CREATE_MUTATION = """
mutation SongMirrorDeezerCreatePlaylist($input: PlaylistCreateMutationInput!) {
  createPlaylist(input: $input) {
    playlist {
      id title description isPrivate isCollaborative estimatedTracksCount
      picture { urls(pictureRequest: {width: 256, height: 256}) }
      defaultPicture { urls(pictureRequest: {width: 256, height: 256}) }
      owner { id name }
    }
  }
}
"""

ADD_MUTATION = """
mutation SongMirrorDeezerAddTracks($input: PlaylistAddTracksMutationInput!) {
  addTracksToPlaylist(input: $input) {
    ... on PlaylistAddTracksOutput { addedTrackIds duplicatedTrackIds }
  }
}
"""

REMOVE_MUTATION = """
mutation SongMirrorDeezerRemoveTracks($input: PlaylistRemoveTracksMutationInput!) {
  removeTracksFromPlaylist(input: $input) {
    removedTrackIds
  }
}
"""

class DeezerWebClient:
    def __init__(
        self,
        raw_headers: str = "",
        *,
        refresh_token: str = "",
        token_file: str = "",
        prefer_persisted: bool = True,
        session=None,
        endpoint: str = ENDPOINT,
    ):
        self.endpoint = endpoint
        self.session = session or requests.Session()
        self._token_file = str(token_file or "")

        persisted = read_token(self._token_file) if self._token_file else {}
        supplied_refresh = parse_refresh_token(refresh_token) if str(refresh_token or "").strip() else ""
        persisted_refresh = str(persisted.get("refresh_token") or "").strip()
        self.refresh_token = (
            persisted_refresh if prefer_persisted and persisted_refresh else supplied_refresh or persisted_refresh
        )

        supplied_access = bearer_from(raw_headers) if str(raw_headers or "").strip() else ""
        persisted_access = str(persisted.get("access_token") or "").strip()
        if prefer_persisted and persisted_access and not bearer_is_expired(persisted_access):
            self._access_token = persisted_access
        else:
            self._access_token = supplied_access or persisted_access
        self.headers = {}
        self._ensure_access()

    def _persist_session(self):
        if not self._token_file:
            return
        state = {
            "access_token": self._access_token,
            "refresh_token": self.refresh_token,
        }
        expiry = jwt_expiry(self._access_token)
        if expiry is not None:
            state["expires_at"] = expiry
        write_token(self._token_file, state)

    def _renew(self):
        if not self.refresh_token:
            raise DeezerWebAuthError(
                "Deezer Pipe token expired; reconnect with an auth.deezer.com renewal request."
            )
        response = self.session.post(
            AUTH_ENDPOINT,
            cookies={"refresh-token": self.refresh_token},
            headers={
                "Accept": "application/json",
                "Origin": "https://www.deezer.com",
                "Referer": "https://www.deezer.com/",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code in (400, 401, 403):
            raise DeezerWebAuthError(
                "Deezer renewal session expired; reconnect with a fresh auth.deezer.com request."
            )
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise DeezerWebAuthError("Deezer renewal returned a non-JSON response.") from exc
        token = str((body or {}).get("jwt") or "").strip()
        if not token or bearer_is_expired(token):
            raise DeezerWebAuthError("Deezer renewal did not return a usable Pipe token.")
        cookies = getattr(response, "cookies", None)
        rotated = cookies.get("refresh-token") if cookies is not None else None
        rotated = rotated or (body or {}).get("refresh_token") or (body or {}).get("refreshToken")
        if rotated:
            self.refresh_token = parse_refresh_token(str(rotated))
        self._access_token = token
        self.headers = {"authorization": f"Bearer {token}"}
        self._persist_session()

    def _ensure_access(self, *, force=False):
        if force or not self._access_token or bearer_is_expired(self._access_token):
            self._renew()
        else:
            self.headers = {"authorization": f"Bearer {self._access_token}"}

    def serialized_headers(self) -> str:
        return json.dumps(self.headers, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _auth_error(message: str) -> bool:
        lowered = message.casefold()
        return any(marker in lowered for marker in ("auth", "forbidden", "token", "unauthorized"))

    def execute(self, operation_name: str, query: str, variables=None, *, mutation=False):
        attempts = (2 if self.refresh_token else 1) if mutation else 4
        refreshed = False
        for attempt in range(attempts):
            self._ensure_access()
            headers = {
                **self.headers,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.deezer.com",
                "Referer": "https://www.deezer.com/",
            }
            try:
                response = self.session.post(
                    self.endpoint,
                    headers=headers,
                    json={"operationName": operation_name, "query": query, "variables": variables or {}},
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException:
                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 12) + random.uniform(0, 1))
                    continue
                raise
            if response.status_code in (401, 403) and self.refresh_token and not refreshed:
                self._ensure_access(force=True)
                refreshed = True
                continue
            if response.status_code in (401, 403):
                raise DeezerWebAuthError(
                    "Deezer web session expired; reconnect with a fresh auth.deezer.com renewal request."
                )
            if response.status_code in (429,) or response.status_code >= 500:
                if attempt < attempts - 1:
                    time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0, 1))
                    continue
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError as exc:
                raise RuntimeError("Deezer web API returned a non-JSON response") from exc
            errors = body.get("errors") if isinstance(body, dict) else None
            if errors:
                message = "; ".join(str(error.get("message", error)) for error in errors)
                error_context = " ".join(
                    str(value)
                    for error in errors
                    for value in (
                        error.get("type"),
                        (error.get("extensions") or {}).get("type"),
                        (error.get("extensions") or {}).get("code"),
                    )
                    if value
                )
                if self._auth_error(f"{message} {error_context}"):
                    if self.refresh_token and not refreshed:
                        self._ensure_access(force=True)
                        refreshed = True
                        continue
                    raise DeezerWebAuthError(
                        "Deezer web session expired or was rejected; reconnect with a fresh "
                        "auth.deezer.com renewal request."
                    )
                raise RuntimeError(f"Deezer web API error: {message}")
            return body.get("data") or {}
        raise RuntimeError("Deezer web request retry budget exhausted")

    def validate(self) -> str:
        me = (self.execute("SongMirrorDeezerSession", ME_QUERY).get("me") or {})
        if not me.get("id"):
            raise DeezerWebAuthError("Deezer did not recognize a signed-in user.")
        return str(me["id"])

    def list_playlists(self) -> tuple[str, list[dict]]:
        rows = []
        cursor = None
        user_id = ""
        while True:
            data = self.execute("SongMirrorDeezerPlaylists", PLAYLISTS_QUERY, {"first": 50, "after": cursor})
            me = data.get("me") or {}
            if not user_id:
                user_id = str(me.get("id") or "")
            connection = me.get("playlists") or {}
            edges = connection.get("edges") or []
            rows.extend(edge.get("node") or {} for edge in edges)
            page = connection.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            next_cursor = page.get("endCursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        return user_id, rows

    def playlist(self, playlist_id: str) -> dict:
        data = self.execute(
            "SongMirrorDeezerPlaylist", PLAYLIST_QUERY, {"playlistId": str(playlist_id)}
        )
        return data.get("playlist") or {}

    def playlist_tracks(self, playlist_id: str) -> list[dict]:
        rows, cursor = [], None
        while True:
            page_rows, cursor = self.playlist_tracks_page(
                playlist_id,
                cursor=cursor,
                limit=100,
            )
            rows.extend(page_rows)
            if cursor is None:
                return rows

    def playlist_tracks_page(
        self,
        playlist_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[dict], str | None]:
        data = self.execute(
            "SongMirrorDeezerPlaylistTracks",
            PLAYLIST_TRACKS_QUERY,
            {"playlistId": str(playlist_id), "first": limit, "cursor": cursor},
        )
        connection = (((data.get("playlist") or {}).get("tracks")) or {})
        rows = [edge.get("node") or {} for edge in connection.get("edges") or []]
        page = connection.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            return rows, None
        next_cursor = page.get("endCursor")
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Deezer returned a non-advancing playlist cursor")
        if not rows:
            raise RuntimeError("Deezer playlist read incomplete: an empty page advertised more tracks")
        return rows, str(next_cursor)

    def create(self, title: str, description: str = "") -> dict:
        create_input = {
            "title": title,
            "isPrivate": True,
            "isCollaborative": False,
        }
        if description:
            create_input["description"] = description
        data = self.execute(
            "SongMirrorDeezerCreatePlaylist",
            CREATE_MUTATION,
            {"input": create_input},
            mutation=True,
        )
        return ((data.get("createPlaylist") or {}).get("playlist")) or {}

    def add(self, playlist_id: str, track_ids: list[str]) -> None:
        self.execute(
            "SongMirrorDeezerAddTracks",
            ADD_MUTATION,
            {"input": {"playlistId": str(playlist_id), "trackIds": [str(i) for i in track_ids]}},
            mutation=True,
        )

    def remove(self, playlist_id: str, track_ids: list[str]) -> None:
        self.execute(
            "SongMirrorDeezerRemoveTracks",
            REMOVE_MUTATION,
            {
                "input": {
                    "playlistId": str(playlist_id),
                    "trackIds": [str(track_id) for track_id in track_ids],
                }
            },
            mutation=True,
        )
