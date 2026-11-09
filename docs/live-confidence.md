# Live confidence run

`scripts/live_confidence.py` runs the real sync engine against your own connected accounts, on temporary playlists only. Run it locally before you open a pull request that touches syncing, matching, removals, or a provider. It cannot run in CI because it needs a signed-in session for every provider, and it refuses to start when the `CI` environment variable is set.

The unit tests prove the engine's rules against fakes. This run proves them against what each provider's API actually returns: real catalog searches, real playlist reads (including ones that lag after a write), and real write and delete calls.

## Run it

```bash
uv run python scripts/live_confidence.py --seed-playlist "Drive" --sessions shared
```

- `--seed-playlist` names an existing playlist on the seed provider (Jellyfin by default; change it with `--seed-provider`). Its first songs (`--seed-count`, default 8) are cloned. The playlist itself is only read, and the run checks that it is unchanged.
- `--sessions` is required, because some providers renew their session while they run:
  - `shared` writes renewed TIDAL, Deezer and Amazon Music sessions back to the data directory, so the live app keeps reading a valid session. Nothing else in the data directory is written.
  - `copy` never writes the data directory. A provider whose session would renew during the run (`--session-budget`, default 25 minutes) is skipped, because a renewal could sign the live app out.
- `--data-dir` points at the data directory that holds `settings.json` (default: the repository's `data/`, or `SONGMIRROR_CONFIDENCE_DATA_DIR`).
- `--providers spotify,tidal` limits the run. By default every provider the live app reports as connected for playlist writes is tested.
- `--merge-sources spotify,tidal` picks the two merge sources (default: the first two providers tested).
- `--jobs` sets how many providers are tested at once (default 4). Every provider also reads and writes the seed provider, so a local server like Jellyfin can drop connections under more load.

## What it checks

Each provider runs in its own process, up to `--jobs` at a time, with its own scratch directory, caches and song database:

| Stage | Checks |
|---|---|
| One-way | The seed clone reaches a new mirror playlist. A steady-state pass writes nothing. A deletion the source still offers reaches the mirror. A simulated delisting stays on the mirror and is reported. The saved catalog answer is reused without searching again. |
| Catalog | The provider's own catalog check finds every song on its playlist, both with its own metadata and with the seed provider's. A miss here means a user deletion on that provider would be kept as a delisting. |
| N-way | The provider and the seed provider pair up. A deletion on either side waits for its second read, then propagates and never comes back. The final pass is stable. |
| Merge | Two providers feed a seed-provider destination. A song removed from every source leaves it. A song one source delisted stays and names that source. The saved answer is reused. |
| Cleanup | Each worker deletes its temporary playlists and lists the provider again to verify them. A final sweep then lists every provider for this run's playlists, deletes any it finds, and verifies none remain. |

A delisting is simulated by hiding a song from every catalog lookup path of the source (search and resolve), since a real provider cannot be made to drop a song on demand.

## Safety

- Temporary playlists are named `SongMirror confidence <stamp> ...`, and the delete helper refuses any playlist without that prefix.
- Before starting, the script reads the live app (`--live-url`, default `http://127.0.0.1:8888`, `''` to skip) and refuses to run while a sync is running, within `--quiet-minutes` (default 15) of a scheduled sync, or when an enabled live job syncs every playlist on a tested provider, because that job could copy a temporary playlist to your other accounts.
- Credential files other than the three shared sessions are copied into the scratch directory, and resolve caches stay there.

## Results

The run prints one line per worker (`spotify  16/16 passed`), every failed check with its detail, and the path of `report.json` and the per-worker logs. It exits with status 1 when any check fails.

Some failures point at the environment, not the engine:

- `bootstrap copies the cloned songs` needs at least four seed songs that the provider's catalog has.
- A provider that briefly returns stale reads after a delete (YouTube Music does) needs an extra pass before a deletion confirms. The N-way checks allow up to two extra reads.

If a run is interrupted, delete what it left with:

```bash
uv run python scripts/live_confidence.py --sweep --sessions shared
```

## Adding a provider

No provider has a playlist delete API in the engine, so the script carries a test-only `delete_playlist` helper per provider. A new provider needs a branch there, or its run fails at cleanup and reports the leftover playlist by name.
