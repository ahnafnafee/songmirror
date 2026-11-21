"""Parse explicit track references without guessing or following arbitrary URLs.

Manual input is a trust boundary: a playlist/album link or a different service's
URL must never become a catalog id. These checks validate the reference's shape;
catalog availability and account permissions remain the provider's responsibility.
"""

import re
from urllib.parse import parse_qs, unquote, unquote_plus, urlsplit


_LABELS = {
    "spotify": "Spotify", "apple": "Apple Music", "ytmusic": "YouTube Music",
    "tidal": "Tidal", "qobuz": "Qobuz", "deezer": "Deezer",
    "amazon": "Amazon Music", "lastfm": "Last.fm", "listenbrainz": "ListenBrainz",
    "soundcloud": "SoundCloud",
}
_PATTERNS = {
    "spotify": r"[A-Za-z0-9]{22}", "ytmusic": r"[A-Za-z0-9_-]{11}",
    "apple": r"[1-9][0-9]*", "tidal": r"[1-9][0-9]*",
    "qobuz": r"[1-9][0-9]*", "deezer": r"[1-9][0-9]*",
    "amazon": r"[A-Za-z0-9]{10}",
}
_AMAZON_HOSTS = {
    "music.amazon." + suffix for suffix in (
        "com", "co.uk", "de", "fr", "it", "es", "co.jp", "ca", "com.au",
        "com.br", "com.mx", "in",
    )
}


def reference_text(value):
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Paste a track link or catalog id as text.")
    text = str(value)
    if len(text) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError("That track reference contains invalid characters.")
    return text.strip()


def reference_url(raw):
    """Only ordinary web URLs, including a pasted hostname without its scheme."""
    try:
        parts = urlsplit(raw if "://" in raw else "https://" + raw)
        if (parts.scheme not in {"https", "http"} or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.port not in {None, 80, 443}):
            return None
        return parts
    except ValueError:
        return None


def _one(query, key):
    values = query.get(key, [])
    return values[0] if len(values) == 1 else ""


def normalize_track_reference(provider, value):
    raw = reference_text(value)
    if not raw:
        return ""
    label = _LABELS.get(provider, provider)
    error = f"Paste a valid {label} track link or catalog id. Album and playlist links cannot identify a track."
    pattern = _PATTERNS.get(provider)
    if provider == "listenbrainz":
        uuid = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
        match = re.fullmatch(rf"(?:(mbid|msid):)?({uuid})", raw)
        if match:
            return f"{match[1] or 'mbid'}:{match[2].lower()}"
        parts = reference_url(raw)
        if parts and parts.hostname.lower() in {"musicbrainz.org", "www.musicbrainz.org"}:
            match = re.fullmatch(rf"/recording/({uuid})/?", parts.path)
            if match:
                return f"mbid:{match[1].lower()}"
        raise ValueError("Paste a MusicBrainz recording link, recording MBID, or msid:UUID. Album and artist links cannot identify a recording.")
    if pattern and re.fullmatch(pattern, raw):
        return raw.upper() if provider == "amazon" else raw
    if provider == "lastfm" and raw.count("\u241f") == 1:
        artist, title = (part.strip() for part in raw.split("\u241f"))
        if artist and title:
            return f"{artist}\u241f{title}"
        raise ValueError("A Last.fm track id must contain both artist and title, separated by \u241f.")
    if provider == "soundcloud":
        match = re.fullmatch(r"(?:soundcloud:tracks:)?([1-9][0-9]*)", raw)
        if match:
            return f"soundcloud:tracks:{match[1]}"
        raise ValueError("Enter a SoundCloud track URN or numeric track ID.")
    if provider == "spotify":
        match = re.fullmatch(r"spotify:track:([A-Za-z0-9]{22})", raw)
        if match:
            return match[1]
    parts = reference_url(raw)
    if parts is None:
        raise ValueError(error)
    host = parts.hostname.lower()
    path = unquote(parts.path).rstrip("/")
    query = parse_qs(parts.query, keep_blank_values=True)
    candidate = ""
    if provider == "spotify" and host in {"open.spotify.com", "play.spotify.com"}:
        match = re.fullmatch(r"/(?:intl-[A-Za-z-]+/)?(?:embed/)?track/([A-Za-z0-9]{22})", path)
        candidate = match[1] if match else ""
    elif provider == "ytmusic":
        if host in {"youtube.com", "www.youtube.com", "music.youtube.com", "m.youtube.com"}:
            if path == "/watch":
                candidate = _one(query, "v")
            else:
                match = re.fullmatch(r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})", path)
                candidate = match[1] if match else ""
        elif host in {"youtu.be", "www.youtu.be"}:
            candidate = path.removeprefix("/")
    elif provider == "apple" and host in {"music.apple.com", "itunes.apple.com"}:
        match = re.fullmatch(r"/(?:[a-zA-Z]{2}/)?song/(?:[^/]+/)?([0-9]+)", path)
        if match:
            candidate = match[1]
        elif re.fullmatch(r"/(?:[a-zA-Z]{2}/)?album/(?:[^/]+/)?[0-9]+", path):
            candidate = _one(query, "i")
    elif provider == "tidal" and host in {"tidal.com", "www.tidal.com", "listen.tidal.com"}:
        match = re.fullmatch(r"/(?:browse/)?track/([0-9]+)", path)
        candidate = match[1] if match else ""
    elif provider == "qobuz" and host in {"open.qobuz.com", "play.qobuz.com"}:
        route = path or ("/" + parts.fragment.lstrip("/"))
        match = re.fullmatch(r"/track/([0-9]+)", route)
        candidate = match[1] if match else ""
    elif provider == "deezer" and host in {"deezer.com", "www.deezer.com"}:
        match = re.fullmatch(r"/(?:[a-zA-Z]{2}/)?track/([0-9]+)", path)
        candidate = match[1] if match else ""
    elif provider == "deezer" and host == "link.deezer.com" and parts.scheme == "https":
        destination = _one(query, "dest")
        dest_url = reference_url(destination) if destination else None
        if dest_url and dest_url.hostname.lower() in {"deezer.com", "www.deezer.com"}:
            return normalize_track_reference(provider, destination)
    elif provider == "amazon" and host in _AMAZON_HOSTS:
        match = re.fullmatch(r"/tracks/([A-Za-z0-9]{10})", path)
        if match:
            candidate = match[1]
        elif re.fullmatch(r"/albums/[A-Za-z0-9]{10}", path):
            candidate = _one(query, "trackAsin")
    elif provider == "lastfm" and host in {"last.fm", "www.last.fm"}:
        # Decode each name independently so an escaped slash stays inside a name.
        match = re.fullmatch(r"/(?:[a-zA-Z]{2}/)?music/([^/]+)/_/([^/]+)/?", parts.path.rstrip("/"))
        if match:
            artist, title = (reference_text(unquote_plus(part)) for part in match.groups())
            if artist and title and "\u241f" not in artist + title:
                return f"{artist}\u241f{title}"
    elif provider not in _LABELS:
        # Server-local/custom providers own their opaque ids, never arbitrary URLs.
        if "://" not in raw and not any(c.isspace() for c in raw) and "/" not in raw:
            return raw
    if candidate and pattern and re.fullmatch(pattern, candidate):
        return candidate.upper() if provider == "amazon" else candidate
    if provider == "lastfm":
        error = "Paste a Last.fm track link or an artist\u241ftitle id."
    raise ValueError(error)
