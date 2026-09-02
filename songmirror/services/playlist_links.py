"""How a provider is named and addressed on the public web.

`parse_playlist_link` turns a pasted playlist link into (provider, playlist id)
so a transfer can read a playlist the account does not own. `external_url` and
`track_url` build the reverse, so a browse row or a resolve-mapping links back
out to the provider. `provider_label` is the display name those messages use.

All three live here so the URL shapes and service names have one home rather
than being restated per service module and again in the frontend.
"""

import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

import requests

from ..engine.config import REQUEST_TIMEOUT
from ..engine.targets.deezer import SHARE_LINK_HOSTS as _DEEZER_SHARE_HOSTS

# Shown when a paste does not resolve to a playlist on any known service.
PLAYLIST_LINK_HINT = (
    "That does not look like a playlist link. Paste a playlist URL from Spotify, "
    "Apple Music, YouTube Music, TIDAL, Deezer, Qobuz, or Amazon Music."
)


class PlaylistLinkError(ValueError):
    """A paste that names a service but cannot be turned into a playlist id."""


# host suffix -> provider id. Matched against the URL's hostname, longest first,
# so a more specific host wins over a bare domain.
_HOSTS = {
    "open.spotify.com": "spotify",
    "play.spotify.com": "spotify",
    "spotify.com": "spotify",
    "music.apple.com": "apple",
    "music.youtube.com": "ytmusic",
    "youtube.com": "ytmusic",
    "youtu.be": "ytmusic",
    "tidal.com": "tidal",
    "listen.tidal.com": "tidal",
    "deezer.com": "deezer",
    "link.deezer.com": "deezer",
    "qobuz.com": "qobuz",
    "open.qobuz.com": "qobuz",
    "play.qobuz.com": "qobuz",
    "music.amazon.com": "amazon",
}

# Amazon runs one host per marketplace (music.amazon.co.uk, .de, .co.jp, ...),
# so it is matched by prefix instead of being enumerated.
_AMAZON_HOST_PREFIX = "music.amazon."

_SPOTIFY_PATH_RE = re.compile(r"/playlist/([A-Za-z0-9]+)")
_SPOTIFY_URI_RE = re.compile(r"^spotify:playlist:([A-Za-z0-9]+)$", re.IGNORECASE)
_APPLE_PATH_RE = re.compile(r"/playlist/(?:[^/]+/)?(pl\.[A-Za-z0-9._-]+)")
_TIDAL_PATH_RE = re.compile(r"/playlist/([0-9a-fA-F-]{16,})")
_DEEZER_PATH_RE = re.compile(r"/playlist/(\d+)")
_QOBUZ_PATH_RE = re.compile(r"/playlist/(?:[^/]*?-)?(\d+)")
_AMAZON_PATH_RE = re.compile(r"/(?:user-playlists|playlists)/([A-Za-z0-9._-]+)")


def _host(parts):
    return (parts.hostname or "").lower().removeprefix("www.")


def _provider_for(host):
    if host.startswith(_AMAZON_HOST_PREFIX):
        return "amazon"
    if host in _HOSTS:
        return _HOSTS[host]
    # A regional or app subdomain (listen.tidal.com, embed.music.apple.com) still
    # ends in the service's registrable domain.
    for known, provider in sorted(_HOSTS.items(), key=lambda kv: -len(kv[0])):
        if host.endswith("." + known):
            return provider
    return None


def _ytmusic_id(parts):
    """YouTube exposes a playlist as ?list=<id>, and its browse route as VL<id>."""
    listed = parse_qs(parts.query).get("list") or []
    if listed and listed[0]:
        return listed[0]
    match = re.search(r"/browse/VL([A-Za-z0-9_-]+)", parts.path)
    return match.group(1) if match else None


def _resolve_share_link(url, resolve_redirect):
    """Follow a Deezer share link one hop to the real playlist URL."""
    location = resolve_redirect(url)
    if not location:
        raise PlaylistLinkError(
            "Could not resolve that Deezer share link. Open it once and paste the "
            "full playlist URL instead."
        )
    return location


def _head_location(url):
    try:
        response = requests.head(url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException:
        return None
    return response.headers.get("Location", "")


def parse_playlist_link(text, *, resolve_redirect=_head_location):
    """(provider_id, playlist_id) for a pasted playlist link, or None.

    None means "not a playlist link on any service we know". A link that names a
    known service but points at something else (an album, a track, a profile)
    raises PlaylistLinkError, because that distinction is worth telling the user.
    """
    raw = unquote(str(text or "").strip())
    if not raw:
        return None

    uri = _SPOTIFY_URI_RE.match(raw)
    if uri:
        return "spotify", uri.group(1)

    try:
        parts = urlsplit(raw if "//" in raw else f"https://{raw}")
    except ValueError:
        return None
    provider = _provider_for(_host(parts))
    if provider is None:
        return None

    if provider == "deezer" and _host(parts) in _DEEZER_SHARE_HOSTS:
        return parse_playlist_link(
            _resolve_share_link(raw, resolve_redirect),
            resolve_redirect=resolve_redirect,
        )

    playlist_id = _playlist_id(provider, parts)
    if not playlist_id:
        raise PlaylistLinkError(
            f"That {_LABELS[provider]} link is not a playlist. Open the playlist "
            "itself and copy its link."
        )
    return provider, playlist_id


def _playlist_id(provider, parts):
    if provider == "ytmusic":
        return _ytmusic_id(parts)
    pattern = {
        "spotify": _SPOTIFY_PATH_RE,
        "apple": _APPLE_PATH_RE,
        "tidal": _TIDAL_PATH_RE,
        "deezer": _DEEZER_PATH_RE,
        "qobuz": _QOBUZ_PATH_RE,
        "amazon": _AMAZON_PATH_RE,
    }[provider]
    match = pattern.search(parts.path)
    return match.group(1) if match else None


_LABELS = {
    "spotify": "Spotify",
    "apple": "Apple Music",
    "ytmusic": "YouTube Music",
    "tidal": "TIDAL",
    "deezer": "Deezer",
    "qobuz": "Qobuz",
    "amazon": "Amazon Music",
    "jellyfin": "Jellyfin",
}


def provider_label(provider_id):
    return _LABELS.get(provider_id, provider_id)


def external_url(provider_id, kind, item_id):
    """Stable first-party web URL for a provider playlist or track."""
    item_id = quote(str(item_id), safe="")
    routes = {
        "spotify": f"https://open.spotify.com/{kind}/{item_id}",
        "tidal": f"https://listen.tidal.com/{kind}/{item_id}",
        "qobuz": f"https://open.qobuz.com/{kind}/{item_id}",
        "deezer": f"https://www.deezer.com/{kind}/{item_id}",
        "amazon": f"https://music.amazon.com/{kind}s/{item_id}",
        "apple": (
            f"https://music.apple.com/library/playlist/{item_id}"
            if kind == "playlist"
            else f"https://music.apple.com/song/{item_id}"
        ),
        "ytmusic": (
            f"https://music.youtube.com/playlist?list={item_id}"
            if kind == "playlist"
            else f"https://music.youtube.com/watch?v={item_id}"
        ),
    }
    return routes.get(provider_id, "")


def track_url(provider_id, track_id):
    """Web link for a resolved catalog id, or "" when there is nothing to link to
    (an unmatched cache entry, or a service with no track pages)."""
    return external_url(provider_id, "track", track_id) if track_id else ""
