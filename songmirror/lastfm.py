"""Last.fm API client.

Last.fm's documented API has no playlist writes. It exposes listening history: loved tracks, ranked
top tracks per period, and the raw scrobble feed. Those are what this client
reads, and the engine adapter surfaces them as fixed virtual playlists.

Two credential levels, both documented:

* **API key plus username.** Public reads only. No expiry, no refresh.
* **Plus a shared secret and a session key.** Reads the account's private data
  and unlocks the write methods (``track.love`` / ``track.unlove``). The
  session key is obtained once through the browser flow in ``auth_url`` and
  ``get_session``, and then has an infinite lifetime; the user revokes it from
  their Last.fm settings.

Authenticated calls are signed: order every parameter alphabetically by name,
concatenate as ``<name><value>``, append the shared secret, and md5 the result.
``format`` and ``api_sig`` itself are excluded from that base string. Write
methods must be HTTP POST with every parameter in the body.

The ``user.*`` endpoints carry artist and track name strings and no ISRC, so
consumers identify tracks through the engine's fuzzy matching helpers rather
than on catalog identity.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from .engine.config import REQUEST_TIMEOUT, polite_sleep, required_env

API = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth"
USER_AGENT = "SongMirror"

PAGE_LIMIT = 200
POLITE_BASE = 0.25

# Last.fm period token -> the user-facing suffix of its virtual playlist.
TOP_PERIODS = {
    "7day": "7 days",
    "1month": "1 month",
    "3month": "3 months",
    "6month": "6 months",
    "12month": "12 months",
    "overall": "all time",
}

# Last.fm answers HTTP 200 with an error envelope, so status codes alone do not
# classify a failure. 8/11/16/29 are the documented retryable conditions.
# 4/9/10/13/26 mean the credentials or the signature must be fixed before a
# retry can help. Code 6 stays a plain error: on a read it means a bad username,
# but on track.love it means that one track name was rejected.
_RETRY_CODES = {8, 11, 16, 29}
_AUTH_CODES = {4, 9, 10, 13, 26}
_RETRY_STATUS = {429, 500, 502, 503, 504}

# Excluded from the signature base string: `format` is a transport concern and
# `api_sig` is the output.
_UNSIGNED = {"format", "api_sig"}

INVALID_TRACK = 6


class LastfmError(RuntimeError):
    """Last.fm answered with an error envelope or an unusable shape."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class LastfmAuthError(LastfmError):
    """Credentials or signature rejected; configuration must change."""


class LastfmTransient(RuntimeError):
    """Rate limited or a server fault; the same call may succeed later."""


def sign(params, api_secret):
    """The api_sig for one call. Order matters, so this is the only place that
    builds it."""
    base = "".join(f"{key}{params[key]}"
                   for key in sorted(params)
                   if key not in _UNSIGNED and params[key] is not None)
    return hashlib.md5((base + api_secret).encode("utf-8")).hexdigest()


def auth_url(api_key, callback):
    """Where to send the user to approve this application. Last.fm redirects
    back to `callback` with a `token` query parameter, valid 60 minutes and
    usable once."""
    return f"{AUTH_URL}?{urlencode({'api_key': api_key, 'cb': callback})}"


def _payload(response):
    if response.status_code in _RETRY_STATUS:
        raise LastfmTransient(f"Last.fm returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        if not response.ok:
            raise LastfmError(f"Last.fm returned HTTP {response.status_code}") from exc
        raise LastfmError("Last.fm returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise LastfmError("Last.fm returned an unexpected body")
    code = payload.get("error")
    if code:
        detail = f"Last.fm error {code}: {payload.get('message') or ''}".strip()
        if code in _RETRY_CODES:
            raise LastfmTransient(detail)
        if code in _AUTH_CODES:
            raise LastfmAuthError(detail, code)
        raise LastfmError(detail, code)
    if not response.ok:
        raise LastfmError(f"Last.fm returned HTTP {response.status_code}")
    return payload


def get_session(api_key, api_secret, token, session=None):
    """Exchange an approved token for a session key. Returns
    ``(session_key, username)``. The token is consumed by this call."""
    params = {"method": "auth.getSession", "api_key": api_key, "token": token}
    params["api_sig"] = sign(params, api_secret)
    params["format"] = "json"
    try:
        response = (session or requests).get(
            API, params=params, timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        raise LastfmTransient(f"could not reach Last.fm ({exc!r})") from exc
    info = _payload(response).get("session") or {}
    key, name = (info.get("key") or "").strip(), (info.get("name") or "").strip()
    if not (key and name):
        raise LastfmError("Last.fm returned no session key")
    return key, name


def _iso(uts):
    """Last.fm timestamps are string epoch seconds, and absent on ranked rows."""
    if not uts:
        return None
    try:
        return datetime.fromtimestamp(int(uts), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _artist_name(row):
    """getLovedTracks nests the artist as ``name``, getRecentTracks as ``#text``."""
    artist = row.get("artist")
    if isinstance(artist, str):
        return artist
    if isinstance(artist, dict):
        return artist.get("name") or artist.get("#text") or ""
    return ""


def _duration_ms(row):
    """getTopTracks reports whole seconds; the other endpoints omit duration."""
    raw = str(row.get("duration") or "").strip()
    if not raw.isdigit():
        return None
    seconds = int(raw)
    return seconds * 1000 if seconds else None


def _track(row):
    """One normalized row. ``id`` is left to the adapter, which owns matching."""
    return {
        "name": (row.get("name") or "").strip(),
        "artist": _artist_name(row).strip(),
        "mbid": (row.get("mbid") or "").strip(),
        "duration_ms": _duration_ms(row),
        "added_at": _iso((row.get("date") or {}).get("uts")
                         if isinstance(row.get("date"), dict) else None),
    }


class Lastfm:
    """Client for one username. Writes need `api_secret` plus `session_key`."""

    def __init__(self, api_key=None, api_secret=None, user=None, session_key=None,
                 session=None):
        self._key = api_key or required_env("LASTFM_API_KEY")
        self._secret = api_secret or ""
        self._user = user or required_env("LASTFM_USER")
        self._sk = session_key or ""
        self._session = session or requests

    @property
    def user(self):
        return self._user

    @property
    def authenticated(self):
        """Whether signed, account-scoped calls are possible."""
        return bool(self._secret and self._sk)

    def _request(self, method, params, *, post=False):
        query = {"method": method, "api_key": self._key, **params}
        # Signing every call once a session exists is what makes a private
        # profile readable; it is harmless on a public one.
        if self.authenticated:
            query["sk"] = self._sk
            query["api_sig"] = sign(query, self._secret)
        query["format"] = "json"
        try:
            if post:
                response = self._session.post(
                    API, data=query, timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": USER_AGENT})
            else:
                response = self._session.get(
                    API, params=query, timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:
            raise LastfmTransient(f"could not reach Last.fm ({exc!r})") from exc
        return _payload(response)

    def _get(self, method, **params):
        return self._request(method, params)

    def _write(self, method, **params):
        """A write service: authentication required, POST only."""
        if not self.authenticated:
            raise LastfmAuthError(
                "Last.fm writes need a shared secret and a session key; "
                "reconnect the account to authorize it")
        return self._request(method, params, post=True)

    def _paged(self, method, container, **params):
        """Every row across pages. ``container`` is the response envelope key;
        rows live under its ``track`` member."""
        page = 1
        while True:
            payload = self._get(method, user=self._user, limit=PAGE_LIMIT,
                                page=page, **params)
            envelope = payload.get(container) or {}
            rows = envelope.get("track") or []
            # A collection holding exactly one track is not wrapped in a list.
            if isinstance(rows, dict):
                rows = [rows]
            yield from rows
            attrs = envelope.get("@attr") or {}
            try:
                total = int(attrs.get("totalPages") or 1)
            except (TypeError, ValueError):
                total = 1
            if not rows or page >= total:
                return
            page += 1
            polite_sleep(POLITE_BASE)

    def _total(self, method, container, **params):
        """Row count from the envelope, without walking the collection."""
        payload = self._get(method, user=self._user, limit=1, page=1, **params)
        attrs = (payload.get(container) or {}).get("@attr") or {}
        try:
            return int(attrs.get("total"))
        except (TypeError, ValueError):
            return None

    # -- reads ---------------------------------------------------------------

    def loved_tracks(self):
        return [_track(row) for row in self._paged("user.getLovedTracks", "lovedtracks")]

    def top_tracks(self, period):
        if period not in TOP_PERIODS:
            raise LastfmError(f"unknown Last.fm period {period!r}")
        return [_track(row)
                for row in self._paged("user.getTopTracks", "toptracks", period=period)]

    def recent_tracks(self):
        """The scrobble feed, minus the currently-playing row, which has no
        timestamp and disappears on the next request."""
        return [_track(row)
                for row in self._paged("user.getRecentTracks", "recenttracks")
                if not (row.get("@attr") or {}).get("nowplaying")]

    def loved_total(self):
        return self._total("user.getLovedTracks", "lovedtracks")

    def top_total(self, period):
        return self._total("user.getTopTracks", "toptracks", period=period)

    def recent_total(self):
        return self._total("user.getRecentTracks", "recenttracks")

    def display_name(self):
        """The account's real name or username, for the connector's status line."""
        info = self._get("user.getInfo", user=self._user).get("user") or {}
        return (info.get("realname") or "").strip() or (info.get("name") or "").strip()

    def track_info(self, artist, name):
        """Last.fm's canonical spelling of one track as ``(artist, name)``, or
        None when the catalog does not know it. Correcting before a write is
        what stops a near-miss spelling creating a second loved entry."""
        try:
            payload = self._get("track.getInfo", artist=artist, track=name,
                                autocorrect=1)
        except LastfmError as exc:
            if exc.code == INVALID_TRACK:
                return None
            raise
        info = payload.get("track") or {}
        found_name = (info.get("name") or "").strip()
        found_artist = ((info.get("artist") or {}).get("name") or "").strip()
        return (found_artist, found_name) if (found_artist and found_name) else None

    # -- writes --------------------------------------------------------------

    def love(self, artist, name):
        self._write("track.love", artist=artist, track=name)

    def unlove(self, artist, name):
        self._write("track.unlove", artist=artist, track=name)
