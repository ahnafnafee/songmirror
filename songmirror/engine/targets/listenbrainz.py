"""ListenBrainz loved recordings and JSPF playlists: public reads, token-authorized writes."""

import os

from ... import listenbrainz
from ...listenbrainz import ListenBrainz
from ..logs import log_warn
from ..matching import score_candidate
from .base import MirrorTarget, TargetCapabilityError
from .provider_utils import source_playlist_details


def _playlist_track(row):
    identifiers = row.get("identifier") or []
    if isinstance(identifiers, str):
        identifiers = [identifiers]
    mbid = next((value[len(listenbrainz.RECORDING_URI):] for value in identifiers
                 if isinstance(value, str) and value.startswith(listenbrainz.RECORDING_URI)), "")
    try:
        target_id = ListenBrainzTarget.normalize_manual_track_id(f"mbid:{mbid}")
    except ValueError:
        target_id = ""
    if not target_id:
        raise RuntimeError("ListenBrainz returned a playlist track without a recording MBID; sync was stopped.")
    extension = (row.get("extension") or {}).get(listenbrainz.TRACK_EXTENSION) or {}
    duration = row.get("duration")
    name = str(row.get("title") or "").strip()
    artist = str(row.get("creator") or "").strip()
    return {
        "id": target_id, "recording_mbid": target_id.split(":", 1)[1], "recording_msid": None,
        "name": name, "artist": artist,
        "album": str(row.get("album") or "").strip(),
        "duration_ms": duration if isinstance(duration, int) and not isinstance(duration, bool) else None,
        "added_at": str(extension.get("added_at") or ""),
        "_metadata_incomplete": not name or not artist,
    }


class ListenBrainzTarget(MirrorTarget):
    name = "ListenBrainz"
    tag = "listenbrainz"
    source = "listenbrainz"
    favorite_tracks_name = "Loved Recordings"
    favorite_tracks_id = "loved"
    # Every request waits for the shared one-per-second budget, so the engine
    # appends in source order instead of restaging a playlist suffix.
    replay_chronology = None

    def __init__(self, client=None):
        self._api = client or ListenBrainz()
        self.cache_file = self.resolve_cache_path()

    @classmethod
    def resolve_cache_path(cls, opts=None):
        return os.getenv("LISTENBRAINZ_CACHE_FILE", "listenbrainz_resolve_cache.json")

    @classmethod
    def creates_public_playlists(cls):
        return True

    def _playlist(self, jspf):
        identifier = str(jspf.get("identifier") or "")
        playlist_id = identifier.removeprefix(listenbrainz.PLAYLIST_URI).strip("/")
        if not identifier.startswith(listenbrainz.PLAYLIST_URI) or not playlist_id:
            raise RuntimeError("ListenBrainz returned an unidentified playlist; sync was stopped.")
        extension = (jspf.get("extension") or {}).get(listenbrainz.PLAYLIST_EXTENSION) or {}
        user = self._api.user.casefold()
        creator = str(extension.get("creator") or jspf.get("creator") or "").casefold()
        collaborators = {str(name).casefold() for name in extension.get("collaborators") or []}
        public = extension.get("public")
        return {
            "id": playlist_id, "name": str(jspf.get("title") or ""),
            "description": str(jspf.get("annotation") or ""),
            "public": public if isinstance(public, bool) else None,
            "_owned": creator == user, "_editable": creator == user or user in collaborators,
        }

    def browse_playlists(self):
        return [self._playlist(row) for row in self._api.playlists()]

    def list_playlists(self):
        best = {}
        for playlist in self.browse_playlists():
            key = self.playlist_name(playlist).strip().casefold()
            if key not in best or (self.is_editable(playlist) and not self.is_editable(best[key])):
                best[key] = playlist
        return best

    def is_editable(self, playlist):
        return bool(playlist.get("_editable"))

    def _require_editable(self, playlist):
        if not self.is_editable(playlist):
            raise TargetCapabilityError("Only the creator or a collaborator can edit this ListenBrainz playlist.")

    def playlist_public(self, playlist):
        return playlist.get("public")

    def playlist_tracks(self, playlist):
        return [_playlist_track(row) for row in self._api.playlist(playlist["id"]).get("track") or []]

    def create(self, sp_playlist):
        name, description = source_playlist_details(sp_playlist)
        public = self._create_public(sp_playlist)
        playlist_id = self._api.create_playlist(name, description, public)
        return {"id": playlist_id, "name": name, "description": description, "public": public,
                "_owned": True, "_editable": True}

    def add(self, playlist, target_ids):
        self._require_editable(playlist)
        requested = list(target_ids)
        # Reject malformed saved references before writing even the first item.
        ids = [self.normalize_manual_track_id(value) for value in requested]
        written = []
        for original, target_id in zip(requested, ids):
            kind, _, identifier = target_id.partition(":")
            # Playlists accept only recording MBIDs. An MSID-only recording is
            # reported as rejected so it stays visible for a manual match.
            if kind != "mbid":
                continue
            self._api.add_playlist_recording(playlist["id"], identifier)
            written.append(original)
        return written if len(written) != len(requested) else None

    def remove(self, playlist, track):
        rows = self.playlist_tracks(playlist)
        position = next((i for i, row in enumerate(rows) if row["id"] == self.track_id(track)), None)
        if position is not None:
            self.remove_occurrences(playlist, [(position, rows[position])])

    def remove_occurrences(self, playlist, positioned):
        self._require_editable(playlist)
        positioned = list(positioned)
        current = self.playlist_tracks(playlist)
        if any(position < 0 or position >= len(current)
               or current[position]["id"] != self.track_id(row) for position, row in positioned):
            raise RuntimeError("ListenBrainz playlist changed; refresh it before removing tracks.")
        positions = sorted({position for position, _ in positioned}, reverse=True)
        # Descending deletes keep every remaining read-time index valid.
        for position in positions:
            self._api.delete_playlist_items(playlist["id"], position)
        return len(positions)

    def validate_favorite_tracks(self, *, write=False, remove=False):
        if write or remove:
            self._api.validate_token()

    def favorite_tracks(self):
        tracks = self._api.loved_tracks()
        for track in tracks:
            if not track.get("name") or not track.get("artist"):
                log_warn(
                    f"Loved recording {track['id']} has incomplete metadata; "
                    "it remains unresolved and destination removals are held.", tag=self.tag,
                )
        return tracks

    def track_id(self, track):
        return track.get("id")

    def resolve(self, track, cache):
        name = track.get("name") or ""
        artists = track.get("artists") or ([track["artist"]] if track.get("artist") else [])
        artists = [artist for artist in artists if artist.strip()]
        key = self.search_cache_key(name, artists)
        if key in cache["search"]:
            return self._cached_id(key, cache), "search"
        raw = track.get("_raw") or track
        # Recording MBIDs carried by a source are already global identifiers.
        # MSIDs describe ListenBrainz submissions, not another provider's ids.
        for kind in ("mbid", "msid"):
            identifier = raw.get(f"recording_{kind}")
            if identifier:
                try:
                    found = self.normalize_manual_track_id(f"{kind}:{identifier}")
                except ValueError:
                    continue
                if name and artists:
                    cache["search"][key] = found
                    cache["dirty"] = True
                return found, kind
        if not name or not artists:
            return None, "search"
        body = self._api.lookup_recording(" ".join(artists), name, raw.get("album") or "")
        found = None
        if body.get("recording_mbid"):
            candidate_name, candidate_artist = body.get("recording_name"), body.get("artist_credit_name")
            if (not isinstance(candidate_name, str) or not candidate_name.strip()
                    or not isinstance(candidate_artist, str) or not candidate_artist.strip()):
                raise RuntimeError("ListenBrainz returned incomplete recording metadata; matching was stopped.")
            candidate_id = self.normalize_manual_track_id(f"mbid:{body['recording_mbid']}")
            _, acceptable = score_candidate(
                name, artists, track.get("duration_ms"), candidate_name, candidate_artist, None,
            )
            if acceptable:
                found = candidate_id
        cache["search"][key] = found
        cache["dirty"] = True
        return found, "search"

    def add_favorite_tracks(self, target_ids):
        # Reject malformed saved references before writing even the first item.
        ids = [self.normalize_manual_track_id(value) for value in target_ids]
        if any(not value for value in ids):
            raise ValueError("A ListenBrainz recording identifier is required.")
        for target_id in dict.fromkeys(ids):
            self._api.set_feedback(target_id, 1)

    def remove_favorite_track(self, track):
        self._api.set_feedback(self.track_id(track), 0)
