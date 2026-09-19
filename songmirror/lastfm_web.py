"""Last.fm playlists through the signed-in website.

Last.fm's documented API has no playlist methods at all: the Playlists API is
marked DEPRECATED and only ever offered ``playlist.fetch``. The website does
have playlists, so this module drives that instead, from a pasted signed-in
request the same way the Qobuz and TIDAL adapters do.

Two things to know before relying on it.

It is HTML, not an API. Every call parses a server-rendered Django page, so a
template change breaks it with no deprecation notice, and the session cookie
must be re-captured when it lapses. Nothing else in the engine depends on this
module: the Last.fm API reads and loved-track writes keep working when it
breaks.

The catalogue behind it is video search, not Last.fm's music catalogue. A
search for POWER by Kanye West offers rows like ``Kanye West - Power``,
``01 Kanye West - Power`` and one credited to ``KanyeWestVEVO``, so a track
added here keeps the title and artist strings of whichever row was chosen,
rather than the recording's own name. `add` therefore stores exactly the
strings a row supplied, and `resolve` returns them as the track id, so a later
read matches what was written instead of re-adding it every pass.

The traced endpoints:

===========================  ========================================
list playlists               GET  /user/<u>/playlists
create (empty, untitled)     POST /user/<u>/playlists
rename / describe            POST /user/<u>/playlists/<id>
delete playlist              POST /user/<u>/playlists/<id>  action=delete
list entries                 GET  /user/<u>/playlists/<id>
search the catalogue         GET  /user/<u>/playlists/<id>/search-catalogue
add an entry                 POST /user/<u>/playlists/<id>/entries
remove an entry              POST /user/<u>/playlists/<id>/entries/<entry>
===========================  ========================================
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import unquote, urlsplit

import requests

from .browser_session import selected_headers
from .engine.config import REQUEST_TIMEOUT

BASE = "https://www.last.fm"
# The site rejects a request without a browser-ish agent.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

_CSRF_INPUT = re.compile(
    r'name="csrfmiddlewaretoken"\s+value="([^"]+)"|value="([^"]+)"\s+name="csrfmiddlewaretoken"')
_PLAYLIST_LINK = re.compile(r'href="(/user/[^"/]+/playlists/(\d+))"[^>]*>([^<]*)<')
_ENTRY_ROW = re.compile(r'<tr\b[^>]*data-playlist-entry-url="([^"]+)"(.*?)</tr>', re.S)
_MUSIC_LINK = re.compile(r'href="/music/([^"/]+)(?:/_/([^"]+))?"[^>]*>([^<]*)<')
_ADD_FORM = re.compile(r'<form\b[^>]*data-playlisting-add-form[^>]*>(.*?)</form>', re.S)
_INPUT_VALUE = re.compile(r'<input\b[^>]*name="([^"]+)"[^>]*value="([^"]*)"')


class LastfmWebAuthError(RuntimeError):
    """The pasted session is missing, malformed, or no longer signed in."""


def parse_web_request(raw: str) -> dict[str, str]:
    """The minimal cookie set from a copied signed-in request.

    Only the two cookies the site needs are kept; every other cookie and header
    in the paste is discarded rather than persisted.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("paste a signed-in last.fm request, request headers, or copied cURL command")

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    direct = parsed if isinstance(parsed, dict) else {}
    if isinstance(direct.get("credentials"), dict):
        direct = direct["credentials"]

    cookie_header = selected_headers(raw, {"cookie"}).get("cookie", "")
    jar = dict(re.findall(r"(?:^|;\s*)([^=;\s]+)=([^;]*)", cookie_header))

    def first(*names):
        for name in names:
            value = direct.get(name) or jar.get(name)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    credentials = {
        "sessionid": first("sessionid"),
        "csrftoken": first("csrftoken", "csrf_token"),
    }
    missing = [key for key, value in credentials.items() if not value]
    if missing:
        raise ValueError(
            "the copied request is missing the " + " and ".join(missing)
            + " cookie; copy a request from a signed-in last.fm page (the Cookie "
              "header carries both)")
    if any("\r" in value or "\n" in value for value in credentials.values()):
        raise ValueError("last.fm cookies contain a line break")
    return credentials


def serialize_web_request(raw: str) -> str:
    return json.dumps(parse_web_request(raw), separators=(",", ":"), sort_keys=True)


def _csrf(html: str) -> str:
    match = _CSRF_INPUT.search(html)
    if not match:
        raise LastfmWebAuthError(
            "no CSRF token on the page; the last.fm session has probably expired, "
            "so copy a fresh signed-in request")
    return match.group(1) or match.group(2)


def _text(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


class LastfmWeb:
    """Playlist operations against the signed-in last.fm website."""

    def __init__(self, credentials: dict[str, str], user: str, session=None):
        self._user = str(user or "").strip()
        if not self._user:
            raise LastfmWebAuthError("a last.fm username is required")
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Referer": BASE})
        for name, value in credentials.items():
            self._session.cookies.set(name, value, domain=".last.fm")

    @property
    def root(self) -> str:
        return f"/user/{self._user}/playlists"

    # -- transport -----------------------------------------------------------

    def _get(self, path: str, **params) -> str:
        try:
            response = self._session.get(BASE + path, params=params or None,
                                         timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise LastfmWebAuthError(f"could not reach last.fm ({exc!r})") from exc
        if response.status_code in (401, 403):
            raise LastfmWebAuthError("last.fm rejected the session; copy a fresh signed-in request")
        response.raise_for_status()
        return response.text

    def _post(self, path: str, token: str, **fields):
        payload = {"csrfmiddlewaretoken": token, **{k: v for k, v in fields.items() if v is not None}}
        try:
            response = self._session.post(
                BASE + path, data=payload, timeout=REQUEST_TIMEOUT,
                headers={"Referer": BASE + path})
        except requests.RequestException as exc:
            raise LastfmWebAuthError(f"could not reach last.fm ({exc!r})") from exc
        if response.status_code in (401, 403):
            raise LastfmWebAuthError("last.fm rejected the session; copy a fresh signed-in request")
        response.raise_for_status()
        return response

    # -- playlists -----------------------------------------------------------

    def list_playlists(self) -> list[dict]:
        """``[{id, name}]`` for the signed-in user's playlists."""
        html = self._get(self.root)
        seen: dict[str, str] = {}
        for _href, playlist_id, label in _PLAYLIST_LINK.findall(html):
            name = _text(label)
            # The same playlist is linked by its cover (no text) and its title.
            if name and playlist_id not in seen:
                seen[playlist_id] = name
        return [{"id": pid, "name": name} for pid, name in seen.items()]

    def create(self, name: str, description: str = "") -> dict:
        """Create a playlist and title it. The site creates it empty and
        untitled, then takes the title through a separate edit post."""
        token = _csrf(self._get(self.root))
        created = self._post(self.root, token)
        match = re.search(r"/playlists/(\d+)", created.url or "")
        if not match:
            raise LastfmWebAuthError("last.fm did not report the new playlist's id")
        playlist_id = match.group(1)
        self.rename(playlist_id, name, description)
        return {"id": playlist_id, "name": name}

    def rename(self, playlist_id: str, name: str, description: str = "") -> None:
        path = f"{self.root}/{playlist_id}"
        token = _csrf(self._get(path))
        self._post(path, token, title=name)
        if description:
            self._post(path, _csrf(self._get(path)), description=description)

    def delete(self, playlist_id: str) -> None:
        path = f"{self.root}/{playlist_id}"
        self._post(path, _csrf(self._get(path)), action="delete")

    # -- entries -------------------------------------------------------------

    def entries(self, playlist_id: str) -> list[dict]:
        """``[{entry_id, name, artist}]`` in playlist order."""
        html = self._get(f"{self.root}/{playlist_id}")
        rows = []
        for entry_url, body in _ENTRY_ROW.findall(html):
            entry_id = entry_url.rstrip("/").rsplit("/", 1)[-1]
            name = artist = ""
            for link_artist, link_track, label in _MUSIC_LINK.findall(body):
                text = _text(label)
                if not text or text.lower().startswith("go to"):
                    continue
                if link_track and not name:
                    name = text
                elif not link_track and not artist:
                    artist = text
            if not name:
                # Fall back to the cover art's alt text, which carries the row's
                # own "<artist> - <track>" label.
                alt = re.search(r'<img[^>]*alt="([^"]*)"', body)
                name = _text(alt.group(1)) if alt else ""
            if name:
                rows.append({"entry_id": entry_id, "name": name,
                             "artist": artist or unquote(link_artist or "")})
        return rows

    def search(self, query: str, playlist_id: str, limit: int = 10) -> list[dict]:
        """Catalogue rows for a query, as ``[{track, artist}]``.

        The values come straight from each row's add form, because those exact
        strings are what an add has to send back.
        """
        html = self._get(f"{self.root}/{playlist_id}/search-catalogue", q=query)
        found = []
        for body in _ADD_FORM.findall(html)[:limit]:
            fields = dict(_INPUT_VALUE.findall(body))
            track, artist = fields.get("track"), fields.get("artist")
            if track:
                found.append({"track": unescape(track), "artist": unescape(artist or "")})
        return found

    def add(self, playlist_id: str, track: str, artist: str) -> None:
        path = f"{self.root}/{playlist_id}"
        self._post(f"{path}/entries", _csrf(self._get(path)), track=track, artist=artist)

    def remove(self, playlist_id: str, entry_id: str) -> None:
        path = f"{self.root}/{playlist_id}"
        self._post(f"{path}/entries/{entry_id}", _csrf(self._get(path)),
                   action="delete-entry")

    def check(self) -> str:
        """Confirm the session is live, returning the signed-in username."""
        html = self._get(self.root)
        if "csrfmiddlewaretoken" not in html:
            raise LastfmWebAuthError(
                "last.fm returned a signed-out page; copy a fresh signed-in request")
        return self._user


def configured(credentials) -> bool:
    return bool(credentials and credentials.get("sessionid") and credentials.get("csrftoken"))


def credentials_from(raw: str):
    """Stored credentials, or None when nothing usable is configured."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        try:
            parsed = parse_web_request(raw)
        except ValueError:
            return None
    return parsed if configured(parsed) else None


def profile_path(url: str) -> str:
    """The path part of a pasted last.fm URL, for error messages."""
    return urlsplit(str(url or "")).path
