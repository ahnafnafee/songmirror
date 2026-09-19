"""Last.fm: history source, loved tracks, and website-backed playlists.

Three surfaces, two of them on the documented API and one not.

* **Read-only history** (the API): ranked top tracks per period and the recent
  scrobble feed, as fixed virtual collections.
* **Loved Tracks** (the API): the native favorites collection, writable once the
  account is authorized.
* **Playlists** (the website): only present when a signed-in web session is
  configured, because Last.fm's API has no playlist methods at all. See
  `lastfm_web` for the endpoints and for why the track names it stores are the
  ones its own search supplied rather than the recording's.

Track ids are ``<artist>␟<name>``. ``track.love`` addresses a track by artist
and title, and a playlist entry keeps whatever strings its catalogue row
carried, so in both cases an id has to round-trip to that pair rather than to a
catalogue identifier, of which Last.fm has none.
"""

import os

from ...lastfm import (
    INVALID_TRACK,
    TOP_PERIODS,
    Lastfm,
    LastfmAuthError,
    LastfmError,
    LastfmTransient,
)
from ...lastfm_web import LastfmWeb, LastfmWebAuthError, credentials_from
from ..config import polite_sleep
from ..logs import log_warn
from ..matching import track_artist, track_key
from .base import (
    MirrorTarget,
    TargetAuthError,
    TargetCapabilityError,
    TargetTransientError,
)

RECENT_ID = "recent"
TOP_PREFIX = "top:"
WEB_PREFIX = "web:"
#  U+241F SYMBOL FOR UNIT SEPARATOR: printable, and never part of a track title.
ID_SEP = "␟"

_NO_PLAYLISTS = ("Last.fm's API has no playlists. Paste a signed-in last.fm web "
                 "session on the Accounts page to sync playlists to it.")
_NEEDS_AUTH = ("loving tracks on Last.fm needs the shared secret and an "
               "authorized session; reconnect the Last.fm account")


def compose_id(artist, name):
    return f"{artist}{ID_SEP}{name}"


def split_id(value):
    artist, _, name = str(value or "").partition(ID_SEP)
    return (artist.strip(), name.strip()) if name else ("", "")


def web_credentials():
    return credentials_from(os.getenv("LASTFM_WEB_SESSION") or "")


class LastfmTarget(MirrorTarget):
    name = "Last.fm"
    tag = "lastfm"
    source = "lastfm"
    favorite_tracks_name = "Loved Tracks"
    favorite_tracks_id = "loved"
    # No positional insert, so date-order repair cannot be performed here.
    replay_chronology = None

    def __init__(self, client=None, web=None):
        self._api = client or Lastfm(
            api_secret=os.getenv("LASTFM_API_SECRET") or "",
            session_key=os.getenv("LASTFM_SESSION_KEY") or "",
        )
        self._web = web if web is not None else self._build_web()
        # search-catalogue is addressed per playlist even though its results are
        # global, so resolve borrows whichever playlist was last seen.
        self._search_scope = None
        self.cache_file = self.resolve_cache_path()

    def _build_web(self):
        credentials = web_credentials()
        if not credentials:
            return None
        try:
            return LastfmWeb(credentials, self._api.user)
        except LastfmWebAuthError as exc:
            log_warn(f"last.fm web session unusable: {exc}", tag="lastfm")
            return None

    @classmethod
    def supports_playlists(cls):
        """Evaluated, not read: Last.fm only has playlists when a web session is
        configured, so this depends on settings rather than on the class."""
        return bool(web_credentials())

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("LASTFM_CACHE_FILE", "lastfm_resolve_cache.json")

    # -- collections ----------------------------------------------------------

    @staticmethod
    def _history_rows():
        rows = [{"id": RECENT_ID, "name": "Recent Scrobbles"}]
        rows.extend({"id": f"{TOP_PREFIX}{period}", "name": f"Top Tracks ({label})"}
                    for period, label in TOP_PERIODS.items())
        for row in rows:
            row.setdefault("description", "")
            row.setdefault("images", [])
        return rows

    def list_playlists(self):
        """The read-only history collections, plus the account's real playlists
        when a web session is configured. Loved Tracks is deliberately absent:
        it is the native favorites resource, as on every other provider."""
        rows = self._history_rows()
        for row in self._web_playlists():
            rows.append(row)
        return {row["name"].casefold(): row for row in rows}

    def _web_playlists(self):
        if self._web is None:
            return []
        try:
            found = self._web.list_playlists()
        except LastfmWebAuthError as exc:
            raise TargetAuthError(str(exc)) from exc
        if found and self._search_scope is None:
            self._search_scope = found[0]["id"]
        return [{"id": f"{WEB_PREFIX}{row['id']}", "name": row["name"],
                 "description": "", "images": [], "_web": True} for row in found]

    @staticmethod
    def _web_id(playlist_id):
        value = str(playlist_id or "")
        return value[len(WEB_PREFIX):] if value.startswith(WEB_PREFIX) else None

    def is_editable(self, playlist):
        return self._web_id(self.playlist_id(playlist)) is not None

    def hydrate_playlist_counts(self, playlists):
        """Browse-only enrichment. The history listing is synthetic, so each
        count costs one ``limit=1`` request. Best-effort."""
        for playlist in playlists:
            try:
                playlist["count"] = self._count(str(self.playlist_id(playlist) or ""))
            except (LastfmError, LastfmTransient, LastfmWebAuthError):
                playlist.setdefault("count", None)
        return playlists

    def _count(self, playlist_id):
        web_id = self._web_id(playlist_id)
        if web_id is not None:
            return len(self._web.entries(web_id)) if self._web else None
        if playlist_id == self.favorite_tracks_id:
            return self._api.loved_total()
        if playlist_id == RECENT_ID:
            return self._api.recent_total()
        period = self._period(playlist_id)
        return self._api.top_total(period) if period else None

    @staticmethod
    def _period(playlist_id):
        if not playlist_id.startswith(TOP_PREFIX):
            return None
        period = playlist_id[len(TOP_PREFIX):]
        return period if period in TOP_PERIODS else None

    def playlist_count(self, playlist):
        return playlist.get("count")

    # -- reads ----------------------------------------------------------------

    def playlist_tracks(self, playlist):
        playlist_id = str(self.playlist_id(playlist) or "")
        web_id = self._web_id(playlist_id)
        if web_id is not None:
            self._search_scope = web_id
            with _translated():
                return [
                    {"id": compose_id(row["artist"], row["name"]),
                     "name": row["name"], "artist": row["artist"],
                     "entry_id": row["entry_id"], "added_at": None}
                    for row in self._web.entries(web_id)
                ]
        return self._identified(self._read(playlist_id))

    def favorite_tracks(self):
        return self._identified(self._read(self.favorite_tracks_id))

    def _identified(self, rows):
        return [{**row, "id": compose_id(row.get("artist") or "", row.get("name") or "")}
                for row in rows]

    def _read(self, playlist_id):
        with _translated():
            if playlist_id == self.favorite_tracks_id:
                return self._api.loved_tracks()
            if playlist_id == RECENT_ID:
                return self._api.recent_tracks()
            period = self._period(playlist_id)
            if period:
                return self._api.top_tracks(period)
        raise TargetCapabilityError(
            f"Last.fm has no collection named {playlist_id!r}")

    def track_id(self, track):
        existing = str(track.get("id") or "")
        if ID_SEP in existing:
            return existing
        artist, name = track.get("artist") or "", track.get("name") or ""
        return compose_id(artist, name) if (artist and name) else existing

    def occurrence_id(self, track):
        """A playlist entry's own id, which is what a removal addresses."""
        entry = track.get("entry_id")
        return str(entry) if entry not in (None, "") else None

    # -- resolving a foreign track --------------------------------------------

    def resolve(self, track, cache):
        """Last.fm carries no ISRC, so this is always a name lookup.

        With a web session the catalogue search is authoritative, because an
        entry has to be added with the exact strings one of its rows supplied.
        Without one, only loved tracks are writable, and track.getInfo's
        canonical spelling is what stops a near-miss creating a second entry.
        """
        name = track.get("name") or ""
        artists = track.get("artists") or []
        primary = track.get("artist") or (artists[0] if artists else "")
        key = self.search_cache_key(name, artists or ([primary] if primary else []))
        if key in cache["search"]:
            return cache["search"][key] or None, "search"
        if not (name and primary):
            return None, "search"
        found = (self._resolve_web(name, primary) if self._web is not None
                 else self._resolve_api(name, primary))
        cache["search"][key] = found
        cache["dirty"] = True
        polite_sleep(0.25)
        return found, "search"

    def _resolve_api(self, name, primary):
        with _translated():
            corrected = self._api.track_info(primary, name)
        return compose_id(*corrected) if corrected else None

    def _resolve_web(self, name, primary):
        scope = self._search_scope or self._any_playlist_id()
        if scope is None:
            # Nothing to scope the catalogue search to yet; the playlist the
            # engine is about to write will provide one on the next pass.
            return None
        with _translated():
            rows = self._web.search(f"{primary} {name}", scope)
        best = _best_row(rows, name, primary)
        return compose_id(best["artist"], best["track"]) if best else None

    def _any_playlist_id(self):
        rows = self._web_playlists()
        return self._web_id(rows[0]["id"]) if rows else None

    # -- playlist writes ------------------------------------------------------

    def create(self, sp_playlist):
        if self._web is None:
            raise TargetCapabilityError(_NO_PLAYLISTS)
        name = sp_playlist.get("name") or "New Playlist"
        with _translated():
            created = self._web.create(name, sp_playlist.get("description") or "")
        self._search_scope = created["id"]
        return {"id": f"{WEB_PREFIX}{created['id']}", "name": created["name"],
                "description": "", "images": [], "_web": True}

    def add(self, playlist, target_ids):
        web_id = self._require_web(playlist)
        for target_id in target_ids:
            artist, name = split_id(target_id)
            if not (artist and name):
                log_warn(f"skipped an unaddressable track id {target_id!r}", tag=self.tag)
                continue
            with _translated():
                self._web.add(web_id, name, artist)
            polite_sleep(0.3)

    def remove(self, playlist, track):
        web_id = self._require_web(playlist)
        entry_id = self.occurrence_id(track)
        if not entry_id:
            log_warn("skipped a removal with no entry id", tag=self.tag)
            return
        with _translated():
            self._web.remove(web_id, entry_id)

    def remove_occurrence(self, playlist, track_id, occurrence_id):
        self.remove(playlist, {"id": track_id, "entry_id": occurrence_id})

    def _require_web(self, playlist):
        web_id = self._web_id(self.playlist_id(playlist))
        if self._web is None or web_id is None:
            raise TargetCapabilityError(_NO_PLAYLISTS)
        return web_id

    # -- favorites writes -----------------------------------------------------

    def validate_favorite_tracks(self, *, write=False, remove=False):
        if (write or remove) and not self._api.authenticated:
            raise TargetCapabilityError(_NEEDS_AUTH)

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            artist, name = split_id(target_id)
            if not (artist and name):
                log_warn(f"skipped an unaddressable track id {target_id!r}", tag=self.tag)
                continue
            self._love(self._api.love, artist, name, "love")
            polite_sleep(0.25)

    def remove_favorite_track(self, track):
        artist, name = split_id(self.track_id(track))
        if not (artist and name):
            return
        self._love(self._api.unlove, artist, name, "unlove")

    def _love(self, action, artist, name, verb):
        """One write, with a rejected title skipped rather than failing the
        whole collection."""
        try:
            action(artist, name)
        except LastfmTransient as exc:
            raise TargetTransientError(str(exc)) from exc
        except LastfmAuthError as exc:
            raise TargetAuthError(str(exc)) from exc
        except LastfmError as exc:
            if exc.code == INVALID_TRACK:
                log_warn(f"Last.fm rejected '{artist} - {name}' on {verb}", tag=self.tag)
                return
            raise


def _best_row(rows, name, artist):
    """The catalogue row closest to the wanted recording.

    Its search returns video-ish titles, so the row whose own strings score
    best against the source track is chosen rather than simply the first.
    """
    wanted = track_key(name, artist)
    scored = []
    for row in rows:
        candidate = track_key(row["track"], row["artist"])
        exact = candidate == wanted
        contains = name.casefold() in row["track"].casefold()
        artist_ok = artist.casefold() in f"{row['artist']} {row['track']}".casefold()
        scored.append(((exact, contains and artist_ok, contains, artist_ok), row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    for score, row in scored:
        if any(score):
            return row
    return rows[0] if rows else None


class _translated:
    """Map client failures onto the engine's error vocabulary."""

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        if value is None:
            return False
        if isinstance(value, LastfmTransient):
            raise TargetTransientError(str(value)) from value
        if isinstance(value, (LastfmAuthError, LastfmWebAuthError)):
            raise TargetAuthError(str(value)) from value
        return False
