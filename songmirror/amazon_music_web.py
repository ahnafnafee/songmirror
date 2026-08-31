"""Amazon Music's first-party web-player GraphQL transport.

Amazon's documented Music Web API is a closed beta.  The consumer web player
uses a separate GraphQL endpoint, authenticated by short-lived request headers
from the signed-in browser.  The web player renews those headers through its
same-origin ``/pandaToken`` route.  This module persists only the minimal
GraphQL context plus a named allowlist of cookies needed by that renewal route;
analytics, experiment, AWS-console, and other unrelated cookies are discarded.

The endpoint is private/unsupported and can change without notice.  Keeping the
transport isolated here makes that failure mode explicit and easy to replace.
"""

from __future__ import annotations

import base64
import json
import random
import re
import time
from urllib.parse import urlsplit

import requests

from .engine.config import REQUEST_TIMEOUT
from .oauth import read_token, write_token

ENDPOINT = "https://gql.music.amazon.dev"
CONFIG_ENDPOINT = "https://music.amazon.com/config.json"
PANDA_TOKEN_ENDPOINT = "https://music.amazon.com/pandaToken"
MUSIC_HOME_URL = "https://music.amazon.com/"
DEFAULT_WEB_SESSION_FILE = "data/amazon_music_web_session.json"

_DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Public identifier embedded in Amazon Music's first-party Firefly web bundle.
# It identifies the web client; it is not a customer secret.  The signed-in
# ``config.json`` response supplies the per-user access token and device
# context used to construct the web player's Authorization value.
FIREFLY_WEB_API_KEY = "amzn1.application.e1dc16675f9f4c78b31927d5bfd5c229"

# The signed-in Firefly client only needs these two headers.  The optional
# context headers are accepted because older/newer web-player builds may emit
# anonymous-style requests while transitioning profiles.  Notably absent:
# Cookie, CSRF, Host, Origin, and every sec-* browser header.
_ALLOWED_HEADERS = {
    "authorization",
    "x-api-key",
    "device-id",
    "device-type",
    "x-device-id",
    "x-device-type",
    "music-territory",
    "x-amzn-session-id",
    "x-amzn-client-app-version",
    "accept-language",
}
_REQUIRED_HEADERS = {"authorization", "x-api-key"}

# Amazon's ``/pandaToken`` route is cookie-authenticated.  Keep only known
# authentication/session cookies observed on the Music request, never the
# complete amazon.com cookie jar.  These can still grant account access and
# therefore live only in SongMirror's owner-only settings/session files.
_ALLOWED_RENEWAL_COOKIES = {
    "am-token",
    "at-main",
    "at-main-music",
    "sess-at-main",
    "sid",
    "session-id",
    "session-id-time",
    "session-token",
    "sso-state-main",
    "sst-main",
    "ubid-main",
    "x-main",
}

# These cookies are scoped to music.amazon.com; the remaining allowlisted
# cookies use Amazon's parent domain so redirects cannot widen their scope.
_MUSIC_SCOPED_COOKIES = {"am-token", "at-main-music", "sid"}
_ALLOWED_RENEWAL_BROWSER_HEADERS = {"accept-language", "referer", "user-agent"}


class AmazonMusicWebAuthError(RuntimeError):
    """The pasted web-player session is missing, expired, or rejected."""


class _AmazonMusicRenewalRejected(AmazonMusicWebAuthError):
    """A token endpoint rejected cookies that may recover after config bootstrap."""


def _header_pairs(raw: str):
    """Yield header pairs from DevTools text, cURL, or stored JSON."""

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        source = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else parsed
        yield from source.items()
        return

    # Chrome/Firefox "Copy as cURL" output.
    for match in re.finditer(r"(?:^|\s)(?:-H|--header)\s+(?:'([^']*)'|\"([^\"]*)\")", raw):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if ":" in value:
            yield value.split(":", 1)

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        # The raw Headers pane usually copies as ``name: value``.
        match = re.match(r"^([^:\s][^:]*):\s*(.+)$", line)
        if match:
            yield match.group(1), match.group(2)
            continue
        # Chromium sometimes copies the two visible table columns on separate
        # lines (``authorization`` then ``AmznMusic ...``).
        if line.casefold() in _ALLOWED_HEADERS and index + 1 < len(lines):
            yield line, lines[index + 1]


def parse_web_headers(raw: str) -> dict[str, str]:
    """Parse and minimize Amazon Music ``config.json`` or GraphQL headers.

    The returned dictionary is safe to persist in SongMirror's owner-only
    settings file.  It intentionally cannot contain an Amazon retail cookie.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("paste the Response JSON from a signed-in Amazon Music config.json request")

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict) and any(
        key in parsed for key in ("accessToken", "deviceId", "deviceType", "musicTerritory")
    ):
        access_token = str(parsed.get("accessToken") or "").strip()
        device_id = str(parsed.get("deviceId") or "").strip()
        device_type = str(parsed.get("deviceType") or "").strip()
        if not access_token:
            raise ValueError("config.json has no accessToken; copy it after signing in to Amazon Music")
        if not device_id or not device_type:
            raise ValueError("config.json is missing deviceId or deviceType")
        if any("\r" in value or "\n" in value for value in (access_token, device_id, device_type)):
            raise ValueError("Amazon Music config values contain a line break")
        payload = json.dumps(
            {"deviceId": device_id, "deviceType": device_type, "access_token": access_token},
            separators=(",", ":"),
        ).encode()
        headers = {
            "authorization": "AmznMusic " + base64.b64encode(payload).decode(),
            "x-api-key": FIREFLY_WEB_API_KEY,
            "device-id": device_id,
            "device-type": device_type,
        }
        optional = {
            "music-territory": parsed.get("musicTerritory"),
            "x-amzn-session-id": parsed.get("sessionId"),
            "x-amzn-client-app-version": parsed.get("version"),
            "accept-language": parsed.get("locale") or parsed.get("language"),
        }
        for key, value in optional.items():
            if value not in (None, ""):
                normalized = str(value).strip()
                if "\r" in normalized or "\n" in normalized:
                    raise ValueError(f"{key} value contains a line break")
                headers[key] = normalized
        return headers

    headers: dict[str, str] = {}
    for name, value in _header_pairs(raw):
        key = str(name).strip().casefold()
        if key in _ALLOWED_HEADERS and value is not None:
            normalized = str(value).strip()
            if "\r" in normalized or "\n" in normalized:
                raise ValueError(f"{key} request header contains a line break")
            headers[key] = normalized

    missing = sorted(key for key in _REQUIRED_HEADERS if not headers.get(key))
    if missing:
        raise ValueError(
            "missing " + " and ".join(missing)
            + " request header(s); paste config.json Response JSON or GraphQL request headers"
        )
    if not headers["authorization"].casefold().startswith("amznmusic "):
        raise ValueError("authorization must come from a gql.music.amazon.dev web-player request")
    return headers


def serialize_web_headers(raw: str) -> str:
    """Return the whitelisted headers as compact, single-line JSON."""

    return json.dumps(parse_web_headers(raw), separators=(",", ":"), sort_keys=True)


def _add_cookie(out: dict[str, str], name, value) -> None:
    key = str(name).strip().casefold()
    if key not in _ALLOWED_RENEWAL_COOKIES or value is None:
        return
    normalized = str(value).strip().strip('"')
    if not normalized:
        return
    if any(char in normalized for char in "\r\n;"):
        raise ValueError(f"{key} cookie is malformed")
    out[key] = normalized


def _cookies_from_header(out: dict[str, str], value) -> None:
    for part in str(value or "").split(";"):
        name, separator, cookie_value = part.strip().partition("=")
        if separator:
            _add_cookie(out, name, cookie_value)


def parse_renewal_cookies(raw: str) -> dict[str, str]:
    """Extract the minimized cookie set used by Amazon Music ``/pandaToken``.

    Accepted inputs are copied request headers, Copy-as-cURL text, a bare
    Cookie value, or the compact JSON previously saved by SongMirror.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            "paste a signed-in Amazon Music config.json or /pandaToken request (headers or cURL)"
        )

    out: dict[str, str] = {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        nested = parsed.get("renewal_cookies") or parsed.get("cookies")
        if isinstance(nested, dict):
            for name, value in nested.items():
                _add_cookie(out, name, value)
        for name, value in parsed.items():
            if str(name).strip().casefold() == "cookie":
                _cookies_from_header(out, value)
            else:
                _add_cookie(out, name, value)

    for name, value in _header_pairs(raw):
        key = str(name).strip().casefold()
        if key == "cookie":
            _cookies_from_header(out, value)
        else:
            _add_cookie(out, name, value)

    # Some Copy-as-cURL variants use ``-b``/``--cookie`` rather than a Cookie
    # header, and Firefox can copy only the Cookie header's bare value.
    for match in re.finditer(r"(?:^|\s)(?:-b|--cookie)\s+(?:'([^']*)'|\"([^\"]*)\")", raw):
        _cookies_from_header(out, match.group(1) if match.group(1) is not None else match.group(2))
    # Only apply the bare-value fallback when no structured request/header
    # parser found cookies.  Re-parsing a complete header block here made its
    # final cookie absorb every following request-header line.
    if not out:
        _cookies_from_header(out, raw)

    if not out:
        raise ValueError(
            "no supported Amazon Music authentication cookies found; copy a signed-in "
            "config.json or /pandaToken request's headers or cURL"
        )
    return out


def serialize_renewal_cookies(raw: str) -> str:
    return json.dumps(parse_renewal_cookies(raw), separators=(",", ":"), sort_keys=True)


def _add_renewal_browser_header(out: dict[str, str], name, value) -> None:
    key = str(name).strip().casefold()
    if key not in _ALLOWED_RENEWAL_BROWSER_HEADERS or value is None:
        return
    normalized = str(value).strip()
    if not normalized:
        return
    if any(char in normalized for char in "\r\n"):
        raise ValueError(f"{key} request header contains a line break")
    if len(normalized) > 1024:
        raise ValueError(f"{key} request header is too long")
    if key == "referer":
        parsed = urlsplit(normalized)
        if parsed.scheme != "https" or parsed.hostname != "music.amazon.com":
            raise ValueError("Amazon Music referer must use https://music.amazon.com")
    out[key] = normalized


def parse_renewal_browser_headers(raw: str) -> dict[str, str]:
    """Extract non-secret browser context needed to replay Music requests."""

    if not isinstance(raw, str) or not raw.strip():
        return {}
    out: dict[str, str] = {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        nested = parsed.get("browser_headers")
        if isinstance(nested, dict):
            for name, value in nested.items():
                _add_renewal_browser_header(out, name, value)
    for name, value in _header_pairs(raw):
        _add_renewal_browser_header(out, name, value)
    return out


def serialize_renewal_request(raw: str) -> str:
    payload: dict[str, dict[str, str]] = {
        "renewal_cookies": parse_renewal_cookies(raw),
    }
    browser_headers = parse_renewal_browser_headers(raw)
    if browser_headers:
        payload["browser_headers"] = browser_headers
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


SESSION_QUERY = """
query SongMirrorAmazonSession {
  user { id }
}
"""


class AmazonMusicWebClient:
    """GraphQL client backed by Amazon Music's renewable first-party session."""

    def __init__(
        self,
        raw_headers: str = "",
        *,
        renewal_request: str = "",
        token_file: str = "",
        prefer_persisted: bool = True,
        session=None,
        endpoint: str = ENDPOINT,
        config_endpoint: str = CONFIG_ENDPOINT,
        panda_token_endpoint: str = PANDA_TOKEN_ENDPOINT,
    ):
        self.endpoint = endpoint
        self.config_endpoint = config_endpoint
        self.panda_token_endpoint = panda_token_endpoint
        self.session = session or requests.Session()
        self._token_file = str(token_file or "")

        persisted = read_token(self._token_file) if self._token_file else {}
        supplied_headers = parse_web_headers(raw_headers) if str(raw_headers or "").strip() else {}
        stored_headers = persisted.get("headers") if isinstance(persisted.get("headers"), dict) else {}
        if stored_headers:
            stored_headers = parse_web_headers(json.dumps(stored_headers))
        if prefer_persisted and stored_headers:
            self.headers = stored_headers
            self._expires_at = self._number(persisted.get("expires_at"))
        else:
            self.headers = supplied_headers or stored_headers
            self._expires_at = 0

        supplied_cookies = (
            parse_renewal_cookies(renewal_request) if str(renewal_request or "").strip() else {}
        )
        stored_cookies = persisted.get("renewal_cookies")
        if isinstance(stored_cookies, dict) and stored_cookies:
            stored_cookies = parse_renewal_cookies(json.dumps(stored_cookies))
        else:
            stored_cookies = {}
        self.renewal_cookies = (
            stored_cookies
            if prefer_persisted and stored_cookies
            else supplied_cookies or stored_cookies
        )
        supplied_browser_headers = parse_renewal_browser_headers(renewal_request)
        stored_browser_headers = persisted.get("browser_headers")
        if not isinstance(stored_browser_headers, dict):
            stored_browser_headers = {}
        else:
            stored_browser_headers = parse_renewal_browser_headers(
                json.dumps({"browser_headers": stored_browser_headers})
            )
        self.browser_headers = (
            stored_browser_headers
            if prefer_persisted and stored_browser_headers
            else supplied_browser_headers or stored_browser_headers
        )
        self.browser_headers.setdefault("user-agent", _DEFAULT_BROWSER_USER_AGENT)
        self.browser_headers.setdefault("referer", MUSIC_HOME_URL)
        self._seed_session_cookies()

        if not self.headers and not self.renewal_cookies:
            raise ValueError(
                "paste a signed-in Amazon Music config.json or /pandaToken request; the config "
                "response is an optional bootstrap"
            )

    @staticmethod
    def _number(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _response_json(response, label: str) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise AmazonMusicWebAuthError(f"Amazon Music {label} returned a non-JSON response.") from exc
        if not isinstance(body, dict):
            raise AmazonMusicWebAuthError(f"Amazon Music {label} returned an invalid response.")
        return body

    @staticmethod
    def _cookie_domain(name: str) -> str:
        return ".music.amazon.com" if name in _MUSIC_SCOPED_COOKIES else ".amazon.com"

    def _session_cookie_jar(self):
        jar = getattr(self.session, "cookies", None)
        return jar if hasattr(jar, "set") and hasattr(jar, "clear") else None

    @staticmethod
    def _clear_jar_cookie(jar, cookie) -> None:
        try:
            jar.clear(domain=cookie.domain, path=cookie.path, name=cookie.name)
        except (KeyError, ValueError):
            pass

    def _seed_session_cookies(self) -> None:
        jar = self._session_cookie_jar()
        if jar is None:
            return
        for cookie in list(jar):
            if str(cookie.name).casefold() in _ALLOWED_RENEWAL_COOKIES:
                self._clear_jar_cookie(jar, cookie)
        for name, value in self.renewal_cookies.items():
            jar.set(
                name,
                value,
                domain=self._cookie_domain(name),
                path="/",
                secure=True,
            )

    def _sync_response_cookies(self, response) -> None:
        session_jar = self._session_cookie_jar()
        if session_jar is not None:
            refreshed: dict[str, str] = {}
            for cookie in session_jar:
                name = str(cookie.name).casefold()
                value = str(cookie.value or "").strip()
                if name not in _ALLOWED_RENEWAL_COOKIES or not value:
                    continue
                expected_domain = self._cookie_domain(name).lstrip(".")
                actual_domain = str(cookie.domain or "").lstrip(".").casefold()
                # Redirect targets must never be able to smuggle a familiar
                # cookie name into persisted state and have it widened onto an
                # Amazon domain the next time the session jar is seeded.
                if actual_domain != expected_domain:
                    continue
                refreshed[name] = value
            self.renewal_cookies = refreshed
            return

        # Lightweight test doubles may not expose a session jar. Preserve the
        # previous response-cookie fallback for those callers, including empty
        # values that explicitly revoke an existing cookie.
        for item in [*getattr(response, "history", []), response]:
            jar = getattr(item, "cookies", None)
            if jar is None:
                continue
            try:
                values = jar.get_dict()
            except AttributeError:
                try:
                    values = dict(jar)
                except (TypeError, ValueError):
                    continue
            for name, value in values.items():
                key = str(name).strip().casefold()
                if key not in _ALLOWED_RENEWAL_COOKIES:
                    continue
                if value is None or not str(value).strip():
                    self.renewal_cookies.pop(key, None)
                else:
                    _add_cookie(self.renewal_cookies, key, value)

    def _cookie_kwargs(self) -> dict:
        if self._session_cookie_jar() is not None:
            return {}
        return {"cookies": self.renewal_cookies}

    def _persist_session(self) -> None:
        if not self._token_file:
            return
        state = {
            "headers": self.headers,
            "renewal_cookies": self.renewal_cookies,
            "browser_headers": self.browser_headers,
        }
        if self._expires_at:
            state["expires_at"] = self._expires_at
        write_token(self._token_file, state)

    @staticmethod
    def _authorization_context(headers: dict[str, str]) -> dict:
        authorization = str(headers.get("authorization") or "")
        if not authorization.casefold().startswith("amznmusic "):
            return {}
        try:
            return json.loads(base64.b64decode(authorization.split(None, 1)[1]))
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}

    def _api_browser_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Origin": MUSIC_HOME_URL.rstrip("/"),
            "Referer": self.browser_headers.get("referer", MUSIC_HOME_URL),
            "User-Agent": self.browser_headers.get("user-agent", _DEFAULT_BROWSER_USER_AGENT),
        }
        if self.browser_headers.get("accept-language"):
            headers["Accept-Language"] = self.browser_headers["accept-language"]
        return headers

    def _request_config(self) -> dict:
        try:
            response = self.session.post(
                self.config_endpoint,
                params={"skipToken": "false"},
                headers=self._api_browser_headers(),
                timeout=REQUEST_TIMEOUT,
                **self._cookie_kwargs(),
            )
        except requests.RequestException as exc:
            raise AmazonMusicWebAuthError(f"Amazon Music config renewal failed ({exc!r}).") from exc
        self._sync_response_cookies(response)
        if response.status_code in (400, 401, 403):
            raise _AmazonMusicRenewalRejected(
                "Amazon Music config renewal rejected the copied browser session."
            )
        response.raise_for_status()
        return self._response_json(response, "config renewal")

    def _request_panda_token(self) -> dict:
        try:
            response = self.session.get(
                self.panda_token_endpoint,
                headers=self._api_browser_headers(),
                timeout=REQUEST_TIMEOUT,
                **self._cookie_kwargs(),
            )
        except requests.RequestException as exc:
            raise AmazonMusicWebAuthError(f"Amazon Music token renewal failed ({exc!r}).") from exc
        self._sync_response_cookies(response)
        if response.status_code in (400, 401, 403):
            raise _AmazonMusicRenewalRejected(
                "Amazon Music /pandaToken rejected the copied browser session."
            )
        response.raise_for_status()
        return self._response_json(response, "token renewal")

    def _renew(
        self,
        *,
        persist: bool = True,
        require_panda_token: bool = False,
    ) -> None:
        if not self.renewal_cookies:
            raise AmazonMusicWebAuthError(
                "Amazon Music access token expired; reconnect once with a signed-in config.json or "
                "/pandaToken request "
                "to enable automatic renewal."
            )

        current = self._authorization_context(self.headers)
        has_device_context = bool(
            (self.headers.get("device-id") or current.get("deviceId"))
            and (self.headers.get("device-type") or current.get("deviceType"))
        )
        config: dict = {}
        config_requested = False
        # A newly connected session must prove the config bootstrap as well as
        # panda-token minting.  Otherwise a still-live one-hour Music cookie
        # could satisfy validation while the recovery path is already broken.
        if require_panda_token or not has_device_context:
            try:
                config = self._request_config()
            except _AmazonMusicRenewalRejected as exc:
                raise AmazonMusicWebAuthError(
                    "Amazon Music rejected the signed-in config.json request; reconnect with "
                    "a fresh complete request."
                ) from exc
            config_requested = True

        try:
            token = self._request_panda_token()
        except _AmazonMusicRenewalRejected as exc:
            if config_requested:
                raise AmazonMusicWebAuthError(
                    "Amazon Music rejected /pandaToken after replaying the signed-in browser "
                    "context; reconnect with a fresh complete config.json request."
                ) from exc
            try:
                config = self._request_config()
                config_requested = True
                token = self._request_panda_token()
            except _AmazonMusicRenewalRejected as retry_exc:
                raise AmazonMusicWebAuthError(
                    "Amazon Music rejected renewal after replaying the signed-in browser context; "
                    "reconnect with a fresh complete config.json request."
                ) from retry_exc

        panda_access_token = str(
            token.get("accessToken") or token.get("access_token") or ""
        ).strip()
        config_access_token = str(config.get("accessToken") or "").strip()
        if not panda_access_token and not config_requested:
            try:
                config = self._request_config()
                config_requested = True
                token = self._request_panda_token()
            except _AmazonMusicRenewalRejected as exc:
                raise AmazonMusicWebAuthError(
                    "Amazon Music rejected renewal after replaying the signed-in browser context; "
                    "reconnect with a fresh complete config.json request."
                ) from exc
            panda_access_token = str(
                token.get("accessToken") or token.get("access_token") or ""
            ).strip()
            config_access_token = str(config.get("accessToken") or "").strip()
        access_token = (
            panda_access_token
            if require_panda_token
            else panda_access_token or config_access_token
        )
        device_id = str(
            config.get("deviceId") or self.headers.get("device-id") or current.get("deviceId") or ""
        ).strip()
        device_type = str(
            config.get("deviceType") or self.headers.get("device-type") or current.get("deviceType") or ""
        ).strip()
        if not access_token:
            raise AmazonMusicWebAuthError(
                "Amazon Music /pandaToken did not return an access token with the copied browser "
                "context; reconnect after signing in."
            )
        if require_panda_token and not self.renewal_cookies.get("at-main-music"):
            raise AmazonMusicWebAuthError(
                "Amazon Music revoked the Music renewal cookie during validation; reconnect and "
                "copy the complete config.json request from the same signed-in browser."
            )
        if not device_id or not device_type:
            raise AmazonMusicWebAuthError(
                "Amazon Music config.json did not return device context; reload the signed-in web player "
                "and reconnect."
            )

        refreshed_config = dict(config)
        refreshed_config.update(
            {"accessToken": access_token, "deviceId": device_id, "deviceType": device_type}
        )
        self.headers = parse_web_headers(json.dumps(refreshed_config))
        expires_in = self._number(token.get("expiresIn") or token.get("expires_in"))
        self._expires_at = time.time() + expires_in if expires_in > 0 else 0
        if persist:
            self._persist_session()

    def _ensure_access(self) -> bool:
        if not self.headers or (self._expires_at and self._expires_at <= time.time() + 90):
            self._renew()
            return True
        return False

    def serialized_headers(self) -> str:
        return json.dumps(self.headers, separators=(",", ":"), sort_keys=True)

    def serialized_renewal(self) -> str:
        return json.dumps(
            {
                "browser_headers": self.browser_headers,
                "renewal_cookies": self.renewal_cookies,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _auth_error(message: str) -> bool:
        lowered = message.casefold()
        return any(
            marker in lowered
            for marker in (
                "access denied",
                "auth_",
                "authorization",
                "forbidden",
                "invalid access token",
                "not authenticated",
                "not authorized",
                "session expired",
                "token expired",
                "token_expired",
                "unauthenticated",
                "unauthorized",
            )
        )

    def execute(
        self,
        operation_name: str,
        query: str,
        variables=None,
        *,
        mutation=False,
        allow_renewal=True,
    ):
        """Execute one operation and refresh/retry once on auth rejection."""

        can_renew = allow_renewal and bool(self.renewal_cookies)
        attempts = (2 if can_renew else 1) if mutation else 5
        refreshed = self._ensure_access() if allow_renewal else False
        for attempt in range(attempts):
            headers = {
                **self.headers,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://music.amazon.com",
                "Referer": "https://music.amazon.com/",
            }
            try:
                response = self.session.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "operationName": operation_name,
                        "query": query,
                        "variables": variables or {},
                    },
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException:
                if not mutation and attempt < attempts - 1:
                    time.sleep(min(2**attempt, 20) + random.uniform(0, 1.5))
                    continue
                raise

            if response.status_code in (401, 403):
                if can_renew and not refreshed:
                    self._renew()
                    refreshed = True
                    continue
                raise AmazonMusicWebAuthError(
                    "Amazon Music renewal session expired or was rejected; reconnect with a fresh "
                    "config.json or /pandaToken request."
                )
            if not mutation and response.status_code == 429 and attempt < attempts - 1:
                time.sleep(float(response.headers.get("Retry-After") or 2**attempt) + random.uniform(0.5, 2))
                continue
            if not mutation and response.status_code >= 500 and attempt < attempts - 1:
                time.sleep(min(2**attempt, 20) + random.uniform(0, 1.5))
                continue
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError as exc:
                raise RuntimeError("Amazon Music web API returned a non-JSON response") from exc

            errors = body.get("errors") if isinstance(body, dict) else None
            if errors:
                messages = "; ".join(str(error.get("message", error)) for error in errors)
                codes = " ".join(
                    str((error.get("extensions") or {}).get("code", "")) for error in errors
                )
                if self._auth_error(f"{messages} {codes}"):
                    if can_renew and not refreshed:
                        self._renew()
                        refreshed = True
                        continue
                    raise AmazonMusicWebAuthError(
                        "Amazon Music renewal session expired or was rejected; reconnect with a fresh "
                        "config.json or /pandaToken request."
                    )
                raise RuntimeError(f"Amazon Music web API error: {messages}")
            return body.get("data") or {}
        raise RuntimeError("Amazon Music web request retry budget exhausted")

    def validate(self, *, require_renewal: bool = False) -> None:
        if require_renewal:
            # Exercise the same browser-context config/panda flow used by the
            # web player before accepting a newly pasted session. The session
            # jar must retain its Music renewal cookie and mint a distinct
            # panda token before "connected" is reported.
            # Keep the candidate session off disk until both the panda-token
            # response and the signed-in GraphQL identity have been proven.
            # Disabling execute's normal retry also prevents a hidden second
            # renewal from persisting before that identity check completes.
            self._renew(persist=False, require_panda_token=True)
        data = self.execute(
            "SongMirrorAmazonSession",
            SESSION_QUERY,
            allow_renewal=not require_renewal,
        )
        if not (data.get("user") or {}).get("id"):
            raise AmazonMusicWebAuthError(
                "Amazon Music did not recognize a signed-in user; reconnect from a signed-in web player."
            )
        if require_renewal:
            self._persist_session()
