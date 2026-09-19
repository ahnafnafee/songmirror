# Last.fm source and local-library-first download mirror

Design date: 2026-09-18
Status: implemented. See "Changes made during implementation" at the end for the
three points where the built version departs from the original design.

## Summary

Two additions, one dependent on the other:

1. **Last.fm as a read-only playlist source.** Loved Tracks, Top Tracks (six
   periods) and Recent Scrobbles become SongMirror playlists that sync to any
   connected service.
2. **A source-agnostic download mirror with a local-library-first resolver.**
   The mirror stops being Spotify-shaped, so a Last.fm playlist can feed it at
   all, and it prefers a file already present in the user's music library over
   a fresh lossy spotDL fetch.

Together these answer "download my Last.fm lists in high quality": the track
list comes from Last.fm, the audio comes from files the user already holds, and
spotDL fills only the gaps.

Part 2 is not optional polish. The mirror's entry points take a Spotify client
and read tracks through Spotify-specific paths, so part 1 cannot reach the
download mirror without it.

## Out of scope: streaming-catalog FLAC engines

ClashFLAC (`ajisth69/ClashFLAC`), the backend an earlier LastWave release used,
produces FLAC through three engines: Qobuz MD5-signed CDN stream URLs, TIDAL
DASH master manifests, and Amazon Music Widevine DRM decryption with FLAC
remuxing.

`docs/monochrome-flac-assessment.md`, a repo-local document that `.gitignore`
excludes, already sets this project's bar for any new
FLAC source: a provider-published, versioned download or export endpoint,
user-scoped authorization, explicit permanent-copy rights, documented territory,
expiry and offline-use rules, and no DRM or access-control bypass. None of the
three engines meet it. This design therefore adds no streaming-catalog FLAC
path, and the adapter boundaries documented in `engine/targets/qobuz.py` and
`engine/targets/tidal.py` stay where they are.

Note also that LastWave itself has moved off ClashFLAC. Its current release
describes a YouTube Music client with Opus audio, which is the same source the
existing spotDL mirror already uses.

## Part 1: Last.fm source

Follows `docs/adding-a-provider.md`, with the deviations a metadata-only,
write-incapable service forces.

### 1.1 API client, `songmirror/lastfm.py`

Thin `requests` wrapper over `https://ws.audioscrobbler.com/2.0/`. Auth is an
API key plus a username, both plain config values. No OAuth, no session key,
because every endpoint used here is a public read.

| Call | Endpoint | Notes |
| --- | --- | --- |
| Loved tracks | `user.getLovedTracks` | carries a `date.uts` love timestamp |
| Top tracks | `user.getTopTracks` | `period` in `7day`, `1month`, `3month`, `6month`, `12month`, `overall`; ranked, no timestamps |
| Recent scrobbles | `user.getRecentTracks` | carries `date.uts`; skip the `@attr.nowplaying` row |

Paging is `limit=200` plus `page=N`, looping to `@attr.totalPages`. Each request
goes through the existing `config.polite_sleep` so the client stays inside
Last.fm's request-rate guidance, matching how `targets/qobuz.py` already paces
itself.

### 1.2 Engine target, `songmirror/engine/targets/lastfm.py`

`LastfmTarget(MirrorTarget)`. Read methods are real; every write method raises
`TargetCapabilityError`, which `services/playlists.py:171` and
`services/transfers.py:245` already convert into a clean user-facing message,
exactly as Apple's subscription gate does today.

| Method | Behavior |
| --- | --- |
| `list_playlists()` | `{casefolded name: playlist}` over the eight virtual playlists |
| `playlist_tracks(playlist)` | track dicts, see shape below |
| `track_id(track)` | the Last.fm `mbid` when present, else a normalized `artist`/`title` composite |
| `create`, `add`, `remove`, `resolve` | raise `TargetCapabilityError` |
| `replay_chronology` | `None`; Last.fm has no positional insert, so the engine appends in source order (same choice as `deezer.py`) |
| `resolve_cache_path(opts)` | classmethod returning `LASTFM_CACHE_FILE`, present for Mappings-UI consistency and otherwise unused, because Last.fm is never a resolve destination |

Virtual playlists are fixed and non-creatable: `Loved Tracks`,
`Top Tracks (7 days)` through `Top Tracks (all time)`, and `Recent Scrobbles`.

Track dict shape, where `id` is whatever `track_id` produced:

```python
{"id": mbid_or_composite, "name": title, "artist": artist_name,
 "added_at": iso8601_or_None}
```

Two deliberate absences:

- **No `isrc`.** Last.fm returns artist and track name strings only. Every
  Last.fm track therefore unifies through the fuzzy `matching.track_key` path
  rather than through ISRC. This is a hard limit of the API, not a shortcut.
- **No `added_at` on the top-tracks playlists.** Those are ranked, not dated.
  The undated-track handling already present in the sync path covers this, so
  additions alongside undated tracks behave correctly.

`artist` is supplied as a plain string rather than a list, which is the shape
the one-way target path handles.

Favorites integration was deferred in this draft and then built; see "Auth
became two-level" below. Loved Tracks is the native favorites resource, not a
virtual playlist, so `list_playlists` returns seven entries rather than eight.

### 1.3 Registries

- `engine/targets/__init__.py`: one line each into `_REGISTRY`, `_CLASSES` and
  `_SOURCE_ORDER`. Last.fm goes **last** in `_SOURCE_ORDER`, because that list
  is ISRC-rich first and Last.fm carries no ISRC at all.
  `tests/test_targets_accessors.py` asserts `_REGISTRY` and `_CLASSES` cover the
  same providers, so a missed line fails there.
- `services/accounts/__init__.py`: one line into `CONNECTORS`.

### 1.4 Connector, `songmirror/services/accounts/lastfm.py`

`LastfmConnector(Connector)`, `auth_kind = "api_key"`, `config_fields` of
`LASTFM_API_KEY` (secret) and `LASTFM_USER`. `submit()` validates by calling
`user.getInfo` and reporting the resolved display name.

`status()` returns
`ConnStatus(capabilities=frozenset({"library_read"}))`. The narrower-than-full
capability set is already supported by `accounts/base.py`, so the accounts UI
and the target pickers correctly offer Last.fm as a source and not as a
destination without any new plumbing.

### 1.5 Frontend branding

`frontend/src/lib/constants.ts`: a `SERVICE_STYLES` entry, a `serviceLogoId()`
mapping, `--color-svc-lastfm` and `-soft` CSS vars alongside the other `svc-*`
colors, and the brand mark in `ServiceLogo`. Last.fm's brand red is `#D51007`.

## Part 2: download mirror

### 2.1 Source-agnostic entry points

Today `engine/downloads.py` exposes `run(sp, spotify_playlists, download_dir,
should_continue=None)` and `refresh(sp, spotify_playlists, download_dir)`, called
from `engine/runner.py:1078` and `engine/runner.py:863`. The `playlists`
argument is already a generic list of playlist dicts. The Spotify coupling is
confined to `read_tracks(sp, playlist_id)`, which branches across
`_read_tracks_api`, `_read_tracks_web` and `_read_tracks_cookie`.

Change: both entry points take a `read_tracks` callable of one playlist instead
of a Spotify client. `runner.py` passes the existing Spotify reader when the
source is Spotify, and `source.playlist_tracks` otherwise. The Spotify branches
move behind that default callable unchanged.

The decoupling is narrower than it looks. `sp` reaches only `read_tracks`, at
`downloads.py:653` and `downloads.py:701`. It is also threaded into
`_download_one` at `downloads.py:708`, but that function never reads it, so the
parameter is dead and gets dropped in the same change.

This is the smallest change that decouples the mirror. No new class, one
parameter shape.

### 2.2 Local-library-first resolver, `songmirror/engine/local_library.py`

Indexes an existing music tree and hands the mirror a real file when it already
has one.

- `index(root)` walks `root` for the extensions in `downloads.AUDIO_EXTS` and
  reads tags with `mutagen.File(path, easy=True)`, which is already the pattern
  at `downloads.py:321`. Produces `{"by_isrc": {...}, "by_key": {...}}`.
- `find(track, idx)` matches ISRC first, then falls back to
  `matching.track_key`. It calls the engine's own `matching.normalize_text` and
  `matching.track_key` rather than reimplementing normalization, so a local file
  matches by exactly the same rules as everything else in the engine.
- `place(src, folder, track)` copies into spotDL's
  `{album-artist}/{album}/{artists} - {title}.{ext}` layout, so a placed file
  is matched by `finalize_folder` exactly like a downloaded one. It copies
  rather than hard-links; see "Changes made during implementation".

Per track, the mirror now does: local match, place it, done; otherwise fall
through to spotDL as today. The `.m3u8` generation, cover handling, tagging and
incremental prune paths are untouched, because they already work from whatever
files are on disk in the playlist folder.

The index is built once per run and held in memory. For a very large library
this becomes the run's dominant cost, and the upgrade path is an mtime-keyed
on-disk index next to the other `*_cache.json` files. A `ponytail:` comment will
name that ceiling at the call site.

`mutagen` is already a pinned project dependency, so this adds none.

### 2.3 Existing quality knobs to document

Two settings already in the code raise mirror quality and are currently
undocumented in the accounts flow:

- `LOCAL_MIRROR_FORMAT=opus` keeps YouTube's native stream and skips the mp3
  re-encode.
- `LOCAL_MIRROR_COOKIE_FILE` with a YouTube Music Premium cookie raises the
  ceiling from roughly 128 kbps to 256 kbps AAC.

README gets both, next to the existing local-mirror notes.

## Configuration

| Key | Meaning | Default |
| --- | --- | --- |
| `LASTFM_API_KEY` | Last.fm API key | empty, connector unconfigured |
| `LASTFM_API_SECRET` | shared secret; required to authorize, read a private profile, or love tracks | empty, public reads only |
| `LASTFM_USER` | username to read; set automatically on authorization | empty, connector unconfigured |
| `LASTFM_SESSION_KEY` | written by the connector on authorization, infinite lifetime | empty, no writes |
| `LASTFM_CACHE_FILE` | resolve-cache path, Mappings-UI consistency only | `lastfm_resolve_cache.json` |
| `LOCAL_LIBRARY_DIR` | music tree searched before spotDL | empty, resolver off |

`LOCAL_LIBRARY_DIR` empty means the feature is off and the mirror behaves
exactly as it does now. That matches how `DOWNLOAD_DIR` and `JELLYFIN_URL`
already gate their features.

## Data flow

```
Last.fm  user.getLovedTracks / getTopTracks / getRecentTracks
   |     (title + artist strings, no ISRC)
   v
LastfmTarget.playlist_tracks
   |
   +--> sync / reconcile core  -> Spotify, TIDAL, Qobuz, Deezer, Amazon, Apple, YT Music
   |      (matches via matching.track_key, ISRC unavailable)
   |
   +--> downloads.run(read_tracks=...)
          |
          +-- local_library.find hit  -> os.link or copy2 from LOCAL_LIBRARY_DIR
          +-- miss                    -> spotDL, as today
```

## Error handling

- Missing or invalid `LASTFM_API_KEY` or `LASTFM_USER`: connector reports
  `unconfigured`, builder returns `None`, and the runner logs a clean skip via
  `log_note`, matching `_rest_provider`.
- Last.fm HTTP 429 or 5xx: raise `TargetTransientError` so the existing retry
  and backoff path applies.
- Last.fm selected as a sync destination: `TargetCapabilityError`, surfaced by
  the handlers already in `services/playlists.py` and `services/transfers.py`.
- `LOCAL_LIBRARY_DIR` missing or unreadable: log a warning once, treat every
  lookup as a miss, and let spotDL handle the run. The mirror must never fail a
  download because the resolver is misconfigured.
- Tag read failure on one local file: skip that file during indexing rather than
  aborting the index.

## Testing

New:

- `tests/test_lastfm.py`: paging across `totalPages`; the eight virtual
  playlists and their casefolded map; loved-track timestamps parsed; top tracks
  carrying no `added_at`; the `nowplaying` row skipped in recent tracks; no
  `isrc` key produced; `create`, `add`, `remove` and `resolve` each raising
  `TargetCapabilityError`.
- `tests/test_local_library.py`: ISRC hit; `track_key` fallback hit; miss
  returning `None`; hard link used within one volume; `copy2` fallback when
  `os.link` raises `OSError`; unreadable tag skipped during indexing.

Extended:

- `tests/test_targets_accessors.py`: registry parity picks up the new provider.
- `tests/test_connectors.py`: the new connector's status and validation.
- `tests/test_downloads.py`: the `read_tracks` callable seam, with the Spotify
  default path asserted unchanged.

Gates, per `docs/adding-a-provider.md`:

```
.venv/Scripts/python.exe -m pytest tests/ -q
pnpm -C frontend build
```

## Decisions taken

- **Last.fm is a source, never a peer.** It cannot accept playlist writes, so
  the write methods raise rather than the registry modeling a new "read-only
  provider" concept. `TargetCapabilityError` already exists for this and is
  already handled in both call paths.
- **No ISRC backfill in this pass.** Resolving Last.fm name strings to ISRCs
  through MusicBrainz would improve match quality and is a clean follow-up, but
  it is a separate feature with its own rate-limit and caching design.
- **Favorites contract deferred**, as noted in 1.2.
- **No streaming-catalog FLAC engine**, per the assessment cited above.

## Changes made during implementation

What the design got wrong or left out.

### Placement copies, it does not hard-link

The design proposed `os.link` with a `shutil.copy2` fallback. That is unsafe
here. `finalize_folder` stamps mtimes and backfills tags on every audio file it
finds in a playlist folder, and a hard link shares its inode with the library
original, so the mirror would rewrite the user's own library files as a side
effect of building a playlist. Placement now always copies.

Copying also matches what the mirror already does: a track in two playlists is
already stored twice, so per-playlist duplication is the existing behavior
rather than a new cost.

### The registry needed a "has no playlists" concept after all

The design said Last.fm's write methods would raise and that this was enough.
It is not. `is_peer` reports any provider in `_REGISTRY` as writable, so
Last.fm became a candidate mirror target and an N-way peer, and a "sync to
every connected service" pass would have raised `TargetCapabilityError` on the
Last.fm leg of an otherwise healthy run.

`MirrorTarget.supports_playlists` now carries the fact, defaulting True, and
`LastfmTarget` sets it False. The registry reads it through
`targets.supports_playlists(provider_id)` rather than restating a list, so
there is one authored declaration. It filters `build_peers`,
`nway_order_candidates` and `is_peer` outright; `build_targets` keeps such a
provider only for a liked-tracks job, because its favorites collection is
writable and that sync runs through the same per-target loop.
`run_target` drops the playlist phase for it in a single note instead of
failing once per selected playlist. `TargetCapabilityError` remains the
backstop for a direct playlist write.

### The mirror was gated on Spotify in the runner, not in downloads.py

Decoupling `engine/downloads.py` was necessary but not sufficient.
`runner._post_sync` returned early unless Spotify was the source, logging
"download mirror + Jellyfin covers currently require Spotify as the source",
so a Last.fm job would never have reached the mirror however source-agnostic
the mirror itself became.

`_post_sync` now takes the source target and builds the mirror's view through a
`_mirror_source` helper: the Spotify client when Spotify is the source, so
spotDL keeps resolving catalog URLs directly, and `downloads.TargetSource`
otherwise. The `--refresh-local` path goes through the same helper. Jellyfin
cover pushing is no longer gated either; a source that supplies no playlist art
simply keeps Jellyfin's auto-tiled cover, which `save_cover` and `push_covers`
already handle by returning early on a missing image URL.

`tests/test_downloads.py` guards both halves, including the regression that the
mirror is reached at all for a non-Spotify source.

### Auth became two-level, and Loved Tracks became writable

The design specified `auth_kind = "api_key"` and a strictly read-only provider.
That was revisited after asking whether a pasted cookie or request header could
replace the API key, as it does for the other seven providers.

It cannot, and the reason is worth recording. Every pasted credential in this
project sits in front of a real JSON API: Spotify's pathfinder, TIDAL's
JSON:API, Qobuz's `api.json/0.2`, Amazon's `pandaToken` endpoints, Apple's
`amp-api`. A Last.fm `sessionid` cookie sits in front of `www.last.fm`, which is
server-rendered HTML with no JSON equivalent, so a cookie connector would be an
HTML scraper rather than an API client. It would also be strictly more fragile
than what it replaced, since an API key never expires. And it would not remove
the key regardless: step 1 of every Last.fm auth path is "get an API key".

The real equivalent of "signed in" on Last.fm is a **session key**, so that is
what was built:

* `auth_kind` is now `oauth_redirect`. `begin_redirect` sends the user to
  `last.fm/api/auth` with `api_key` and `cb`; Last.fm redirects back with a
  `token` valid 60 minutes and usable once; `complete_redirect` exchanges it
  through `auth.getSession` for a session key of **infinite lifetime** and
  learns the username from the same response.
* Authenticated calls are signed: parameters ordered by name, concatenated as
  `<name><value>`, shared secret appended, md5. `format` and `api_sig` are
  excluded from the base string. `lastfm.sign` is the only place that builds it.
* Reads are signed whenever a session key exists, which is what makes a private
  profile readable. Write methods are POST with every parameter in the body.
* The API key alone still works for public reads, so the connector has two
  levels rather than a hard requirement.

That unlocked the favorites contract the design had deferred. **Loved Tracks is
now the native favorites resource** rather than an eighth virtual playlist,
matching how all seven other providers model their liked collections, and it is
writable once authorized. `validate_favorite_tracks` raises
`TargetCapabilityError` only when the session is missing, so reads never need it.

Two consequences for track identity:

* Ids are `<artist>␟<name>`, not the sometimes-present mbid, because
  `track.love` addresses a track by artist and title and `remove_favorite_track`
  recovers them from `track_id`. Canonical spelling drift re-keys an id, but the
  no-ISRC diff path compares on the normalized `track_key`, which absorbs case
  and punctuation changes.
* `resolve` asks `track.getInfo` with `autocorrect=1` for Last.fm's own
  spelling before composing an id, so a near-miss title does not create a
  second loved entry. Error code 6 stays a plain `LastfmError` rather than an
  auth failure, because on a write it means that one title was rejected; such a
  track is skipped with a warning instead of failing the collection.

### Playlists arrived after all, through the website

The section above concluded that a pasted cookie was not worth building, and for
the API that still holds: `auth.getSession` is a better credential than a cookie
for everything the API can do. What the reasoning missed is that the API cannot
do playlists at all. There are no `playlist.*` write methods, so the cookie is
not a worse route to the same place, it is the only route to a different one.

So the cookie connector was built, narrowly:

* `songmirror/lastfm_web.py` is an HTML client, separate from `lastfm.py`, and
  it never touches `ws.audioscrobbler.com`. Its docstring records each endpoint
  it depends on, because those are the parts most likely to move.
* The connector takes a pasted request (headers or cURL) and keeps only
  `sessionid` and `csrftoken`. Everything else in the paste is discarded.
* Every write re-reads `csrfmiddlewaretoken` from the page it is about to post
  to rather than reusing the pasted `csrftoken`, because the site issues a fresh
  one per page.
* `supports_playlists` became a **callable** the registry evaluates, so the
  capability is per account: without a web session the target behaves exactly as
  the rest of this document describes, and the runner drops the playlist phase
  with one note instead of failing the pass.
* Adding a track goes through `search-catalogue`, which is backed by video search
  and returns rows like `01 Kanye West - Power` by `KanyeWestVEVO` beside the
  canonical one. `_best_row` scores the rows instead of taking the first, and the
  resolve cache keys each decision so a repeat pass does not re-search.

Ids stay `<artist>␟<name>`, which now pays twice: `track.love` needs the pair,
and the website's add form posts those same two fields. Playlist entries carry
the site's own entry id as their occurrence id, since that is what removal
addresses.

Only the HTML parsing is covered by tests, against fixtures trimmed from real
pages. The endpoints themselves were traced once by hand against a live account.
