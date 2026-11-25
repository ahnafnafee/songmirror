"""SoundCloud's public API and rotating user OAuth credentials."""

import hashlib
import json
import math
import os
import time
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

import requests

from .engine.config import REQUEST_TIMEOUT, required_env
from .services.private_files import write_private

API = "https://api.soundcloud.com"
AUTHORIZE = "https://secure.soundcloud.com/authorize"
TOKEN = "https://secure.soundcloud.com/oauth/token"
HEADERS = {"Accept": "application/json; charset=utf-8"}
TOKEN_FILENAME = "soundcloud_oauth.json"
_LOCK = RLock()


class SoundCloudError(RuntimeError):
    pass


class SoundCloudAuthError(SoundCloudError):
    pass


class SoundCloudTransient(SoundCloudError):
    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class SoundCloudNotFound(SoundCloudError):
    pass


def read_private(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise SoundCloudError("Could not read stored SoundCloud authorization") from exc
    if not isinstance(payload, dict):
        raise SoundCloudError("Invalid stored SoundCloud authorization")
    return payload


def _request(method, url, **kwargs):
    try:
        return requests.request(method, url, timeout=REQUEST_TIMEOUT,
                                allow_redirects=False, **kwargs)
    except requests.RequestException as exc:
        raise SoundCloudTransient("Could not reach SoundCloud") from exc


def _json(response):
    try:
        return response.json()
    except ValueError as exc:
        raise SoundCloudTransient("SoundCloud returned invalid JSON") from exc


def api_result(status, headers, decode_json):
    if status == 401:
        raise SoundCloudAuthError("SoundCloud authorization has expired")
    if status in (404, 410):
        raise SoundCloudNotFound(f"SoundCloud returned HTTP {status}")
    if status == 429:
        try:
            delay = float(headers.get("Retry-After", ""))
        except (TypeError, ValueError):
            delay = 30
        if not math.isfinite(delay) or delay <= 0:
            delay = 30
        raise SoundCloudTransient("SoundCloud returned HTTP 429", retry_after=delay)
    if status >= 500:
        raise SoundCloudTransient(f"SoundCloud returned HTTP {status}")
    if not 200 <= status < 300:
        raise SoundCloudError(f"SoundCloud returned HTTP {status}")
    if status == 204:
        return None
    try:
        return decode_json()
    except ValueError as exc:
        raise SoundCloudTransient("SoundCloud returned invalid JSON") from exc


class SoundCloud:
    _linked_partitioning = "true"

    def __init__(self, token_file):
        self.token_file = Path(token_file)
        self.client_id = required_env("SOUNDCLOUD_CLIENT_ID")
        self._client_secret = required_env("SOUNDCLOUD_CLIENT_SECRET")
        self.app_key = hashlib.sha256(self.client_id.encode()).hexdigest()

    def _exchange(self, **form):
        response = _request("POST", TOKEN, headers=HEADERS, data={
            "client_id": self.client_id, "client_secret": self._client_secret, **form,
        })
        if response.status_code == 429 or response.status_code >= 500:
            raise SoundCloudTransient(f"SoundCloud OAuth returned HTTP {response.status_code}")
        if response.status_code != 200:
            raise SoundCloudAuthError(f"SoundCloud OAuth returned HTTP {response.status_code}")
        body = _json(response)
        try:
            access, refresh = body["access_token"], body["refresh_token"]
            expires = float(body["expires_in"])
            if not isinstance(access, str) or not isinstance(refresh, str) or not (
                access and refresh and 0 < expires < float("inf")
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise SoundCloudError("SoundCloud returned an incomplete token response") from exc
        return {"access_token": access, "refresh_token": refresh,
                "expires_at": time.time() + expires, "app_key": self.app_key}

    def authorize(self, code, verifier, redirect_uri):
        with _LOCK:
            tokens = self._exchange(grant_type="authorization_code", code=code,
                                    code_verifier=verifier, redirect_uri=redirect_uri)
            profile = self._api_request("GET", f"{API}/me", tokens["access_token"])
            if not isinstance(profile, dict) or not profile.get("urn") or not profile.get("username"):
                raise SoundCloudError("SoundCloud returned no account profile")
            write_private(self.token_file, tokens)
            return profile

    def configured(self):
        return bool(read_private(self.token_file).get("refresh_token"))

    def _access_token(self, *, rejected=None):
        with _LOCK:
            tokens = read_private(self.token_file)
            if tokens.get("app_key") != self.app_key or not tokens.get("refresh_token"):
                raise SoundCloudAuthError("Connect your SoundCloud account again")
            access = tokens.get("access_token")
            if access and access != rejected and tokens.get("expires_at", 0) > time.time() + 30:
                return access
            tokens = self._exchange(grant_type="refresh_token", refresh_token=tokens["refresh_token"])
            write_private(self.token_file, tokens)
            return tokens["access_token"]

    @staticmethod
    def _api_request(method, url, access, **kwargs):
        response = _request(method, url, headers={**HEADERS, "Authorization": f"OAuth {access}"},
                            **kwargs)
        return api_result(response.status_code, getattr(response, "headers", {}), response.json)

    def request(self, method, path, **kwargs):
        url = API + path if path.startswith("/") and not path.startswith("//") else path
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "api.soundcloud.com":
            raise SoundCloudTransient("Invalid SoundCloud API page URL")
        access = self._access_token()
        try:
            return self._api_request(method, url, access, **kwargs)
        except SoundCloudAuthError:
            return self._api_request(method, url, self._access_token(rejected=access), **kwargs)

    def collection(self, path, *, pages=True, **params):
        params["linked_partitioning"] = self._linked_partitioning
        seen = set()
        while path:
            if path in seen:
                raise SoundCloudTransient("SoundCloud repeated an API page")
            seen.add(path)
            body = self.request("GET", path, params=params)
            if (not isinstance(body, dict) or not isinstance(body.get("collection"), list)
                    or any(not isinstance(item, dict) for item in body["collection"])):
                raise SoundCloudTransient("SoundCloud returned an incomplete collection")
            yield from body["collection"]
            if not pages:
                return
            path = body.get("next_href")
            if path is not None and not isinstance(path, str):
                raise SoundCloudTransient("Invalid SoundCloud API page URL")
            params = None

    def disconnect(self):
        with _LOCK:
            try:
                if self.configured():
                    self.request("POST", "/disconnect")
            except SoundCloudAuthError:
                # An invalid or revoked authorization can still be removed locally.
                pass
            self.token_file.unlink(missing_ok=True)
