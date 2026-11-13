"""Spotify as a writable mirror peer.

In one-way mode Spotify is just the source and this target isn't built. In
N-way mode it becomes a first-class peer: the same reconcile that edits Apple
and YouTube Music also adds/removes on Spotify. Cookie mode is complete and
needs no developer app; OAuth remains a compatible fallback.
"""

import os

import requests
import spotipy

from .. import archive, spotify, spotify_cookie
from ..config import (
    DEFAULT_SPOTIFY_CACHE_FILE, polite_sleep, spotify_write_backend,
)
from ..matching import normalize_text, romanized, score_candidate, track_key
from ..spotify_ids import track_id as spotify_track_id
from .base import (
    MirrorTarget,
    TargetAuthError,
    TargetDirectoryIncompleteError,
    TargetTransientError,
)
from .provider_utils import source_playlist_details


def _uri(track_id):
    return f"spotify:track:{spotify_track_id(track_id)}"


class SpotifyTarget(MirrorTarget):
    name = "Spotify"
    tag = "spotify"
    source = "spotify"
    favorite_tracks_name = "Liked Songs"
    supports_saved_albums = True

    @property
    def stable_occurrence_ids(self):
        return spotify_write_backend() == "cookie"

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return getattr(opts, "spotify_cache_file", None) or os.getenv(
            "SPOTIFY_CACHE_FILE", DEFAULT_SPOTIFY_CACHE_FILE)

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
            directory = spotify_cookie.library_directory()
            if directory.partial:
                # An incomplete listing must not read as "doesn't exist" and create a duplicate.
                raise TargetDirectoryIncompleteError(
                    "Spotify library read is incomplete - refusing to sync so an "
                    "existing playlist isn't duplicated. Check the warnings above."
                )
            best = {}
            for playlist in directory.playlists:
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

    @classmethod
    def creates_public_playlists(cls):
        # The web-player create call sets only the name.
        return spotify_write_backend() != "cookie"

    @classmethod
    def editable_details(cls):
        # Visibility stays out: the web-player call has no visibility attribute,
        # and the developer API does not reliably make a public playlist private.
        return frozenset({"name", "description"})

    def update_details(self, playlist, changes):
        if spotify_write_backend() == "cookie":
            spotify_cookie.update_details(playlist["id"], **changes)
        else:
            self._write(lambda: self._sp.playlist_change_details(playlist["id"], **changes),
                        "edit playlist details")

    def playlist_public(self, playlist):
        public = playlist.get("public")
        return public if isinstance(public, bool) else None

    def create(self, sp_playlist):
        name, desc = source_playlist_details(sp_playlist)
        public = self._create_public(sp_playlist)
        if spotify_write_backend() == "cookie":
            pl = spotify_cookie.create(name, public=False, description=desc)
        else:
            pl = self._write(
                lambda: self._sp.user_playlist_create(self._user(), name, public=public, description=desc),
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
                known = lambda ids: archive.get_isrcs(  # noqa: E731
                    self._songs, self.archive_source or self.source, ids
                )
            return spotify_cookie.playlist_tracks(
                playlist["id"], require_isrc=False, known_isrc=known)
        return spotify.playlist_tracks(self._sp, playlist["id"])

    @staticmethod
    def _album(data):
        if not data.get("id") or not data.get("name") or not data.get("artists"):
            raise RuntimeError("Spotify saved-album metadata is incomplete")
        return {"id": str(data["id"]), "name": data["name"],
                "artists": [artist["name"] for artist in data["artists"] if artist.get("name")],
                "upc": (data.get("external_ids") or {}).get("upc"),
                "release_date": data.get("release_date") or "",
                "total_tracks": data.get("total_tracks")}

    def validate_saved_albums(self, *, write=False):
        # OAuth's user-library-read/modify scopes are already requested for
        # Liked Songs. Cookie mode uses the web player's native library surface.
        pass

    def saved_albums(self):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return [self._album(album) for album in spotify_cookie.saved_albums()]
        albums, offset = [], 0
        while True:
            page = spotify._retry(lambda: self._sp.current_user_saved_albums(limit=50, offset=offset),
                                  "saved albums")
            if not isinstance(page.get("items"), list) or page.get("total") is None:
                raise RuntimeError("Spotify saved-album response is incomplete")
            items = page["items"]
            albums.extend(self._album(item.get("album") or {}) for item in items)
            offset += len(items)
            if offset >= int(page["total"]):
                return albums
            if not items:
                raise RuntimeError("Spotify saved-album pagination stopped before the library was complete")

    def find_albums(self, album):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return [self._album(item) for item in spotify_cookie.search_albums(album)]
        from ..albums import barcode

        queries = [f"{album['name']} {(album.get('artists') or [''])[0]}"]
        if barcode(album.get("upc")):
            upc = str(album["upc"]).strip()
            queries.insert(0, f"upc:{upc}")
        for query in queries:
            page = spotify._retry(lambda: self._sp.search(q=query, type="album", limit=10), "album search")
            items = (page.get("albums") or {}).get("items")
            if not isinstance(items, list):
                raise RuntimeError("Spotify album search response is incomplete")
            if items:
                # Search returns simplified albums without UPC. Hydrate before
                # comparing editions and known release identifiers.
                return [self._album(spotify._retry(lambda item=item: self._sp.album(item["id"]),
                                                  "album metadata")) for item in items]
        return []

    def add_saved_albums(self, album_ids):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.add_saved_albums(album_ids)
        self._write(lambda: self._sp.current_user_saved_albums_add(list(album_ids)), "save albums")
        polite_sleep(0.3)

    def favorite_tracks(self):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.favorite_tracks()
        return spotify.saved_tracks(self._sp)

    def add_favorite_tracks(self, target_ids):
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.add_favorite_tracks(target_ids)
        for target_id in target_ids:
            self._write(
                lambda tid=target_id: self._sp.current_user_saved_tracks_add([tid]),
                "save liked track",
            )
            polite_sleep(0.3)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if not target_id:
            return
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.remove_favorite_track(target_id)
        self._write(
            lambda: self._sp.current_user_saved_tracks_delete([target_id]),
            "remove liked track",
        )
        polite_sleep(0.3)

    def fetch_playlist(self, playlist_id):
        """A playlist by id even when the account neither owns nor follows it."""
        if spotify_write_backend() == "cookie" or self._sp is None:
            return spotify_cookie.playlist_metadata(str(playlist_id))
        try:
            playlist = spotify._retry(
                lambda: self._sp.playlist(str(playlist_id)), "playlist")
        except spotipy.SpotifyException:
            return None
        return playlist or None

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
        if manual := self.manual_resolution(track, cache):
            return manual
        primary = track["artists"][0] if track["artists"] else ""
        if not f"{track['name']} {primary}".strip():
            return None, None
        key = track_key(track["name"], " ".join(track["artists"]))
        if key in cache["search"]:
            return self._cached_id(key, cache), "search"
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

    def _query(self, q, *, limit=8):
        try:
            if spotify_write_backend() == "cookie" or self._sp is None:
                return spotify_cookie.search_tracks(q, limit=limit)
            res = spotify._retry(
                lambda: self._sp.search(q=q, type="track", limit=limit),
                "search",
            )
        except requests.RequestException as exc:
            raise TargetTransientError(f"Spotify search transport failure: {exc}") from exc
        except spotipy.SpotifyException as e:
            status = e.http_status
            if status in (401, 403):
                raise TargetAuthError(
                    f"Spotify rejected search ({status})."
                ) from e
            if status == 429 or (isinstance(status, int) and status >= 500):
                raise TargetTransientError(
                    f"Spotify search temporary failure ({status})."
                ) from e
            return []
        return (res.get("tracks") or {}).get("items", [])

    def _normalize_search_item(self, item):
        target_id = item.get("id")
        if not target_id:
            return None
        arts = [a.get("name", "") for a in item.get("artists", []) if a.get("name")]
        album = item.get("album") or {}
        images = album.get("images") or item.get("images") or []
        image = ""
        if images and isinstance(images[0], dict):
            image = images[0].get("url") or ""
        elif isinstance(images, list) and images and isinstance(images[0], str):
            image = images[0]
        return {
            "id": str(target_id),
            "name": item.get("name", ""),
            "artist": ", ".join(arts),
            "artists": arts,
            "album": album.get("name") if isinstance(album, dict) else album,
            "duration_ms": item.get("duration_ms"),
            "image": image or None,
            "external_url": f"https://open.spotify.com/track/{target_id}",
            "isrc": ((item.get("external_ids") or {}).get("isrc") if isinstance(item, dict) else None),
        }

    def search_candidates(self, query, *, limit=5):
        query = str(query or "").strip()
        if not query:
            return []
        out = []
        seen = set()
        for item in self._query(query, limit=max(limit, 1)):
            normalized = self._normalize_search_item(item)
            if not normalized or normalized["id"] in seen:
                continue
            seen.add(normalized["id"])
            out.append(normalized)
            if len(out) >= limit:
                break
        return out

    def search_by_isrc(self, isrc):
        isrc = str(isrc or "").strip()
        if not isrc:
            return []
        return self.search_candidates(f"isrc:{isrc}", limit=5)

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
            positioned = list(positioned)
            uids = [raw.get("playlistItemId") for _, raw in positioned]
            if all(uids):
                spotify_cookie.remove_uids(playlist["id"], uids)
            else:
                spotify_cookie.remove_positions(
                    playlist["id"], [pos for pos, _ in positioned],
                    expected_track_ids=[self.track_id(raw) for _, raw in positioned],
                )
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

    def remove_occurrence(self, playlist, track_id, occurrence_id):
        if spotify_write_backend() == "cookie":
            spotify_cookie.remove_uids(playlist["id"], [occurrence_id])
            return
        super().remove_occurrence(playlist, track_id, occurrence_id)
