"""Apple Music target — via the web player's amp-api (captured web tokens, no
Apple Developer account). Writes go to the same endpoints music.apple.com uses.
"""

import random
import time

import requests

from ..config import AMP, REQUEST_TIMEOUT, polite_sleep, required_env
from ..logs import log, log_warn
from ..matching import normalize_text, romanized, score_candidate
from .base import MirrorTarget, TargetAuthError, TargetTransientError
from .provider_utils import source_playlist_details

# playlist_id -> (lastModifiedDate, track_count): in-process cache so the browse
# doesn't re-issue a meta.total call for an unchanged Apple playlist (library
# playlists carry no trackCount attribute, so each count is a live lookup).
_COUNT_CACHE = {}
_PUBLIC_SEARCH_URL = "https://itunes.apple.com/search"
_FAVORITES_URL = "https://api.music.apple.com/v1/me/favorites"
# Apple's documented public Search API is limited to roughly 20 calls/minute.
# It is only a fallback after amp-api throttles, so pace it independently.
_PUBLIC_SEARCH_INTERVAL_S = 3.1


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _headers():
    bearer = required_env("APPLE_BEARER_TOKEN")
    if bearer.lower().startswith("bearer "):
        bearer = bearer[7:]
    return {
        "Authorization": f"Bearer {bearer}",
        "Media-User-Token": required_env("APPLE_USER_TOKEN"),
        "Origin": "https://music.apple.com",
        "Referer": "https://music.apple.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
    }


def _normalized_playlist_track(track):
    attrs = track.get("attributes", {})
    play_params = attrs.get("playParams", {})
    artwork = attrs.get("artwork") or {}
    image = str(artwork.get("url") or "").replace("{w}", "128").replace("{h}", "128")
    return {
        "relationship_id": track.get("id"),
        "catalog_id": play_params.get("catalogId") or play_params.get("id"),
        "name": attrs.get("name", ""),
        "artist": attrs.get("artistName", ""),
        "album": attrs.get("albumName"),
        "album_position": attrs.get("trackNumber"),
        "duration_ms": attrs.get("durationInMillis"),
        "isrc": attrs.get("isrc"),
        "added_at": attrs.get("dateAdded") or "",
        "image": image,
    }


class AppleMusicTarget(MirrorTarget):
    name = "Apple Music"
    tag = "apple"
    source = "apple"
    favorite_tracks_name = "Favorite Songs"

    def __init__(self, storefront, cache_file):
        self.storefront = storefront or "us"  # empty -> a broken /catalog//search URL (400)
        self.cache_file = cache_file
        # One pooled session (keep-alive) for the whole pass — opening a fresh
        # TCP/TLS connection per request is what triggers Apple's connection
        # resets under the ~100+ calls a big playlist needs. Headers read env
        # now so re-captured tokens are picked up per pass.
        self._session = requests.Session()
        self._session.headers.update(_headers())
        self._search_throttled = False  # set once catalog search rate-limits; defer the rest of the pass
        self._write_not_before = 0.0
        self._public_search_not_before = 0.0
        self._validated_catalog_ids = {}
        self._resolved_catalog_context = {}
        self._added_catalog_ids = {}

    # -- HTTP ------------------------------------------------------------------
    def _rebuild_session(self):
        """Replace a possibly-poisoned keep-alive connection without losing auth.

        Apple occasionally keeps returning 5xx on one pooled route while a new
        connection succeeds immediately. GETs are idempotent, so reopening the
        session midway through their existing retry budget is safe.
        """
        headers = dict(self._session.headers)
        try:
            self._session.close()
        except Exception:
            pass
        self._session = requests.Session()
        self._session.headers.update(headers)

    def _request(self, method, url, *, params=None, json_body=None, ok404=False):
        """One amp-api call over the pooled session. GETs retry with exponential
        backoff on network resets / 5xx; 429s back off on every method (a
        rate-limited call never executed); other mutation failures are
        single-shot — a lost add/remove self-heals next pass, a blindly retried
        one could double-apply."""
        attempts = 5
        for attempt in range(attempts):
            try:
                r = self._session.request(method, url, params=params, json=json_body, timeout=REQUEST_TIMEOUT)
            except requests.RequestException:
                # Connection reset / blip: retry GETs (idempotent) with backoff.
                if method == "GET" and attempt < attempts - 1:
                    time.sleep(min(2 ** attempt, 20) + random.uniform(0, 2))
                    continue
                raise
            if r.status_code in (401, 403):
                raise TargetAuthError(
                    f"Apple rejected {method} {url.split('/v1/')[-1]} ({r.status_code}). "
                    "Re-capture APPLE_BEARER_TOKEN / APPLE_USER_TOKEN from music.apple.com DevTools."
                )
            if r.status_code == 404 and ok404:
                return None
            if r.status_code == 429:
                # 429 proves the mutation did not run, so a retry is safe. Give
                # one blip an inline chance; callers then decide whether to hold
                # an ordered queue or retry a known-safe singleton mutation.
                retry_after = float(r.headers.get("Retry-After") or 10)
                if attempt < 1:
                    wait = retry_after + random.uniform(1, 4)
                    log(f"  rate-limited by Apple; waiting {int(wait)}s", tag=self.tag)
                    time.sleep(wait)
                    continue
                path = url.split("/v1/")[-1]
                raise TargetTransientError(
                    f"Apple kept returning HTTP 429 for {path}",
                    retry_after=retry_after,
                )
            if r.status_code >= 500 and method == "GET" and attempt < attempts - 1:
                if attempt == 2:
                    self._rebuild_session()
                    log("  reopening the Apple connection after repeated server errors", tag=self.tag)
                time.sleep(min(2 ** attempt, 20) + random.uniform(0, 2))
                continue
            if r.status_code >= 500 and method == "GET":
                path = url.split("/v1/")[-1]
                raise TargetTransientError(
                    f"Apple Music kept returning HTTP {r.status_code} while reading {path} "
                    f"after {attempts} attempts; this read was abandoned and the next pass will retry it"
                )
            r.raise_for_status()
            return r
        return None

    # -- MirrorTarget ----------------------------------------------------------
    def list_playlists(self):
        out, offset = {}, 0
        while True:
            r = self._request(
                "GET",
                f"{AMP}/me/library/playlists",
                params={"limit": 100, "offset": offset, "extend": "tags"},
            )
            data = r.json()
            rows = data.get("data") or []
            for pl in rows:
                key = (pl.get("attributes", {}).get("name") or "").strip().casefold()
                if key and key not in out:
                    out[key] = pl
            if not data.get("next"):
                return out
            if not rows:
                raise RuntimeError(
                    "Apple Music playlist listing incomplete: next page was advertised but no rows were returned"
                )
            offset += len(rows)

    def is_editable(self, playlist):
        return playlist.get("attributes", {}).get("canEdit") is not False

    def create(self, sp_playlist):
        name, desc = source_playlist_details(sp_playlist)
        attributes = {"name": name}
        if desc:
            attributes["description"] = desc
        r = self._request("POST", f"{AMP}/me/library/playlists", json_body={"attributes": attributes})
        return r.json()["data"][0]

    @staticmethod
    def playlist_page_reference(playlist_id, expected_count=None):
        return {
            "id": str(playlist_id),
            "attributes": {
                "name": "",
                "description": {},
                "canEdit": True,
            },
            "_page_count": expected_count,
        }

    def playlist_tracks_page(self, playlist, cursor=None):
        try:
            offset = 0 if cursor is None else int(cursor)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Apple Music playlist cursor is not a valid offset") from exc
        if offset < 0:
            raise RuntimeError("Apple Music playlist cursor is not a valid offset")

        response = self._request(
            "GET",
            f"{AMP}/me/library/playlists/{playlist['id']}/tracks",
            params={"limit": 20, "offset": offset},
            ok404=True,
        )
        if response is None:
            if offset:
                raise RuntimeError("Apple Music playlist read incomplete: a later page returned 404")
            playlist["_page_count"] = 0
            return [], None
        data = response.json()
        rows = data.get("data") or []
        total = (data.get("meta") or {}).get("total")
        if total is not None:
            playlist["_page_count"] = int(total)
        if data.get("next") and not rows:
            raise RuntimeError(
                "Apple Music playlist read incomplete: next page was advertised but no rows were returned"
            )
        next_cursor = str(offset + len(rows)) if data.get("next") else None
        return [_normalized_playlist_track(track) for track in rows], next_cursor

    def playlist_tracks(self, playlist):
        tracks, offset = [], 0
        while True:
            r = self._request("GET", f"{AMP}/me/library/playlists/{playlist['id']}/tracks",
                              params={"limit": 100, "offset": offset}, ok404=True)
            if r is None:  # empty playlists 404 this endpoint
                if offset:
                    raise RuntimeError(
                        "Apple Music playlist read incomplete: a later page returned 404"
                    )
                return tracks
            data = r.json()
            rows = data.get("data") or []
            tracks.extend(_normalized_playlist_track(track) for track in rows)
            if not data.get("next"):
                return tracks
            if not rows:
                raise RuntimeError(
                    "Apple Music playlist read incomplete: next page was advertised but no rows were returned"
                )
            offset += len(rows)

    @staticmethod
    def _has_favorited_tag(playlist):
        tags = (playlist.get("attributes") or {}).get("tags") or []
        values = [tag.get("name") if isinstance(tag, dict) else tag for tag in tags]
        return any(str(value or "").casefold() == "favorited" for value in values)

    def _favorite_playlist(self):
        playlist = next(
            (item for item in self.list_playlists().values() if self._has_favorited_tag(item)),
            None,
        )
        if playlist is None:
            raise RuntimeError(
                "Apple Music did not return its tagged Favorite Songs system playlist"
            )
        return playlist

    def favorite_tracks(self):
        return self.playlist_tracks(self._favorite_playlist())

    def add_favorite_tracks(self, target_ids):
        for target_id in target_ids:
            self._request(
                "POST",
                _FAVORITES_URL,
                params={"ids[songs]": str(target_id)},
            )
            polite_sleep(0.4)

    def remove_favorite_track(self, track):
        target_id = self.track_id(track)
        if not target_id:
            return
        self._request(
            "DELETE",
            _FAVORITES_URL,
            params={"ids[songs]": str(target_id)},
        )
        polite_sleep(0.4)

    def track_id(self, track):
        return track.get("catalog_id")

    def playlist_count(self, playlist):
        # Library-playlist attributes carry no trackCount, so read it from the
        # tracks endpoint's meta.total (one light limit=1 call). Cached against
        # the playlist's lastModifiedDate so it's recomputed only when it changes.
        if playlist.get("_page_count") is not None:
            return int(playlist["_page_count"])
        pid = playlist.get("id")
        mod = playlist.get("attributes", {}).get("lastModifiedDate")
        hit = _COUNT_CACHE.get(pid)
        if hit and hit[0] == mod:
            return hit[1]
        try:
            data = self._request("GET", f"{AMP}/me/library/playlists/{pid}/tracks",
                                  params={"limit": 1}).json()
            count = data.get("meta", {}).get("total")
        except Exception:
            return hit[1] if hit else None
        _COUNT_CACHE[pid] = (mod, count)
        return count

    def playlist_name(self, playlist):
        return playlist.get("attributes", {}).get("name", "")

    def playlist_description(self, playlist):
        return (playlist.get("attributes", {}).get("description") or {}).get("standard", "")

    def prefetch(self, sp_tracks, cache):
        """Batch-resolve ISRCs to catalog candidates via filter[isrc]. Results
        (including empties) are cached forever — ISRCs don't change."""
        isrcs = sorted({t["isrc"] for t in sp_tracks if t["isrc"]})
        missing = [i for i in isrcs if i not in cache["isrc"]]
        for chunk in _chunks(missing, 25):
            r = self._request("GET", f"{AMP}/catalog/{self.storefront}/songs",
                             params={"filter[isrc]": ",".join(chunk)})
            found = {}
            for song in r.json().get("data", []):
                attrs = song.get("attributes", {})
                isrc = attrs.get("isrc")
                if isrc:
                    found.setdefault(isrc, []).append({
                        "id": song.get("id"), "name": attrs.get("name", ""),
                        "artist": attrs.get("artistName", ""), "duration_ms": attrs.get("durationInMillis"),
                    })
            for isrc in chunk:
                cache["isrc"][isrc] = found.get(isrc, [])
            cache["dirty"] = True
            polite_sleep(0.25)

    def native_isrc_map(self, cache):
        # Apple library reads omit ISRC, but its filter[isrc] resolve cache maps
        # ISRC -> catalog candidates; reverse it to catalog_id -> ISRC.
        out = {}
        for isrc, cands in (cache.get("isrc") or {}).items():
            for c in cands:
                if c.get("id"):
                    out.setdefault(c["id"], isrc)
        return out

    def expected_ids(self, sp_tracks, links, cache):
        out = {}
        for t in sp_tracks:
            ids = set()
            candidates = [
                c for c in cache["isrc"].get(t.get("isrc") or "", [])
                if c.get("id")
            ]
            for c in candidates:
                if c.get("id"):
                    ids.add(c["id"])
            # A current native ISRC result outranks an older archived link. If
            # both are admitted, a stale/wrong linked release already present
            # on Apple can suppress the correct recording forever.
            if not candidates and links.get(t.get("id")):
                ids.add(links[t["id"]])
            if ids:
                out[t.get("id")] = ids
        return out

    def resolve(self, track, cache):
        candidates = [c for c in cache["isrc"].get(track["isrc"] or "", []) if c.get("id")]
        if candidates and track["duration_ms"] is not None:
            candidates.sort(key=lambda c: abs((c.get("duration_ms") or 0) - track["duration_ms"]))
        if candidates:
            target_id = candidates[0]["id"]
            self._remember_resolution(track, target_id, cache)
            return target_id, "isrc"
        target_id = self._search(
            track["name"], track["artists"], track["duration_ms"], cache
        )
        if target_id:
            self._remember_resolution(track, target_id, cache)
        return target_id, "search"

    def _remember_resolution(self, track, target_id, cache):
        if target_id:
            contexts = getattr(self, "_resolved_catalog_context", {})
            contexts[str(target_id)] = (track, cache)
            self._resolved_catalog_context = contexts

    def validate_link(self, track, target_id, cache):
        """Replace a stale historical catalog id with the current ISRC result.

        Deleted Apple playlists can retain catalog ids that now 404 and produce
        an opaque 500 when re-added. Once prefetch has checked this recording's
        ISRC, that current catalog response outranks any older link/archive id.
        """
        isrc = track.get("isrc") or ""
        if isrc not in cache["isrc"]:
            return target_id, "link"
        candidates = [candidate for candidate in cache["isrc"][isrc] if candidate.get("id")]
        if candidates and track.get("duration_ms") is not None:
            candidates.sort(
                key=lambda candidate: abs(
                    (candidate.get("duration_ms") or 0) - track["duration_ms"]
                )
            )
        if candidates:
            target_id = candidates[0]["id"]
            self._remember_resolution(track, target_id, cache)
            return target_id, "isrc"

        # A source identity can point at a different release ISRC even when the
        # archived Apple recording itself is still current. Prove the archived
        # id directly before discarding it; a 404 falls through to live search.
        validated = getattr(self, "_validated_catalog_ids", {})
        if target_id not in validated:
            response = self._request(
                "GET",
                f"{AMP}/catalog/{self.storefront}/songs/{target_id}",
                ok404=True,
            )
            validated[target_id] = response is not None
            self._validated_catalog_ids = validated
        if validated[target_id]:
            self._remember_resolution(track, target_id, cache)
            return target_id, "link"
        return None, None

    def _search_once(self, term, name, artists, duration_ms):
        r = self._request("GET", f"{AMP}/catalog/{self.storefront}/search",
                         params={"term": term, "types": "songs", "limit": 10, "l": "en-us"})
        best_id, best_score = None, -1.0
        for song in r.json().get("results", {}).get("songs", {}).get("data", []):
            attrs = song.get("attributes", {})
            score, ok = score_candidate(name, artists, duration_ms,
                                        attrs.get("name", ""), attrs.get("artistName", ""),
                                        attrs.get("durationInMillis"))
            if ok and score > best_score:
                best_id, best_score = song.get("id"), score
        return best_id

    def _public_search_once(self, term, name, artists, duration_ms):
        """Use Apple's unauthenticated Search API when amp-api is throttled.

        This is a secondary read path only: no Apple credentials are sent to
        the public host. A miss remains provisional and is never cached, while
        a transient response still stops the ordered suffix for a later pass.
        """
        deadline = getattr(self, "_public_search_not_before", 0.0)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

        try:
            response = requests.get(
                _PUBLIC_SEARCH_URL,
                params={
                    "term": term,
                    "country": self.storefront.upper(),
                    "media": "music",
                    "entity": "song",
                    "limit": 50,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise TargetTransientError(
                "Apple public catalog search was temporarily unreachable",
                retry_after=10,
            ) from exc
        finally:
            self._public_search_not_before = (
                time.monotonic() + _PUBLIC_SEARCH_INTERVAL_S
            )

        if response.status_code == 429:
            try:
                retry_after = max(
                    _PUBLIC_SEARCH_INTERVAL_S,
                    float(response.headers.get("Retry-After") or 10),
                )
            except (TypeError, ValueError):
                retry_after = 10
            raise TargetTransientError(
                "Apple public catalog search was rate-limited",
                retry_after=retry_after,
            )
        if response.status_code >= 500:
            raise TargetTransientError(
                f"Apple public catalog search returned HTTP {response.status_code}",
                retry_after=10,
            )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TargetTransientError(
                f"Apple public catalog search returned HTTP {response.status_code}",
                retry_after=10,
            ) from exc

        try:
            results = response.json().get("results", [])
        except (AttributeError, TypeError, ValueError) as exc:
            raise TargetTransientError(
                "Apple public catalog search returned an invalid response",
                retry_after=10,
            ) from exc

        best_id, best_score = None, -1.0
        for song in results:
            score, ok = score_candidate(
                name,
                artists,
                duration_ms,
                song.get("trackName", ""),
                song.get("artistName", ""),
                song.get("trackTimeMillis"),
            )
            if ok and score > best_score and song.get("trackId") is not None:
                best_id, best_score = str(song["trackId"]), score
        return best_id

    def _search(self, name, artists, duration_ms, cache):
        primary = artists[0] if artists else ""
        public_term = f"{name} {' '.join(artists[:3])}".strip()
        if not f"{name} {primary}".strip():
            return None  # amp-api 400s on an empty term
        key = f"{name}|{primary}".casefold()
        if key in cache["search"]:
            return cache["search"][key]
        if self._search_throttled:
            # Keep the queue moving via Apple's separately rate-limited public
            # catalog. A miss is deliberately not cached: the authenticated
            # catalog gets another chance on the next pass.
            best = self._public_search_once(
                public_term, name, artists, duration_ms
            )
            if best:
                cache["search"][key] = best
                cache["dirty"] = True
            return best
        try:
            best = self._search_once(f"{name} {primary}".strip(), name, artists, duration_ms)
            if not best:
                rom = f"{romanized(name)} {romanized(primary)}".strip()
                if rom and rom != normalize_text(f"{name} {primary}"):
                    polite_sleep(0.3)
                    best = self._search_once(rom, name, artists, duration_ms)
        except TargetTransientError as e:
            self._search_throttled = True
            retry_after = e.retry_after or 10
            # Catalog and library routes have separate budgets, but a sustained
            # search throttle has repeatedly preceded library-write failures in
            # practice. Keep a small safety margin before the ordered write queue.
            self._write_not_before = max(
                getattr(self, "_write_not_before", 0.0),
                time.monotonic() + retry_after + 5,
            )
            log_warn("Apple Music search temporarily unavailable — switching to its public catalog fallback",
                     tag=self.tag)
            # amp-api and the public Search API have separate rate limits. The
            # latter can resolve or provisionally skip this item so later
            # source-ordered tracks still get a chance during the same pass.
            best = self._public_search_once(
                public_term, name, artists, duration_ms
            )
            if not best:
                return None
        cache["search"][key] = best
        cache["dirty"] = True
        polite_sleep(0.3)
        return best

    @staticmethod
    def _error_status(exc):
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None) if response is not None else None

    @staticmethod
    def _retry_after(exc, fallback):
        response = getattr(exc, "response", None)
        value = response.headers.get("Retry-After") if response is not None else None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return float(fallback)

    @staticmethod
    def _error_payload(exc):
        response = getattr(exc, "response", None)
        if response is None:
            return {}
        try:
            error = (response.json().get("errors") or [])[0]
        except (AttributeError, IndexError, TypeError, ValueError):
            return {}
        return error if isinstance(error, dict) else {}

    @classmethod
    def _error_detail(cls, exc):
        """A short credential-free Apple error description for diagnostics."""
        error = cls._error_payload(exc)
        if not error:
            return ""
        code = error.get("code")
        message = " — ".join(
            part for part in (error.get("title"), error.get("detail")) if part)
        if code and message:
            return f" ({code}: {message})"
        if code:
            return f" (code {code})"
        return f" ({message})" if message else ""

    @classmethod
    def _is_unwritable_track_error(cls, exc):
        """The track-specific 500 Apple uses for a catalog id it cannot add."""
        if cls._error_status(exc) != 500:
            return False
        error = cls._error_payload(exc)
        message = " ".join(
            str(part) for part in (error.get("title"), error.get("detail")) if part
        ).casefold()
        return str(error.get("code") or "") == "50001" and "unable to update tracks" in message

    def _wait_for_write_window(self):
        deadline = getattr(self, "_write_not_before", 0.0)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            log(f"  waiting {int(remaining) + 1}s for Apple's rate limit to clear before writes",
                tag=self.tag)
            time.sleep(remaining)
            if getattr(self, "_write_not_before", 0.0) == deadline:
                self._write_not_before = 0.0

    def _repair_catalog_id(self, catalog_id):
        """Find a current release id after Apple verifies an old id cannot add."""
        context = getattr(self, "_resolved_catalog_context", {}).get(str(catalog_id))
        if not context:
            return None
        track, cache = context
        artists = track.get("artists") or []
        replacement = self._public_search_once(
            f"{track.get('name', '')} {' '.join(artists[:3])}".strip(),
            track.get("name", ""),
            artists,
            track.get("duration_ms"),
        )
        if not replacement or str(replacement) == str(catalog_id):
            # Do not persist a catalog id Apple has proven unwritable. This is
            # especially important for fuzzy public-search hits: the next pass
            # must search again under the current stricter recording-version
            # rules instead of retrying a bad mapping forever.
            self._evict_catalog_id(catalog_id)
            return None

        replacement = str(replacement)
        isrc = track.get("isrc") or ""
        for candidate in cache.get("isrc", {}).get(isrc, []):
            if str(candidate.get("id")) == str(catalog_id):
                candidate["id"] = replacement
        primary = artists[0] if artists else ""
        cache.setdefault("search", {})[
            f"{track.get('name', '')}|{primary}".casefold()
        ] = replacement
        cache["dirty"] = True
        self._resolved_catalog_context.pop(str(catalog_id), None)
        self._resolved_catalog_context[replacement] = (track, cache)
        return replacement

    def _evict_catalog_id(self, catalog_id):
        """Remove one rejected catalog id from every resolution cache."""
        context = getattr(self, "_resolved_catalog_context", {}).get(str(catalog_id))
        if not context:
            return
        track, cache = context
        isrc = track.get("isrc") or ""
        candidates = cache.get("isrc", {}).get(isrc, [])
        if candidates:
            survivors = [
                candidate for candidate in candidates
                if str(candidate.get("id")) != str(catalog_id)
            ]
            if survivors:
                cache["isrc"][isrc] = survivors
            else:
                cache["isrc"].pop(isrc, None)
        search = cache.setdefault("search", {})
        for key, value in list(search.items()):
            if str(value) == str(catalog_id):
                del search[key]
        cache["dirty"] = True
        self._resolved_catalog_context.pop(str(catalog_id), None)

    def _verify_add_landed(self, playlist, catalog_id, before_count):
        """True/False when a post-error read proves the outcome, None if reads fail.

        Polling before retransmission covers Apple's short consistency lag and
        prevents an ambiguous 5xx from creating a duplicate. Counts, rather
        than mere membership, also keep duplicate-cleanup re-appends correct.
        """
        for check in range(3):
            try:
                actual = sum(
                    1 for track in self.playlist_tracks(playlist)
                    if self.track_id(track) == catalog_id
                )
            except TargetAuthError:
                raise
            except Exception as e:
                if check == 2:
                    log_warn(f"couldn't verify Apple add {catalog_id}: {e!r}", tag=self.tag)
                    return None
            else:
                if actual > before_count:
                    return True
            if check < 2:
                time.sleep(1 + check)
        return False

    def _catalog_track_label(self, catalog_id):
        context = getattr(self, "_resolved_catalog_context", {}).get(str(catalog_id))
        if not context:
            return f"catalog id {catalog_id}"
        track, _cache = context
        name = (track.get("name") or "").strip()
        artists = [artist for artist in (track.get("artists") or []) if artist]
        credit = f" by {', '.join(artists)}" if artists else ""
        return f"'{name}'{credit} (catalog id {catalog_id})" if name else f"catalog id {catalog_id}"

    def _add_one(self, playlist, catalog_id, before_count):
        url = f"{AMP}/me/library/playlists/{playlist['id']}/tracks"
        last_error = None
        repaired = False
        for attempt in range(6):
            self._wait_for_write_window()
            try:
                self._request(
                    "POST",
                    url,
                    json_body={"data": [{"id": catalog_id, "type": "songs"}]},
                )
                return catalog_id
            except TargetAuthError:
                raise
            except TargetTransientError as e:
                last_error = e
                wait = float(e.retry_after or min(10 * (attempt + 1), 60)) + random.uniform(1, 3)
                self._write_not_before = time.monotonic() + wait
                log_warn(
                    f"Apple rate-limited add {catalog_id}; preserving its queue position "
                    f"and retrying after {int(wait)}s",
                    tag=self.tag,
                )
                continue
            except requests.RequestException as e:
                status = self._error_status(e)
                if status not in (408, 429) and status is not None and status < 500:
                    raise
                last_error = e

                if status == 429:
                    wait = self._retry_after(e, min(10 * (attempt + 1), 60)) + random.uniform(1, 3)
                    self._write_not_before = time.monotonic() + wait
                    log_warn(
                        f"Apple rate-limited add {catalog_id}; preserving its queue position "
                        f"and retrying after {int(wait)}s",
                        tag=self.tag,
                    )
                    continue

                # A connection loss or 5xx may be a committed write whose reply
                # was lost. Reopen the connection, then prove the occurrence
                # count before deciding whether retransmission is safe.
                wait = min(2 ** attempt, 20) + random.uniform(0, 2)
                detail = self._error_detail(e)
                log_warn(
                    f"Apple add {catalog_id} returned "
                    f"{('HTTP ' + str(status)) if status else 'a network error'}{detail}; "
                    f"verifying the playlist before retrying",
                    tag=self.tag,
                )
                time.sleep(wait)
                self._rebuild_session()
                landed = self._verify_add_landed(playlist, catalog_id, before_count)
                if landed is True:
                    log(f"  Apple confirmed {catalog_id} was added despite the error", tag=self.tag)
                    return catalog_id
                if landed is None:
                    raise RuntimeError(
                        f"Apple add {catalog_id} had an ambiguous outcome and the playlist "
                        "could not be verified; stopping this ordered queue until the next pass"
                    ) from e
                track_label = self._catalog_track_label(catalog_id)
                if not repaired:
                    replacement = self._repair_catalog_id(catalog_id)
                    repaired = True
                    if replacement:
                        log(
                            f"  Apple replaced obsolete catalog id {catalog_id} with {replacement}",
                            tag=self.tag,
                        )
                        catalog_id = replacement
                        before_count = 0
                        continue
                if self._is_unwritable_track_error(e):
                    self._evict_catalog_id(catalog_id)
                    log_warn(
                        f"Apple cannot add {track_label}; "
                        "quarantining this catalog match and continuing with later tracks",
                        tag=self.tag,
                    )
                    return None

        raise RuntimeError(
            f"Apple kept rejecting add {catalog_id} after 6 attempts; "
            "stopping this ordered queue until the next pass"
        ) from last_error

    def add(self, playlist, target_ids):
        # One POST per track — batched arrays can land out of order. Never skip
        # past a transiently failing id: later tracks would then receive earlier
        # date-added stamps, and Apple offers no positional insert to repair it.
        confirmed_counts = {}
        added_catalog_ids = getattr(self, "_added_catalog_ids", {})
        self._added_catalog_ids = added_catalog_ids
        added_requested_ids = []
        for catalog_id in target_ids:
            requested_id = catalog_id
            catalog_id = self.added_id(requested_id)
            before_count = confirmed_counts.get(catalog_id, 0)
            actual_id = self._add_one(playlist, catalog_id, before_count)
            if actual_id is None:
                continue
            added_catalog_ids[str(requested_id)] = str(actual_id)
            confirmed_counts[str(actual_id)] = before_count + 1
            added_requested_ids.append(requested_id)
            polite_sleep(1.0)
        return added_requested_ids

    def added_id(self, target_id):
        return getattr(self, "_added_catalog_ids", {}).get(str(target_id), target_id)

    def remove(self, playlist, track):
        self._request("DELETE", f"{AMP}/me/library/playlists/{playlist['id']}/tracks",
                     params={"ids[library-songs]": track["relationship_id"], "mode": "all"})
        polite_sleep(0.4)

    def remove_occurrences(self, playlist, positioned):
        """Apple's tracks-DELETE addresses the library SONG, not one entry —
        duplicate copies share one library id, so deleting a flagged copy would
        take its keeper with it. Delete each flagged song once, then re-append
        one copy per surviving (unflagged) entry of that song. The re-appended
        keeper lands at the playlist's end (Apple has no positional insert); if
        its catalog id is no longer addable (delisted release), the next sync
        pass restores the song via search."""
        totals = {}
        for t in self.playlist_tracks(playlist):
            rid = t.get("relationship_id")
            totals[rid] = totals.get(rid, 0) + 1
        flagged, catalog = {}, {}
        for _, raw in positioned:
            rid = raw.get("relationship_id")
            if not rid:
                continue
            flagged[rid] = flagged.get(rid, 0) + 1
            catalog.setdefault(rid, raw.get("catalog_id"))
        for rid, n in flagged.items():
            self.remove(playlist, {"relationship_id": rid})
            keep = totals.get(rid, n) - n
            if keep > 0 and catalog.get(rid):
                try:
                    self.add(playlist, [catalog[rid]] * keep)
                except Exception as e:
                    log_warn(f"couldn't re-append the kept copy of {catalog[rid]} ({e!r}); "
                             "the next sync pass restores it via search", tag=self.tag)
