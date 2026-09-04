"""YouTube Music target — hybrid: Data API v3 for reads/writes, ytmusicapi for search.

The playlist reads and writes (list/create/add/remove) go through the official
YouTube Data API v3 with a durable OAuth refresh token — ytmusicapi's internal
youtubei API rejects self-made OAuth clients (HTTP 400) and its browser cookies
die within a day, so neither survives an unattended write loop. Its writes
share YouTube's playlist/video namespace, so they show up in the YouTube Music
app.

Resolution (matching a track to a video id) instead uses ytmusicapi's PUBLIC,
unauthenticated search. Two reasons: it costs no Data API quota (the killer
constraint — a Data API search is 100 of only 10k units/day), and it returns
real catalog songs (`- Topic` art-tracks) with durations, so matches are both
free and higher quality than the Data API's video search.

Setup: create a Google "TVs and Limited Input devices" OAuth client, then
    uvx ytmusicapi oauth --file data/ytmusic_oauth.json \
        --client-id <ID> --client-secret <SECRET>
and set YTMUSIC_OAUTH_CLIENT_ID / YTMUSIC_OAUTH_CLIENT_SECRET.
"""

import json
import os
import random
import re
import time

import requests

from ..config import REQUEST_TIMEOUT, polite_sleep
from ..logs import log, log_note, log_warn
from ..matching import normalize_text, romanized, score_candidate, track_key
from .base import MirrorTarget, TargetAuthError
from .provider_utils import source_playlist_details

DEFAULT_AUTH_FILE = "ytmusic_oauth.json"
API = "https://www.googleapis.com/youtube/v3"

_TOPIC_RE = re.compile(r"\s*-\s*Topic$")
_CHANNEL_DECORATION_RE = re.compile(
    r"(?:\s*vevo|\s+official(?:\s+channel)?)$",
    re.IGNORECASE,
)
_TITLE_SEPARATOR = r"(?:\s+-\s+|\s*[–—]\s*|\s+\|\s+|:\s+)"
_TITLE_PREFIX_RE = re.compile(
    rf"^(?P<prefix>.+?){_TITLE_SEPARATOR}(?P<title>.+)$"
)
_TRAILING_BRACKET_RE = re.compile(
    r"\s*(?:\((?P<paren>[^()]*)\)|\[(?P<bracket>[^\[\]]*)\]|\{(?P<brace>[^{}]*)\})\s*$"
)
_TRAILING_SEPARATOR_RE = re.compile(
    rf"^(?P<title>.+){_TITLE_SEPARATOR}(?P<tag>.+)$"
)
_VIDEO_PRODUCTION_TAGS = {
    "audio",
    "audio video",
    "clip",
    "lyrics",
    "lyric video",
    "lyrics video",
    "m v",
    "music clip",
    "music video",
    "mv",
    "official audio",
    "official audio video",
    "official clip",
    "official lyrics",
    "official lyric video",
    "official lyrics video",
    "official m v",
    "official music clip",
    "official music video",
    "official music video clip",
    "official mv",
    "official video",
    "official video clip",
    "official visualiser",
    "official visualizer",
    "video",
    "video clip",
    "visualiser",
    "visualizer",
}
_VIDEO_QUALITY_TAGS = {
    "4k", "8k", "720p", "1080p", "1440p", "2160p", "hd", "hq", "uhd",
}
_PRODUCER_CREDIT_RE = re.compile(r"prod(?:uced)?\s+by\s+.+")


ROTATE_URL = "https://accounts.youtube.com/RotateCookies"
ROTATE_COOKIE = "__Secure-1PSIDTS"


def rotate_browser_cookie(auth_file):
    """Keep a pasted browser session alive by refreshing its one perishable cookie.

    Of everything in a pasted `Cookie:` header, only `__Secure-1PSIDTS` goes
    stale: Google invalidates it server-side within days, while the signing
    cookies (SAPISID, __Secure-3PAPISID) stay valid for months. A signed-in
    browser is continuously reissued one from this endpoint, which is the only
    reason its session outlives a copied snapshot — so calling it on the same
    cadence is what lets an unattended paste survive.

    This is a keep-alive, not a repair: an already-expired session is refused,
    so it has to run well inside the stored cookie's lifetime. Best-effort —
    a refusal, a rate limit (rotation is throttled) or an offline host leaves
    the file untouched and the pass runs on the cookie already there.
    """
    try:
        with open(auth_file) as f:
            auth = json.load(f)
        pairs = [p.strip().split("=", 1) for p in auth.get("cookie", "").split(";") if "=" in p]
        jar = dict(pairs)
        if ROTATE_COOKIE not in jar:
            return False
        r = requests.post(
            ROTATE_URL, cookies=jar, data=json.dumps([0, "-0000000000000000000"]),
            headers={"Content-Type": "application/json", "User-Agent": auth.get("user-agent", ""),
                     "Origin": "https://www.youtube.com", "Referer": "https://www.youtube.com/"},
            timeout=REQUEST_TIMEOUT)
        issued = r.cookies.get_dict()  # response Set-Cookie only, never the jar we sent
        if r.status_code != 200 or issued.get(ROTATE_COOKIE, jar[ROTATE_COOKIE]) == jar[ROTATE_COOKIE]:
            return False
        auth["cookie"] = "; ".join(f"{k}={issued.get(k, v)}" for k, v in pairs)
        tmp = f"{auth_file}.tmp"
        with open(tmp, "w") as f:
            json.dump(auth, f)
        os.replace(tmp, auth_file)  # swap whole, so a torn write can't replace a working session
        return True
    except (OSError, ValueError, requests.RequestException):
        return False


def build():
    """A ready YT target, or None (logged) when YT isn't set up. Prefers the
    no-quota browser (youtubei) backend when YTMUSIC_PREFER_BROWSER is on and
    YTMUSIC_BROWSER_AUTH points at a ytmusicapi browser-auth file; otherwise the
    durable OAuth Data API (the default)."""
    browser = os.getenv("YTMUSIC_BROWSER_AUTH", "")
    if os.getenv("YTMUSIC_PREFER_BROWSER", "").lower() in ("1", "on", "true", "yes") and browser and os.path.exists(browser):
        try:
            if rotate_browser_cookie(browser):
                log_note("refreshed the YouTube Music session cookie", tag="yt")
            return YTMusicBrowserTarget(browser)
        except Exception as e:
            log_warn(f"YouTube Music no-quota (browser) mode failed ({e!r}); falling back to the Data API", tag="yt")
    auth = os.getenv("YTMUSIC_AUTH_FILE", DEFAULT_AUTH_FILE)
    cid, secret = os.getenv("YTMUSIC_OAUTH_CLIENT_ID"), os.getenv("YTMUSIC_OAUTH_CLIENT_SECRET")
    if not os.path.exists(auth):
        log_note(f"YouTube Music skipped: no OAuth token '{auth}' (create with: "
                 "uvx ytmusicapi oauth --file data/ytmusic_oauth.json --client-id ... --client-secret ...)", tag="yt")
        return None
    if not (cid and secret):
        log_note("YouTube Music skipped: set YTMUSIC_OAUTH_CLIENT_ID and YTMUSIC_OAUTH_CLIENT_SECRET", tag="yt")
        return None
    try:
        from ytmusicapi.auth.oauth import OAuthCredentials
    except ImportError:
        log_note("YouTube Music skipped: ytmusicapi not installed", tag="yt")
        return None
    try:
        return YTMusicTarget(auth, OAuthCredentials(client_id=cid, client_secret=secret))
    except Exception as e:
        log_warn(f"YouTube Music unavailable (re-run the ytmusicapi oauth setup?): {e!r}", tag="yt")
        return None


def _parse_count(value):
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _artist_from_channel(channel):
    """'The Cranberries - Topic' -> 'The Cranberries'; VEVO/plain kept as-is.

    Both YT readers run every artist through this because the two shapes name the
    SAME artist, and YouTube serves them interchangeably for one unchanging
    video. Leaving them apart makes a track's identity flap between passes."""
    return _TOPIC_RE.sub("", channel or "").strip()


def _channel_name_keys(channel):
    """Comparable channel spellings used only for a video-title prefix.

    YouTube appends branding such as ``VEVO`` and ``Official Channel`` to many
    owner names while the video's leading credit remains the plain artist.
    Keep the stored artist convention unchanged, but accept each progressively
    undecorated spelling when deciding whether a prefix is safe to remove.
    """
    variants = set()
    current = str(channel or "").strip()
    while current:
        key = normalize_text(current)
        if key:
            variants.add(key)
        undecorated = _CHANNEL_DECORATION_RE.sub("", current).strip()
        if undecorated == current:
            break
        current = undecorated
    return variants


def _is_video_production_tag(value):
    normalized = normalize_text(value)
    if _PRODUCER_CREDIT_RE.fullmatch(normalized):
        return True
    words = normalized.split()
    without_quality = [word for word in words if word not in _VIDEO_QUALITY_TAGS]
    return bool(words) and (
        not without_quality or " ".join(without_quality) in _VIDEO_PRODUCTION_TAGS
    )


def _clean_data_api_video_title(title, channel):
    """Turn an unstructured Data API video title into a search-safe track name.

    Prefix removal is gated on the owner channel, so a legitimate title such as
    ``Love - Hate`` is never split just because it contains a dash. Production
    labels are removed only when they occupy a complete trailing bracket or a
    separator-delimited suffix. Creative recording qualifiers (live, acoustic,
    remix, remaster, featured artists) deliberately remain for match safety.
    """
    raw = str(title or "").strip()
    if not raw:
        return ""

    cleaned = raw
    prefix = _TITLE_PREFIX_RE.match(cleaned)
    if prefix and normalize_text(prefix.group("prefix")) in _channel_name_keys(channel):
        candidate = prefix.group("title").strip()
        if candidate:
            cleaned = candidate

    while cleaned:
        bracket = _TRAILING_BRACKET_RE.search(cleaned)
        if bracket:
            tag = next(
                value
                for value in (
                    bracket.group("paren"),
                    bracket.group("bracket"),
                    bracket.group("brace"),
                )
                if value is not None
            )
            if _is_video_production_tag(tag):
                candidate = cleaned[:bracket.start()].rstrip(" -–—|:")
                if candidate:
                    cleaned = candidate
                    continue

        suffix = _TRAILING_SEPARATOR_RE.match(cleaned)
        if suffix and _is_video_production_tag(suffix.group("tag")):
            candidate = suffix.group("title").rstrip(" -–—|:")
            if candidate:
                cleaned = candidate
                continue
        break

    return cleaned or raw


def _normalized_data_api_playlist_item(item):
    video_id = item.get("contentDetails", {}).get("videoId")
    if not video_id:
        return None
    snippet = item.get("snippet", {})
    artist = _artist_from_channel(snippet.get("videoOwnerChannelTitle", ""))
    thumbnails = snippet.get("thumbnails") or {}
    image = next((
        (thumbnails.get(size) or {}).get("url")
        for size in ("medium", "high", "default")
        if (thumbnails.get(size) or {}).get("url")
    ), "")
    return {
        "id": video_id,
        "videoId": video_id,
        "playlistItemId": item.get("id"),
        "name": _clean_data_api_video_title(snippet.get("title", ""), artist),
        "artist": artist,
        "artists": [artist] if artist else [""],
        "album": None,
        "duration_ms": None,
        "added_at": snippet.get("publishedAt") or "",
        "image": image,
    }


def _normalized_youtubei_playlist_track(track):
    video_id = track.get("videoId")
    if not video_id:
        return None
    artists = [
        artist
        for artist in (
            _artist_from_channel(value.get("name", ""))
            for value in (track.get("artists") or [])
        )
        if artist
    ]
    album = track.get("album")
    duration_seconds = track.get("duration_seconds")
    thumbnails = track.get("thumbnails") or []
    image = next((
        thumb.get("url")
        for thumb in reversed(thumbnails)
        if isinstance(thumb, dict) and thumb.get("url")
    ), "")
    return {
        "id": video_id,
        "videoId": video_id,
        "setVideoId": track.get("setVideoId"),
        "name": track.get("title", ""),
        "artist": ", ".join(artists),
        "artists": artists or [""],
        "album": album.get("name") if isinstance(album, dict) else None,
        "duration_ms": duration_seconds * 1000 if duration_seconds else None,
        "added_at": track.get("dateAdded") or "",
        "image": image,
    }


def _err_reason(response):
    try:
        errors = response.json().get("error", {}).get("errors", [])
        return errors[0].get("reason", "") if errors else ""
    except ValueError:
        return ""


def _with_backoff(fn, what):
    """Retry a ytmusicapi search past YouTube's bot-detection throttle (403/429).
    This path spends no Data API quota — the limit here is IP-based, not the
    daily unit budget — so backing off and retrying is worthwhile."""
    for attempt in range(4):
        try:
            return fn()
        except Exception as e:
            if not any(code in str(e) for code in ("403", "429")) or attempt == 3:
                raise
            wait = 15 * (2 ** attempt) + random.uniform(0, 8)
            log(f"  YT search throttled ({what}); backing off {int(wait)}s", tag="yt")
            time.sleep(wait)


class YTMusicTarget(MirrorTarget):
    name = "YouTube Music"
    tag = "yt"
    source = "ytmusic"
    stable_occurrence_ids = True
    favorite_tracks_name = "Liked Music"

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("YTMUSIC_CACHE_FILE", "ytmusic_resolve_cache.json")

    def __init__(self, auth_file, creds):
        self._auth_file = auth_file
        self._creds = creds
        with open(auth_file) as f:
            self._tok = json.load(f)
        self.cache_file = self.resolve_cache_path()
        self._session = requests.Session()  # Data API (reads + writes)
        from ytmusicapi import YTMusic
        self._ytm = YTMusic()  # public, unauthenticated search for resolution (no Data API quota)

    # -- auth ------------------------------------------------------------------
    def _access(self):
        """A valid access token, refreshed and persisted when near expiry. The
        refresh token is durable — this is the whole point of the Data API."""
        if time.time() >= self._tok.get("expires_at", 0) - 60:
            fresh = self._creds.refresh_token(self._tok["refresh_token"])
            fresh = fresh if isinstance(fresh, dict) else fresh.as_dict()
            self._tok.update(fresh)
            self._tok["expires_at"] = int(time.time()) + int(fresh.get("expires_in", 3600))
            with open(self._auth_file, "w") as f:
                json.dump(self._tok, f)
        return self._tok["access_token"]

    # -- HTTP (Data API: reads + writes only; search never touches this) --------
    def _request(self, method, path, *, params=None, json_body=None, ok404=False):
        """One Data API call. GET/5xx retry with backoff; 429/409 back off and
        retry (write volume is low now that search is off the Data API); 401 ->
        re-auth; 403 quota -> fail closed for the pass."""
        attempts = 5
        for attempt in range(attempts):
            headers = {"Authorization": f"Bearer {self._access()}"}
            try:
                r = self._session.request(method, f"{API}/{path}", params=params,
                                          json=json_body, headers=headers, timeout=REQUEST_TIMEOUT)
            except requests.RequestException:
                if method == "GET" and attempt < attempts - 1:
                    time.sleep(min(2 ** attempt, 20) + random.uniform(0, 2))
                    continue
                raise
            if r.status_code == 401:
                raise TargetAuthError("YouTube rejected the OAuth token (401). Re-run the ytmusicapi oauth setup.")
            if r.status_code == 403:
                reason = _err_reason(r)
                if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
                    raise TargetAuthError(
                        f"YouTube Data API quota exhausted ({reason}); YT paused until the daily reset (~midnight PT).")
                raise TargetAuthError(f"YouTube refused {method} {path} (403 {reason or 'forbidden'}).")
            if r.status_code == 404 and ok404:
                return None
            if r.status_code in (409, 429) and attempt < attempts - 1:
                # 409 = transient write-conflict on rapid edits; 429 = brief rate
                # blip. The write didn't apply, so a backed-off retry is safe.
                wait = float(r.headers.get("Retry-After") or 0) + min(2 ** attempt, 15) + random.uniform(1, 4)
                time.sleep(wait)
                continue
            if r.status_code >= 500 and method == "GET" and attempt < attempts - 1:
                time.sleep(min(2 ** attempt, 20) + random.uniform(0, 2))
                continue
            r.raise_for_status()
            return r
        return None

    def _paged(self, path, params):
        params = dict(params)
        while True:
            data = self._request("GET", path, params=params).json()
            yield from data.get("items", [])
            token = data.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token

    # -- MirrorTarget ----------------------------------------------------------
    def list_playlists(self):
        out = {}
        for pl in self._paged("playlists", {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}):
            title = (pl.get("snippet", {}).get("title") or "").strip()
            key = title.casefold()
            if key and key not in out:
                out[key] = {"playlistId": pl["id"], "title": title,
                            "count": pl.get("contentDetails", {}).get("itemCount"),
                            "thumbnails": pl.get("snippet", {}).get("thumbnails")}  # cover art for browse
        return out

    def is_editable(self, playlist):
        return True  # mine=true only returns playlists we own

    def playlist_count(self, playlist):
        return _parse_count(playlist.get("count"))

    def playlist_id(self, playlist):
        return playlist.get("playlistId")

    def playlist_name(self, playlist):
        return playlist.get("title", "")

    def create(self, sp_playlist):
        name, description = source_playlist_details(sp_playlist)
        body = {"snippet": {"title": name, "description": description},
                "status": {"privacyStatus": "private"}}
        pid = self._request("POST", "playlists", params={"part": "snippet,status"}, json_body=body).json()["id"]
        polite_sleep(2.0)  # let the new playlist settle before writing to it
        return {"playlistId": pid, "title": name, "count": 0}

    def fetch_playlist(self, playlist_id):
        """A playlist by id, public ones included. `playlists?id=` reads any
        playlist the id addresses, unlike the `mine=true` listing."""
        try:
            data = self._request(
                "GET",
                "playlists",
                params={"part": "snippet,contentDetails", "id": str(playlist_id)},
            ).json()
        except Exception:
            return None
        rows = data.get("items") or []
        if not rows:
            return None
        row = rows[0]
        snippet = row.get("snippet") or {}
        return {
            "playlistId": row.get("id") or str(playlist_id),
            "title": snippet.get("title") or "",
            "description": snippet.get("description") or "",
            "count": (row.get("contentDetails") or {}).get("itemCount"),
            "thumbnails": snippet.get("thumbnails"),
        }

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "playlistId": str(playlist_id),
            "title": "",
            "count": expected_count,
        }

    def playlist_tracks_page(self, playlist, cursor=None):
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist["playlistId"],
            "maxResults": 20,
        }
        if cursor:
            params["pageToken"] = cursor
        data = self._request("GET", "playlistItems", params=params).json()
        items = data.get("items") or []
        next_cursor = data.get("nextPageToken") or None
        if next_cursor is not None and next_cursor == cursor:
            raise RuntimeError("YouTube Music returned a non-advancing playlist cursor")
        if next_cursor is not None and not items:
            raise RuntimeError(
                "YouTube Music playlist read incomplete: an empty page advertised more tracks"
            )
        return [
            track
            for item in items
            if (track := _normalized_data_api_playlist_item(item)) is not None
        ], next_cursor

    def playlist_tracks(self, playlist):
        return [
            track
            for item in self._paged("playlistItems", {
                "part": "snippet,contentDetails",
                "playlistId": playlist["playlistId"],
                "maxResults": 50,
            })
            if (track := _normalized_data_api_playlist_item(item)) is not None
        ]

    def _liked_playlist_id(self):
        data = self._request(
            "GET",
            "channels",
            params={"part": "contentDetails", "mine": "true", "maxResults": 1},
        ).json()
        channels = data.get("items") or []
        playlist_id = (
            (((channels[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("likes"))
            if channels
            else None
        )
        if not playlist_id:
            raise RuntimeError("YouTube did not return the account's liked-videos collection")
        return str(playlist_id)

    def favorite_tracks(self):
        return self.playlist_tracks({
            "playlistId": self._liked_playlist_id(),
            "title": self.favorite_tracks_name,
        })

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            self._request(
                "POST",
                "videos/rate",
                params={"id": str(target_id), "rating": "like"},
            )
            polite_sleep(1.0)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if not target_id:
            return
        self._request(
            "POST",
            "videos/rate",
            params={"id": target_id, "rating": "none"},
        )
        polite_sleep(1.0)

    def track_id(self, track):
        return track.get("videoId")

    def resolve(self, track, cache):
        primary = track["artists"][0] if track["artists"] else ""
        if not f"{track['name']} {primary}".strip():
            return None, None
        key = track_key(track["name"], " ".join(track["artists"]))
        if key in cache["search"]:
            return cache["search"][key], "search"
        best_id, method = self._search(track, primary)
        cache["search"][key] = best_id
        cache["dirty"] = True
        polite_sleep(0.4)
        return best_id, method

    def _search(self, track, primary):
        """Resolve via ytmusicapi's public search (no Data API quota). Prefer a
        `songs` (art-track) match so tracks land as native songs; fall back to
        `videos` only when no song scores acceptably."""
        queries = [f"{track['name']} {primary}".strip()]
        rom = f"{romanized(track['name'])} {romanized(primary)}".strip()
        if rom and rom != normalize_text(queries[0]):
            queries.append(rom)  # romanized retry for cross-script titles
        for query in queries:
            for filt in ("songs", "videos"):
                try:
                    results = _with_backoff(lambda q=query, f=filt: self._ytm.search(q, filter=f, limit=8),
                                            f"{filt}")
                except Exception:
                    results = []
                best_id, best_score = None, -1.0
                for cand in results or []:
                    vid = cand.get("videoId")
                    if not vid:
                        continue
                    cand_artist = ", ".join(a.get("name", "") for a in cand.get("artists") or []) or cand.get("author") or ""
                    ds = cand.get("duration_seconds")
                    score, ok = score_candidate(track["name"], track["artists"], track["duration_ms"],
                                                cand.get("title", ""), cand_artist, ds * 1000 if ds else None)
                    if ok and score > best_score:
                        best_id, best_score = vid, score
                if best_id:
                    return best_id, ("song" if filt == "songs" else "video")
        return None, None

    def add(self, playlist, target_ids):
        for video_id in target_ids:  # one at a time, in order — append order is date-added order
            self._request("POST", "playlistItems", params={"part": "snippet"}, json_body={
                "snippet": {"playlistId": playlist["playlistId"],
                            "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
            polite_sleep(1.0)

    def remove(self, playlist, track):
        if not track.get("playlistItemId"):
            return  # removal needs the playlist-item id (from playlist_tracks)
        self._request("DELETE", "playlistItems", params={"id": track["playlistItemId"]})
        polite_sleep(1.0)


def _expired(fn, what):
    """Translate an expired browser session into the auth error it actually is.
    A logged-out youtubei response carries no `contents`, which ytmusicapi walks
    into a bare KeyError — unreadable, and easily mistaken for a broken playlist
    rather than dead cookies."""
    try:
        return fn()
    except KeyError:
        raise TargetAuthError(f"YouTube Music session expired while reading {what}; "
                              "re-export the browser cookies (Settings -> YouTube Music).")


_YOUTUBEI_COLLABORATIVE_CURSOR_PREFIX = "songmirror:ytmusic:collaborative:"


def _youtubei_playlist_page(api, playlist_id, cursor=None):
    """Read one native youtubei shelf page while retaining its continuation.

    ytmusicapi's public ``get_playlist`` intentionally follows every shelf
    continuation and discards the token. The inspector needs the lower-level
    page boundary, so use the same parser/navigation helpers as that method and
    return the opaque token to the browser. YouTube currently serves up to 100
    entries in a native page; unlike the Data API, that size is not configurable.
    """
    from ytmusicapi.continuations import get_continuation_token
    from ytmusicapi.navigation import (
        CONTENT,
        EDITABLE_PLAYLIST_DETAIL_HEADER,
        HEADER,
        RESPONSIVE_HEADER,
        SECTION,
        SECTION_LIST_ITEM,
        TAB_CONTENT,
        TWO_COLUMN_RENDERER,
        nav,
    )
    from ytmusicapi.parsers.playlists import parse_playlist_header_meta, parse_playlist_items

    native_cursor = cursor
    is_collaborative = False
    if cursor and cursor.startswith(_YOUTUBEI_COLLABORATIVE_CURSOR_PREFIX):
        native_cursor = cursor[len(_YOUTUBEI_COLLABORATIVE_CURSOR_PREFIX):]
        if not native_cursor:
            raise RuntimeError("YouTube Music returned an invalid playlist cursor")
        is_collaborative = True

    if native_cursor:
        response = api._send_request("browse", {"continuation": native_cursor})
        items = nav(
            response,
            [
                "onResponseReceivedActions",
                0,
                "appendContinuationItemsAction",
                "continuationItems",
            ],
            True,
        )
        if not items:
            raise RuntimeError(
                "YouTube Music playlist read incomplete: a continuation returned no items"
            )
    else:
        browse_id = str(playlist_id)
        if not browse_id.startswith("VL"):
            browse_id = f"VL{browse_id}"
        response = api._send_request("browse", {"browseId": browse_id}, "")
        header_data = nav(
            response,
            [*TWO_COLUMN_RENDERER, *TAB_CONTENT, *SECTION_LIST_ITEM],
            True,
        )
        is_audio_playlist = str(playlist_id).startswith(("OLA", "VLOLA"))
        if header_data:
            if EDITABLE_PLAYLIST_DETAIL_HEADER[0] in header_data:
                header = nav(
                    header_data,
                    [*EDITABLE_PLAYLIST_DETAIL_HEADER, *HEADER, *RESPONSIVE_HEADER],
                )
            else:
                header = nav(header_data, RESPONSIVE_HEADER)
            is_collaborative = "collaborators" in parse_playlist_header_meta(header)
        elif not is_audio_playlist:
            # Logged-out responses are translated by _expired after their
            # missing shelf raises below. OLA/audio playlists legitimately
            # omit the normal playlist header, matching ytmusicapi's reader.
            is_collaborative = False
        section = nav(
            response,
            [*TWO_COLUMN_RENDERER, "secondaryContents", *SECTION],
        )
        shelf = nav(
            section,
            [*CONTENT, "musicPlaylistShelfRenderer"],
        )
        items = shelf.get("contents") or []

    next_native_cursor = get_continuation_token(items) if items else None
    if next_native_cursor is not None and next_native_cursor == native_cursor:
        raise RuntimeError("YouTube Music returned a non-advancing playlist cursor")
    next_cursor = (
        f"{_YOUTUBEI_COLLABORATIVE_CURSOR_PREFIX}{next_native_cursor}"
        if is_collaborative and next_native_cursor is not None
        else next_native_cursor
    )
    return parse_playlist_items(items, is_collaborative=is_collaborative), next_cursor


class YTMusicBrowserTarget(YTMusicTarget):
    """No-quota YT reads/writes via ytmusicapi's authenticated youtubei API, so a
    large backfill isn't capped at the Data API's ~200 adds/day. Trade-off: the
    browser cookies are a session snapshot Google rotates, so they need
    re-exporting periodically (the OAuth refresh token is durable by comparison).
    Inherits resolve/search (still the free public ytmusicapi) and the dict-shape
    accessors — only the reads/writes swap to the youtubei path."""

    def __init__(self, browser_auth_file):
        self.cache_file = self.resolve_cache_path()
        from ytmusicapi import YTMusic
        self._ytm = YTMusic()                   # public search (used by inherited resolve/_search)
        self._api = YTMusic(browser_auth_file)  # authenticated reads + writes, no Data API quota

    def _session_alive(self):
        """Whether the cookies still authenticate. Needed because the logged-out
        stub reaches ytmusicapi's library parser as an empty list, indistinguishable
        from an account that genuinely owns no playlists."""
        try:
            return bool((self._api.get_account_info() or {}).get("accountName"))
        except Exception:
            return False

    def list_playlists(self):
        out = {}
        for pl in _expired(lambda: self._api.get_library_playlists(limit=None), "the library"):
            title = (pl.get("title") or "").strip()
            key = title.casefold()
            if key and key not in out:
                out[key] = {"playlistId": pl.get("playlistId"), "title": title, "count": pl.get("count"),
                            "thumbnails": pl.get("thumbnails")}  # cover art for browse
        # An empty read must fail the pass, not report "no playlists" — the caller
        # creates whatever it can't find, so a degraded read would duplicate every
        # playlist. Only a live session is allowed to answer "genuinely empty".
        if not out and not self._session_alive():
            raise TargetAuthError("YouTube Music returned an empty library on a logged-out session; "
                                  "re-export the browser cookies (Settings -> YouTube Music).")
        return out

    def create(self, sp_playlist):
        name, description = source_playlist_details(sp_playlist)
        pid = self._api.create_playlist(name, description, privacy_status="PRIVATE")
        if not isinstance(pid, str):  # ytmusicapi returns a status dict/response on failure
            raise TargetAuthError(f"YouTube Music refused to create the playlist ({pid!r}).")
        polite_sleep(2.0)
        return {"playlistId": pid, "title": name, "count": 0}

    def fetch_playlist(self, playlist_id):
        """A playlist by id, public ones included. youtubei's get_playlist is not
        limited to the signed-in library."""
        try:
            data = self._api.get_playlist(str(playlist_id), limit=1) or {}
        except Exception:
            return None
        if not data.get("title"):
            return None
        return {
            "playlistId": data.get("id") or str(playlist_id),
            "title": data.get("title") or "",
            "description": data.get("description") or "",
            "count": data.get("trackCount"),
            "thumbnails": data.get("thumbnails"),
        }

    def playlist_tracks(self, playlist):
        data = _expired(lambda: self._api.get_playlist(playlist["playlistId"], limit=None),
                        f"playlist '{playlist.get('title', '')}'") or {}
        return [
            track
            for raw in data.get("tracks") or []
            if (track := _normalized_youtubei_playlist_track(raw)) is not None
        ]

    def favorite_tracks(self):
        data = _expired(
            lambda: self._api.get_liked_songs(limit=None),
            self.favorite_tracks_name,
        ) or {}
        return [
            track
            for raw in data.get("tracks") or []
            if (track := _normalized_youtubei_playlist_track(raw)) is not None
        ]

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            self._api.rate_song(str(target_id), "LIKE")
            polite_sleep(1.0)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if target_id:
            self._api.rate_song(target_id, "INDIFFERENT")
            polite_sleep(1.0)

    def playlist_tracks_page(self, playlist, cursor=None):
        rows, next_cursor = _expired(
            lambda: _youtubei_playlist_page(
                self._api,
                playlist["playlistId"],
                cursor=cursor,
            ),
            f"playlist '{playlist.get('title', '')}'",
        )
        return [
            track
            for raw in rows
            if (track := _normalized_youtubei_playlist_track(raw)) is not None
        ], next_cursor

    def add(self, playlist, target_ids):
        # YouTube may stamp a whole batch alike and reorder it. Singleton writes
        # make its append chronology match every other provider's contract.
        for target_id in target_ids:
            self._api.add_playlist_items(
                playlist["playlistId"], [target_id], duplicates=True)
            polite_sleep(1.0)

    def remove(self, playlist, track):
        if not track.get("setVideoId"):
            return  # youtubei removal needs setVideoId (from playlist_tracks)
        self._api.remove_playlist_items(
            playlist["playlistId"], [{"videoId": track["videoId"], "setVideoId": track["setVideoId"]}])
        polite_sleep(1.0)
