"""SoundCloud metadata transport using a user-supplied web session."""

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .browser_session import selected_headers, urls_in
from .engine.config import REQUEST_TIMEOUT
from .soundcloud import SoundCloud, SoundCloudAuthError, SoundCloudTransient, api_result, read_private

WEB_API = "https://api-v2.soundcloud.com"
WEB_SESSION_FILENAME = "soundcloud_browser.json"


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
                raise SoundCloudAuthError(
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

    def __init__(self, session=None):
        if session is None:
            session = read_private(browser_session_path())
        try:
            self.credentials = _credentials(session.get("authorization"), session.get("client_id"))
        except ValueError as exc:
            raise SoundCloudAuthError("Paste a fresh SoundCloud browser request") from exc

    def request(self, method, path, *, params=None, json=None):
        url = WEB_API + path if path.startswith("/") and not path.startswith("//") else path
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "api-v2.soundcloud.com" or parts.fragment:
            raise SoundCloudTransient("Invalid SoundCloud web API page URL")
        # A pagination URL may carry its own client_id. Keep the one from the
        # selected browser session and preserve the provider's cursor.
        query = {"client_id": self.credentials["client_id"], **parse_qs(parts.query), **(params or {})}
        query["client_id"] = self.credentials["client_id"]
        return _request(method, parts._replace(query=urlencode(query, doseq=True)).geturl(),
                        authorization=self.credentials["authorization"], body=json)

    def profile(self):
        user = self.request("GET", "/me")
        if not isinstance(user, dict) or not user.get("id") or not user.get("username"):
            raise SoundCloudAuthError("SoundCloud did not confirm the browser account")
        return user
