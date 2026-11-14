"""One strict destination grammar for outbound Deezer share resolution."""

from urllib.parse import urlsplit

import requests

SHARE_LINK_HOSTS = frozenset({"deezer.page.link", "link.deezer.com"})


def share_url(value):
    raw = str(value or "").strip()
    if "://" not in raw:
        raw = "https://" + raw
    if "\\" in raw or any(ord(char) < 33 or ord(char) == 127 for char in raw):
        raise ValueError("Invalid Deezer share URL.")
    try:
        parts = urlsplit(raw)
        if (parts.scheme != "https" or parts.hostname not in SHARE_LINK_HOSTS
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or "%" in parts.netloc):
            raise ValueError
        prepared = requests.Request("HEAD", raw).prepare().url
        canonical = urlsplit(prepared)
        if (canonical.scheme, canonical.hostname, canonical.port) != (parts.scheme, parts.hostname, parts.port):
            raise ValueError
    except (ValueError, requests.RequestException) as exc:
        raise ValueError("Invalid Deezer share URL.") from exc
    return prepared


def share_location(value, *, timeout):
    response = requests.head(share_url(value), allow_redirects=False, timeout=timeout)
    response.raise_for_status()
    return response.headers.get("Location", "")
