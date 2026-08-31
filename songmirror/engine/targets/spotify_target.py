"""Spotify as a writable mirror peer.

In one-way mode Spotify is just the source and this target isn't built. In
N-way mode it becomes a first-class peer: the same reconcile that edits Apple
and YouTube Music also adds/removes on Spotify. Cookie mode is complete and
needs no developer app; OAuth remains a compatible fallback.
"""

import spotipy

from .. import archive, spotify, spotify_cookie
from ..config import polite_sleep, spotify_write_backend
from ..matching import normalize_text, romanized, score_candidate, track_key
from .base import MirrorTarget, TargetAuthError
from .provider_utils import source_playlist_details


def _uri(track_id):
    return track_id if str(track_id).startswith("spotify:") else f"spotify:track:{track_id}"


class SpotifyTarget(MirrorTarget):
    name = "Spotify"
    tag = "spotify"
    source = "spotify"

    def __init__(self, sp, cache_file, sync_peer=False, songs=None):
        self._sp = sp
        self.cache_file = cache_file
        self._me = None
        # True when built as an N-way reconcile peer (not a one-off transfer).
        self._sync_peer = sync_peer
        # The songs archive (sqlite conn) supplies identities previously proven
        # by another peer. New cookie-only tracks are seeded during the all-peer
        # read instead of being fetched from Spotify's developer API.
        self._songs = songs

    def bind_archive(self, songs):
        self._songs = songs

    def _user(self):
        if self._me is None:
            if spotify_write_backend() == "cookie" or self._sp is None:
                self._me = spotify_cookie.current_user_id()
            else:
                self._me = spotify._retry(lambda: self._sp.current_user(), "current_user")["id"]
        return self._me

    def _write(self, fn, what):
        """Run a mutation; map an auth/scope rejection to the fail-closed path."""
        try:
            return spotify._retry(fn, what)
        except spotipy.SpotifyException as e:
            if e.http_status in (401, 403):
                raise TargetAuthError(
                    f"Spotify rejected {what} ({e.http_status}). N-way mode needs the playlist-modify "
                    "scopes — delete the token cache (data/spotify_token_cache) and re-run the OAuth flow."
                ) from e
            raise

    # -- MirrorTarget ----------------------------------------------------------
    def list_playlists(self):
        if spotify_write_backend() == "cookie" or self._sp is None:
            best = {}
            for playlist in spotify_cookie.library_playlists():
                key = self.playlist_name(playlist).strip().casefold()
                if not key:
                    continue
                rank = (bool(playlist.get("_editable")), playlist.get("snapshot_id") or "")
                if key not in best or rank > best[key][0]:
                    best[key] = (rank, playlist)
            return {key: playlist for key, (_, playlist) in best.items()}
        return spotify.playlists_by_name(self._sp)

    def browse_playlists(self):
        # Un-deduped, with `_owned` — so browse lists (and the inherited find_playlist
        # scans) every playlist, including a followed one that shares a name with an
        # owned one. list_playlists() name-dedupes for the sync engine and would hide it.
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.library_playlists()
        return spotify.all_playlists(self._sp)

    def is_editable(self, playlist):
        if "_editable" in playlist:
            return bool(playlist["_editable"])
        owner = (playlist.get("owner") or {}).get("id")
        return owner is None or owner == self._user()

    def playlist_count(self, playlist):
        return spotify.track_total(playlist)

    def hydrate_playlist_counts(self, playlists):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.hydrate_playlist_counts(playlists)
        return playlists

    def create(self, sp_playlist):
        name, desc = source_playlist_details(sp_playlist)
        if spotify_write_backend() == "cookie":
            pl = spotify_cookie.create(name, public=False, description=desc)
        else:
            pl = self._write(
                lambda: self._sp.user_playlist_create(self._user(), name, public=False, description=desc),
                "create playlist")
        polite_sleep(1.0)
        return pl

    def playlist_tracks(self, playlist):
        # Cookie mode reads the web-player payload. It reuses persisted ISRCs but
        # never backfills cache misses through the developer API; reconcile learns
        # those identities from the other ISRC-bearing peers in the same read phase.
        if spotify_write_backend() == "cookie":
            known = None
            if self._sync_peer and self._songs is not None:
                known = lambda ids: archive.get_isrcs(self._songs, "spotify", ids)  # noqa: E731
            return spotify_cookie.playlist_tracks(
                playlist["id"], require_isrc=False, known_isrc=known)
        return spotify.playlist_tracks(self._sp, playlist["id"])

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "id": str(playlist_id),
            "name": "",
            "description": "",
            "items": {"total": expected_count},
            "_owned": True,
            "_editable": True,
        }

    def playlist_tracks_page(self, playlist, cursor=None):
        if spotify_write_backend() == "cookie":
            return spotify_cookie.playlist_tracks_page(playlist["id"], cursor=cursor)
        return spotify.playlist_tracks_page(self._sp, playlist["id"], cursor=cursor)

    def track_id(self, track):
        return track.get("id")

    def resolve(self, track, cache):
        primary = track["artists"][0] if track["artists"] else ""
        if not f"{track['name']} {primary}".strip():
            return None, None
        key = track_key(track["name"], " ".join(track["artists"]))
        if key in cache["search"]:
            return cache["search"][key], "search"
        best, method = self._search(track, primary)
        cache["search"][key] = best
        cache["dirty"] = True
        polite_sleep(0.3)
        return best, method

    def _search(self, track, primary):
        isrc = track.get("isrc")
        if isrc:  # the hard cross-walk when the originating provider carried an ISRC
            best = self._best(track, self._query(f"isrc:{isrc}"))
            if best:
                return best, "isrc"
        base = f"{track['name']} {primary}".strip()
        queries = [f'track:{track["name"]} artist:{primary}'.strip(), base]
        rom = f"{romanized(track['name'])} {romanized(primary)}".strip()
        if rom and rom != normalize_text(base):
            queries.append(rom)
        for q in queries:
            best = self._best(track, self._query(q))
            if best:
                return best, "search"
        return None, None

    def _query(self, q):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.search_tracks(q, limit=8)
        try:
            res = spotify._retry(lambda: self._sp.search(q=q, type="track", limit=8), "search")
        except spotipy.SpotifyException:
            return []
        return (res.get("tracks") or {}).get("items", [])

    def _best(self, track, items):
        best_id, best_score = None, -1.0
        for it in items:
            arts = [a.get("name", "") for a in it.get("artists", []) if a.get("name")]
            score, ok = score_candidate(track["name"], track["artists"], track["duration_ms"],
                                        it.get("name", ""), ", ".join(arts), it.get("duration_ms"))
            if ok and score > best_score:
                best_id, best_score = it.get("id"), score
        return best_id

    def add(self, playlist, target_ids):
        if spotify_write_backend() == "cookie":
            spotify_cookie.add(playlist["id"], target_ids)  # one at a time, in order (see spotify_cookie.add)
            return
        for tid in target_ids:  # one at a time preserves date-added order
            self._write(lambda t=tid: self._sp.playlist_add_items(playlist["id"], [_uri(t)]), "add")
            polite_sleep(0.3)

    def remove(self, playlist, track):
        tid = self.track_id(track)
        if not tid:
            return
        if spotify_write_backend() == "cookie":
            spotify_cookie.remove(playlist["id"], [tid])
            return
        self._write(lambda: self._sp.playlist_remove_all_occurrences_of_items(playlist["id"], [_uri(tid)]), "remove")
        polite_sleep(0.3)

    def remove_occurrences(self, playlist, positioned):
        if spotify_write_backend() == "cookie":
            spotify_cookie.remove_positions(playlist["id"], [pos for pos, _ in positioned])
            return
        # Position-addressed removal against the read-time snapshot: with the
        # same uri present twice, remove() would drop BOTH copies. All positions
        # are evaluated against the one snapshot, so batches never shift indexes.
        items = [{"uri": _uri(self.track_id(raw)), "positions": [pos]}
                 for pos, raw in positioned if self.track_id(raw)]
        snapshot = playlist.get("snapshot_id")
        for i in range(0, len(items), 100):
            self._write(lambda chunk=items[i:i + 100]: self._sp.playlist_remove_specific_occurrences_of_items(
                playlist["id"], chunk, snapshot_id=snapshot), "remove occurrences")
            polite_sleep(0.3)
