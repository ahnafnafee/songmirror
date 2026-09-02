# Public-URL transfer and resolve-cache UI implementation plan

**Status:** COMPLETED
**Spec:** [`docs/design/2026-09-02-public-url-transfer-and-resolve-cache-ui.md`](../design/2026-09-02-public-url-transfer-and-resolve-cache-ui.md)
**Issue:** [#37](https://github.com/ahnafnafee/songmirror/issues/37)
**Baseline:** `fc0edfe2`

**Goal:** Let a user transfer a playlist from a pasted public link, and manage the per-provider resolve caches from the web UI.

**Architecture:** Feature 1 adds one optional `MirrorTarget.fetch_playlist(id)` method plus a server-side link parser; `TransferService._find` falls back to it, so the existing copy engine is untouched. Feature 2 adds a `manual` provenance list to the resolve-cache files, a `ResolveCacheStore` service that reads them through a new per-target `resolve_cache_path` classmethod, and a new `/mappings` page.

**Tech stack:** Python 3.13 / FastAPI / pytest on the backend; React 19 + Vite + Tailwind + react-router on the frontend.

## Global constraints

- No AI attribution anywhere (commits, PRs, comments, docs).
- Conventional Commits for every commit and PR title.
- No em dashes or en dashes in any produced text, including code comments.
- US English spelling throughout.
- No time-anchored references (dates, PR numbers, version numbers) in code comments.
- No legality or terms-of-service editorializing in code or docs.
- Transfers stay adds-only. Nothing in this work may touch `mirror_pair` or `reconcile`.

---

## File structure

**New backend**

| File | Responsibility |
|---|---|
| `songmirror/services/playlist_links.py` | Provider URL grammar, both directions: `parse_playlist_link(text)` and `track_url(provider, id)`. The single home for provider URL shapes. |
| `songmirror/services/resolve_cache.py` | `ResolveCacheStore`: list providers, page and filter entries, set, delete, clear unmatched. |
| `songmirror/web/routers/resolve_cache.py` | HTTP surface for the store. |

**Modified backend**

| File | Change |
|---|---|
| `songmirror/engine/targets/base.py` | `MirrorTarget.fetch_playlist` (returns `None`), `MirrorTarget.resolve_cache_path` (returns `None`). |
| `songmirror/engine/targets/{spotify_target,deezer,qobuz,tidal,ytmusic,amazon_music,apple}.py` | `fetch_playlist` + `resolve_cache_path`; Apple also gets the catalog read branch. |
| `songmirror/engine/spotify_cookie.py` | Widen `_hydrate_playlist_name` into a metadata fetch. |
| `songmirror/engine/runner.py` | `load_cache` / `save_cache` carry `manual`. |
| `songmirror/services/transfers.py` | `_find` falls back to `fetch_playlist`; `resolve()` records provenance. |
| `songmirror/web/routers/transfers.py` | `POST /api/transfers/preview`. |
| `songmirror/web/__init__.py` | Register the resolve-cache router and store. |

**New frontend**

| File | Responsibility |
|---|---|
| `frontend/src/pages/ResolveMappings.tsx` | The Mappings page. |
| `frontend/src/components/mappings/MappingRow.tsx` | One row, with inline edit and delete. |
| `frontend/src/hooks/useResolveCache.ts` | Fetch providers + a filtered page. |

**Modified frontend**

| File | Change |
|---|---|
| `frontend/src/components/transfers/TransferSetupForm.tsx` | Deck A source mode toggle and link preview. |
| `frontend/src/api.ts`, `frontend/src/types.ts` | New endpoints and types. |
| `frontend/src/App.tsx`, `frontend/src/components/layout/Sidebar.tsx` | `/mappings` route and nav entry. |

---

## Tasks

Order matters: task 1 is a pure function with no dependencies, tasks 2 to 4 build the transfer path bottom-up, tasks 5 to 8 do the same for the cache, and the two frontend tasks land last so they consume settled contracts.

### Task 1: link parser

**Files:** create `songmirror/services/playlist_links.py`, `tests/test_playlist_links.py`

**Produces:**
- `parse_playlist_link(text: str) -> tuple[str, str] | None`
- `track_url(provider_id: str, track_id: str) -> str` (empty when there is nothing to link to)
- `external_url(provider_id, kind, item_id)`, moved here from `services/playlists.py`
- `provider_label(provider_id)`, moved here from `services/playlists.py`
- `PLAYLIST_LINK_HINT: str` (the "that does not look like a playlist link" copy)

Pure string work, no network, except the Deezer share-link `HEAD` which is behind a `resolve_redirect` callable so tests inject a stub.

**Verify:** `pytest tests/test_playlist_links.py -q`

### Task 2: `fetch_playlist` contract and the easy providers

**Files:** modify `targets/base.py`, `spotify_target.py`, `deezer.py`, `qobuz.py`, `tidal.py`, `ytmusic.py`, `amazon_music.py`, `engine/spotify_cookie.py`; test in `tests/test_new_providers.py`

**Consumes:** nothing. **Produces:** `MirrorTarget.fetch_playlist(playlist_id) -> dict | None` on every target.

Each provider returns its native playlist dict with the real name, description and count, matching the shape its own `playlist_page_reference` produces so `playlist_name` / `playlist_tracks` / `playlist_count` read it unchanged.

**Verify:** `pytest tests/test_new_providers.py -q`

### Task 3: Apple catalog branch

**Files:** modify `targets/apple.py`; test in `tests/test_new_providers.py`

Catalog ids (`pl.`, `pl.u-`) read from `catalog/{storefront}/playlists/{id}`; `fetch_playlist` tags the reference `_catalog: True` and `playlist_tracks` / `playlist_tracks_page` branch on it. Library reads unchanged.

**Verify:** `pytest tests/test_new_providers.py -k apple -q`

### Task 4: transfer source fallback and the preview endpoint

**Files:** modify `services/transfers.py`, `web/routers/transfers.py`; test in `tests/test_transfers.py`, `tests/test_web.py`

`_find` becomes `find_playlist(id) or fetch_playlist(id)`. `POST /api/transfers/preview` parses, checks the provider is connected, fetches, and returns the preview payload or a 422 carrying user-facing copy.

**Verify:** `pytest tests/test_transfers.py tests/test_web.py -q`

### Task 5: cache provenance

**Files:** modify `engine/runner.py`, `services/transfers.py`; test in `tests/test_resolve_cache.py`

`load_cache` returns `manual` (a `set`), `save_cache` writes it as a sorted list, and a legacy file with no `manual` key loads as empty. `TransferService.resolve` adds the key it sets.

**Verify:** `pytest tests/test_resolve_cache.py -q && pytest tests/test_runner_summary.py -q`

### Task 6: cache-path authority

**Files:** modify all seven target modules; test in `tests/test_targets_accessors.py`

`resolve_cache_path(opts=None)` classmethod per target, called by each `__init__` so the environment lookup has one home.

**Verify:** `pytest tests/test_targets_accessors.py -q`

### Task 7: `ResolveCacheStore`

**Files:** create `songmirror/services/resolve_cache.py`; test in `tests/test_resolve_cache.py`

**Produces:** `providers()`, `entries(provider, *, query, kind, offset, limit)`, `set(provider, key, target_id)`, `delete(provider, key)`, `clear_unmatched(provider)`.

**Verify:** `pytest tests/test_resolve_cache.py -q`

### Task 8: resolve-cache router

**Files:** create `songmirror/web/routers/resolve_cache.py`; modify `web/__init__.py`; test in `tests/test_web.py`

Writes return 409 while `sync.status()["running"]`.

**Verify:** `pytest tests/test_web.py -q`

### Task 9: transfer link UI

**Files:** modify `TransferSetupForm.tsx`, `api.ts`, `types.ts`

**Verify:** `pnpm -C frontend exec tsc --noEmit && pnpm -C frontend build`

### Task 10: Mappings page

**Files:** create `pages/ResolveMappings.tsx`, `components/mappings/MappingRow.tsx`, `hooks/useResolveCache.ts`; modify `App.tsx`, `Sidebar.tsx`, `api.ts`, `types.ts`

**Verify:** `pnpm -C frontend exec tsc --noEmit && pnpm -C frontend build`

### Task 11: docs

**Files:** modify `README.md`, `docs/adding-a-provider.md`

README gets the link-transfer and Mappings sections; the provider guide gains `fetch_playlist` and `resolve_cache_path` in its checklist, since a new provider must now implement both.

**Verify:** full suite, `pytest -q`

---

## Self-review against the spec

| Spec section | Task |
|---|---|
| `fetch_playlist` seam and `_find` fallback | 2, 4 |
| Link parsing table, Deezer share links | 1 |
| Preview endpoint and its 422 copy | 4 |
| Abuse review (parse to id, check connected, provider's own client) | 4 |
| Per-provider metadata reads | 2 |
| Apple catalog branch | 3 |
| Transfer frontend | 9 |
| `manual` provenance and legacy load | 5 |
| `resolve_cache_path` authority | 6 |
| Store methods including `clear_unmatched` | 7 |
| Router, key in body, 409 during a sync | 8 |
| Mappings page, filters, bulk clear | 10 |
| Test files listed in the spec | 1, 3, 4, 5, 7, 8 |
| Out-of-scope items | none, by construction |
