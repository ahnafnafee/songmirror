# Public-URL playlist transfer and resolve-cache management

Date: 2026-09-02
Issue: [#37 — direct playlist transfer via public URL & resolve cache management UI](https://github.com/ahnafnafee/songmirror/issues/37)
Repository baseline: [`fc0edfe2`](https://github.com/ahnafnafee/songmirror/tree/fc0edfe23f70bd58b0376f768d2b3265bf8a1e87)

## Summary

Two independent features from one issue, specified together because both add API surface and both are shipped in one cycle.

1. **Transfer from a pasted playlist link.** A user pastes a public playlist URL from any of the seven providers and copies it to a destination, without first saving or following the playlist in their own library.
2. **Resolve-mappings page.** A searchable, paginated view of every `name|artist -> catalog id` mapping SongMirror has cached per provider, with edit, delete, and a bulk clear of the negative ("no match") entries.

Both build on machinery that already exists. Neither changes the sync engine's reconciliation path.

## Feature 1: transfer from a pasted link

### Why it is small

`transfer()` ([`services/transfers.py:24`](../../songmirror/services/transfers.py)) already works off a *playlist object*, not off library membership. It reads the source through `playlist_tracks` / `playlist_name` / `playlist_description`, and every provider's track read is addressed by a bare id.

The single thing that limits a transfer source to the user's own library is `TransferService._find`, which calls `find_playlist(id)`. That is a scan of `browse_playlists()`.

Every target already builds a synthetic playlist dict from a bare id in `playlist_page_reference(id)`, used by the paginated browse. So "read a playlist the user does not own" is one new method plus link parsing.

### The seam

A new optional method on `MirrorTarget`:

```python
def fetch_playlist(self, playlist_id):
    """A playlist by id whether or not it is in this account's library.

    The pasted-link transfer source. Returns the provider-native playlist
    dict (same shape playlist_page_reference builds, with the real name,
    description and count), or None when the provider cannot read a
    playlist it does not own.
    """
    return None
```

`TransferService._find` becomes:

```python
def _find(self, provider, playlist_id):
    return provider.find_playlist(playlist_id) or provider.fetch_playlist(playlist_id)
```

Library first. Today's behavior is unchanged for every id already reachable, including the `_owned` and `_editable` flags that `is_editable` reads. The public read only fires for an id the library does not have.

**Rejected alternative:** a separate `PublicPlaylistSource` adapter type. It would duplicate seven track readers to gain nothing, because the provider readers are already id-addressed.

### Link parsing

New module `songmirror/services/playlist_links.py`, one public function:

```python
parse_playlist_link(text) -> (provider_id, playlist_id) | None
```

Server-side only. The frontend posts the raw string, so the URL grammar has exactly one home.

| Provider | Accepted forms |
|---|---|
| Spotify | `open.spotify.com/playlist/{id}`, `open.spotify.com/intl-xx/playlist/{id}`, `spotify:playlist:{id}` |
| Deezer | `deezer.com/{lang}/playlist/{digits}`, `link.deezer.com/s/...` |
| YT Music | `music.youtube.com/playlist?list={id}`, `youtube.com/playlist?list={id}` |
| Tidal | `tidal.com/playlist/{uuid}`, `tidal.com/browse/playlist/{uuid}`, `listen.tidal.com/playlist/{uuid}` |
| Apple | `music.apple.com/{storefront}/playlist/{slug}/{pl.id}` |
| Qobuz | `open.qobuz.com/playlist/{digits}`, `play.qobuz.com/playlist/{digits}` |
| Amazon | `music.amazon.{tld}/user-playlists/{id}`, `music.amazon.{tld}/playlists/{id}` |

Deezer share links resolve by a `HEAD` request with `allow_redirects=False`. The share host is read from `SHARE_LINK_HOSTS` in [`targets/deezer.py`](../../songmirror/engine/targets/deezer.py), which already resolves the same links for manually pasted track ids, so the host list has one home.

A link that parses to a non-playlist resource (album, artist, track) returns `None` and the caller reports it as such, rather than passing a wrong id to a provider.

### Preview endpoint

`POST /api/transfers/preview` with `{"url": "..."}`, returning:

```json
{"provider": "spotify", "playlist_id": "...", "name": "...", "description": "...", "count": 123, "image": "..."}
```

Failures return 422 with a message the UI can show verbatim:

- link did not parse: "That does not look like a playlist link."
- provider not connected: "Spotify is not connected. Connect it on the Accounts page first."
- provider read failed or returned nothing: "&lt;Service&gt; could not open that playlist. It may be private, or the link may have expired."
- provider has no public read: "&lt;Service&gt; cannot open a link to a playlist you do not own. Save it to your library first, then transfer it from there."

The endpoint builds a target exactly the way `PlaylistService._target` does. It deliberately does **not** take `SyncService.run_exclusive`: it is a single GET, and the browse endpoints already read providers outside that lock.

**Abuse review** (a caller-supplied URL drives a server-side fetch, so this needs stating). The URL never becomes a fetch URL. It is parsed into `(provider_id, playlist_id)`, the provider is checked against the connected-accounts list, and only the id is handed to that provider's own configured client. The endpoint can therefore only ever read a playlist from a service the user has connected, using their own credentials. There is no general-purpose proxy, no unbounded fan-out, and no per-call cost beyond one provider GET that browse already permits.

### Per-provider implementation

| Provider | Metadata by id | Tracks by id | Work |
|---|---|---|---|
| Spotify (cookie) | pathfinder `fetchPlaylist`, already present as `_hydrate_playlist_name` | already id-addressed | widen the existing helper to return name, description, count |
| Spotify (OAuth) | `sp.playlist(id)` | already id-addressed | one method |
| Deezer | `GET playlist/{id}`, already used by `create()` | already id-addressed | one method |
| Qobuz | `playlist/get?playlist_id=`, already used by `playlist_tracks` | already id-addressed | one method |
| Tidal | `GET playlists/{id}` | already id-addressed | one method |
| YT Music (Data API) | `playlists?id=` | `playlistItems?playlistId=` | one method |
| YT Music (youtubei) | `get_playlist(id)` | already id-addressed | one method |
| Amazon Music | GraphQL `playlist(id)` / `GET playlists/{id}` | already id-addressed | one method, unverified against a non-owned id |
| Apple Music | `catalog/{storefront}/playlists/{id}` | **separate endpoint** | catalog branch, see below |

#### Apple Music is the exception

A public Apple Music link carries a **catalog** playlist id (`pl.` for editorial, `pl.u-` for a user-shared playlist), not a **library** id (`p.`). The library endpoints SongMirror uses today (`me/library/playlists/{id}/tracks`) cannot read one.

`AppleMusicTarget.fetch_playlist` returns a reference tagged `_catalog: True`, and `playlist_tracks` / `playlist_tracks_page` branch on that tag to `catalog/{storefront}/playlists/{id}/tracks`. Library reads are untouched.

Catalog song rows carry `playParams.id` as the catalog id, so `_normalized_playlist_track` and `track_id` (which reads `catalog_id`) work without modification. That keeps same-provider Apple copies correct.

#### Stated risk

Apple and Amazon public reads cannot be verified in development without live credentials against a playlist the account does not own. Both are implemented against the documented and observed request shapes, both fail into the explicit "cannot open a link you do not own" message rather than crashing, and both get fixture-driven tests. If Amazon's GraphQL rejects a non-owned id in practice, the correction is one line (return `None` from `fetch_playlist`), not a redesign.

### Frontend

`TransferSetupForm` Deck A gains a Segmented control, "Your library" and "Paste a link".

Link mode shows a `TextField` plus a preview card (service badge, playlist name, track count). On a successful preview the component sets `sourceProvider` and `sourcePlaylistId` from the response, so the `StartTransferRequest` body, the confirm dialog, `TransferProgress`, and `ConflictList` are all unchanged.

The "Create new" destination-name default already derives from the source playlist's name; in link mode it derives from the preview's `name` instead of from a `entries[...]` lookup.

## Feature 2: resolve-mappings page

### The existing shape, and its gap

Each provider keeps a resolution cache as JSON:

```json
{"isrc": {"<ISRC>": [candidate, ...]}, "search": {"<name|artist>": "<catalog id>" | null}}
```

`search` is the mapping the issue is about. A `null` value is a **negative** entry, meaning "searched, found nothing" and, because `resolve()` short-circuits on `key in cache["search"]`, meaning it will never be searched again. Those dominate: the caches on a live install hold 2000 to 4000 `search` rows each, most of them `null`.

There is no manual/automatic provenance. `TransferService.resolve` writes `cache["search"][key] = dest_id`, the same slot the automatic resolver writes.

### Provenance

`load_cache` / `save_cache` ([`engine/runner.py:54`](../../songmirror/engine/runner.py)) gain a third key:

```json
{"isrc": {...}, "search": {...}, "manual": ["name|artist", ...]}
```

- A file written by an older build loads with `manual: []`.
- A file written by this build is still read correctly by an older build, which ignores the extra key.
- `TransferService.resolve` appends the key it sets.
- No stickiness work is required: automatic resolution already returns early on a present key, so a manual entry already wins over a later search.

### Cache-path authority

Each target resolves its own cache path differently: five read their own environment variable in `__init__`, while Apple and Spotify take the path from `opts` (`APPLE_CACHE_FILE`, `SPOTIFY_CACHE_FILE`).

Rather than restate seven environment-variable names in a new service, each target class gains:

```python
@classmethod
def resolve_cache_path(cls, opts=None) -> str | None
```

and its own `__init__` calls it. The path then has one home, and the store reads exactly the file the engine writes.

### Service

New `songmirror/services/resolve_cache.py`:

| Method | Behavior |
|---|---|
| `providers()` | provider ids with a cache file on disk, each with `{total, manual, unmatched}` counts |
| `entries(provider, *, query, kind, offset, limit)` | one page of rows; `kind` in `all` / `manual` / `unmatched`; filter, search and paging are server-side because the largest cache is ~4000 rows |
| `set(provider, key, target_id)` | normalizes through the target class's `normalize_manual_track_id` (the same code path the transfer conflict modal uses), writes, and marks the key manual |
| `delete(provider, key)` | removes from `search` and from `manual` |
| `clear_unmatched(provider)` | removes every `search` key whose value is `null`; returns the count removed |

A row is:

```json
{"key": "name|artist", "name": "name", "artist": "artist",
 "target_id": "abc123" , "manual": true, "url": "https://..."}
```

`name` and `artist` are the key split on its last `|`. The key is the normalized form (`loose_name(name)|normalize_text(artist)`), so the display is lower-cased and stripped. That is honest about what is stored; the alternative would be inventing display text the cache does not hold.

`url` is built server-side by `external_url`, which moves out of `services/playlists.py` into the link-parser module so the provider URL grammar has one home rather than a second copy in TypeScript.

### Concurrency

A sync pass loads the cache into memory at its start and writes it at the end. A UI edit landing mid-pass would be silently overwritten when the pass saves.

Writes therefore return **409** while `SyncService.status()["running"]` is true, with a message telling the user to retry once the pass finishes. This is preferred over queuing behind `run_exclusive`, which would hang the HTTP request for the duration of a pass. It cannot lose a write.

Reads are unrestricted.

### Router

New `songmirror/web/routers/resolve_cache.py`:

| Route | Body / query | Returns |
|---|---|---|
| `GET /api/resolve-cache` | | providers with counts |
| `GET /api/resolve-cache/{provider}` | `q`, `kind`, `offset`, `limit` | `{total, entries: [...]}` |
| `PUT /api/resolve-cache/{provider}` | `{key, target_id}` | `{ok, entry}` |
| `DELETE /api/resolve-cache/{provider}` | `{key}` | `{ok}` |
| `POST /api/resolve-cache/{provider}/clear-unmatched` | | `{removed}` |

The key travels in the body rather than the path because `name|artist` keys contain slashes and other path-hostile characters.

### Frontend

New sidebar entry "Mappings" at `/mappings`, page `frontend/src/pages/ResolveMappings.tsx`:

- provider segmented control, each with its row count
- debounced search box, filtering server-side
- filter control: All / Manual / No match
- table rows showing title, artist, the resolved id with an open-in-provider link, and Edit / Delete actions
- edit accepts a pasted provider URL or a raw id, normalized server-side
- a "Clear all no-match entries" action per provider, behind a `ConfirmDialog` that states the next sync will re-search those tracks

The bulk clear exists because the negative entries are the ones users actually need to remove, and there can be thousands of them; clearing them twenty rows at a time is not a usable option.

## Testing

| File | Covers |
|---|---|
| `tests/test_playlist_links.py` (new) | one parse case per provider, plus album/artist/track links and junk input |
| `tests/test_transfers.py` | `fetch_playlist` on the existing stub: library-first, public fallback, and the clean failure when a provider returns `None` |
| `tests/test_resolve_cache.py` (new) | `manual` round-trip including a legacy file with no `manual` key; filter, search and paging; set and delete; `clear_unmatched`; 409 while a sync is running |
| `tests/test_web.py` | the preview endpoint and the resolve-cache endpoints |
| `tests/test_new_providers.py` | the Apple catalog-playlist branch, fixture-driven, beside the existing Apple cases |

## Out of scope

- Transferring a public link *without* the source service connected. Spotify allows an app-token read of public playlists, but SongMirror's model is connected accounts, and adding an unauthenticated read path for one provider would be inconsistent.
- Editing the `isrc` section of the caches. It holds candidate lists from prefetch, not user-facing mappings.
- Mirroring (removals) on a link transfer. Transfers remain adds-only, as today.
- A resolve-mappings view of the cross-provider `song_cache.db` archive. Different store, different problem.
