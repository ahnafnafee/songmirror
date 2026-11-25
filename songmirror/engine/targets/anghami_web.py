"""Playlist operations in Anghami's signed-in web player."""

import os
import re
from urllib.parse import urlsplit

import requests
from playwright.sync_api import Error as BrowserError, sync_playwright

from ..matching import normalize_isrc
from .base import MirrorTarget, TargetAuthError, TargetCapabilityError, TargetDirectoryIncompleteError, TargetTransientError
from .music_server import integer, resolve_catalog_track, rows
from .provider_utils import source_playlist_details

PLAYER_URL = "https://play.anghami.com/playlists"
GATEWAY_URL = "https://coussa.anghami.com/gateway.php"
ID = re.compile(r"[1-9][0-9]{0,24}")
_INCOMPLETE = "Anghami returned an incomplete playlist. Sync was stopped."

_WEB_REQUEST = """
async ({operation, params, form, gateway}) => {
  if (location.origin !== 'https://play.anghami.com') return {state: 'signed_out'};
  const session = performance.getEntriesByType('resource').map(e => new URL(e.name)).reverse().find(u =>
    u.origin + u.pathname === gateway && u.searchParams.get('type') === 'GETplaylists' && u.searchParams.has('sid'));
  if (!session) return {state: 'signed_out'};
  let url = new URL(gateway);
  const search = operation === 'search';
  if (search) url.pathname = '/rest/v2/GETSearchResults.view';
  for (const key of ['lang','language','userlanguageprod','output','web2','fingerprint','sid','appsid']) {
    if (session.searchParams.has(key) && !(search && ['sid','appsid'].includes(key))) {
      url.searchParams.set(key, session.searchParams.get(key));
    }
  }
  if (!search) {
    url.searchParams.set('angh_type', operation);
    if (!form) url.searchParams.set('type', operation);
  }
  for (const [key,value] of Object.entries(params)) url.searchParams.set(key, value);
  try {
    const response = await fetch(url, {redirect: 'error', signal: AbortSignal.timeout(10000),
      ...(form ? {method: 'POST', body: new URLSearchParams({type: operation, ...form})} : {method: 'GET'})});
    const body = response.ok ? await response.json() : null;
    return {status: response.status, body};
  } catch (_) { return {state: 'request_error'}; }
}
"""


def normalize_browser_endpoint(value):
    try:
        address = urlsplit(str(value).strip())
        if (address.scheme != "http" or address.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
                or not address.port or address.path not in {"", "/"} or address.query or address.fragment or address.username
                or address.password):
            raise ValueError
    except ValueError:
        raise ValueError("Enter a loopback Chrome DevTools address with a port.") from None
    return f"http://{address.netloc}"


class AnghamiBrowserClient:
    def __init__(self, endpoint):
        self._endpoint = normalize_browser_endpoint(endpoint)

    def request(self, operation, *, params=None, form=None):
        if operation not in {"GETplaylists", "GETplaylistdata", "search", "PUTplaylist", "UPDATEplaylist"}:
            raise ValueError("Unexpected Anghami web-player operation.")
        try:
            address = urlsplit(self._endpoint)
            # Chrome requires a loopback Host header even when Docker reaches the
            # local desktop through its built-in host alias.
            headers = {"Host": f"127.0.0.1:{address.port}"}
            with requests.Session() as session:
                session.trust_env = False
                discovery = session.get(f"{self._endpoint}/json/version", headers=headers,
                                        allow_redirects=False, timeout=5)
                if discovery.status_code != 200:
                    raise ValueError
                path = urlsplit(discovery.json().get("webSocketDebuggerUrl", "")).path
            if not re.fullmatch(r"/devtools/browser/[a-f0-9-]{36}", path):
                raise ValueError
            with sync_playwright() as driver:
                browser = driver.chromium.connect_over_cdp(f"ws://{address.netloc}{path}", headers=headers, timeout=5000)
                page = next((p for context in browser.contexts for p in context.pages
                             if p.url.rstrip("/") == PLAYER_URL), None)
                if page is None:
                    raise TargetAuthError("Open Anghami's playlist library in the connected Chrome browser.")
                reply = page.evaluate(_WEB_REQUEST, {"operation": operation, "params": params or {},
                                                   "form": form, "gateway": GATEWAY_URL})
        except (BrowserError, requests.RequestException, ValueError, AttributeError):
            raise TargetTransientError("SongMirror could not reach the connected Anghami browser.") from None
        status = reply.get("status")
        if status in (401, 403) or reply.get("state") == "signed_out":
            raise TargetAuthError("Sign in to Anghami and reload your playlist library in the connected browser.")
        if status is None or status == 429 or status >= 500:
            raise TargetTransientError("The Anghami web player could not complete the request.")
        body = reply.get("body")
        if status != 200 or not isinstance(body, dict) or (operation != "search" and body.get("status") != "ok"):
            raise TargetCapabilityError("Anghami rejected the web-player request.")
        return body


def _id(value):
    key = str(value or "")
    if not ID.fullmatch(key):
        raise TargetDirectoryIncompleteError("Anghami returned an invalid playlist or track ID.")
    return key


class AnghamiWebTarget(MirrorTarget):
    name = "Anghami"
    tag = source = "anghami"
    supports_favorites = supports_favorite_writes = supports_saved_albums = False
    replay_chronology = None
    no_playlists_note = "connect its signed-in web player to write playlists."

    def __init__(self, client):
        self._api = client
        self.cache_file = self.resolve_cache_path()

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("ANGHAMI_CACHE_FILE", "anghami_resolve_cache.json")

    @classmethod
    def playlist_writes_configured(cls):
        return bool(os.getenv("ANGHAMI_BROWSER_ENDPOINT"))

    def browse_playlists(self):
        body = self._api.request("GETplaylists")
        result = {}
        for section in rows(body.get("sections"), _INCOMPLETE):
            if section.get("type") != "playlist" or section.get("group") != "playlists":
                continue
            for item in rows(section.get("data"), _INCOMPLETE):
                if not ID.fullmatch(str(item.get("id") or "")):
                    continue  # The directory also contains system collections.
                key = str(item["id"])
                name = item.get("name")
                count = integer(item.get("count"))
                if not isinstance(name, str) or not name.strip() or count is None or count < 0:
                    raise TargetDirectoryIncompleteError(_INCOMPLETE)
                image = item.get("coverArt")
                result.setdefault(key, {"id": key, "name": name, "count": count,
                                        "images": [{"url": image}] if isinstance(image, str) and image.startswith("https://") else [],
                                        "_account_playlist": True, "_private": str(item.get("public")).lower() == "false"})
        return list(result.values())

    def list_playlists(self):
        return {entry["name"].strip().casefold(): entry for entry in self.browse_playlists()}

    def find_playlist(self, playlist_id):
        return next((entry for entry in self.browse_playlists() if entry["id"] == str(playlist_id)), None)

    def is_editable(self, playlist):
        return playlist.get("_account_playlist") is True

    @staticmethod
    def _track(item):
        title, artist = item.get("title"), item.get("artist")
        if not isinstance(title, str) or not isinstance(artist, str):
            raise TargetDirectoryIncompleteError(_INCOMPLETE)
        duration = integer(item.get("duration"))
        return {"id": _id(item.get("id")), "name": title, "artist": artist, "artists": [artist] if artist else [],
                "album": item.get("album") or "", "duration_ms": duration * 1000 if duration is not None else None,
                "isrc": normalize_isrc(item.get("isrc")) or None}

    def _detail(self, key, *, expected=None):
        body = self._api.request("GETplaylistdata", params={"playlistid": key, "buffered": "0"})
        if str(body.get("playlistid") or body.get("id")) != key:
            raise TargetDirectoryIncompleteError("Anghami returned a different playlist.")
        sections = rows(body.get("sections"), _INCOMPLETE)
        member_sections = [section for section in sections
                           if section.get("type") == "song" and "show_recommendations" in section]
        if len(member_sections) > 1:
            raise TargetDirectoryIncompleteError(_INCOMPLETE)
        items = rows(member_sections[0].get("data"), _INCOMPLETE) if member_sections else []
        count = integer(body.get("PlaylistCount"))
        if count is None and not items and expected == 0:
            count = 0
        if count != len(items) or (expected is not None and expected != count):
            raise TargetDirectoryIncompleteError(_INCOMPLETE)
        name = body.get("name") or body.get("title")
        if not isinstance(name, str) or not name.strip():
            raise TargetDirectoryIncompleteError(_INCOMPLETE)
        return {"id": key, "name": name, "count": count, "_owned": body.get("canedit") is True,
                "_tracks": [self._track(item) for item in items]}

    def fetch_playlist(self, playlist_id):
        key = _id(playlist_id)
        entry = self.find_playlist(key)
        if entry is not None:
            return dict(entry, _tracks=self._detail(key, expected=entry["count"])["_tracks"])
        return self._detail(key)

    def playlist_tracks(self, playlist):
        if "_tracks" in playlist:
            return playlist["_tracks"]
        return self._detail(_id(playlist["id"]), expected=playlist.get("count"))["_tracks"]

    def playlist_count(self, playlist):
        return playlist.get("count")

    def track_id(self, track):
        return track.get("id")

    def _owned(self, playlist):
        if not self.is_editable(playlist):
            raise TargetCapabilityError("Select a playlist from the connected Anghami account to change it.")
        entry = self.find_playlist(_id(playlist["id"]))
        if entry is None:
            raise TargetCapabilityError("Anghami could not confirm the destination in your playlist library.")
        snapshot = self._detail(entry["id"], expected=entry["count"])
        if not snapshot["_owned"]:
            raise TargetCapabilityError("Anghami could not confirm ownership of the destination playlist.")
        return snapshot

    def create(self, playlist):
        self._create_public(playlist)
        name, _ = source_playlist_details(playlist)
        body = self._api.request("PUTplaylist", form={"name": name, "public": "false"})
        created = body.get("playlist")
        if not isinstance(created, dict):
            raise TargetDirectoryIncompleteError("Anghami did not identify the new playlist.")
        item = self.find_playlist(_id(created.get("id")))
        if item is None or item["name"] != name or not item["_private"]:
            raise TargetDirectoryIncompleteError("Anghami did not confirm the new private playlist.")
        return item

    def _verify(self, key, expected):
        actual = self._detail(key, expected=len(expected))["_tracks"]
        if [entry["id"] for entry in actual] != expected:
            raise TargetDirectoryIncompleteError("Anghami did not confirm the expected playlist track order.")

    def add(self, playlist, track_ids):
        desired = list(dict.fromkeys(_id(key) for key in track_ids))
        current = self._owned(playlist)
        ordered = [entry["id"] for entry in current["_tracks"]]
        existing = set(ordered)
        added = [key for key in desired if key not in existing]
        for key in added:
            self._api.request("PUTplaylist", form={"playlistid": current["id"], "action": "append", "songID": key})
        if added:
            self._verify(current["id"], ordered + added)
        return added

    def remove(self, playlist, track):
        key = _id(track.get("id"))
        current = self._owned(playlist)
        ordered = [entry["id"] for entry in current["_tracks"]]
        if ordered.count(key) != 1:
            return False
        self._api.request("PUTplaylist", form={"playlistid": current["id"], "action": "delete", "songid": key})
        ordered.remove(key)
        self._verify(current["id"], ordered)
        return True

    def search_candidates(self, query, *, limit=5):
        result = self._api.request("search", params={"query": query, "page": "0", "filter_type": "top",
                                                     "simple_results": "false"})
        found = {}
        for section in rows(result.get("sections"), _INCOMPLETE):
            for item in rows(section.get("data"), _INCOMPLETE):
                if "duration" in item and "albumID" in item and "artist" in item:
                    candidate = self._track(item)
                    found.setdefault(candidate["id"], candidate)
        return list(found.values())[:limit]

    def resolve(self, track, cache):
        return resolve_catalog_track(self, track, cache)
