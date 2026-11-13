"""Short-lived, single-use provider connection transactions."""

import secrets
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

COOKIE = "songmirror_authorization"
TTL = 600


def with_query(url, **values):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in values]
    return urlunsplit(parts._replace(query=urlencode(query + list(values.items()))))


class ConnectionAttempts:
    def __init__(self):
        self._pending = {}
        self._lock = threading.Lock()

    def begin(self, profile, kind, **data):
        with self._lock:
            now = time.monotonic()
            self._pending = {key: value for key, value in self._pending.items()
                             if value["expires"] > now and value["profile"] != profile}
            if len(self._pending) >= 64:
                raise ValueError("Too many pending connections. Try again later.")
            nonce = secrets.token_urlsafe(32)
            self._pending[nonce] = {"profile": profile, "kind": kind, "expires": now + TTL, **data}
            return nonce

    def get(self, nonce, profile, *, browser=None, consume=False):
        with self._lock:
            attempt = self._pending.get(nonce)
            if not attempt or attempt["profile"] != profile or attempt["expires"] <= time.monotonic():
                raise ValueError("Authorization attempt is missing or expired. Connect again.")
            if browser is not None and (not attempt.get("browser") or not browser or
                                        not secrets.compare_digest(attempt["browser"], browser)):
                raise ValueError("Authorization belongs to a different browser. Connect again.")
            if consume:
                del self._pending[nonce]
            return dict(attempt)

    def configure(self, nonce, **data):
        with self._lock:
            self._pending[nonce].update(data)

    def device(self, profile, browser, code):
        with self._lock:
            for nonce, attempt in self._pending.items():
                if (attempt["profile"] == profile and attempt["kind"] == "device"
                        and attempt["expires"] > time.monotonic() and browser
                        and secrets.compare_digest(attempt.get("browser", ""), browser)
                        and secrets.compare_digest(attempt.get("device_code", ""), code)):
                    return nonce, dict(attempt)
        raise ValueError("Device authorization is missing or belongs to another browser. Connect again.")

    def bind(self, nonce, profile, browser):
        with self._lock:
            attempt = self._pending.get(nonce)
            if not attempt or attempt["profile"] != profile or attempt["expires"] <= time.monotonic():
                raise ValueError("Authorization attempt is missing or expired. Connect again.")
            if attempt.get("browser") and not secrets.compare_digest(attempt["browser"], browser):
                raise ValueError("Authorization already started in another browser.")
            attempt["browser"] = browser
            return dict(attempt)

    def invalidate(self, profile):
        with self._lock:
            self._pending = {key: value for key, value in self._pending.items() if value["profile"] != profile}

    def clear(self):
        with self._lock:
            self._pending.clear()
