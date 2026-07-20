# Spotify cookie write backend (sp_dc → web-player API)

**Date:** 2026-07-20
**Status:** BUILT & verified end-to-end in-container — entirely off api.spotify.com
**Supersedes memory:** `spotify-cookie-mode-future.md` (this is the built version)

## Build status

Full "Create new" transfer flow verified in the running container: **create → visible in
library → read empty dest → add**, none of it touching `api.spotify.com`.

- **token mint** (`CookieTokenProvider`), **reads/add/remove** (pathfinder), **user id**
  (`profileAttributes`), **create** (spclient `POST /playlist/v2/playlist`, JSON change-set —
  not REST, not protobuf) + **rootlist filing** (spclient `/rootlist/changes`, so the new
  playlist shows in the library). Routing toggle, connector + Accounts UI, hash self-heal.
- Suite green (118 + 3 cookie tests). See the memory note for exact endpoints/bodies/hashes.
- **Known limitation:** create/add target the *cookie* account; the transfer UI lists the
  *OAuth* account's playlists — fine when they're the same account (this user's are).
- **Superseded:** the earlier REST `create` (blocked by the api.spotify.com rate limit) was
  replaced by the spclient path, which sidesteps that host entirely.

## N-way sync safeguard (`SPOTIFY_COOKIE_SYNC`, default off)

Cookie mode makes Spotify writable, which also *unblocks the N-way (bidirectional)
reconcile* — and the dev-mode cookie read carries **no ISRC**, so cross-provider
matching is unreliable and a sync can churn playlists (adding karaoke/tribute
matches, removing unmatched tracks). So cookie-mode **sync** writes to Spotify are
gated off by default: `SpotifyTarget(sync_peer=True)` fails closed on write (like the
pre-cookie 403 path) unless `SPOTIFY_COOKIE_SYNC=1`. **Transfers** (explicit,
adds-only, `sync_peer=False`) always write. Recovery from a churn is possible via the
`playlist_order` table (full per-provider track lists per capture; restore to the
last pre-churn capture with original IDs).

## Problem

A self-hosted Spotify **developer app in Development Mode** gets `403 Forbidden` on
the *content* surface — `POST /users/{id}/playlists` (create), and
`GET/POST/DELETE /playlists/{id}/tracks` (read/add/remove items) — while
list/metadata/rename/search return `200`. The `playlist-modify-*` scopes are
granted *and* effective (rename works), so this is **not** a scope, token, or
app-code problem — it is Spotify gating those endpoints for dev-mode apps.
Reproduced via raw HTTP outside the app. Reads already have a scraper fallback
(`spotify_web.py`); **writes have none**, so no transfer or N-way write to
Spotify can complete.

## Decision

Add an **opt-in cookie write backend** that authenticates as Spotify's own
first-party web client (via the `sp_dc` cookie), which is not subject to the
dev-app dev-mode gate. Reads are unchanged; only writes route through it when
enabled.

## Proven by spike (reverse-engineered facts — will drift, see self-heal)

- **Token mint:** `spotify_scraper.auth.cookies.CookieTokenProvider(transport, sp_dc).token()`
  → real first-party Bearer (TOTP handled by the lib). **No `client-token` needed**
  for pathfinder (confirmed: Bearer-only read returned 200).
- **Endpoint:** `POST https://api-partner.spotify.com/pathfinder/v2/query`
- **Headers:** `authorization: Bearer …`, `app-platform: WebPlayer`,
  `spotify-app-version: <bundle ver>`, `Origin`/`Referer: https://open.spotify.com`,
  `Content-Type: application/json;charset=UTF-8`.
- **Persisted-query request shape:**
  `{"operationName", "variables", "extensions":{"persistedQuery":{"version":1,"sha256Hash"}}}`
- **Ops + hashes** (from `open.spotifycdn.com/cdn/build/web-player/web-player.*.js`;
  add/remove/move share one *per-document* hash, selected by `operationName`):
  | op | type | hash (as of spike) |
  |---|---|---|
  | `addToPlaylist` / `removeFromPlaylist` / `moveItemsInPlaylist` | mutation | `47b2a1234b17748d332dd0431534f22450e9ecbb3d5ddcdacbd83368636a0990` |
  | `editablePlaylists` | query | `d5c4b8096437dcc2ac9528c91dfcd299e35b747cda2f8f75d28f41f49c5092ba` |
  | `fetchPlaylist` / `fetchPlaylistContents` / `fetchPlaylistMetadata` | query | `a65e12194ed5fc443a1cdebed5fabe33ca5b07b987185d63c72483867ad13cb4` |
- **Variable schemas** (from bundle call sites):
  - `addToPlaylist`: `{playlistUri, playlistItemUris:[uri…], newPosition:{moveType:"BOTTOM_OF_PLAYLIST"}}`
    (enum also: `AFTER_UID`/`BEFORE_UID`/`TOP_OF_PLAYLIST`)
  - `removeFromPlaylist`: `{playlistUri, uids:[uid…]}` — remove is by **item uid**, not track uri
    (uid comes from `fetchPlaylistContents`)
- **Create:** NOT a pathfinder mutation. Web player creates via the `spclient
  playlist/v2` REST path (or possibly the first-party Bearer on official REST,
  which likely bypasses dev-mode). → **Resolved in Milestone 1.**

## Architecture

1. **Cookie connector** (`services/accounts/spotify_cookie.py`, mirrors the YT
   browser-auth connector): paste box for `sp_dc`, stored at
   `data/spotify_sp_dc.private` (gitignored, `0600` via `_open_private`, never
   logged). Status = cookie present / token mints OK.
2. **Config toggle:** `SPOTIFY_WRITE_BACKEND = oauth | cookie` (default `oauth`;
   cookie is opt-in). Lives in `engine/config.py` + SettingsStore.
3. **Cookie write client** (`engine/spotify_cookie.py`, one focused module):
   `create(name, public, desc)`, `add(playlist_uri, track_uris)`,
   `remove(playlist_uri, uids)`. Mints/caches the Bearer; invalidates on 401.
   **Hash table in one place** + `refresh_hashes()` that re-scrapes the live
   bundle on a `PersistedQueryNotFound` response → a rotation self-heals.
4. **Integration seam:** `SpotifyTarget` reads unchanged (official API + scraper
   fallback). Its write methods (`create`/`add`/`remove`/`remove_occurrences`)
   route to the cookie client when `SPOTIFY_WRITE_BACKEND=cookie`, via one
   injected `writer`. No duplicate target class.

## Non-goals (YAGNI)

No `client-token` minting (proven unnecessary), no async client, no separate
`SpotifyCookieTarget`, no removal-by-search. Reuse the existing reconcile/safety
rails untouched.

## Fragility / maintenance (technical, for the module docstring)

Persisted-query hashes and `spotify-app-version` rotate on web-player releases;
the self-heal re-scrape absorbs that. `sp_dc` lasts ~1 year; the connector
surfaces when it needs re-pasting. All behind `SPOTIFY_WRITE_BACKEND=cookie`, so
the default OAuth path is untouched.

## Milestones

1. **Prove writes live (net-zero):** pathfinder `addToPlaylist` → owned playlist,
   verify via `fetchPlaylistContents`, `removeFromPlaylist` by uid → net-zero.
   Resolve the **create** mechanism (spclient vs first-party REST). Land the
   hash-scrape + token-mint as a tested `engine/spotify_cookie.py`.
2. **Connector + config toggle** + settings/accounts UI wiring.
3. **Integration** into `SpotifyTarget` writes; end-to-end transfer green.

## Related

- Cache-path fix (engine vs connector token cache) landed separately this session.
- `spotify_web.py` (read fallback) is the sibling pattern this mirrors for writes.
