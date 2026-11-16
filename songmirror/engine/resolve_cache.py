"""Read through sibling catalog caches and merge only profile-local edits."""

import json
import math
import os
import tempfile
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from .track_references import normalize_track_reference


MATCHING_CACHE_VERSION = 5
_LOCK = threading.RLock()
_MISSING = object()


def _read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        data = {}
    # A corrupt file must remain available for recovery, not become an empty
    # cache that the next successful playlist silently writes over.
    manual = set(data.get("manual") or [])
    migrate = bool(data) and data.get("matching_version") != MATCHING_CACHE_VERSION
    search = data.get("search", {})
    if not isinstance(search, dict) or not isinstance(data.get("isrc", {}), dict):
        raise ValueError("Resolution cache search and ISRC data must be objects")
    return {
        "isrc": {} if migrate else data.get("isrc", {}),
        "search": {key: value for key, value in search.items() if key in manual} if migrate else search,
        "manual": manual,
        "shared_exclusions": set(data.get("shared_exclusions") or []),
        "dirty": migrate,
    }


def _snapshot(cache):
    return deepcopy({key: cache[key] for key in ("isrc", "search", "manual", "shared_exclusions")})


def _catalog_id(provider, value):
    try:
        return normalize_track_reference(provider, value) or None
    except (ValueError, TypeError):
        return None


def _inherit_matches(cache):
    """Overlay positive catalog evidence without copying it into this account.

    Local choices win. Sibling manual choices outrank sibling automatic ones,
    but disagreement within the winning tier is ignored. Negative results and
    account-local identifiers never become shared evidence.
    """
    provider, paths = cache.get("_fallbacks", (None, ()))
    if not provider or not paths:
        return
    siblings = []
    for path in paths:
        try:
            siblings.append(_read(path))
        except (OSError, ValueError, TypeError, AttributeError):
            # A damaged donor is not an empty primary cache to repair/replace.
            continue
    keys = set().union(*(sibling["search"] for sibling in siblings))
    for key in keys:
        if (cache["search"].get(key) or key in cache["manual"]
                or key in cache["shared_exclusions"]):
            continue
        manual, automatic = set(), set()
        for sibling in siblings:
            found = _catalog_id(provider, sibling["search"].get(key))
            if found:
                (manual if key in sibling["manual"] else automatic).add(found)
        choices = manual or automatic
        if len(choices) == 1:
            cache["search"][key] = next(iter(choices))
            if manual:
                cache["manual"].add(key)
    shared_isrc = {}
    for sibling in siblings:
        for isrc, candidates in sibling["isrc"].items():
            if cache["isrc"].get(isrc) or not isinstance(candidates, list):
                continue
            inherited = shared_isrc.setdefault(isrc, {})
            for candidate in candidates:
                if not isinstance(candidate, dict) or any(
                    not isinstance(candidate.get(field), str) or not candidate[field].strip()
                    for field in ("name", "artist")
                ):
                    continue
                artists = candidate.get("artists")
                if artists is not None and (
                    not isinstance(artists, (str, list))
                    or (isinstance(artists, list) and any(not isinstance(artist, str) for artist in artists))
                ):
                    continue
                duration = candidate.get("duration_ms")
                try:
                    invalid_duration = duration is not None and (
                        isinstance(duration, bool) or not isinstance(duration, (int, float))
                        or not math.isfinite(duration) or duration < 0
                    )
                except OverflowError:
                    invalid_duration = True
                if invalid_duration:
                    continue
                found = _catalog_id(provider, candidate.get("id"))
                if found:
                    inherited.setdefault(found, {**candidate, "id": found})
    cache["isrc"].update({isrc: list(candidates.values()) for isrc, candidates in shared_isrc.items() if candidates})


def load_cache(cache_file, *, fallbacks=(), provider=None):
    """Load matches and remember the baseline so saves can apply only edits.

    Matching-version upgrades discard automatic results and ISRC candidates,
    while preserving the search keys explicitly chosen by the user.
    """
    with _LOCK:
        cache = _read(cache_file)
        cache["_local_baseline"] = _snapshot(cache)
        cache["_fallbacks"] = (provider, tuple(path for path in fallbacks
            if Path(path).resolve() != Path(cache_file).resolve()))
        _inherit_matches(cache)
    cache["_baseline"] = _snapshot(cache)
    return cache


def load_target_cache(target):
    """Use the selected profile's cache with safe same-provider fallbacks."""
    fallback_paths = getattr(target, "cache_fallback_files", None)
    paths = fallback_paths() if callable(fallback_paths) and getattr(target, "catalog_ids_global", True) else ()
    return load_cache(target.cache_file, fallbacks=paths,
                      provider=getattr(target, "provider", None) or getattr(target, "source", None))


@contextmanager
def _writer_lock(path):
    """Serialize the read/merge/replace across threads and CLI/server processes."""
    with _LOCK, open(str(path) + ".lock", "a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0, os.SEEK_END)
            if not lock.tell():
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _search_state(cache, key):
    return cache["search"].get(key, _MISSING), key in cache.get("manual", ())


def save_cache(cache_file, cache, *, manual_keys=()):
    """Merge this snapshot's changes into current disk data and replace atomically.

    Unchanged entries never overwrite newer values or revive deleted mappings.
    Explicit manual edits beat concurrent matches. Worker normalization of an
    existing manual choice still requires an unchanged baseline. Deletions apply only while
    the disk entry still matches the baseline, preserving concurrent corrections.
    A caller without a baseline can contribute entries, but cannot delete history.
    """
    if not cache.get("dirty", False):
        return
    path = Path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    manual_keys = set(manual_keys)
    baseline = cache.get("_baseline", {"search": {}, "isrc": {}, "manual": set(), "shared_exclusions": set()})
    local_baseline = cache.get("_local_baseline", baseline)
    with _writer_lock(path):
        merged = _read(path)
        for key in baseline["search"].keys() | cache["search"].keys():
            before = _search_state(baseline, key)
            local_before = _search_state(local_baseline, key)
            after = _search_state(cache, key)
            current = _search_state(merged, key)
            if after == before and key not in manual_keys:
                continue
            value, manual = after
            if value is _MISSING:
                if current == local_before:
                    merged["search"].pop(key, None)
                    merged["manual"].discard(key)
            elif (manual and key in manual_keys) or (current == local_before and (manual or not current[1])):
                merged["search"][key] = value
                if manual:
                    merged["manual"].add(key)
                else:
                    merged["manual"].discard(key)

        for key in baseline["isrc"].keys() | cache["isrc"].keys():
            before = baseline["isrc"].get(key, _MISSING)
            after = cache["isrc"].get(key, _MISSING)
            if after == before or merged["isrc"].get(key, _MISSING) != local_baseline["isrc"].get(key, _MISSING):
                continue
            if after is _MISSING:
                merged["isrc"].pop(key, None)
            else:
                merged["isrc"][key] = after

        before_excluded = baseline.get("shared_exclusions", set())
        after_excluded = cache.get("shared_exclusions", set())
        merged["shared_exclusions"] |= after_excluded - before_excluded
        merged["shared_exclusions"] -= before_excluded - after_excluded

        payload = {
            "matching_version": MATCHING_CACHE_VERSION,
            "isrc": merged["isrc"], "search": merged["search"],
            "manual": sorted(merged["manual"]),
        }
        if merged["shared_exclusions"]:
            payload["shared_exclusions"] = sorted(merged["shared_exclusions"])
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
                temporary = stream.name
                json.dump(payload, stream, indent=1)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)
        cache.update(merged)
        cache["dirty"] = False
        cache["_local_baseline"] = _snapshot(cache)
        _inherit_matches(cache)
        cache["_baseline"] = _snapshot(cache)
