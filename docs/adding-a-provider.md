# Adding a music provider (Tidal, Qobuz, Deezer, …)

## The short version

A provider that carries **ISRC** (every hi-fi service does) drops in with **no changes
to the sync / reconcile / transfer / browse core**. You write two small classes — a
`MirrorTarget` (how the engine *uses* the service) and a `Connector` (how the UI
*authenticates* it) — register each with one line, and add branding. ISRC is what makes
cross-provider matching free: a track with an ISRC unifies with the same song on every
other provider automatically, no per-pair code.

The core (`mirror_pair`, `reconcile`, `browse`, `transfer`, the runner, the web routers)
is provider-agnostic and never changes.

## The five touchpoints

### 1. Engine target — `songmirror/engine/targets/<svc>.py`

Subclass `MirrorTarget` (`targets/base.py`). **Required** (no default — must implement):

| Method | Returns |
|---|---|
| `list_playlists()` | `{casefolded name: playlist}` — the sync engine's name-keyed map |
| `create(sp_playlist)` | a new same-named playlist (copy name + description) |
| `playlist_tracks(playlist)` | existing tracks as dicts — **carry `isrc`** here; also `name`, `artists`/`artist`, `duration_ms`, `added_at`, and a stable id |
| `track_id(track)` | the provider's stable id for one of its tracks |
| `resolve(sp_track, cache)` | `(target_id, method)` for a track not yet linked — your search |
| `add(playlist, target_ids)` | append in order, **one request per id** (never batch — preserves date-added order) |
| `remove(playlist, track)` | remove one existing track |

The base class also supplies `replay_chronology()`. It stages duplicate copies of a recovered track and every newer
entry before retiring the old copies, so every replacement write succeeds before the original suffix is touched.
If the provider's ordinary `add()` suppresses duplicates, override `add_chronology_copies()` with the same ordered,
one-request-per-track behavior but with duplicate insertion enabled. Amazon Music and Qobuz are the reference adapters.
Set `replay_chronology = None` on the class if the provider cannot perform the repair safely (no positional insert,
a catalog-id-scoped delete, and reads that trail its own writes); the engine then appends in source order. `deezer.py`
is the reference for that.

**Override only if your dict shape differs from Spotify's** (`{"id", "name", "images", ...}`):
`playlist_id`, `playlist_name`, `playlist_description`, `playlist_count`. See `apple.py`
(`attributes.name`) and `ytmusic.py` (`playlistId`/`title`) for non-Spotify shapes.

**Override if the service exposes followed / non-owned playlists** (like Spotify):
`browse_playlists()` — return the full, un-deduped list, tagging each dict with `_owned`
(owner is the current user). The default returns `list(self.list_playlists().values())`
with everything treated as owned, which is correct for a service whose list API only
returns your own playlists (Apple, YouTube Music). `find_playlist()` scans
`browse_playlists()`, so you get correct id lookup for free.

**Optional performance/quality hooks:** `prefetch()` (batch work before resolving —
Apple bulk-fetches ISRCs), `native_isrc_map()` (expose `{track_id: ISRC}` your resolve
cache already knows), `expected_ids()`, `is_editable()`, and
`hydrate_playlist_counts()` (browse-only enrichment when the listing response omits totals).

**Resolve-cache path:** implement `resolve_cache_path(opts)` as a `classmethod` returning where
your `cache_file` lives (usually one `os.getenv`), and have `__init__` set
`self.cache_file = self.resolve_cache_path()`. The Mappings UI reads the path from the class,
with no configured account, so the environment lookup must have exactly one home.

**Reading a playlist by id, outside the library:** implement `fetch_playlist(playlist_id)` if the
service can open a playlist the account neither owns nor follows. Return the provider-native
playlist dict (the shape `playlist_page_reference` builds, with the real name, description and
count), or `None` when it cannot. That is what backs the "paste a playlist link" transfer source;
the base class returns `None`, so skipping it just means links to your service are refused with a
clear message instead of breaking. Most services need one metadata GET, because their track reads
are already addressed by bare id. Apple is the exception worth reading: a public link carries a
`pl.` **catalog** id, which its library endpoints cannot open at all, so its `fetch_playlist`
tags the reference `_catalog` and `playlist_tracks` branches on it.

**Native liked/favorite collection:** set `favorite_tracks_name` to the provider's user-facing
name and implement `favorite_tracks()`, `add_favorite_tracks(target_ids)`, and
`remove_favorite_track(track)`. `MirrorTarget.favorite_tracks_resource()` supplies the stable,
non-creatable virtual collection and the `resource_*` methods route reads/writes without making
the reconcile core provider-aware. Add the provider to `frontend/src/lib/likedTracks.ts`, then
extend its single contract case in `tests/test_favorite_tracks.py`.

### 2. Targets registry — `songmirror/engine/targets/__init__.py`

Three lines: add a builder to `_REGISTRY` (`source -> builder(opts, sp) -> target | None`,
returning `None` when unconfigured), the class to `_CLASSES` (the same providers by class, for the
facts a caller needs without credentials), and the id to `_SOURCE_ORDER`. **Put ISRC-rich
providers first** — they seed cross-provider identity for the rest. `test_targets_accessors`
asserts `_CLASSES` and `_REGISTRY` cover the same providers, so a missed line fails there.

### 3. Connector (auth) — `songmirror/services/accounts/<svc>.py`

Subclass `Connector` (`accounts/base.py`). Pick an `auth_kind`
(`oauth_redirect` | `oauth_device` | `token_paste` | `api_key`), set `config_fields`
(what the wizard asks the user for), and implement `status()` plus the methods for that
kind (e.g. `begin_redirect`/`complete_redirect` for OAuth, or `submit` for a pasted
token/key). The engine reads whatever the connector saves to the `SettingsStore`.

### 4. Connectors registry — `songmirror/services/accounts/__init__.py`

One line in `CONNECTORS`. The service now appears in the accounts wizard, the
source/target pickers, and transfers automatically.

### 5. Frontend branding — `frontend/src/lib/constants.ts` (+ two more)

- `SERVICE_STYLES`: a `{ label, dot, soft, text }` entry keyed by the provider id.
- `serviceLogoId()`: map the id to a logo id.
- `--color-svc-<svc>` / `-soft` CSS vars (where the other `svc-*` colors are defined) and
  the brand SVG in the `ServiceLogo` component.

Skip this and the provider still works — it just falls back to a neutral dot/label
(`DEFAULT_SERVICE_STYLE`) instead of its brand color and mark.

## Why the `== "spotify"` branches aren't your problem

A grep shows a handful of `source == "spotify"` checks in the engine. They are all
Spotify's role as the **identity anchor**, not per-provider special-casing:

- the archive `links` table maps `spotify_id -> target_id`, so links are only
  consulted/written when Spotify is the source (`base.py`);
- only Spotify exposes a `snapshot_id`, so the read-cache skip optimization keys on it
  (`runner.py`);
- `_canonicalize` skips the reverse-link lookup for Spotify because it *is* the anchor
  (`base.py`).

A new provider added as a **write target** or an **N-way peer** touches none of these — it
unifies through ISRC (or, lacking one, a fuzzy `track_key`). You would only revisit them
to make a *new* provider a second canonical hub, which isn't needed.

## Verify

- Unit-test your target's dict-shape accessors and any resolve/matching quirks — see
  `tests/test_targets_accessors.py` (accessors) and `tests/test_reconcile.py` (merge
  behavior). Fakes there are the template.
- `.venv/Scripts/python.exe -m pytest tests/ -q` and `pnpm -C frontend build`.
