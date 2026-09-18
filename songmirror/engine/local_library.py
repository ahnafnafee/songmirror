"""Serve mirror tracks from an existing local music library.

A track the user already has is copied into the playlist folder instead of
being fetched again, so the mirror keeps the local file's format and bitrate:
a library FLAC stays a FLAC rather than being re-acquired as a lossy copy.
Only the tracks with no local match fall through to spotDL.

Placement copies rather than hard-links, deliberately. ``finalize_folder``
stamps mtimes and backfills tags on every audio file it finds in a playlist
folder, and a hard link shares its inode with the library original, so linking
would let the mirror rewrite the user's own library files. Copying also matches
what the mirror already does, since a track in two playlists is already stored
twice.

Identification reuses the engine's own matching helpers, so a local file is
recognized by exactly the rules the rest of the engine uses.
"""

import os
import shutil
from pathlib import Path

from .logs import log_download, log_note, log_warn
from .matching import normalize_isrc, track_artist, track_key

TAG = "local"

# ponytail: one in-memory index per root per process. If the initial walk ever
# dominates a pass, replace with an mtime-keyed index next to the other
# *_cache.json files rather than making this smarter.
_INDEX_CACHE = {}


def _downloads():
    """Imported at call time: downloads imports this module, so a module-level
    import here would close the cycle."""
    from .downloads import AUDIO_EXTS, sanitize_folder
    return AUDIO_EXTS, sanitize_folder


def _tags(path):
    import mutagen
    try:
        return mutagen.File(path, easy=True)
    except Exception:
        return None


def _first(tags, key):
    """Easy-mode tags are lists; a missing or unreadable key yields ''."""
    if tags is None:
        return ""
    try:
        values = tags.get(key) or []
    except Exception:
        return ""
    if isinstance(values, str):
        return values.strip()
    return str(values[0]).strip() if values else ""


def index(root, refresh=False):
    """``{'by_isrc': {...}, 'by_key': {...}}`` over every readable audio file
    under ``root``. First writer wins, so a duplicate leaves the first copy
    found in place."""
    root = str(root)
    if not refresh and root in _INDEX_CACHE:
        return _INDEX_CACHE[root]
    exts, _ = _downloads()
    by_isrc, by_key = {}, {}
    base = Path(root)
    if not base.is_dir():
        log_warn(f"local library not found: {root}", tag=TAG)
        _INDEX_CACHE[root] = {"by_isrc": by_isrc, "by_key": by_key}
        return _INDEX_CACHE[root]
    scanned = 0
    for path in base.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
        except OSError:
            continue
        tags = _tags(path)
        if tags is None:
            continue
        scanned += 1
        isrc = normalize_isrc(_first(tags, "isrc"))
        if isrc:
            by_isrc.setdefault(isrc, str(path))
        title = _first(tags, "title")
        if title:
            artist = _first(tags, "artist") or _first(tags, "albumartist")
            by_key.setdefault(track_key(title, artist), str(path))
    log_note(f"{scanned} local file(s) indexed from {root}", tag=TAG)
    _INDEX_CACHE[root] = {"by_isrc": by_isrc, "by_key": by_key}
    return _INDEX_CACHE[root]


def find(track, idx):
    """Path of a local file for this track, or None. ISRC first, then the fuzzy
    name key, so a library rip carrying no ISRC still matches."""
    if not track:
        return None
    isrc = normalize_isrc(track.get("isrc"))
    if isrc:
        hit = idx["by_isrc"].get(isrc)
        if hit:
            return hit
    name = track.get("name") or ""
    if not name:
        return None
    return idx["by_key"].get(track_key(name, track_artist(track)))


def place(src, folder, track):
    """Copy a library file into the playlist folder in spotDL's
    ``{album-artist}/{album}/{artists} - {title}.{ext}`` layout, so
    finalize_folder matches it exactly like a downloaded file. Returns the
    placed path relative to the folder, or None."""
    _, sanitize = _downloads()
    src = Path(src)
    tags = _tags(src)
    artist = track_artist(track) or _first(tags, "artist")
    title = track.get("name") or _first(tags, "title")
    album_artist = _first(tags, "albumartist") or _first(tags, "artist") or artist
    album = _first(tags, "album") or track.get("album") or "Unknown Album"
    dest = (folder / sanitize(album_artist or "Unknown Artist") / sanitize(album)
            / (sanitize(f"{artist} - {title}") + src.suffix.lower()))
    rel = None
    try:
        rel = dest.relative_to(folder).as_posix()
    except ValueError:
        return None
    if dest.exists():
        return rel
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    except OSError as exc:
        log_warn(f"could not copy '{src.name}': {exc!r}", tag=TAG)
        return None
    return rel


def configured(root=None):
    """Whether a local library is configured. Empty means the resolver is off
    and the mirror behaves exactly as it did before."""
    value = root if root is not None else os.getenv("LOCAL_LIBRARY_DIR", "")
    return bool(str(value).strip())


def serve(folder, tracks, new_ids, root=None):
    """Place every new track the local library already holds. Returns the ids
    that still need downloading, in their original order.

    Never raises: a misconfigured or unreadable library degrades to "everything
    needs downloading" rather than failing the pass.
    """
    remaining = [str(track_id) for track_id in new_ids]
    value = root if root is not None else os.getenv("LOCAL_LIBRARY_DIR", "")
    value = str(value).strip()
    if not value or not remaining:
        return remaining
    try:
        idx = index(value)
        if not (idx["by_isrc"] or idx["by_key"]):
            return remaining
        by_id = {str(track["id"]): track for track in tracks if track.get("id")}
        still, served = [], 0
        for track_id in remaining:
            track = by_id.get(track_id)
            source = find(track, idx) if track else None
            if source and place(source, folder, track):
                served += 1
            else:
                still.append(track_id)
        if served:
            log_download(f"{served} track(s) served from the local library", tag=TAG)
        return still
    except Exception as exc:
        log_warn(f"local library lookup failed ({exc!r}); downloading instead", tag=TAG)
        return remaining
