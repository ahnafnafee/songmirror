"""Helpers for importing narrowly scoped authentication from browser requests.

The account wizards accept DevTools header blocks, copied cURL commands, or
small JSON objects.  These helpers deliberately expose individual headers so
provider adapters can whitelist only what their playlist APIs need.  Cookie
jars, CSRF values, user agents, and unrelated browser metadata are never
returned implicitly.
"""

from __future__ import annotations

import base64
import json
import re
import time
from urllib.parse import parse_qs, urlparse


def header_pairs(raw: str):
    """Yield ``(name, value)`` pairs from JSON, cURL, or copied headers."""

    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        source = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else parsed
        yield from source.items()
        return

    for match in re.finditer(r"(?:^|\s)(?:-H|--header)\s+(?:'([^']*)'|\"([^\"]*)\")", raw):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if ":" in value:
            yield value.split(":", 1)

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        match = re.match(r"^([^:\s][^:]*):\s*(.+)$", line)
        if match:
            yield match.group(1), match.group(2)
            continue
        # Chromium can copy the two columns on separate lines.
        if index + 1 < len(lines) and re.fullmatch(r"[A-Za-z0-9_-]+", line):
            yield line, lines[index + 1]


def selected_headers(raw: str, allowed: set[str]) -> dict[str, str]:
    """Return only explicitly allowed, single-line headers."""

    out: dict[str, str] = {}
    folded = {name.casefold() for name in allowed}
    for name, value in header_pairs(raw):
        key = str(name).strip().casefold()
        if key not in folded or value is None:
            continue
        normalized = str(value).strip()
        if "\r" in normalized or "\n" in normalized:
            raise ValueError(f"{key} request header contains a line break")
        out[key] = normalized
    return out


def bearer_from(raw: str) -> str:
    """Extract and validate one Bearer authorization header."""

    authorization = selected_headers(raw, {"authorization"}).get("authorization", "")
    if not authorization.casefold().startswith("bearer "):
        raise ValueError("missing Bearer authorization header")
    token = authorization.split(None, 1)[1].strip()
    if not token or any(char in token for char in "\r\n"):
        raise ValueError("Bearer token is empty or malformed")
    return token


def jwt_expiry(token: str) -> int | None:
    """Read a JWT ``exp`` claim without treating it as signature validation."""

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        body = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return int(body["exp"]) if body.get("exp") is not None else None
    except (IndexError, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def jwt_scopes(token: str) -> set[str] | None:
    """Read a JWT ``scope``/``scp`` claim without validating its signature.

    The caller already received the token from a trusted provider response.  A
    missing or opaque payload returns ``None`` so capability checks can defer
    to the provider instead of mistaking an unparseable token for no scopes.
    """

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        body = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        value = body.get("scope", body.get("scp"))
        if isinstance(value, str):
            return {item for item in value.split() if item}
        if isinstance(value, list):
            return {str(item) for item in value if str(item)}
        return None
    except (AttributeError, IndexError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def bearer_is_expired(token: str, leeway: int = 60) -> bool:
    expiry = jwt_expiry(token)
    return expiry is not None and expiry <= int(time.time()) + leeway


def urls_in(raw: str):
    """Yield HTTP URLs found in plain text, JSON strings, or copied cURL."""

    seen: set[str] = set()
    for match in re.finditer(r"https?://[^\s'\"\\]+", raw):
        url = match.group(0).rstrip(",);]")
        if url not in seen:
            seen.add(url)
            yield url


def query_values(raw: str) -> dict[str, str]:
    """Collect the first value of each query parameter in pasted URLs."""

    out: dict[str, str] = {}
    for url in urls_in(raw):
        for key, values in parse_qs(urlparse(url).query).items():
            if values and key not in out:
                out[key] = values[0]
    return out
