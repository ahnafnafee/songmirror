"""Bounded artwork requests pinned to validated addresses without credentials."""

import ipaddress
import os
import socket
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from queue import Empty, Queue
from urllib.parse import urljoin, urlsplit

import requests
import urllib3

MAX_IMAGE_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT = 20
_FETCH_SLOTS = threading.BoundedSemaphore(4)
_TRUSTED = ContextVar("media_origins", default=())


def _parts(value):
    raw = str(value or "")
    if "\\" in raw or any(ord(char) < 33 or ord(char) == 127 for char in raw):
        raise ValueError("Invalid artwork URL")
    parts = urlsplit(raw)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username is not None or parts.password is not None or "%" in parts.netloc):
        raise ValueError("Invalid artwork origin")
    parts.port
    return parts


def _origin(parts):
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)


@contextmanager
def trusted_origins(origins):
    token = _TRUSTED.set(tuple(origins))
    try:
        yield
    finally:
        _TRUSTED.reset(token)


def fetch_image(url):
    # Native DNS lookups cannot be interrupted portably. Bound caller latency
    # and outstanding workers even when a resolver stalls, without waiting for
    # those workers at process shutdown. A late lookup cannot start a request.
    deadline = time.monotonic() + FETCH_TIMEOUT
    slots = _FETCH_SLOTS
    if not slots.acquire(blocking=False):
        raise ValueError("Artwork fetch capacity exceeded")
    result = Queue(maxsize=1)
    context = copy_context()

    def run():
        try:
            outcome = (True, context.run(_fetch_image, url, deadline))
        except BaseException as exc:
            outcome = (False, exc)
        finally:
            slots.release()
        result.put(outcome)

    worker = threading.Thread(target=run, name="artwork-fetch", daemon=True)
    try:
        worker.start()
    except BaseException:
        slots.release()
        raise
    try:
        ok, value = result.get(timeout=max(0, deadline - time.monotonic()))
    except Empty:
        raise ValueError("Artwork deadline exceeded") from None
    if time.monotonic() >= deadline:
        raise ValueError("Artwork deadline exceeded")
    if not ok:
        raise value
    return value


def _fetch_image(url, deadline):
    configured = [os.getenv(key, "") for key in ("SUBSONIC_URL", "JELLYFIN_URL")]
    configured += os.getenv("SONGMIRROR_MEDIA_ORIGINS", "").split(",")
    origins = set()
    for value in (*configured, *_TRUSTED.get()):
        if value:
            origins.add(_origin(_parts(value.strip())))
    current = url
    for _ in range(4):
        if time.monotonic() >= deadline:
            raise ValueError("Artwork deadline exceeded")
        parts = _parts(current)
        origin = _origin(parts)
        addresses = list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(
            parts.hostname, origin[2], type=socket.SOCK_STREAM)))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Artwork deadline exceeded")
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses) and origin not in origins:
            raise ValueError("Artwork destination is not a public or configured media origin")
        # Connect to the validated IP, retaining the original TLS and HTTP host.
        # No environment proxy, cookies, Authorization or provider session is used.
        options = {"timeout": urllib3.Timeout(total=remaining,
            connect=min(5, remaining), read=min(5, remaining)), "maxsize": 1, "block": True}
        if parts.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(addresses[0], origin[2],
                assert_hostname=parts.hostname, server_hostname=parts.hostname,
                cert_reqs="CERT_REQUIRED", ca_certs=requests.certs.where(), **options)
        else:
            pool = urllib3.HTTPConnectionPool(addresses[0], origin[2], **options)
        response = None
        try:
            target = parts.path or "/"
            if parts.query:
                target += "?" + parts.query
            response = pool.urlopen("GET", target, headers={"Host": parts.netloc,
                "User-Agent": "SongMirror", "Accept-Encoding": "identity"},
                redirect=False, retries=False, preload_content=False)
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Artwork redirect is missing a destination")
                current = urljoin(current, location)
                if time.monotonic() >= deadline:
                    raise ValueError("Artwork deadline exceeded")
                continue
            if response.status != 200:
                raise ValueError(f"Artwork returned HTTP {response.status}")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Compressed artwork is not accepted")
            if not response.headers.get("Content-Type", "").lower().startswith("image/"):
                raise ValueError("Artwork response is not an image")
            length = response.headers.get("Content-Length")
            if length and (int(length) < 0 or int(length) > MAX_IMAGE_BYTES):
                raise ValueError("Artwork is too large")
            content = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("Artwork deadline exceeded")
                chunk = response.read1(min(64 * 1024, MAX_IMAGE_BYTES + 1 - len(content)), decode_content=False)
                if not chunk:
                    return bytes(content)
                content.extend(chunk)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("Artwork is too large")
        finally:
            if response is not None:
                response.close()
            pool.close()
    raise ValueError("Artwork has too many redirects")
