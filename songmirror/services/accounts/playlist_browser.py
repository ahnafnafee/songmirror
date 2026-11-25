"""Import a signed-in playlist request without storing its URL or body."""

import json
import re
from urllib.parse import parse_qs, urlsplit

from ...browser_session import selected_headers, urls_in
from ...engine.targets.audiomack_browser import LIBRARY_URL as AUDIOMACK_LIBRARY_URL, SESSION_COOKIES as AUDIOMACK_SESSION_COOKIES
from ...engine.targets.base import TargetAuthError
from .base import ConnStatus


PLAYLIST_WEB_CONNECTIONS = {
    "audiomack": (AUDIOMACK_LIBRARY_URL, "audiomack.com", "/my-library/playlists", "v1/user/playlists"),
    "gaana": ("https://gaana.com/music", "api.gaana.com", "/user.php", "myplaylists"),
    "jiosaavn": ("https://www.jiosaavn.com/my-music/playlists", "www.jiosaavn.com", "/api.php", "library.getAll"),
    "linemusic": ("https://music.line.me/webapp/library/playlists", "music.line.me",
                  "/api2/user/me/libraries.v1", "libraries.v1"),
    "netease": ("https://music.163.com/#/my/", "music.163.com", "/api/user/playlist", "user/playlist"),
    "pandora": ("https://www.pandora.com/collection/playlists", "www.pandora.com",
                "/api/v6/collections/getSortedPlaylists", "getSortedPlaylists"),
    "qqmusic": ("https://y.qq.com/", "u.y.qq.com", "/cgi-bin/musicu.fcg", "musicu.fcg"),
    "vibe": ("https://vibe.naver.com/library/playlists", "apis.naver.com",
             "/vibeWeb/musicapiweb/vibe/v2/library/PLAYLIST/libraries", "PLAYLIST/libraries"),
}
PLAYLIST_WEB_KEYS = {f"{provider.upper()}_PLAYLIST_WEB_SESSION" for provider in PLAYLIST_WEB_CONNECTIONS}


def _signed_request(provider, raw):
    _, host, path, hint = PLAYLIST_WEB_CONNECTIONS[provider]
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 64_000:
        raise ValueError("Copy the signed-in playlist request as cURL (bash).")
    matching = [url for url in map(urlsplit, urls_in(raw))
                if (url.scheme, url.netloc, url.path) == ("https", host, path)]
    if len(matching) != 1:
        raise ValueError(f"Copy the {hint} request from the signed-in web player.")
    return matching[0]


def _cookies(raw):
    value = selected_headers(raw, {"cookie"}).get("cookie", "")
    if not value:
        match = re.search(r"(?:^|\s)(?:-b|--cookie)\s+(?:'([^']*)'|\"([^\"]*)\")", raw)
        if match:
            value = next(part for part in match.groups() if part is not None)
    result = {}
    for part in value.split(";"):
        name, _, token = part.strip().partition("=")
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name) and re.fullmatch(r"[\x21-\x2B\x2D-\x3A\x3C-\x5B\x5D-\x7E]{1,4096}", token):
            result[name] = token
    return result


def _audiomack_session(raw, signing_cookie):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 64_000:
        raise ValueError("Copy the signed-in Audiomack playlist request as cURL (bash).")
    requests = [url for url in map(urlsplit, urls_in(raw))
                if url.scheme == "https" and url.netloc == "api.audiomack.com"
                and re.fullmatch(r"/v1/user/playlists/page/[1-9][0-9]{0,5}", url.path)]
    cookies = _cookies(raw)
    if requests:
        if len(requests) != 1:
            raise ValueError("Copy one v1/user/playlists request from Audiomack.")
        query = parse_qs(requests[0].query)
        tokens = query.get("oauth_token", [])
        if len(tokens) != 1 or query.get("oauth_consumer_key") != ["audiomack-web"] or not query.get("oauth_signature"):
            raise ValueError("Copy the v1/user/playlists request after signing in to Audiomack.")
        cookies["otoken"] = tokens[0]
    else:
        _signed_request("audiomack", raw)
    if isinstance(signing_cookie, str) and signing_cookie.strip():
        cookies["osecret"] = signing_cookie.strip()
    session = {name: cookies.get(name, "") for name in AUDIOMACK_SESSION_COOKIES}
    if not all(re.fullmatch(r"[A-Za-z0-9_~.+=/-]{16,600}", value) for value in session.values()):
        raise ValueError("Audiomack needs the signed-in playlist request and the osecret cookie.")
    return session


def parse_playlist_session(provider, raw, *, signing_cookie=None):
    if provider == "audiomack":
        return _audiomack_session(raw, signing_cookie)
    url = _signed_request(provider, raw)
    if provider == "gaana":
        query = parse_qs(url.query)
        token = query.get("token", [""])[0]
        if query.get("type") != ["myplaylists"] or not re.fullmatch(r"[A-Za-z0-9_\-.~+/=]{16,600}", token):
            raise ValueError("The request is missing Gaana’s signed-in playlist token.")
        headers = selected_headers(raw, {"deviceid", "country"})
        result = {"token": token}
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", headers.get("deviceid", "")):
            result["deviceid"] = headers["deviceid"]
        if re.fullmatch(r"[A-Za-z]{2,6}", headers.get("country", "")):
            result["country"] = headers["country"]
        return result
    if provider == "pandora":
        headers = selected_headers(raw, {"x-authtoken", "x-csrftoken"})
        auth, csrf = headers.get("x-authtoken", ""), headers.get("x-csrftoken", "")
        if not re.fullmatch(r"[\x21-\x7E]{16,1200}", auth) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", csrf):
            raise ValueError("The request is missing the Pandora session or CSRF header.")
        return {"authorization": auth, "csrf": csrf}
    if provider == "jiosaavn" and parse_qs(url.query).get("__call") != ["library.getAll"]:
        raise ValueError("Copy JioSaavn’s library.getAll request from the signed-in web player.")
    cookies = _cookies(raw)
    if provider == "qqmusic":
        login = ("wxuin", "uin", "qqmusic_uin", "p_uin") if cookies.get("login_type") == "2" else (
            "uin", "qqmusic_uin", "wxuin", "p_uin")
        uin = next((cookies[k] for k in login if k in cookies), "").removeprefix("o").lstrip("0")
        auth = next((cookies[k] for k in ("qm_keyst", "qqmusic_key", "music_key") if k in cookies), "")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", uin) or not auth:
            raise ValueError("The request is missing the QQ Music account ID or music session cookie.")
        selected = (*login, "login_type", "qm_keyst", "qqmusic_key", "music_key")
        return {"uin": uin, "authst": auth,
                "cookie": "; ".join(f"{key}={cookies[key]}" for key in selected if key in cookies)}
    if provider == "netease":
        if "MUSIC_U" not in cookies:
            raise ValueError("The request is missing the signed-in NetEase Cloud Music session cookie.")
        cookies = {key: cookies[key] for key in ("MUSIC_U", "__csrf") if key in cookies}
    elif provider == "vibe":
        cookies = {key: cookies[key] for key in ("NID_AUT", "NID_SES") if key in cookies}
    else:
        cookies = {key: value for key, value in cookies.items()
                   if not key.casefold().startswith(("_ga", "_gid", "_fbp", "_cl", "_hj", "optanon"))}
    if not cookies:
        raise ValueError("The signed-in request contains no session cookies.")
    result = {"cookie": "; ".join(f"{key}={value}" for key, value in cookies.items())}
    if provider == "linemusic":
        device_id = selected_headers(raw, {"x-lm-did"}).get("x-lm-did", "")
        if re.fullmatch(r"[A-Za-z0-9_./=+-]{1,160}", device_id):
            result["deviceid"] = device_id
    return result


class PlaylistBrowserConnection:
    """Shared account flow for public readers with an authenticated library."""

    @property
    def playlist_browser(self):
        entry = PLAYLIST_WEB_CONNECTIONS.get(self.id)
        if not entry:
            return None
        login, _, _, hint = entry
        return {"login_url": login, "request_hint": hint, "active": bool(self._store.get(self.target_class.session_key()))}

    def browser_status(self, credentials=None):
        try:
            target = self.target_class(web_session=credentials)
            playlists = target.browse_playlists()
            if self.id == "audiomack" and credentials is not None:
                sample = next((row for row in playlists if row["count"]), None)
                if sample is not None:
                    target.playlist_tracks(sample)
        except TargetAuthError as exc:
            return ConnStatus("expired", str(exc))
        except (RuntimeError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        return ConnStatus("connected", capabilities=frozenset({"library_read", "public_playlist_read"}))

    def enable_playlist_browser(self, raw, *, signing_cookie=None):
        try:
            credentials = parse_playlist_session(self.id, raw, signing_cookie=signing_cookie)
        except ValueError as exc:
            return ConnStatus("error", str(exc))
        status = self.browser_status(credentials)
        if status.state == "connected":
            self._store.save({self.target_class.session_key(): json.dumps(credentials, separators=(",", ":"))})
        return status

    def disable_playlist_browser(self):
        self._store.save({self.target_class.session_key(): ""})
        return self.status()
