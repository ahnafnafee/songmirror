"""Cookie (sp_dc) web-session backend for Spotify.

A self-hosted Spotify developer app in Development Mode is refused (403) by the
official API on the *content* surface — creating playlists and adding/removing
playlist items — even with the modify scopes granted. Reads already have a
web-player fallback (`spotify_web.py`); this is the matching path for writes.

It authenticates as Spotify's own first-party web client via the `sp_dc` cookie
(spotify_scraper mints the bearer, TOTP and all), which is not subject to the
dev-app gate. Item add/remove go through the web-player GraphQL API
("pathfinder"); playlist creation goes through Spotify's first-party playlist
service. When ``SPOTIFY_WRITE_BACKEND=cookie`` this module is a complete peer:
library listing, playlist reads, catalog search and writes all use the signed-in
web session. No Spotify developer Client ID, secret or Premium account is needed.

Fragility (why the self-heal exists): pathfinder persisted-query hashes rotate
on each web-player release and a stale one is rejected as PersistedQueryNotFound.
`_refresh_hashes` re-scrapes the current hashes from the live web-player bundle
on that error, so a rotation self-heals instead of hard-failing. The `sp_dc`
session can be revoked or rotated; the connector surfaces when it needs renewing.
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import requests

from .config import REQUEST_TIMEOUT, polite_sleep
from .logs import log, log_note, log_warn
from .targets.base import TargetAuthError

_PATHFINDER = "https://api-partner.spotify.com/pathfinder/v2/query"
_SPCLIENT = "https://spclient.wg.spotify.com"   # web-player backend — no api.spotify.com rate limit / dev-mode gate
_API = "https://api.spotify.com/v1"             # official REST with either the web-player user token or an ISRC app token
_WEB = "https://open.spotify.com/"
# Sent as spotify-app-version; loosely paired with the persisted-query hashes and
# refreshed alongside them. A slightly stale value still resolves in practice.
_APP_VERSION = "1.2.95.312.gda5d7e47"
# A browser User-Agent is required — Spotify's edge 403s the default python-requests one.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/152.0"

# Persisted-query sha256 hashes, keyed by the document they belong to. add/remove/
# move share one mutation document (op selected by name); the fetch* reads share
# another. Seeded with known-good values; _refresh_hashes rewrites them in place
# when a call reports the hash is unknown (a web-player release rotated them).
_HASHES = {
    "playlist_mut": "47b2a1234b17748d332dd0431534f22450e9ecbb3d5ddcdacbd83368636a0990",
    "playlist_read": "a65e12194ed5fc443a1cdebed5fabe33ca5b07b987185d63c72483867ad13cb4",
    "profile": "b197b5adb4b761690f76ad9d9fb278c14c14e7331f357c04a56e7001af7106e0",
    "library": "390c78e5b951029bad359785e69b07b536a509c581cbcd0aded5e5067f187455",
}
# Which operation name maps to which hashed document — also drives the re-scrape.
_OP_DOC = {
    "addToPlaylist": "playlist_mut", "removeFromPlaylist": "playlist_mut",
    "fetchPlaylistContents": "playlist_read", "fetchPlaylist": "playlist_read",
    "profileAttributes": "profile", "libraryV3": "library",
}

_provider = None   # cached spotify_scraper CookieTokenProvider (lazy)
_catalog = None    # cached spotify_scraper SpotifyClient (lazy)
_uid = None        # cached cookie-account user id (for rootlist filing)
_isrc_cache = {}   # track_id -> isrc|None, backfilled from /tracks (see _track_isrcs)
_playlist_count_cache = {}  # playlist_id -> (revision_id, total); libraryV3 omits totals


def configured():
    """True when an sp_dc cookie is available (env or the stored file)."""
    return bool(_sp_dc(soft=True))


def reset_session():
    """Drop every object derived from the current ``sp_dc`` value.

    The account wizard can replace a cookie while the server stays running. A
    reset makes the very next read/search/token request use that new account
    instead of a cached provider or catalog client from the old session.
    """
    global _provider, _catalog, _uid
    old_catalog = _catalog
    _provider = None
    _catalog = None
    _uid = None
    _isrc_cache.clear()
    _playlist_count_cache.clear()
    if old_catalog is not None:
        try:
            old_catalog.close()
        except Exception:
            pass


def sp_dc_path():
    """Where the sp_dc cookie is stored. Under SONGMIRROR_DATA_DIR so it lands on
    the same persistent volume as the other secrets (Docker points it at /data)."""
    return os.getenv("SPOTIFY_SP_DC_FILE") or os.path.join(
        os.getenv("SONGMIRROR_DATA_DIR") or "data", "spotify_sp_dc.private")


def _sp_dc(soft=False):
    # The Accounts wizard writes the private file. Prefer it over a bootstrap
    # environment value so replacing a cookie in the running UI remains fixed
    # after a container restart even when its original .env still has an older
    # value. Headless installs fall back to SPOTIFY_SP_DC when no file exists.
    path = sp_dc_path()
    try:
        with open(path, encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return value
    except OSError:
        pass
    value = (os.getenv("SPOTIFY_SP_DC") or "").strip()
    if value:
        return value
    if soft:
        return None
    raise TargetAuthError(
        "Spotify cookie mode is on but no sp_dc cookie is set — paste it on the "
        "Accounts page (or set SPOTIFY_SP_DC).")


def _prov():
    global _provider
    if _provider is None:
        # Imported lazily: spotify_scraper is only pulled in when cookie mode runs.
        from spotify_scraper.auth.cookies import CookieTokenProvider
        from spotify_scraper.http.transport import HttpxTransport
        _provider = CookieTokenProvider(HttpxTransport(), _sp_dc())
    return _provider


def _token():
    try:
        return _prov().token()
    except Exception as e:  # AuthenticationError (bad/rotated cookie) or transport
        raise TargetAuthError(
            f"Spotify cookie rejected ({e}). Re-paste the sp_dc cookie on the Accounts page.") from e


def _headers():
    return {
        "authorization": f"Bearer {_token()}",
        "app-platform": "WebPlayer",
        "spotify-app-version": _APP_VERSION,
        "Origin": "https://open.spotify.com",
        "Referer": _WEB,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "User-Agent": _UA,
    }


def _persisted_missing(body):
    for err in (body.get("errors") or []):
        msg = (err.get("message") or "") if isinstance(err, dict) else str(err)
        if "PersistedQueryNotFound" in msg:
            return True
    return False


def _pf(op, variables):
    """Run a pathfinder operation, self-healing a stale hash and a stale token.

    One retry each: a 401 means the bearer expired (drop it and re-mint); a
    PersistedQueryNotFound means the web player rotated its hashes (re-scrape and
    retry). Anything else surfaces as a fatal TargetAuthError so a pass never
    half-writes."""
    doc = _OP_DOC[op]
    refreshed = False
    for _ in range(3):
        body = {"variables": variables, "operationName": op,
                "extensions": {"persistedQuery": {"version": 1, "sha256Hash": _HASHES[doc]}}}
        r = requests.post(_PATHFINDER, headers=_headers(), data=json.dumps(body), timeout=REQUEST_TIMEOUT)
        if r.status_code == 401:
            _prov().invalidate()
            continue
        try:
            payload = r.json() if r.content else {}
        except ValueError:
            payload = {}
        if _persisted_missing(payload) and not refreshed:
            refreshed = True
            _refresh_hashes()
            continue
        if r.status_code == 403:
            raise TargetAuthError(
                f"Spotify refused {op} (403) for the cookie account — the sp_dc account must own "
                "the playlist. Check you pasted the right account's cookie.")
        r.raise_for_status()
        if payload.get("errors"):
            raise TargetAuthError(f"Spotify pathfinder {op} error: {payload['errors']}")
        return payload.get("data") or {}
    raise TargetAuthError(f"Spotify pathfinder {op} failed after token/hash refresh.")


def _refresh_hashes():
    """Re-scrape the current persisted-query hashes from the live web-player
    bundle. Best-effort: on any failure the seeded hashes stay and the caller's
    retry surfaces the original error."""
    try:
        cookie = {"Cookie": f"sp_dc={_sp_dc()}"}
        ua = {"User-Agent": _UA}
        shell = requests.get(_WEB, headers={**ua, **cookie}, timeout=REQUEST_TIMEOUT).text
        urls = set(re.findall(r"https://open\.spotifycdn\.com/cdn/build/web-player/[^\"']+\.js", shell))
        blob = "".join(requests.get(u, headers=ua, timeout=REQUEST_TIMEOUT).text for u in urls)
        for op, doc in _OP_DOC.items():
            m = re.search(rf'\.l\("{op}","(?:mutation|query)","([a-f0-9]{{64}})"', blob)
            if m:
                _HASHES[doc] = m.group(1)
        log_note("refreshed Spotify web-player query hashes", tag="spotify")
    except Exception as e:
        log_warn(f"could not refresh Spotify web-player hashes ({e!r})", tag="spotify")


# -- public write operations --------------------------------------------------

def _puri(playlist):
    pid = playlist if isinstance(playlist, str) else playlist.get("id", "")
    return pid if str(pid).startswith("spotify:") else f"spotify:playlist:{pid}"


def _turi(track_id):
    return track_id if str(track_id).startswith("spotify:") else f"spotify:track:{track_id}"


def add(playlist, track_ids):
    """Append tracks one at a time (bottom, in order). One track per call so each
    gets a distinct date-added — a single batched add stamps them all identically,
    which scrambles the destination's "Recently added" view. Mirrors the OAuth /
    Apple sequential-add pattern."""
    puri = _puri(playlist)
    for tid in track_ids:
        _pf("addToPlaylist", {"playlistUri": puri, "playlistItemUris": [_turi(tid)],
                              "newPosition": {"moveType": "BOTTOM_OF_PLAYLIST", "fromUid": None}})
        polite_sleep(0.3)


def _content_page(playlist, cursor=None, *, limit=20):
    """One raw web-player page plus a private numeric continuation offset."""
    try:
        offset = 0 if cursor is None else int(cursor)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Spotify playlist cursor is not a valid offset") from exc
    if offset < 0:
        raise RuntimeError("Spotify playlist cursor is not a valid offset")

    data = _pf(
        "fetchPlaylistContents",
        {"uri": _puri(playlist), "offset": offset, "limit": limit},
    )
    page = (data.get("playlistV2") or {}).get("content") or {}
    items = page.get("items") or []
    raw_total = page.get("totalCount")
    if raw_total is None:
        raise RuntimeError("Spotify playlist read incomplete: page did not include totalCount")
    total = int(raw_total)
    if not items and offset < total:
        raise RuntimeError(
            f"Spotify playlist read incomplete: stopped at {offset} of {total} items"
        )
    next_offset = offset + len(items)
    return items, (str(next_offset) if next_offset < total else None)


def _content_items(playlist):
    """Yield every raw playlist item (paginated) from the web-player read."""
    cursor = None
    while True:
        items, cursor = _content_page(playlist, cursor, limit=100)
        yield from items
        if cursor is None:
            return


def contents(playlist):
    """[{uid, uri}] for every item — `uid` is the per-item handle remove needs
    (the mutation deletes by item uid, not track uri)."""
    return [{"uid": it.get("uid"), "uri": ((it.get("itemV2") or {}).get("data") or {}).get("uri")}
            for it in _content_items(playlist)]


def _library_image_sources(images):
    """Flatten libraryV3's ``images.items[].sources[]`` to Web-API shape."""
    out = []
    for image in (images or {}).get("items") or []:
        sources = image.get("sources") or []
        if isinstance(sources, dict):
            sources = sources.get("items") or []
        for source in sources:
            if source.get("url"):
                out.append({"url": source["url"], "width": source.get("width"),
                            "height": source.get("height")})
    return out


def library_playlists():
    """Every playlist in the signed-in account's library.

    ``libraryV3`` is the web player's own filtered library query. It avoids the
    old rootlist plus one metadata request per playlist, and its capability data
    identifies followed playlists that are readable but not editable.
    """
    out, offset, limit = [], 0, 100
    while True:
        variables = {
            "filters": ["Playlists"], "order": "Alphabetical", "textFilter": None,
            "features": [], "limit": limit, "offset": offset, "flatten": True,
            "expandedFolders": None, "folderUri": None,
            "includeFoldersWhenFlattening": True,
        }
        library = ((_pf("libraryV3", variables).get("me") or {}).get("libraryV3") or {})
        rows = library.get("items") or []
        total = library.get("totalCount")
        if total is None:
            raise RuntimeError("Spotify library read incomplete: page did not include totalCount")
        if not rows and offset < int(total):
            raise RuntimeError(
                f"Spotify library read incomplete: stopped at {offset} of {total} items")
        for row in rows:
            item = row.get("item") or {}
            data = item.get("data") or {}
            if data.get("__typename") != "Playlist":
                continue
            uri = data.get("uri") or item.get("_uri") or ""
            if not str(uri).startswith("spotify:playlist:") or not data.get("name"):
                raise RuntimeError("Spotify library read incomplete: playlist metadata was missing")
            owner = (data.get("ownerV2") or {}).get("data") or {}
            editable = bool((data.get("currentUserCapabilities") or {}).get("canEditItems"))
            out.append({
                "id": str(uri).rsplit(":", 1)[-1],
                "uri": uri,
                "name": data.get("name") or "",
                "description": data.get("description") or "",
                "snapshot_id": data.get("revisionId"),
                "owner": {"id": owner.get("username") or owner.get("id")},
                "images": _library_image_sources(data.get("images")),
                "_owned": editable,
                "_editable": editable,
            })
        offset += len(rows)
        if offset >= int(total):
            return out


def _playlist_track_total(playlist):
    """One playlist's item total through the signed-in web-player API.

    The libraryV3 projection does not include a count. Its revisionId does
    change with playlist contents, so it is a safe cache validator for this
    lightweight limit=1 lookup.
    """
    pid = str(playlist.get("id") or "")
    revision = playlist.get("snapshot_id") or playlist.get("revisionId")
    hit = _playlist_count_cache.get(pid)
    if pid and revision is not None and hit and hit[0] == revision:
        return hit[1]
    try:
        data = _pf("fetchPlaylistContents", {
            "uri": playlist.get("uri") or _puri(pid),
            "offset": 0,
            "limit": 1,
        })
        raw_total = ((data.get("playlistV2") or {}).get("content") or {}).get("totalCount")
        if raw_total is None:
            raise RuntimeError("Spotify playlist count response did not include totalCount")
        count = int(raw_total)
    except Exception:
        return hit[1] if hit else None
    if pid and revision is not None:
        _playlist_count_cache[pid] = (revision, count)
    return count


def hydrate_playlist_counts(playlists):
    """Attach Web-API-shaped ``items.total`` values to libraryV3 rows.

    Counts are browse metadata, not required for sync correctness. Fetch cache
    misses concurrently so a large library does not turn into a long serial
    request train; individual failures leave that card's count unknown while
    preserving the playlist list itself.
    """
    rows = list(playlists)
    if not rows:
        return rows
    workers = min(6, len(rows))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        counts = list(pool.map(_playlist_track_total, rows))
    for playlist, count in zip(rows, counts):
        if count is not None:
            playlist["items"] = {"total": count}
    return rows


def _catalog_client():
    """The public web-player catalog client used for destination search."""
    global _catalog
    if _catalog is None:
        from spotify_scraper import SpotifyClient

        _catalog = SpotifyClient(cookies={"sp_dc": _sp_dc()}, timeout=REQUEST_TIMEOUT)
    return _catalog


def search_tracks(query, limit=8):
    """Spotipy-shaped catalog hits without the developer Web API."""
    result = _catalog_client().search(query, types=("track",), limit=limit)
    out = []
    for track in result.tracks[:limit]:
        out.append({
            "id": track.id,
            "name": track.name,
            "artists": [{"name": artist.name} for artist in track.artists],
            "album": {"name": track.album.name if track.album else ""},
            "duration_ms": track.duration_ms,
        })
    return out


def _track_isrcs(ids):
    """{track_id: isrc|None} from the official catalog via a CLIENT-CREDENTIALS APP token on
    the BATCH /tracks?ids endpoint (50 ids/call). Cached in-process; only unknown ids fetch.

    Token+endpoint choice — every alternative tested live:
      • OAuth user token → 403 on /tracks (dev-mode gate).
      • cookie (first-party) token → does batch, but rate-limits PER-ACCOUNT and, retried
        into a 429, escalates into an hours-long penalty box. Kept for WRITES, not this.
      • APP token → a SEPARATE rate bucket from the user account, so ISRC reads never touch
        the per-account limit. A DEV-MODE app 403s on batch and caps ~300/24h on single; an
        EXTENDED-QUOTA app does the 50-ids batch — a whole library in ~len/50 calls. The
        SPOTIFY_ISRC_CLIENTS pool supplies batch-capable app creds.

    Three outcomes per batch, and the distinction between the last two is the point:
      • 429 rotates to the next pool app; when the LAST app 429s it raises, so the sync
        fails closed rather than matching blind. No retry INTO a 429 on the same app
        (that's what earns a penalty box).
      • 403 means that app cannot serve this endpoint at all, which is not something a
        retry or a wait fixes. Every pool app is tried, then _isrc_singles carries the
        batch. A refused app must not take the sync down: an expired Premium on the
        pool app's owner account, or no extended-quota app at all, is a slower path,
        not a broken one.
    With the DB cache (playlist_tracks' known_isrc), steady-state fetches trend to zero."""
    from . import spotify
    want = [i for i in dict.fromkeys(ids) if i and i not in _isrc_cache]
    napps = spotify.isrc_app_count()
    for i in range(0, len(want), 50):
        chunk = want[i:i + 50]
        for app_idx in range(napps):
            r = requests.get(f"{_API}/tracks", params={"ids": ",".join(chunk)},
                             headers={"Authorization": f"Bearer {spotify.app_token(app_idx)}", "User-Agent": _UA},
                             timeout=REQUEST_TIMEOUT)
            if r.status_code == 403:
                continue   # this app can't batch at all: next app, then the single fallback
            if r.status_code == 429 and app_idx < napps - 1:
                continue   # this app is rate-limited — fail over to the next pool app
            r.raise_for_status()   # last-app 429 / other error -> HTTPError -> fail-closed upstream
            for t in (r.json().get("tracks") or []):
                if t:
                    _isrc_cache[t["id"]] = (t.get("external_ids") or {}).get("isrc")
            break
        else:
            _isrc_singles(chunk)   # every app refused the batch endpoint
        if i + 50 < len(want):
            polite_sleep(0.5)   # space multi-batch backfills; a single-batch pass doesn't sleep
    return {i: _isrc_cache.get(i) for i in ids}


_singles_warned = False   # the degraded-path warning is once per process, not per batch
_singles_used = 0         # tracks served by the degraded path, drained per pass


def take_singles_used():
    """How many tracks the per-track ISRC path served since the last read, and
    resets. The runner drains this into the pass summary so the dashboard can say
    the sync is on the slow path and how much of the daily budget it spent. A
    counter rather than a return value because the lookup sits several layers
    inside a provider read, with nothing summary-shaped to thread it back through."""
    global _singles_used
    n, _singles_used = _singles_used, 0
    return n


def _isrc_singles(ids):
    """Fill the ISRC cache one track at a time via /tracks/{id} with the PRIMARY app's
    token. That endpoint is not behind the Development-Mode gate, so it still answers
    when every pool app is refused on the batch endpoint.

    ponytail: one call per track against a dev-mode app's ~300/24h budget, and no cap
    of its own. The budget holds because only tracks the songs DB has never seen reach
    here; a first-run backfill of a large library will exhaust it and 429, which raises
    and fails the sync closed. Connecting an extended-quota ISRC app restores batching
    and lifts the ceiling."""
    from . import spotify

    global _singles_warned, _singles_used
    if not _singles_warned:
        _singles_warned = True
        log_warn("batch ISRC lookup refused; falling back to one call per track. Connect an "
                 "extended-quota ISRC lookup app (Accounts > Spotify) to restore batching.",
                 tag="spotify")
    for tid in ids:
        r = requests.get(f"{_API}/tracks/{tid}",
                         headers={"Authorization": f"Bearer {spotify.main_app_token()}", "User-Agent": _UA},
                         timeout=REQUEST_TIMEOUT)
        r.raise_for_status()   # includes a 429 once the daily budget is spent -> fail closed
        _isrc_cache[tid] = (r.json().get("external_ids") or {}).get("isrc")
        _singles_used += 1     # counted per call actually spent, not per track asked for
        polite_sleep(0.2)


def _normalized_content_tracks(items):
    out = []
    for it in items:
        t = (it.get("itemV2") or {}).get("data") or {}
        uri = t.get("uri") or ""
        if not uri.startswith("spotify:track:"):
            continue  # local file / episode / unavailable — excluded like the official read
        artists = [(a.get("profile") or {}).get("name", "") for a in ((t.get("artists") or {}).get("items") or [])]
        album = t.get("albumOfTrack") or {}
        sources = [source for source in ((album.get("coverArt") or {}).get("sources") or [])
                   if source and source.get("url")]
        image = min(
            sources,
            key=lambda candidate: abs(int(candidate.get("width") or 96) - 96),
        )["url"] if sources else ""
        out.append({
            "id": uri.rsplit(":", 1)[-1],
            "isrc": None,
            "name": t.get("name", "") or "",
            "artists": [a for a in artists if a] or [""],
            "album": album.get("name"),
            "album_position": t.get("trackNumber"),
            "duration_ms": (t.get("trackDuration") or {}).get("totalMilliseconds"),
            "added_at": (it.get("addedAt") or {}).get("isoString") or "",
            "image": image,
        })
    return out


def _apply_playlist_isrcs(out, *, require_isrc=False, known_isrc=None):
    # Persisted ISRCs remain valuable in cookie-only mode, but a cache miss is
    # deliberately left blank for reconcile to infer from its ISRC-bearing peers.
    # Only legacy callers that explicitly request a complete ISRC read touch the
    # developer catalog lookup.
    if out and known_isrc:
        ids = [t["id"] for t in out]
        cached = known_isrc(ids) or {}
        for t in out:
            t["isrc"] = cached.get(t["id"])
    if require_isrc and out:
        missing = [t["id"] for t in out if not t.get("isrc")]
        fetched = _track_isrcs(missing)
        for t in out:
            t["isrc"] = t.get("isrc") or fetched.get(t["id"])
    return out


def playlist_tracks_page(playlist, cursor=None, *, known_isrc=None):
    """Read one 20-entry pathfinder page for the progressive playlist UI."""
    items, next_cursor = _content_page(playlist, cursor, limit=20)
    tracks = _normalized_content_tracks(items)
    return _apply_playlist_isrcs(tracks, known_isrc=known_isrc), next_cursor


def playlist_tracks(playlist, require_isrc=False, known_isrc=None):
    """Full track dicts (the shape spotify.playlist_tracks yields) via pathfinder —
    works for private owned playlists the dev-mode official API 403s, and returns []
    for a just-created empty playlist. The pathfinder payload carries no ISRC (confirmed
    absent from the entire web-player surface). N-way reconciliation now seeds
    missing Spotify identities from every ISRC-bearing peer in the same complete
    read. ``require_isrc`` remains only for legacy callers that explicitly opt
    into the developer catalog lookup.

    known_isrc(ids) -> {id: isrc}, when given, supplies already-known ISRCs (the
    persisted songs-DB cache) so only genuinely-new tracks hit the rate-limited /tracks
    endpoint — the difference between "fetch every track every pass" (which earns a
    penalty box) and "fetch each track once, ever". Transfers pass neither flag — a
    same-provider copy uses the track id directly."""
    tracks = _normalized_content_tracks(_content_items(playlist))
    return _apply_playlist_isrcs(
        tracks,
        require_isrc=require_isrc,
        known_isrc=known_isrc,
    )


def _user_api(method, path, *, params=None):
    """Call a current-user REST endpoint with the first-party web token."""
    for attempt in range(2):
        response = requests.request(
            method,
            f"{_API}/{path.lstrip('/')}",
            params=params,
            headers=_spc_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 401 and attempt == 0:
            _prov().invalidate()
            continue
        if response.status_code in (401, 403):
            raise TargetAuthError(
                f"Spotify refused {method} {path} ({response.status_code}); re-paste the sp_dc cookie "
                "on the Accounts page."
            )
        response.raise_for_status()
        return response
    raise TargetAuthError(f"Spotify refused {method} {path} after refreshing the cookie token.")


def favorite_tracks():
    """Read Liked Songs with the cookie account's first-party bearer."""
    from .spotify import _playlist_item_tracks

    tracks, offset = [], 0
    while True:
        body = _user_api("GET", "me/tracks", params={"limit": 50, "offset": offset}).json()
        items = body.get("items") or []
        tracks.extend(_playlist_item_tracks(items))
        if not body.get("next"):
            return tracks
        if not items:
            raise RuntimeError(
                f"Spotify Liked Songs read incomplete: stopped at {offset} with another page advertised"
            )
        offset += len(items)


def add_favorite_tracks(track_ids):
    for track_id in track_ids:
        _user_api("PUT", "me/library", params={"uris": _turi(track_id)})
        polite_sleep(0.3)


def remove_favorite_track(track_id):
    _user_api("DELETE", "me/library", params={"uris": _turi(track_id)})
    polite_sleep(0.3)


def remove(playlist, track_ids):
    """Remove every occurrence of the given tracks. Resolves track uris to item
    uids via a contents read, since the mutation deletes by uid."""
    want = {_turi(t) for t in track_ids}
    uids = [c["uid"] for c in contents(playlist) if c["uri"] in want and c["uid"]]
    if uids:
        _pf("removeFromPlaylist", {"playlistUri": _puri(playlist), "uids": uids})


def remove_positions(playlist, positions):
    """Remove the items at these 0-based positions. ponytail: evaluated against a
    fresh contents read, not the caller's read-time snapshot — acceptable because
    reconcile position-removes within one short pass; revisit if drift bites."""
    items = contents(playlist)
    uids = [items[p]["uid"] for p in positions if 0 <= p < len(items) and items[p]["uid"]]
    if uids:
        _pf("removeFromPlaylist", {"playlistUri": _puri(playlist), "uids": uids})


def _spc_headers():
    return {"authorization": f"Bearer {_token()}", "User-Agent": _UA,
            "Content-Type": "application/json;charset=UTF-8", "Accept": "application/json"}


def current_user_id():
    """The cookie account's user id, read once via pathfinder (not api.spotify.com)
    and cached for the process."""
    global _uid
    if _uid is None:
        prof = ((_pf("profileAttributes", {}).get("me") or {}).get("profile") or {})
        _uid = prof.get("username") or ""
        if not _uid:
            raise TargetAuthError("Couldn't read the Spotify account id from the cookie session.")
    return _uid


def _rootlist_add(playlist_uri):
    """File a just-created playlist into the account's rootlist so it shows in the
    library (spclient create leaves it unfiled). Best-effort: the playlist already
    has its tracks, so a rootlist hiccup shouldn't fail the transfer — just log it."""
    try:
        rl = f"{_SPCLIENT}/playlist/v2/user/{current_user_id()}/rootlist"
        rev = requests.get(rl, headers=_spc_headers(), timeout=REQUEST_TIMEOUT).json()["revision"]
        body = {"baseRevision": rev, "wantResultingRevisions": False, "wantSyncResult": False, "nonces": [],
                "deltas": [{"ops": [{"kind": 2, "add": {"items": [{"uri": playlist_uri}], "addFirst": True}}]}]}
        requests.post(rl + "/changes", headers=_spc_headers(), data=json.dumps(body), timeout=REQUEST_TIMEOUT).raise_for_status()
    except Exception as e:
        log_warn(f"created {playlist_uri} but couldn't add it to the library ({e!r})", tag="spotify")


def create(name, public=False, description=""):
    """Create a playlist via the web-player backend and file it into the account's
    library — neither call touches api.spotify.com or the dev-app dev-mode gate.
    Returns a playlist object shaped like the spotipy path ({id, uri, name}). Only
    the name is set at creation (description/public aren't part of the call); the
    transfer uses name + id."""
    body = {"ops": [{"kind": 6, "updateListAttributes": {"newAttributes": {
        "values": {"name": name or "", "formatAttributes": [], "pictureSize": []}, "noValue": []}}}]}
    r = requests.post(f"{_SPCLIENT}/playlist/v2/playlist", headers=_spc_headers(),
                      data=json.dumps(body), timeout=REQUEST_TIMEOUT)
    if not r.ok:
        raise TargetAuthError(
            f"Couldn't create the playlist via the cookie backend ({r.status_code}). Create '{name}' in "
            "Spotify and re-run the transfer choosing it as an existing playlist (adding tracks works).")
    uri = (r.json() or {}).get("uri", "")
    _rootlist_add(uri)
    return {"id": uri.rsplit(":", 1)[-1], "uri": uri, "name": name}


def demo():
    """Read-only self-check: mint the token and read a playlist's contents.
    Usage: python -m songmirror.engine.spotify_cookie spotify:playlist:<id>
    (needs SPOTIFY_SP_DC / data/spotify_sp_dc.private set)."""
    import sys
    puri = sys.argv[1] if len(sys.argv) > 1 else None
    assert configured(), "no sp_dc cookie configured"
    assert _token(), "token mint failed"
    if puri:
        tracks = playlist_tracks(puri)
        assert isinstance(tracks, list), "playlist_tracks did not return a list"
        assert all("id" in t and "name" in t for t in tracks), "malformed track dict"
        log(f"cookie self-check OK: {len(tracks)} tracks in {puri}", tag="spotify")
    else:
        log("cookie self-check OK: token minted (pass a playlist uri to read-test)", tag="spotify")


if __name__ == "__main__":
    demo()
