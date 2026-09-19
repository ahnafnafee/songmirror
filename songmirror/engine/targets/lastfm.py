"""Last.fm as a history source with a writable loved-tracks collection.

Last.fm's API has no playlist methods, so this adapter never creates or edits one:
`supports_playlists` is False and the playlist write methods raise
TargetCapabilityError, which the playlist and transfer layers already turn into
a user-facing message.

What it does expose:

* **Seven read-only virtual playlists** for the ranked top-tracks periods and
  the recent scrobble feed.
* **Loved Tracks as the native favorites collection**, the same shape every
  other provider uses for its liked tracks. With an authorized session it is
  writable, so another service's liked tracks can sync into Last.fm loves.

Track ids are ``<artist>␟<name>`` rather than the sometimes-present mbid,
because ``track.love`` and ``track.unlove`` address a track by artist and title
and an id has to round-trip to those. Canonical spelling drift would therefore
re-key an id, but the engine's no-ISRC path diffs on the normalized
``track_key``, which absorbs case and punctuation changes.
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
from ..config import polite_sleep
from ..logs import log_warn
from .base import (
    MirrorTarget,
    TargetAuthError,
    TargetCapabilityError,
    TargetTransientError,
)

RECENT_ID = "recent"
TOP_PREFIX = "top:"
#  U+241F SYMBOL FOR UNIT SEPARATOR: printable, and never part of a track title.
ID_SEP = "␟"

_NO_PLAYLISTS = "Last.fm playlist sync is not supported; it cannot receive playlist changes"
_NEEDS_AUTH = ("loving tracks on Last.fm needs the shared secret and an "
               "authorized session; reconnect the Last.fm account")


def compose_id(artist, name):
    return f"{artist}{ID_SEP}{name}"


def split_id(value):
    artist, _, name = str(value or "").partition(ID_SEP)
    return (artist.strip(), name.strip()) if name else ("", "")


class LastfmTarget(MirrorTarget):
    name = "Last.fm"
    tag = "lastfm"
    source = "lastfm"
    favorite_tracks_name = "Loved Tracks"
    favorite_tracks_id = "loved"
    no_playlists_note = _NO_PLAYLISTS
    # No playlist writes, which keeps this provider out of playlist mirroring
    # and out of N-way while leaving its favorites collection usable.
    supports_playlists = False
    # No positional insert and no playlist writes, so date-order repair cannot
    # be performed here; the engine appends in source order instead.
    replay_chronology = None

    def __init__(self, client=None):
        self._api = client or Lastfm(
            api_secret=os.getenv("LASTFM_API_SECRET") or "",
            session_key=os.getenv("LASTFM_SESSION_KEY") or "",
        )
        self.cache_file = self.resolve_cache_path()

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("LASTFM_CACHE_FILE", "lastfm_resolve_cache.json")

    # -- collections ----------------------------------------------------------

    @staticmethod
    def _rows():
        rows = [{"id": RECENT_ID, "name": "Recent Scrobbles"}]
        rows.extend({"id": f"{TOP_PREFIX}{period}", "name": f"Top Tracks ({label})"}
                    for period, label in TOP_PERIODS.items())
        for row in rows:
            row.setdefault("description", "")
            row.setdefault("images", [])
        return rows

    def list_playlists(self):
        """The read-only virtual collections. Loved Tracks is deliberately
        absent: it is the native favorites resource, as on every other
        provider, so it is not also offered as a playlist."""
        return {row["name"].casefold(): row for row in self._rows()}

    def is_editable(self, playlist):
        return False

    def hydrate_playlist_counts(self, playlists):
        """Browse-only enrichment: the listing is synthetic, so each count costs
        one ``limit=1`` request. Best-effort."""
        for playlist in playlists:
            try:
                playlist["count"] = self._count(str(self.playlist_id(playlist) or ""))
            except (LastfmError, LastfmTransient):
                playlist.setdefault("count", None)
        return playlists

    def _count(self, playlist_id):
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
        return self._identified(self._read(str(self.playlist_id(playlist) or "")))

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

    # -- resolving a foreign track to a Last.fm one ---------------------------

    def resolve(self, track, cache):
        """Last.fm carries no ISRC, so this is always a name lookup. Asking
        track.getInfo for the canonical spelling first is what stops a
        near-miss title creating a second loved entry."""
        name = track.get("name") or ""
        artists = track.get("artists") or []
        primary = track.get("artist") or (artists[0] if artists else "")
        key = self.search_cache_key(name, artists or ([primary] if primary else []))
        if key in cache["search"]:
            return cache["search"][key] or None, "search"
        if not (name and primary):
            return None, "search"
        with _translated():
            corrected = self._api.track_info(primary, name)
        found = compose_id(*corrected) if corrected else None
        cache["search"][key] = found
        cache["dirty"] = True
        polite_sleep(0.25)
        return found, "search"

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

    # -- writes Last.fm cannot accept -----------------------------------------

    def create(self, sp_playlist):
        raise TargetCapabilityError(_NO_PLAYLISTS)

    def add(self, playlist, target_ids):
        raise TargetCapabilityError(_NO_PLAYLISTS)

    def remove(self, playlist, track):
        raise TargetCapabilityError(_NO_PLAYLISTS)


class _translated:
    """Map client failures onto the engine's error vocabulary."""

    def __enter__(self):
        return self

    def __exit__(self, kind, value, tb):
        if value is None:
            return False
        if isinstance(value, LastfmTransient):
            raise TargetTransientError(str(value)) from value
        if isinstance(value, LastfmAuthError):
            raise TargetAuthError(str(value)) from value
        return False
