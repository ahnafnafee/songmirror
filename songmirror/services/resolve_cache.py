"""Read and edit the per-provider resolution caches from the UI.

Each provider caches how a source track resolved to a catalog id on its side.
An entry with an id is a match the sync and transfer engines will reuse forever;
an entry with no id is a NEGATIVE result, and it is just as sticky, so a track
that failed to match once is never searched again until the entry is removed.
This store is what makes both visible and correctable without hand-editing JSON
on the server.

Keys are the engine's normalized `track_key` ("<loose name>|<normalized
artist>"), not the original display text, so rows are shown lower-cased and
stripped. That is what the cache actually holds; inventing prettier text would
mean showing something the matcher never sees.
"""

import os

from ..engine.config import parse_args
from ..engine.runner import load_cache, save_cache
from ..engine.targets import provider_ids, target_class
from .playlist_links import provider_label, track_url

# Row kinds the UI can ask for.
KINDS = ("all", "manual", "unmatched")


class ResolveCacheError(RuntimeError):
    """A resolve-cache request that cannot be served, with user-facing copy."""


class ResolveCacheBusy(ResolveCacheError):
    """A write refused because a sync pass owns the cache right now."""


def _split_key(key):
    """("name", "artist") for a stored key.

    A key carries exactly one separator, because both halves are built by
    `normalize_text`, which turns every non-word character into a space. A
    legacy key that predates that guarantee keeps its extra separator in the
    artist rather than losing it.
    """
    name, _, artist = str(key).partition("|")
    return name, artist


class ResolveCacheStore:
    """The resolution caches as an editable table, one file per provider."""

    def __init__(self, settings, sync=None, profiles=None):
        self._settings = settings
        # Consulted only to refuse writes while a pass holds the cache in memory.
        self._sync = sync
        self._profiles = profiles

    def _provider(self, identity):
        return self._profiles.provider_of(identity) if self._profiles else identity

    # -- paths -----------------------------------------------------------------
    def _path(self, provider_id):
        """Where a provider's cache lives, or None when it has no cache at all.

        Read through the target class so this opens exactly the file the engine
        writes, including any operator override of its environment variable.
        """
        provider = self._provider(provider_id)
        cls = target_class(provider)
        if cls is None:
            return None
        if self._profiles is None:
            self._settings.apply_to_env()
            return cls.resolve_cache_path(parse_args([]))
        profile = self._profiles.resolve(provider_id)
        if profile is None:
            return None
        with self._profiles.activate(profile.id):
            opts = parse_args([])
            if provider == "spotify":
                opts.spotify_cache_file = os.getenv("SPOTIFY_CACHE_FILE", opts.spotify_cache_file)
            elif provider == "apple":
                opts.cache_file = os.getenv("APPLE_CACHE_FILE", opts.cache_file)
            return cls.resolve_cache_path(opts)

    def _load(self, provider_id):
        path = self._path(provider_id)
        if path is None:
            raise ResolveCacheError(
                f"{provider_label(self._provider(provider_id))} does not keep a resolve cache.")
        return path, load_cache(path)

    # -- reads -----------------------------------------------------------------
    def providers(self):
        """One row per provider whose cache file exists, with its counts.

        A provider that has never resolved anything has no file and is left out,
        so the page shows the services actually in use rather than seven tabs of
        zeroes.
        """
        out = []
        identities = (
            [profile.id for profile in self._profiles.list()]
            if self._profiles else provider_ids()
        )
        for provider_id in identities:
            path = self._path(provider_id)
            if path is None or not os.path.exists(path):
                continue
            cache = load_cache(path)
            search = cache["search"]
            row = {
                "id": provider_id,
                "name": (
                    self._profiles.display_name(
                        provider_id, provider_label(self._provider(provider_id))
                    )
                    if self._profiles else provider_label(provider_id)
                ),
                "total": len(search),
                "manual": sum(1 for key in cache["manual"] if key in search),
                "unmatched": sum(1 for value in search.values() if not value),
            }
            if self._profiles is not None:
                row["provider"] = self._provider(provider_id)
            out.append(row)
        return out

    def entries(self, provider_id, *, query="", kind="all", offset=0, limit=50):
        """One page of `{total, entries}` for a provider, filtered and searched.

        Paged here rather than in the browser because a live cache runs to a few
        thousand rows per provider.
        """
        if kind not in KINDS:
            raise ResolveCacheError(f"Unknown filter '{kind}'.")
        _path, cache = self._load(provider_id)
        needle = str(query or "").strip().casefold()
        rows = []
        for key, target_id in cache["search"].items():
            manual = key in cache["manual"]
            if kind == "manual" and not manual:
                continue
            if kind == "unmatched" and target_id:
                continue
            if needle and needle not in key.casefold() and needle not in str(target_id or "").casefold():
                continue
            name, artist = _split_key(key)
            rows.append({
                "key": key,
                "name": name,
                "artist": artist,
                "target_id": "" if target_id is None else str(target_id),
                "manual": manual,
                "url": track_url(self._provider(provider_id), target_id),
            })
        rows.sort(key=lambda row: (row["name"], row["artist"]))
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 200))
        return {"total": len(rows), "entries": rows[offset:offset + limit]}

    # -- writes ----------------------------------------------------------------
    def _guard(self):
        """Refuse a write while a sync pass is running.

        A pass loads the cache once, holds it for its whole duration, and writes
        it back at the end, so an edit landing in between would be overwritten
        without a trace. Refusing is better than queuing behind a pass that can
        run for many minutes.
        """
        if self._sync is not None and self._sync.status().get("running"):
            raise ResolveCacheBusy(
                "A sync is running and owns the resolve caches. Try again once it finishes.")

    def set(self, provider_id, key, target_id):
        """Point a key at a catalog id by hand, and record that a person chose it."""
        self._guard()
        path, cache = self._load(provider_id)
        if key not in cache["search"]:
            raise ResolveCacheError("That mapping is no longer in the cache. Refresh the list.")
        provider = self._provider(provider_id)
        cls = target_class(provider)
        try:
            normalized = cls.normalize_manual_track_id(target_id)
        except ValueError as exc:
            raise ResolveCacheError(str(exc)) from exc
        if not normalized:
            raise ResolveCacheError(
                f"Paste a {provider_label(provider)} track link or id.")
        cache["search"][key] = normalized
        cache["manual"].add(key)
        cache["dirty"] = True
        save_cache(path, cache)
        name, artist = _split_key(key)
        return {
            "key": key,
            "name": name,
            "artist": artist,
            "target_id": normalized,
            "manual": True,
            "url": track_url(provider, normalized),
        }

    def delete(self, provider_id, key):
        """Forget a mapping so the next pass resolves the track again."""
        self._guard()
        path, cache = self._load(provider_id)
        if key not in cache["search"]:
            return {"ok": False}
        del cache["search"][key]
        cache["manual"].discard(key)
        cache["dirty"] = True
        save_cache(path, cache)
        return {"ok": True}

    def clear_unmatched(self, provider_id):
        """Drop every "searched, found nothing" entry for one provider.

        These are the entries that make a miss permanent, and a live cache holds
        thousands of them, so removing them one row at a time is not an option.

        Both negative caches go: the `search` misses the table lists, and the
        empty ISRC lookups, which are just as sticky and block the far more
        accurate ISRC path from ever being retried.
        """
        self._guard()
        path, cache = self._load(provider_id)
        stale = [key for key, value in cache["search"].items() if not value]
        for key in stale:
            del cache["search"][key]
            cache["manual"].discard(key)
        stale_isrc = [key for key, value in cache["isrc"].items() if not value]
        for key in stale_isrc:
            del cache["isrc"][key]
        if stale or stale_isrc:
            cache["dirty"] = True
            save_cache(path, cache)
        return {"removed": len(stale), "removed_isrc": len(stale_isrc)}
