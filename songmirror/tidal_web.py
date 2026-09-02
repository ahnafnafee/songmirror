"""Renewable authentication imported from TIDAL's signed-in web player.

The web player receives an ordinary OAuth token response containing a short-
lived access token and a durable refresh token.  SongMirror accepts that
response (or the older access-header-only format), keeps only the fields needed
for playlist requests, and persists refresh rotations in the private token
file.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time

import requests

from .browser_session import bearer_from, query_values, selected_headers
from .engine.config import REQUEST_TIMEOUT
from .oauth import merge_refresh, read_token, token_is_live, with_expiry, write_token

TOKEN_URL = "https://auth.tidal.com/v1/oauth2/token"
DEFAULT_TOKEN_FILE = "data/tidal_oauth.json"
AUTH_MODE = "tidal_web"

_TOKEN_LOCK = threading.Lock()


class TidalWebError(RuntimeError):
    """Base error for an imported TIDAL web-player session."""


class TidalWebRejected(TidalWebError):
    """The saved grant cannot be used again without a fresh browser capture."""


class TidalWebUnavailable(TidalWebError):
    """TIDAL could not be reached or temporarily refused the request."""


def _json_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _jwt_claims(token: str) -> dict:
    """Read non-secret routing claims without treating them as validation."""

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        parsed = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return parsed if isinstance(parsed, dict) else {}
    except (IndexError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _scope_text(value) -> str:
    if isinstance(value, str):
        return " ".join(item for item in value.split() if item)
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value if str(item))
    return ""


def _epoch_seconds(value, *, milliseconds=False) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if milliseconds:
        number /= 1000
    return int(number) if number > 0 else None


def parse_web_headers(raw: str) -> dict:
    """Minimize a web token response or a legacy OpenAPI request.

    Current captures should be the JSON response from the web player's
    ``oauth2/token`` request.  Legacy Authorization header/cURL pastes still
    work, but cannot renew because they contain no refresh token.
    """

    direct = _json_object(raw)
    nested = direct.get("accessToken") if isinstance(direct.get("accessToken"), dict) else {}

    access_token = str(
        direct.get("access_token")
        or nested.get("token")
        or ""
    ).strip()
    if not access_token:
        authorization = str(direct.get("authorization") or "").strip()
        if authorization.casefold().startswith("bearer "):
            access_token = authorization.split(None, 1)[1].strip()
        else:
            access_token = bearer_from(raw)
    if not access_token or any(char in access_token for char in "\r\n"):
        raise ValueError("TIDAL access token is empty or malformed")

    claims = _jwt_claims(access_token)
    refresh_token = str(direct.get("refresh_token") or direct.get("refreshToken") or "").strip()
    client_id = str(
        direct.get("client_id")
        or direct.get("clientId")
        or nested.get("clientId")
        or claims.get("cid")
        or claims.get("client_id")
        or ""
    ).strip()
    if any(char in refresh_token + client_id for char in "\r\n"):
        raise ValueError("TIDAL renewal credentials are malformed")

    headers = selected_headers(raw, {"x-tidal-country-code", "tidal-country-code"})
    query = query_values(raw)
    country = str(
        direct.get("country_code")
        or direct.get("countryCode")
        or claims.get("cc")
        or query.get("countryCode")
        or query.get("country_code")
        or headers.get("x-tidal-country-code")
        or headers.get("tidal-country-code")
        or "US"
    ).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("TIDAL country code must be two letters, for example US")

    scope = _scope_text(
        direct.get("scope")
        or nested.get("grantedScopes")
        or claims.get("scope")
        or claims.get("scp")
    )
    expires_at = (
        _epoch_seconds(direct.get("expires_at"))
        or _epoch_seconds(nested.get("expires"), milliseconds=True)
        or _epoch_seconds(claims.get("exp"))
    )
    if expires_at is None and direct.get("expires_in") is not None:
        relative = _epoch_seconds(direct.get("expires_in"))
        expires_at = int(time.time()) + relative if relative else None

    if expires_at is not None and expires_at <= int(time.time()) + 60 and not refresh_token:
        raise ValueError(
            "the pasted TIDAL token is expired and has no refresh token; "
            "capture the oauth2/token Response JSON after signing in"
        )
    if refresh_token and not client_id:
        raise ValueError(
            "the TIDAL token response did not expose its client id; paste the complete "
            "oauth2/token Response JSON"
        )

    result = {
        "authorization": f"Bearer {access_token}",
        "country_code": country,
    }
    if refresh_token:
        result["refresh_token"] = refresh_token
    if client_id:
        result["client_id"] = client_id
    if scope:
        result["scope"] = scope
    if expires_at is not None:
        result["expires_at"] = expires_at
    return result


def serialize_web_headers(raw: str) -> str:
    """Return the allowlisted, durable subset of a browser capture."""

    return json.dumps(parse_web_headers(raw), separators=(",", ":"), sort_keys=True)


def _session_from_context(context: dict) -> dict:
    access_token = context["authorization"].split(None, 1)[1]
    fingerprint = hashlib.sha256(
        f"{access_token}\0{context.get('refresh_token', '')}".encode()
    ).hexdigest()
    token = {
        "auth_mode": AUTH_MODE,
        "access_token": access_token,
        "country_code": context["country_code"],
        "bootstrap_fingerprint": fingerprint,
    }
    for key in ("refresh_token", "client_id", "scope", "expires_at"):
        if context.get(key) not in (None, ""):
            token[key] = context[key]
    return token


def seed_web_session(raw: str, token_file: str) -> dict:
    """Replace the on-disk session with an explicitly pasted browser grant."""

    token = _session_from_context(parse_web_headers(raw))
    write_token(token_file, token)
    return token


def _refresh_error(response) -> str:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return str(payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}")


def ensure_web_access_token(raw: str, token_file: str, *, force: bool = False) -> dict:
    """Return a live web-player token, refreshing and persisting when needed."""

    with _TOKEN_LOCK:
        bootstrap = _session_from_context(parse_web_headers(raw))
        token = read_token(token_file)
        if (
            token.get("auth_mode") != AUTH_MODE
            or token.get("bootstrap_fingerprint") != bootstrap.get("bootstrap_fingerprint")
        ):
            token = bootstrap
            write_token(token_file, token)

        if not force and token_is_live(token):
            return token

        refresh_token = str(token.get("refresh_token") or "")
        client_id = str(token.get("client_id") or "")
        if not refresh_token or not client_id:
            raise TidalWebRejected(
                "TIDAL web-player authorization expired; capture a fresh oauth2/token "
                "Response JSON in Accounts"
            )

        data = {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        scope = _scope_text(token.get("scope"))
        if scope:
            data["scope"] = scope
        try:
            response = requests.post(TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise TidalWebUnavailable(f"could not reach TIDAL's token service ({exc!r})") from exc
        if response.status_code == 429:
            raise TidalWebUnavailable("TIDAL rate limit reached while renewing; try again shortly (HTTP 429)")
        if response.status_code in (400, 401, 403):
            raise TidalWebRejected(
                f"TIDAL rejected the saved web-player renewal ({_refresh_error(response)}); "
                "capture a fresh token response in Accounts"
            )
        if not response.ok:
            raise TidalWebUnavailable(
                f"TIDAL's token service returned HTTP {response.status_code}; try again shortly"
            )
        try:
            fresh = response.json()
        except (TypeError, ValueError) as exc:
            raise TidalWebUnavailable("TIDAL's token service returned invalid JSON") from exc
        if not isinstance(fresh, dict) or not fresh.get("access_token"):
            raise TidalWebUnavailable("TIDAL's token service did not return an access token")

        merged = merge_refresh(token, with_expiry(fresh))
        merged["auth_mode"] = AUTH_MODE
        merged["client_id"] = client_id
        merged["country_code"] = token.get("country_code") or "US"
        merged["bootstrap_fingerprint"] = token["bootstrap_fingerprint"]
        write_token(token_file, merged)
        return merged
