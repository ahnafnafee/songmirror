"""Spotify — playlist source, and (in N-way mode) a writable peer.

Read and write share one OAuth grant (config.SPOTIFY_SCOPE, the set the connector
also requests): spotipy stamps the requesting client's scope onto the cached token
on every refresh, so a read-only client that asked for less would strip the modify
scopes from the cache and make the next writable pass fail. Track dicts produced
here are the common currency the mirror targets consume.
"""

import html
import os
import random
import time

import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from . import spotify_web
from .config import (
    DEFAULT_SPOTIFY_REDIRECT_URI, DEFAULT_SPOTIFY_TOKEN_CACHE, REQUEST_TIMEOUT, SPOTIFY_SCOPE, required_env)
from .logs import log, log_note, log_warn

# Connection-level failures spotipy's status-code retry doesn't cover.
_TRANSIENT = (
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ReadTimeout,
)


def _retry(fn, what, attempts=5):
    """Retry a Spotify call on connection resets / read timeouts with backoff —
    reads are idempotent, so a reset page just re-fetches."""
    for attempt in range(attempts):
        try:
            return fn()
        except _TRANSIENT:
            if attempt == attempts - 1:
                raise
            wait = min(2 ** attempt, 20) + random.uniform(0, 2)
            log(f"connection issue ({what}); retrying in {int(wait)}s", tag="spotify")
            time.sleep(wait)


_API = "https://api.spotify.com/v1"   # official REST, reached directly only for the ISRC probe

_app_tokens = {}   # client_id -> {"token", "expires_at"}
_isrc_problem = {}  # client_id -> (checked_at, problem|None), see isrc_app_problem

# Any catalog track: the probe reads only the status code, never the payload.
_PROBE_TRACK = "6pHtgTMzsmP6ccN2ocv7XN"
# How long an ISRC-app verdict is trusted. The accounts endpoint is polled, so an
# uncached probe would put an HTTPS round trip on every poll.
ISRC_PROBE_TTL = 900


def _main_app():
    """The primary (OAuth) app's credentials. Doubles as the ISRC fallback: a
    Development-Mode app is refused on the batch /tracks endpoint but still serves
    /tracks/{id}, so it can carry ISRC lookups when no pool app can."""
    return (required_env("SPOTIFY_CLIENT_ID"), required_env("SPOTIFY_CLIENT_SECRET"))


def _isrc_pool():
    """[(client_id, secret)] parsed from the SPOTIFY_ISRC_CLIENTS pool
    ("id:secret,id:secret", set by the connect wizard's ISRC-app section); empty when
    none is configured. Read fresh each call so a wizard change takes effect without
    a restart."""
    pool = []
    for pair in (os.getenv("SPOTIFY_ISRC_CLIENTS") or "").split(","):
        cid, _, sec = pair.strip().partition(":")
        if cid and sec:
            pool.append((cid, sec))
    return pool


def _isrc_apps():
    """Which apps to try for ISRC catalog reads, best first. An app
    (client-credentials) token reads /tracks on a rate bucket SEPARATE from the OAuth
    user token and the web-player cookie token; the pool lets a rate-limited app fail
    over to the next (see spotify_cookie._track_isrcs)."""
    return _isrc_pool() or [_main_app()]


def isrc_app_count():
    return len(_isrc_apps())


def _token(cid, sec):
    """Client-credentials bearer, cached per client_id until ~1 min before expiry."""
    cached = _app_tokens.get(cid)
    now = time.time()
    if cached and now < cached["expires_at"] - 60:
        return cached["token"]
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec},
        timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    _app_tokens[cid] = {"token": body["access_token"], "expires_at": now + int(body.get("expires_in", 3600))}
    return _app_tokens[cid]["token"]


def app_token(index=0):
    """Bearer for the ISRC app pool[index]. Callers rotate `index` to fail over."""
    apps = _isrc_apps()
    return _token(*apps[index % len(apps)])


def main_app_token():
    """Bearer for the primary app, the single-track ISRC fallback's token."""
    return _token(*_main_app())


def tracks_probe_problem(status, body):
    """None when a client-credentials app can serve the BATCH /tracks?ids endpoint,
    else a short reason phrased to slot into a sentence.

    Two unrelated failures both answer 403 here, and telling them apart is the
    difference between "renew a subscription" and "request Extended Quota Mode".
    Spotify cuts off an app whose OWNER's Premium has lapsed on EVERY endpoint and
    says so in a plain-text body; a Development-Mode app is refused only on the batch
    endpoint and answers with the usual JSON error envelope."""
    if status in (200, 429):   # 429 means reachable, just rate-limited
        return None
    if status == 403 and "premium" in (body or "").lower():
        return "its owner account no longer has an active Spotify Premium subscription"
    if status == 403:
        return "it needs Extended Quota Mode (request it on the app's page at developer.spotify.com)"
    return f"Spotify answered {status}"


def isrc_app_problem():
    """Why the configured ISRC app can't serve batch /tracks, or None when it can.
    Also None when no ISRC app is configured, since there is nothing the user set up
    to be broken; the primary app's single-track fallback covers that case.

    Cached per client_id for ISRC_PROBE_TTL so a polled status endpoint stays cheap."""
    pool = _isrc_pool()
    if not pool:
        return None
    cid, sec = pool[0]
    hit = _isrc_problem.get(cid)
    now = time.time()
    if hit and now - hit[0] < ISRC_PROBE_TTL:
        return hit[1]
    try:
        r = requests.get(f"{_API}/tracks", params={"ids": _PROBE_TRACK},
                         headers={"Authorization": f"Bearer {_token(cid, sec)}"}, timeout=REQUEST_TIMEOUT)
        problem = tracks_probe_problem(r.status_code, r.text)
    except Exception as e:
        problem = f"Spotify could not be reached to check it ({e!r})"
    _isrc_problem[cid] = (now, problem)
    return problem


def clear_isrc_probe_cache():
    """Drop cached verdicts so a just-saved or just-cleared ISRC app is re-checked
    on the next status read instead of after ISRC_PROBE_TTL."""
    _isrc_problem.clear()


def client(writable=False):
    # Read and write request the same grant (SPOTIFY_SCOPE) so a read-only pass
    # never downscopes the cached token on refresh — see the module docstring.
    auth = SpotifyOAuth(
        client_id=required_env("SPOTIFY_CLIENT_ID"),
        client_secret=required_env("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", DEFAULT_SPOTIFY_REDIRECT_URI),
        scope=SPOTIFY_SCOPE,
        cache_path=os.getenv("SPOTIFY_TOKEN_CACHE") or DEFAULT_SPOTIFY_TOKEN_CACHE,
        open_browser=os.getenv("SPOTIFY_OAUTH_OPEN_BROWSER", "1") != "0",
    )
    # With no usable cached token, spotipy prints a URL and calls input() to paste
    # the redirect back — which EOFErrors in a headless server. Pre-check the cache
    # non-interactively so a missing/unrefreshable authorization fails with a clear,
    # actionable message instead of a cryptic EOF.
    try:
        token = auth.validate_token(auth.get_cached_token())
    except Exception:
        token = None
    if not token:
        from .targets.base import TargetAuthError

        detail = ("expired or lacks the write access N-way sync needs" if writable
                  else "missing or expired")
        raise TargetAuthError(
            f"Spotify needs reconnecting — its saved authorization is {detail}. "
            "Reconnect Spotify in the app.")
    return spotipy.Spotify(auth_manager=auth, requests_timeout=REQUEST_TIMEOUT, retries=5)


def description(sp_playlist):
    return html.unescape(sp_playlist.get("description") or "").strip()


def track_total(playlist):
    """Track count from a playlist list-object (the /me/playlists shape), or
    None. The count sits under `items` in the current API response and under
    `tracks` in the older shape — read the new key first, then the legacy one."""
    meta = playlist.get("items") or playlist.get("tracks") or {}
    return meta.get("total")


def playlists_by_name(sp):
    """name (casefolded) -> playlist, preferring playlists I own, then bigger."""
    me = _retry(lambda: sp.current_user(), "current_user")["id"]
    best = {}
    results = _retry(lambda: sp.current_user_playlists(limit=50), "playlists")
    while results:
        for playlist in results.get("items", []):
            if not playlist:
                continue
            name = (playlist.get("name") or "").strip().casefold()
            if not name:
                continue
            rank = (
                (playlist.get("owner") or {}).get("id") == me,
                track_total(playlist) or 0,
            )
            if name not in best or rank > best[name][0]:
                best[name] = (rank, playlist)
        page = results
        results = _retry(lambda: sp.next(page), "playlists page") if results.get("next") else None
    return {name: playlist for name, (rank, playlist) in best.items()}


def all_playlists(sp):
    """Every library playlist (owned AND followed), un-deduped, each annotated with
    `_owned` (its owner is the current user). playlists_by_name collapses by name
    for the sync engine's name-matching; browsing and transfers need the full,
    id-addressable list so a followed playlist that shares a name with an owned one
    stays reachable and can be labelled as followed."""
    me = _retry(lambda: sp.current_user(), "current_user")["id"]
    out = []
    results = _retry(lambda: sp.current_user_playlists(limit=50), "playlists")
    while results:
        for playlist in results.get("items", []):
            if not playlist:
                continue
            playlist["_owned"] = (playlist.get("owner") or {}).get("id") == me
            out.append(playlist)
        page = results
        results = _retry(lambda: sp.next(page), "playlists page") if results.get("next") else None
    return out


def playlist_item_track(item):
    """The track object of a playlist item, handling both the legacy shape
    ({"track": {...}}) and the current Web API shape ({"item": {...}}). Returns
    None for local files, episodes, and ghost entries."""
    track = item.get("track")
    if not isinstance(track, dict):
        track = item.get("item")
    if not isinstance(track, dict):
        return None
    if track.get("type", "track") != "track":
        return None
    if item.get("is_local") or track.get("is_local"):
        return None
    return track


def _playlist_item_tracks(items):
    tracks = []
    for item in items:
        track = playlist_item_track(item)
        if not track:
            continue
        artists = [a.get("name", "") for a in track.get("artists", []) if a.get("name")]
        album = track.get("album") or {}
        images = [image for image in album.get("images") or [] if image and image.get("url")]
        image = min(
            images,
            key=lambda candidate: abs(int(candidate.get("width") or 96) - 96),
        )["url"] if images else ""
        tracks.append({
            "id": track.get("id"),
            "isrc": (track.get("external_ids") or {}).get("isrc"),
            "name": track.get("name", ""),
            "artists": artists or [""],
            "album": album.get("name"),
            "album_position": track.get("track_number"),
            "duration_ms": track.get("duration_ms"),
            "added_at": item.get("added_at") or "",
            "image": image,
        })
    return tracks


def _playlist_tracks_api(sp, playlist_id):
    tracks = []
    results = _retry(
        lambda: sp.playlist_items(playlist_id, market="from_token", additional_types=("track",), limit=100),
        "playlist_items",
    )
    while results:
        tracks.extend(_playlist_item_tracks(results.get("items", [])))
        page = results
        results = _retry(lambda: sp.next(page), "tracks page") if results.get("next") else None
    return tracks


def saved_tracks(sp):
    """Every track in the current user's Liked Songs collection.

    Keep pagination explicit instead of using ``sp.next`` so the collection
    contract remains testable against the provider client alone and so an
    advertised-but-empty page fails closed rather than looking like removals.
    """
    tracks, offset = [], 0
    while True:
        results = _retry(
            lambda: sp.current_user_saved_tracks(limit=50, offset=offset),
            "saved tracks",
        )
        items = results.get("items") or []
        tracks.extend(_playlist_item_tracks(items))
        if not results.get("next"):
            return tracks
        if not items:
            raise RuntimeError(
                f"Spotify Liked Songs read incomplete: stopped at {offset} with another page advertised"
            )
        offset += len(items)


def _playlist_page_offset(cursor):
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Spotify playlist cursor is not a valid offset") from exc
    if offset < 0:
        raise RuntimeError("Spotify playlist cursor is not a valid offset")
    return offset


def playlist_tracks_page(sp, playlist_id, cursor=None):
    """Read one 20-entry Web API page for the progressive playlist UI."""
    offset = _playlist_page_offset(cursor)
    try:
        results = _retry(
            lambda: sp.playlist_items(
                playlist_id,
                market="from_token",
                additional_types=("track",),
                limit=20,
                offset=offset,
            ),
            "playlist_items",
        )
    except spotipy.SpotifyException as exc:
        # Development-mode apps cannot read followed playlists. The scraper has
        # no offset primitive, so only a first-page rejection can safely fall
        # back to its complete read without appending duplicates.
        if cursor is None and exc.http_status == 403 and spotify_web.enabled():
            log_note(f"{playlist_id}: official read forbidden (403); trying web-player fallback", tag="spotify")
            try:
                tracks = spotify_web.playlist_tracks(playlist_id)
                log_note(f"{playlist_id}: web-player fallback read {len(tracks)} tracks", tag="spotify")
                return tracks, None
            except Exception as web_exc:
                log_warn(f"{playlist_id}: web-player fallback failed ({web_exc!r})", tag="spotify")
                raise exc
        raise

    items = results.get("items") or []
    if results.get("next") and not items:
        raise RuntimeError(
            f"Spotify playlist read incomplete: stopped at {offset} with another page advertised"
        )
    next_cursor = str(offset + len(items)) if results.get("next") else None
    return _playlist_item_tracks(items), next_cursor


def playlist_tracks(sp, playlist_id):
    """Playlist tracks via the official API, falling back to the web-player read
    on a 403 — which is what the official API returns for the tracks of a followed
    (non-owned) playlist under a Development-Mode app. The fallback (SpotifyScraper)
    is opt-outable via SPOTIFY_WEB_FALLBACK; on any fallback failure the original
    403 is re-raised so the caller's safety guards still apply."""
    try:
        return _playlist_tracks_api(sp, playlist_id)
    except spotipy.SpotifyException as e:
        if e.http_status == 403 and spotify_web.enabled():
            log_note(f"{playlist_id}: official read forbidden (403); trying web-player fallback", tag="spotify")
            try:
                tracks = spotify_web.playlist_tracks(playlist_id)
                log_note(f"{playlist_id}: web-player fallback read {len(tracks)} tracks", tag="spotify")
                return tracks
            except Exception as we:
                log_warn(f"{playlist_id}: web-player fallback failed ({we!r})", tag="spotify")
                raise e
        raise
