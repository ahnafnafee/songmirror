"""Cookie (sp_dc) write backend for Spotify.

A self-hosted Spotify developer app in Development Mode is refused (403) by the
official API on the *content* surface — creating playlists and adding/removing
playlist items — even with the modify scopes granted. Reads already have a
web-player fallback (`spotify_web.py`); this is the matching path for writes.

It authenticates as Spotify's own first-party web client via the `sp_dc` cookie
(spotify_scraper mints the bearer, TOTP and all), which is not subject to the
dev-app gate. Item add/remove go through the web-player GraphQL API
("pathfinder"); playlist creation goes through the official REST endpoint with
the same first-party token. Only writes route here, and only when
SPOTIFY_WRITE_BACKEND=cookie — reads stay on the official API + scraper fallback.

Fragility (why the self-heal exists): pathfinder persisted-query hashes rotate
on each web-player release and a stale one is rejected as PersistedQueryNotFound.
`_refresh_hashes` re-scrapes the current hashes from the live web-player bundle
on that error, so a rotation self-heals instead of hard-failing. The `sp_dc`
cookie itself lasts about a year; the connector surfaces when it needs renewing.
"""

import json
import os
import re

import requests

from .config import REQUEST_TIMEOUT, polite_sleep
from .logs import log, log_note, log_warn
from .targets.base import TargetAuthError

_PATHFINDER = "https://api-partner.spotify.com/pathfinder/v2/query"
_SPCLIENT = "https://spclient.wg.spotify.com"   # web-player backend — no api.spotify.com rate limit / dev-mode gate
_API = "https://api.spotify.com/v1"             # official REST — the batch /tracks?ids ISRC lookup (client-credentials app token; see _track_isrcs)
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
}
# Which operation name maps to which hashed document — also drives the re-scrape.
_OP_DOC = {
    "addToPlaylist": "playlist_mut", "removeFromPlaylist": "playlist_mut",
    "fetchPlaylistContents": "playlist_read", "profileAttributes": "profile",
}

_provider = None   # cached spotify_scraper CookieTokenProvider (lazy)
_uid = None        # cached cookie-account user id (for rootlist filing)
_isrc_cache = {}   # track_id -> isrc|None, backfilled from /tracks (see _track_isrcs)


def configured():
    """True when an sp_dc cookie is available (env or the stored file)."""
    return bool(_sp_dc(soft=True))


def sp_dc_path():
    """Where the sp_dc cookie is stored. Under SONGMIRROR_DATA_DIR so it lands on
    the same persistent volume as the other secrets (Docker points it at /data)."""
    return os.getenv("SPOTIFY_SP_DC_FILE") or os.path.join(
        os.getenv("SONGMIRROR_DATA_DIR") or "data", "spotify_sp_dc.private")


def _sp_dc(soft=False):
    v = os.getenv("SPOTIFY_SP_DC")
    if v:
        return v.strip()
    path = sp_dc_path()
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
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


def _content_items(playlist):
    """Yield every raw playlist item (paginated) from the web-player read."""
    puri, offset = _puri(playlist), 0
    while True:
        data = _pf("fetchPlaylistContents", {"uri": puri, "offset": offset, "limit": 100})
        page = (data.get("playlistV2") or {}).get("content") or {}
        items = page.get("items") or []
        yield from items
        offset += len(items)
        if not items or offset >= (page.get("totalCount") or 0):
            return


def contents(playlist):
    """[{uid, uri}] for every item — `uid` is the per-item handle remove needs
    (the mutation deletes by item uid, not track uri)."""
    return [{"uid": it.get("uid"), "uri": ((it.get("itemV2") or {}).get("data") or {}).get("uri")}
            for it in _content_items(playlist)]


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

    Fail-over then fail-CLOSED: a 429 rotates to the next pool app; when the last app 429s it
    raises, so an N-way sync read fails closed rather than matching blind. No retry INTO a
    429 on the same app (that's what earns a penalty box). With the DB cache (playlist_tracks'
    known_isrc), steady-state fetches trend to zero."""
    from . import spotify
    want = [i for i in dict.fromkeys(ids) if i and i not in _isrc_cache]
    napps = spotify.isrc_app_count()
    for i in range(0, len(want), 50):
        chunk = want[i:i + 50]
        for app_idx in range(napps):
            r = requests.get(f"{_API}/tracks", params={"ids": ",".join(chunk)},
                             headers={"Authorization": f"Bearer {spotify.app_token(app_idx)}", "User-Agent": _UA},
                             timeout=REQUEST_TIMEOUT)
            if r.status_code == 429 and app_idx < napps - 1:
                continue   # this app is rate-limited — fail over to the next pool app
            r.raise_for_status()   # last-app 429 / other error -> HTTPError -> fail-closed upstream
            for t in (r.json().get("tracks") or []):
                if t:
                    _isrc_cache[t["id"]] = (t.get("external_ids") or {}).get("isrc")
            break
        if i + 50 < len(want):
            polite_sleep(0.5)   # space multi-batch backfills; a single-batch pass doesn't sleep
    return {i: _isrc_cache.get(i) for i in ids}


def playlist_tracks(playlist, require_isrc=False, known_isrc=None):
    """Full track dicts (the shape spotify.playlist_tracks yields) via pathfinder —
    works for private owned playlists the dev-mode official API 403s, and returns []
    for a just-created empty playlist. The pathfinder payload carries no ISRC (confirmed
    absent from the entire web-player surface); with require_isrc (set for N-way sync
    reads) it is backfilled so cross-provider matching stays reliable, and a hard lookup
    failure raises so the sync fails closed instead of matching on name/artist alone.

    known_isrc(ids) -> {id: isrc}, when given, supplies already-known ISRCs (the
    persisted songs-DB cache) so only genuinely-new tracks hit the rate-limited /tracks
    endpoint — the difference between "fetch every track every pass" (which earns a
    penalty box) and "fetch each track once, ever". Transfers pass neither flag — a
    same-provider copy uses the track id directly."""
    out = []
    for it in _content_items(playlist):
        t = (it.get("itemV2") or {}).get("data") or {}
        uri = t.get("uri") or ""
        if not uri.startswith("spotify:track:"):
            continue  # local file / episode / unavailable — excluded like the official read
        artists = [(a.get("profile") or {}).get("name", "") for a in ((t.get("artists") or {}).get("items") or [])]
        out.append({
            "id": uri.rsplit(":", 1)[-1],
            "isrc": None,
            "name": t.get("name", "") or "",
            "artists": [a for a in artists if a] or [""],
            "album": (t.get("albumOfTrack") or {}).get("name"),
            "duration_ms": (t.get("trackDuration") or {}).get("totalMilliseconds"),
            "added_at": (it.get("addedAt") or {}).get("isoString") or "",
        })
    if require_isrc and out:
        ids = [t["id"] for t in out]
        cached = known_isrc(ids) if known_isrc else {}
        fetched = _track_isrcs([i for i in ids if not cached.get(i)])
        for t in out:
            t["isrc"] = cached.get(t["id"]) or fetched.get(t["id"])
    return out


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
