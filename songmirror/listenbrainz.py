"""ListenBrainz loved recordings, playlists, metadata lookup, and authorized writes."""

import math
import os
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from .engine.config import REQUEST_TIMEOUT, required_env

API = "https://api.listenbrainz.org"
WEBSITE = "https://listenbrainz.org"
PAGE_SIZE = 100
# JSPF names, as https://listenbrainz.readthedocs.io/en/latest/users/api/playlist.html defines them.
PLAYLIST_URI = "https://listenbrainz.org/playlist/"
PLAYLIST_EXTENSION = "https://musicbrainz.org/doc/jspf#playlist"
TRACK_EXTENSION = "https://musicbrainz.org/doc/jspf#track"
RECORDING_URI = "https://musicbrainz.org/recording/"
USER_AGENT = "SongMirror/0.1.0 (https://github.com/ahnafnafee/songmirror/issues)"


def _retry_delay(headers):
    delays = []
    for key in ("Retry-After", "X-RateLimit-Reset-In"):
        value = headers.get(key)
        try:
            delay = float(value)
        except (TypeError, ValueError):
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                continue
        if math.isfinite(delay) and delay > 0:
            delays.append(delay)
    return max(delays, default=30)


class _RequestGate:
    """Share the API's one-request-per-second budget across account profiles."""

    def __init__(self, *, clock=None, sleep=None):
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._next = self._retry_at = 0

    def request(self, send, url, **kwargs):
        from .engine.targets.base import TargetTransientError

        with self._lock:
            now = self._clock()
            if self._retry_at > now:
                delay = math.ceil(self._retry_at - now)
                raise TargetTransientError(
                    f"ListenBrainz rate limit reached; retry in {delay} seconds.", retry_after=delay,
                )
            if self._next > now:
                self._sleep(self._next - now)
            self._next = self._clock() + 1
            response = send(url, **kwargs)
            headers = getattr(response, "headers", {})
            if response.status_code == 429 or str(headers.get("X-RateLimit-Remaining")) == "0":
                delay = _retry_delay(headers)
                self._retry_at = self._clock() + delay
                if response.status_code == 429:
                    raise TargetTransientError(
                        f"ListenBrainz rate limit reached; retry in {math.ceil(delay)} seconds.",
                        retry_after=delay,
                    )
            return response


_REQUESTS = _RequestGate()


class ListenBrainz:
    def __init__(self, user=None, session=None, *, token=None):
        self.user = user or required_env("LISTENBRAINZ_USER")
        self._session = session or requests
        self.token = (os.getenv("LISTENBRAINZ_TOKEN", "") if token is None else token).strip()
        self._validated = False

    def _authorized_json(self, method, path, *, token_optional=False, **kwargs):
        """JSON API call. A token-optional read still sends a configured token,
        which makes the profile's private playlists visible."""
        from .engine.targets.base import TargetAuthError, TargetCapabilityError, TargetTransientError

        if not self.token and not token_optional:
            raise TargetCapabilityError(
                "Add a ListenBrainz user token to receive loved recordings and playlist changes."
            )
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        try:
            response = _REQUESTS.request(
                getattr(self._session, method), f"{API}{path}", headers=headers,
                timeout=REQUEST_TIMEOUT, allow_redirects=False, **kwargs,
            )
        except requests.RequestException as exc:
            raise TargetTransientError("Could not reach ListenBrainz; retry later.") from exc
        if response.status_code in {401, 403}:
            self._validated = False
            raise TargetAuthError("ListenBrainz rejected the user token. Reconnect the account.")
        if response.status_code >= 500 or response.status_code == 429:
            raise TargetTransientError(f"ListenBrainz returned HTTP {response.status_code}; retry later.")
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"ListenBrainz returned HTTP {response.status_code}; the operation was not confirmed.")
        try:
            if "text/html" in getattr(response, "headers", {}).get("Content-Type", "").lower():
                raise ValueError
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise TargetTransientError(
                "ListenBrainz returned a web page or invalid data; the operation was not confirmed. Try again later."
            ) from exc
        return body

    def validate_token(self):
        """Bind writes to the configured profile, rather than any valid token."""
        from .engine.targets.base import TargetAuthError, TargetTransientError

        if self._validated:
            return
        body = self._authorized_json("get", "/1/validate-token")
        if body.get("valid") is False:
            raise TargetAuthError("ListenBrainz user token is invalid. Reconnect the account.")
        user = body.get("user_name")
        if body.get("valid") is not True or not isinstance(user, str) or not user.strip():
            raise TargetTransientError("ListenBrainz did not confirm the token's username. Try again later.")
        if user.casefold() != self.user.casefold():
            raise TargetAuthError("ListenBrainz token belongs to a different username. Use that profile's own token.")
        self._validated = True

    def lookup_recording(self, artist, name, album=""):
        from .engine.targets.base import TargetTransientError

        self.validate_token()
        params = {"artist_name": artist, "recording_name": name}
        if album:
            params["release_name"] = album
        body = self._authorized_json("get", "/1/metadata/lookup/", params=params)
        # The API returns {} for a completed lookup with no match. An error
        # envelope or partial response must not become a cached negative match.
        if body and not body.get("recording_mbid"):
            raise TargetTransientError("ListenBrainz returned incomplete recording data; matching was stopped.")
        return body

    def set_feedback(self, target_id, score):
        from .engine.targets.base import TargetTransientError
        from .engine.track_references import normalize_track_reference

        # Validate before any network operation, including token validation.
        target_id = normalize_track_reference("listenbrainz", target_id)
        if not target_id or score not in {0, 1}:
            raise ValueError("ListenBrainz feedback needs a recording identifier and a love or removal score.")
        kind, identifier = target_id.split(":", 1)
        self.validate_token()
        body = self._authorized_json("post", "/1/feedback/recording-feedback",
                                     json={f"recording_{kind}": identifier, "score": score})
        if body.get("status") != "ok":
            raise TargetTransientError("ListenBrainz did not confirm the feedback change. Try again later.")

    def _playlist_write(self, path, body):
        from .engine.targets.base import TargetTransientError

        self.validate_token()
        result = self._authorized_json("post", path, json=body)
        if result.get("status") != "ok":
            raise TargetTransientError("ListenBrainz did not confirm the playlist change. Try again later.")
        return result

    def playlists(self):
        """Every JSPF playlist the profile created, private ones included with its token."""
        offset, rows = 0, []
        while True:
            body = self._authorized_json(
                "get", f"/1/user/{quote(self.user, safe='')}/playlists", token_optional=True,
                params={"count": PAGE_SIZE, "offset": offset},
            )
            page, total = body.get("playlists"), body.get("playlist_count")
            if (not isinstance(page, list) or not isinstance(total, int) or isinstance(total, bool)
                    or not all(isinstance(row, dict) and isinstance(row.get("playlist"), dict) for row in page)
                    or offset + len(page) > total or (not page and offset < total)):
                raise RuntimeError("ListenBrainz returned an incomplete playlist list; sync was stopped.")
            rows.extend(row["playlist"] for row in page)
            offset += len(page)
            if offset >= total:
                return rows

    def playlist(self, mbid):
        body = self._authorized_json("get", f"/1/playlist/{quote(str(mbid), safe='')}", token_optional=True)
        playlist = body.get("playlist")
        if not isinstance(playlist, dict) or not isinstance(playlist.get("track", []), list):
            raise RuntimeError("ListenBrainz returned an incomplete playlist; sync was stopped.")
        return playlist

    def create_playlist(self, title, annotation="", public=False):
        from .engine.targets.base import TargetTransientError

        if not str(title or "").strip():
            raise ValueError("A ListenBrainz playlist needs a title.")
        playlist = {"title": title, "track": [], "extension": {PLAYLIST_EXTENSION: {"public": bool(public)}}}
        if annotation:
            playlist["annotation"] = annotation
        mbid = self._playlist_write("/1/playlist/create", {"playlist": playlist}).get("playlist_mbid")
        if not isinstance(mbid, str) or not mbid:
            raise TargetTransientError("ListenBrainz did not return the new playlist's id. Try again later.")
        return mbid

    def add_playlist_recording(self, mbid, recording_mbid):
        self._playlist_write(f"/1/playlist/{quote(str(mbid), safe='')}/item/add",
                             {"playlist": {"track": [{"identifier": [RECORDING_URI + recording_mbid]}]}})

    def delete_playlist_items(self, mbid, index, count=1):
        self._playlist_write(f"/1/playlist/{quote(str(mbid), safe='')}/item/delete",
                             {"index": index, "count": count})

    def feedback_page(self, offset=0, count=PAGE_SIZE):
        from .engine.targets.base import TargetTransientError

        try:
            response = _REQUESTS.request(
                self._session.get,
                f"{API}/1/feedback/user/{quote(self.user, safe='')}/get-feedback",
                params={"score": 1, "metadata": "true", "offset": offset, "count": count},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise TargetTransientError("Could not reach ListenBrainz; retry later.") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise TargetTransientError(f"ListenBrainz returned HTTP {response.status_code}; retry later.")
        if response.status_code == 404:
            raise RuntimeError("ListenBrainz profile was not found. Check the username.")
        if not response.ok:
            raise RuntimeError(f"ListenBrainz returned HTTP {response.status_code}.")
        content_type = getattr(response, "headers", {}).get("Content-Type", "")
        if "text/html" in content_type.lower():
            return self._website_feedback(offset, count)
        try:
            body = response.json()
            if not isinstance(body, dict) or not isinstance(body.get("feedback"), list):
                raise ValueError
            total = int(body["total_count"])
            if total < 0 or int(body["offset"]) != offset:
                raise ValueError
            if not all(isinstance(row, dict) for row in body["feedback"]):
                raise ValueError
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("ListenBrainz returned incomplete feedback; sync was stopped.") from exc
        return body["feedback"], total

    def _website_feedback(self, offset, count):
        """Read the public Taste page's JSON, only when it contains all loves.

        This website route always returns its first 25 entries, regardless of
        pagination arguments. Its count must prove completeness before any
        slice can stand in for an API page.
        """
        from .engine.targets.base import TargetTransientError

        try:
            response = _REQUESTS.request(
                self._session.post,
                f"{WEBSITE}/user/{quote(self.user, safe='')}/taste/",
                params={"score": 1},
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise TargetTransientError("Could not reach the ListenBrainz website; retry later.") from exc
        if response.status_code == 404:
            raise RuntimeError("ListenBrainz profile was not found. Check the username.")
        content_type = getattr(response, "headers", {}).get("Content-Type", "")
        if not response.ok or 300 <= response.status_code < 400 or "text/html" in content_type.lower():
            raise TargetTransientError(
                "ListenBrainz returned a web page or error instead of recording data. Try again later."
            )
        try:
            body = response.json()
            rows, total = body["feedback"], int(body["feedback_count"])
            user = body["user"]["name"]
            if (not isinstance(rows, list) or total < 0 or not isinstance(user, str)
                    or user.casefold() != self.user.casefold()
                    or not all(isinstance(row, dict) and row.get("score") == 1 for row in rows)):
                raise ValueError
        except (ValueError, KeyError, TypeError) as exc:
            raise TargetTransientError("ListenBrainz returned incomplete website data; sync was stopped.") from exc
        if len(rows) != total:
            raise TargetTransientError(
                f"ListenBrainz's website returned {len(rows)} of {total} loved recordings. "
                "The API is unavailable, so sync was stopped to avoid using a partial collection. Try again later."
            )
        return rows[offset:offset + count], total

    def loved_tracks(self):
        offset, tracks, seen, expected_total = 0, [], set(), None
        while True:
            rows, total = self.feedback_page(offset)
            if expected_total is not None and total != expected_total:
                raise RuntimeError("ListenBrainz loves changed during pagination; retry the sync.")
            expected_total = total
            if offset + len(rows) > total:
                raise RuntimeError("ListenBrainz returned an inconsistent feedback count.")
            if not rows and offset < total:
                raise RuntimeError("ListenBrainz feedback ended before all loved recordings were read.")
            for row in rows:
                if row.get("score") != 1:
                    raise RuntimeError("ListenBrainz returned feedback outside the loved collection.")
                track = _track(row)
                if track["id"] not in seen:
                    seen.add(track["id"])
                    tracks.append(track)
            offset += len(rows)
            if offset >= total:
                return tracks


def _track(row):
    metadata = row.get("track_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    mbid, msid = row.get("recording_mbid"), row.get("recording_msid")
    if not (mbid or msid):
        raise RuntimeError("ListenBrainz returned a loved recording without an MBID or MSID.")
    try:
        added_at = datetime.fromtimestamp(float(row["created"]), timezone.utc).isoformat()
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        added_at = ""
    return {
        "id": f"mbid:{mbid}" if mbid else f"msid:{msid}",
        "recording_mbid": mbid, "recording_msid": msid,
        "name": str(metadata.get("track_name") or "").strip(),
        "artist": str(metadata.get("artist_name") or "").strip(),
        "album": str(metadata.get("release_name") or "").strip(),
        "duration_ms": None, "added_at": added_at,
        "_metadata_incomplete": not str(metadata.get("track_name") or "").strip()
                                or not str(metadata.get("artist_name") or "").strip(),
    }
