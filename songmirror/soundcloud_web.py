"""SoundCloud metadata transport using a user-supplied web session."""

import json
import os
import re
import time
from pathlib import Path
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .browser_session import selected_headers, urls_in
from .engine.config import REQUEST_TIMEOUT
from .soundcloud import (
    SoundCloud, SoundCloudAuthError, SoundCloudError, SoundCloudTransient, api_result, read_private, write_private,
)
from .soundcloud_renewal import renew_on_site

WEB_API = "https://api-v2.soundcloud.com"
WEB_SESSION_FILENAME = "soundcloud_browser.json"
BROWSER_SESSION_LOCK = RLock()
_renewal_failure = {}
_proactive_attempt = {}
_RENEW_AFTER = 50 * 60
_PROACTIVE_RETRY = 15 * 60


class BrowserVerificationRequired(SoundCloudAuthError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_WEB_OPENER = build_opener(_NoRedirect())


def _browser_verification_required(response):
    if response.code != 403:
        return False
    try:
        body = json.loads(response.read(16_384))
        challenge_url = body.get("url") if isinstance(body, dict) else None
        if not isinstance(challenge_url, str):
            return False
        url = urlsplit(challenge_url)
    except (OSError, TypeError, ValueError):
        return False
    return (url.scheme == "https" and url.netloc == "geo.captcha-delivery.com"
            and (url.path == "/captcha" or url.path.startswith("/captcha/")))


def _request(method, url, *, authorization, body=None):
    headers = {"Authorization": authorization, "Accept": "application/json"}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with _WEB_OPENER.open(request, timeout=REQUEST_TIMEOUT) as response:
            return api_result(response.status, response.headers, lambda: json.load(response))
    except HTTPError as exc:
        with exc:
            if _browser_verification_required(exc):
                raise BrowserVerificationRequired(
                    "SoundCloud requested browser verification. Complete it on soundcloud.com "
                    "and paste a fresh SoundCloud library request."
                ) from None
            return api_result(exc.code, exc.headers, lambda: json.load(exc))
    except (OSError, URLError) as exc:
        raise SoundCloudTransient("Could not reach SoundCloud's web API") from exc


def browser_mode(get=os.getenv):
    return str(get("SOUNDCLOUD_PREFER_BROWSER") or "").lower() in {"1", "true", "yes", "on"}


def browser_session_path():
    default = Path(os.getenv("SONGMIRROR_DATA_DIR") or "data") / "profiles" / "profile_default_soundcloud"
    return Path(os.getenv("SOUNDCLOUD_WEB_SESSION_FILE") or default / WEB_SESSION_FILENAME)


def _credentials(authorization, client_id):
    if not isinstance(authorization, str) or not re.fullmatch(r"OAuth [!-~]{1,4096}", authorization):
        raise ValueError("The SoundCloud request needs an OAuth authorization header")
    if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", client_id):
        raise ValueError("The SoundCloud request needs a client_id in its URL")
    return {"authorization": authorization, "client_id": client_id}


def parse_browser_request(raw):
    if not isinstance(raw, str) or len(raw) > 128_000:
        raise ValueError("Paste a single SoundCloud library request")
    urls = [urlsplit(url) for url in urls_in(raw)]
    requests = [
        url for url in urls
        if url.scheme == "https" and url.netloc == "api-v2.soundcloud.com"
        and url.path == "/me/library/all"
    ]
    if len(requests) != 1:
        raise ValueError("Copy the signed-in SoundCloud /me/library/all request as cURL")
    values = parse_qs(requests[0].query).get("client_id", [])
    auth = selected_headers(raw, {"authorization"}).get("authorization")
    return _credentials(auth, values[0] if len(values) == 1 else None)


class SoundCloudWeb:
    """Reuse the public API response handling with the web client's own origin."""

    collection = SoundCloud.collection
    _linked_partitioning = "1"

    def __init__(self, session=None, *, session_file=None):
        self._session_file = Path(session_file) if session_file is not None else None
        if session is None:
            self._session_file = self._session_file or browser_session_path()
            session = read_private(self._session_file)
        try:
            self.credentials = _credentials(session.get("authorization"), session.get("client_id"))
        except ValueError as exc:
            raise SoundCloudAuthError("Paste a fresh SoundCloud browser request") from exc
        self._user_id = session.get("user_id")
        captured_at = session.get("captured_at")
        self._refresh_after = (captured_at + _RENEW_AFTER if self._session_file
                               and session.get("renewal_cookies")
                               and isinstance(captured_at, (int, float)) else None)

    def _send(self, method, path, credentials, *, params=None, json=None):
        url = WEB_API + path if path.startswith("/") and not path.startswith("//") else path
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "api-v2.soundcloud.com" or parts.fragment:
            raise SoundCloudTransient("Invalid SoundCloud web API page URL")
        # A pagination URL may carry its own client_id. Keep the one from the
        # selected browser session and preserve the provider's cursor.
        query = {**parse_qs(parts.query), **(params or {}), "client_id": credentials["client_id"]}
        return _request(method, parts._replace(query=urlencode(query, doseq=True)).geturl(),
                        authorization=credentials["authorization"], body=json)

    def _renew(self, rejected, *, ahead=False):
        with BROWSER_SESSION_LOCK:
            session = read_private(self._session_file)
            if self._user_id is None or session.get("user_id") != self._user_id:
                raise SoundCloudAuthError("Reconnect the selected SoundCloud browser account.")
            try:
                current = _credentials(session.get("authorization"), session.get("client_id"))
            except ValueError:
                raise SoundCloudAuthError("Paste fresh SoundCloud requests to reconnect.") from None
            if current["authorization"] != rejected:
                return current
            cookies = session.get("renewal_cookies")
            if not cookies:
                raise SoundCloudAuthError("Paste fresh SoundCloud requests to reconnect and enable automatic renewal.")
            key = (self._session_file, hash(rejected))
            delay_until = _renewal_failure.get(self._session_file)
            if ahead:
                previous = _proactive_attempt.get(self._session_file)
                if previous and previous[0] == key and time.monotonic() < previous[1]:
                    return current
                _proactive_attempt[self._session_file] = (key, time.monotonic() + _PROACTIVE_RETRY)
            elif delay_until and delay_until[0] == key and time.monotonic() < delay_until[1]:
                raise SoundCloudTransient("SoundCloud browser renewal recently failed. Try again shortly.")
            try:
                authorization, client_id, cookies = renew_on_site(cookies, rejected, current["client_id"])
                renewed = _credentials(authorization, client_id)
                if renewed["authorization"] == rejected:
                    raise SoundCloudAuthError("SoundCloud did not issue a new browser token.")
                profile = self._send("GET", "/me", renewed)
                if not isinstance(profile, dict) or str(profile.get("id")) != str(self._user_id):
                    raise SoundCloudAuthError("The renewed SoundCloud session belongs to a different account.")
                captured_at = time.time()
                write_private(self._session_file, {
                    **session, **renewed, "renewal_cookies": cookies, "captured_at": captured_at,
                })
                self._refresh_after = captured_at + _RENEW_AFTER
            except (SoundCloudAuthError, SoundCloudTransient):
                if not ahead:
                    _renewal_failure[self._session_file] = (key, time.monotonic() + 60)
                raise
            except (ValueError, OSError):
                if not ahead:
                    _renewal_failure[self._session_file] = (key, time.monotonic() + 60)
                raise SoundCloudTransient("Could not validate or save the renewed SoundCloud browser session.") from None
            _renewal_failure.pop(self._session_file, None)
            _proactive_attempt.pop(self._session_file, None)
            return renewed

    def request(self, method, path, *, params=None, json=None):
        if self._refresh_after is not None and time.time() >= self._refresh_after:
            self._refresh_after = time.time() + _PROACTIVE_RETRY
            try:
                self.credentials = self._renew(self.credentials["authorization"], ahead=True)
            except SoundCloudError:
                # A still-valid token can carry the call through a temporary
                # website failure. A later 401 still triggers the normal retry.
                pass
        credentials = self.credentials
        try:
            return self._send(method, path, credentials, params=params, json=json)
        except BrowserVerificationRequired:
            raise
        except SoundCloudAuthError:
            if self._session_file is None:
                raise
            self.credentials = self._renew(credentials["authorization"])
            return self._send(method, path, self.credentials, params=params, json=json)

    def profile(self):
        user = self.request("GET", "/me")
        if not isinstance(user, dict) or not user.get("id") or not user.get("username"):
            raise SoundCloudAuthError("SoundCloud did not confirm the browser account")
        return user
