"""Ever-growing local SQLite archive + resolution memory.

The main tables in one file:
- songs:      every track ever seen on any service (never deleted) — a durable
              metadata record with first/last-seen timestamps.
- links:      spotify_id -> target_id for every successful match, so later
              passes match by hard identifier instead of re-searching.
- sync_state: a playlist's Spotify snapshot_id after a clean pass, so an
              unchanged pair can be skipped wholesale.
- playlist_cache / playlist_track_cache: the last complete normalized playlist
              read, so the in-app editor can reopen large playlists without a
              fresh provider round trip.

SQLite over a pickle blob: incremental writes, crash-safe, and inspectable
(`sqlite3 song_cache.db "SELECT name, artist, last_seen FROM songs"`).
"""

import json
import sqlite3
from datetime import datetime, timezone

SCHEMAS = [
    """
CREATE TABLE IF NOT EXISTS songs (
    source      TEXT NOT NULL,
    id          TEXT NOT NULL,
    isrc        TEXT,
    name        TEXT,
    artist      TEXT,
    album       TEXT,
    duration_ms INTEGER,
    meta        TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    PRIMARY KEY (source, id)
)
""",
    """
CREATE TABLE IF NOT EXISTS links (
    spotify_id TEXT NOT NULL,
    target     TEXT NOT NULL,
    target_id  TEXT NOT NULL,
    updated    TEXT NOT NULL,
    PRIMARY KEY (spotify_id, target)
)
""",
    """
CREATE TABLE IF NOT EXISTS sync_state (
    pair         TEXT NOT NULL,
    target       TEXT NOT NULL,
    snapshot_id  TEXT,
    target_count INTEGER,
    updated      TEXT NOT NULL,
    PRIMARY KEY (pair, target)
)
""",
    # N-way sync: the canonical membership of a logical playlist ON EACH PROVIDER
    # after the last clean pass. Per-provider (not one shared set) is essential:
    # a track absent from a provider's own prior membership is never a removal
    # there, so a track that simply can't be matched on that service is not
    # mistaken for a user deletion. See targets/base.py.
    """
CREATE TABLE IF NOT EXISTS playlist_state (
    playlist     TEXT NOT NULL,
    source       TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    PRIMARY KEY (playlist, source, canonical_id)
)
""",
    # Membership rows alone cannot distinguish "never initialized" from an
    # initialized empty playlist. N-way merge semantics need that distinction:
    # a newly connected peer contributes bootstrap state, while an established
    # empty peer can contribute a real deletion. Keep the marker separately so
    # an empty canonical set remains representable.
    """
CREATE TABLE IF NOT EXISTS playlist_state_meta (
    playlist            TEXT NOT NULL,
    source              TEXT NOT NULL,
    initialized_at      TEXT NOT NULL,
    physical_playlist_id TEXT,
    PRIMARY KEY (playlist, source)
)
""",
    # One trusted executing pass has observed this established baseline member
    # missing from its provider. N-way reconcile requires the same absence on a
    # second trusted pass before it may propagate a deletion elsewhere.
    """
CREATE TABLE IF NOT EXISTS playlist_pending_removal (
    playlist      TEXT NOT NULL,
    source        TEXT NOT NULL,
    canonical_id  TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (playlist, source, canonical_id)
)
""",
    # The last HARD canonical id (ISRC / Spotify-linked) a provider's track
    # resolved to. Provider metadata is mutable: YouTube's youtubei read
    # alternates between a track's artist and its auto-generated channel for the
    # same video, and a re-keyed entry is indistinguishable from a deletion. So
    # once a physical entry has earned a hard identity it keeps it, even when a
    # later read is too degraded to derive one. See targets/base.py.
    """
CREATE TABLE IF NOT EXISTS track_identity (
    source       TEXT NOT NULL,
    track_id     TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    updated      TEXT NOT NULL,
    PRIMARY KEY (source, track_id)
)
""",
    # Every hard identity a stable provider track has held. The current value in
    # track_identity is global to the provider track, while playlist baselines
    # are scoped per playlist; retaining transition history lets each playlist
    # repair OLD -> NEW when it is reconciled, instead of only the first one.
    """
CREATE TABLE IF NOT EXISTS track_identity_history (
    source       TEXT NOT NULL,
    track_id     TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    observed_at  TEXT NOT NULL,
    PRIMARY KEY (source, track_id, canonical_id)
)
""",
    # Ordered per-provider snapshots of each playlist, kept as a short history.
    # A recovery / forensics trail (what did this playlist look like, in order,
    # and when) — the sync logic itself never reads these back.
    """
CREATE TABLE IF NOT EXISTS playlist_order (
    playlist    TEXT NOT NULL,
    source      TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    tracks      TEXT NOT NULL,
    PRIMARY KEY (playlist, source, captured_at)
)
""",
    # Persistent, inspectable cache for the in-app playlist ledger. Keep the
    # playlist metadata and ordered physical entries relational rather than in
    # one opaque JSON blob: this makes provider coverage/order easy to audit and
    # lets a future migration enrich individual rows without rewriting a large
    # payload.
    """
CREATE TABLE IF NOT EXISTS playlist_cache (
    provider     TEXT NOT NULL,
    playlist_id  TEXT NOT NULL,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,
    count        INTEGER NOT NULL,
    image        TEXT NOT NULL,
    owned        INTEGER NOT NULL,
    editable     INTEGER NOT NULL,
    external_url TEXT NOT NULL,
    refreshed_at TEXT NOT NULL,
    PRIMARY KEY (provider, playlist_id)
)
""",
    """
CREATE TABLE IF NOT EXISTS playlist_track_cache (
    provider      TEXT NOT NULL,
    playlist_id   TEXT NOT NULL,
    position      INTEGER NOT NULL,
    track_id      TEXT NOT NULL,
    isrc          TEXT NOT NULL,
    occurrence_id TEXT NOT NULL,
    name          TEXT NOT NULL,
    artist        TEXT NOT NULL,
    album         TEXT,
    duration_ms   INTEGER,
    image         TEXT NOT NULL,
    added_at      TEXT NOT NULL,
    external_url  TEXT NOT NULL,
    PRIMARY KEY (provider, playlist_id, position)
)
""",
    """
CREATE INDEX IF NOT EXISTS idx_playlist_track_cache_track
ON playlist_track_cache (provider, track_id)
""",
]

# Columns whose values historically held a provider type (``spotify``,
# ``tidal``, ...), but now hold an account-profile identity. Profile-aware
# archive opens migrate them every time because an older headless CLI may write
# fresh legacy rows into a database after the first web-app upgrade.
_PROFILE_ID_COLUMNS = (
    ("songs", "source"),
    ("links", "target"),
    ("sync_state", "target"),
    ("playlist_state", "source"),
    ("playlist_state_meta", "source"),
    ("playlist_pending_removal", "source"),
    ("track_identity", "source"),
    ("track_identity_history", "source"),
    ("playlist_order", "source"),
)

_GROUP_KEY_COLUMNS = (
    ("sync_state", "pair"),
    ("playlist_state", "playlist"),
    ("playlist_state_meta", "playlist"),
    ("playlist_pending_removal", "playlist"),
    ("playlist_order", "playlist"),
)

UPSERT = """
INSERT INTO songs (source, id, isrc, name, artist, album, duration_ms, meta, first_seen, last_seen)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(source, id) DO UPDATE SET
    isrc = excluded.isrc, name = excluded.name, artist = excluded.artist,
    album = excluded.album, duration_ms = excluded.duration_ms,
    meta = excluded.meta, last_seen = excluded.last_seen
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path, source_aliases=None):
    # Connections are opened on the coordinator thread and then assigned
    # exclusively to one provider worker. check_same_thread=False permits that
    # handoff; separate connections plus the timeout safely serialize file writes.
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    # Migrate a pre-per-provider playlist_state (no `source` column). It's
    # regenerable snapshot state, so drop it and let the schema recreate it.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(playlist_state)").fetchall()]
    if cols and "source" not in cols:
        conn.execute("DROP TABLE playlist_state")
    for schema in SCHEMAS:
        conn.execute(schema)
    cache_cols = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(playlist_track_cache)"
        ).fetchall()
    ]
    if cache_cols and "isrc" not in cache_cols:
        conn.execute(
            "ALTER TABLE playlist_track_cache "
            "ADD COLUMN isrc TEXT NOT NULL DEFAULT ''"
        )
    state_meta_cols = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(playlist_state_meta)"
        ).fetchall()
    ]
    if state_meta_cols and "physical_playlist_id" not in state_meta_cols:
        conn.execute(
            "ALTER TABLE playlist_state_meta "
            "ADD COLUMN physical_playlist_id TEXT"
        )
    # Existing non-empty baselines predate playlist_state_meta. Mark them as
    # initialized in place; providers with no rows remain correctly classified
    # as bootstrap peers on their next N-way pass.
    now = _now()
    conn.execute(
        "INSERT OR IGNORE INTO playlist_state_meta (playlist, source, initialized_at) "
        "SELECT DISTINCT playlist, source, ? FROM playlist_state",
        (now,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO track_identity_history "
        "SELECT source, track_id, canonical_id, updated FROM track_identity",
    )
    conn.commit()
    if source_aliases:
        try:
            _migrate_profile_namespaces(conn, source_aliases)
        except Exception:
            conn.close()
            raise
    return conn


def _table_columns(conn, table):
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def _insert_remapped_rows(conn, table, column, old, new, *, extra="", params=()):
    """Copy matching rows with one column replaced, preserving destination rows."""
    columns = _table_columns(conn, table)
    quoted = ", ".join(f'"{name}"' for name in columns)
    selected = ", ".join("?" if name == column else f'"{name}"' for name in columns)
    conn.execute(
        f'INSERT OR IGNORE INTO "{table}" ({quoted}) '
        f'SELECT {selected} FROM "{table}" WHERE "{column}" = ?{extra}',
        (new, old, *params),
    )


def _remap_column_value(conn, table, column, old, new):
    if old == new:
        return
    _insert_remapped_rows(conn, table, column, old, new)
    conn.execute(f'DELETE FROM "{table}" WHERE "{column}" = ?', (old,))


def _profile_group_key(value, aliases):
    """Rewrite the authority set embedded in an authoritative-group state key."""
    value = str(value)
    if not value.startswith("group:"):
        return value
    authorities, separator, logical_key = value.removeprefix("group:").partition(":")
    if not separator:
        return value
    mapped = sorted({aliases.get(identity, identity) for identity in authorities.split(",")})
    return f"group:{','.join(mapped)}:{logical_key}"


def _migrate_playlist_cache(conn, old, new):
    """Move complete cached ledgers without blending colliding snapshots."""
    legacy_ids = conn.execute(
        "SELECT playlist_id FROM playlist_cache WHERE provider = ?", (old,)
    ).fetchall()
    for (playlist_id,) in legacy_ids:
        destination = conn.execute(
            "SELECT 1 FROM playlist_cache WHERE provider = ? AND playlist_id = ?",
            (new, playlist_id),
        ).fetchone()
        if destination is None:
            # An orphaned destination track set has no readable header and must
            # not collide position-by-position with the complete legacy ledger.
            conn.execute(
                "DELETE FROM playlist_track_cache WHERE provider = ? AND playlist_id = ?",
                (new, playlist_id),
            )
            _insert_remapped_rows(
                conn,
                "playlist_track_cache",
                "provider",
                old,
                new,
                extra=" AND playlist_id = ?",
                params=(playlist_id,),
            )
            _insert_remapped_rows(
                conn,
                "playlist_cache",
                "provider",
                old,
                new,
                extra=" AND playlist_id = ?",
                params=(playlist_id,),
            )
    # A profile-era destination ledger wins a collision as one atomic snapshot;
    # never merge extra legacy positions into it.
    conn.execute("DELETE FROM playlist_track_cache WHERE provider = ?", (old,))
    conn.execute("DELETE FROM playlist_cache WHERE provider = ?", (old,))


def _migrate_profile_namespaces(conn, source_aliases):
    """Atomically move legacy provider-keyed state to default profile ids.

    Inserts happen before deletes and use ``OR IGNORE`` so current profile-era
    rows win primary-key collisions. Membership/history tables naturally union
    non-conflicting evidence. The transaction makes a failed copy fully
    rollback-safe, and the absence of a one-time marker lets later legacy CLI
    writes migrate on the next profile-aware open.
    """
    aliases = {
        str(old): str(new)
        for old, new in source_aliases.items()
        if old and new and str(old) != str(new)
    }
    if not aliases:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        for old, new in aliases.items():
            for table, column in _PROFILE_ID_COLUMNS:
                _remap_column_value(conn, table, column, old, new)
            _migrate_playlist_cache(conn, old, new)

        # Group reconciliation keys embed a sorted authority set in addition to
        # carrying a source column. Rewrite both dimensions so established
        # baselines and pending-removal confirmations survive the upgrade.
        for table, column in _GROUP_KEY_COLUMNS:
            values = conn.execute(
                f'SELECT DISTINCT "{column}" FROM "{table}" '
                f'WHERE "{column}" LIKE \'group:%\''
            ).fetchall()
            for (old_value,) in values:
                new_value = _profile_group_key(old_value, aliases)
                if new_value != old_value:
                    _remap_column_value(conn, table, column, old_value, new_value)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert_many(conn, source, tracks):
    """Archive the sync's own snapshot dicts (any service shape). first_seen is
    preserved on refresh; meta keeps the full snapshot as JSON."""
    now = _now()
    rows = []
    for track in tracks:
        song_id = track.get("id") or track.get("catalog_id") or track.get("relationship_id")
        if not song_id:
            continue
        artist = track.get("artist") or ", ".join(track.get("artists") or [])
        rows.append((
            source, song_id, track.get("isrc"), track.get("name"), artist,
            track.get("album"), track.get("duration_ms"),
            json.dumps(track, ensure_ascii=False), now, now,
        ))
    if rows:
        conn.executemany(UPSERT, rows)
        conn.commit()
    return len(rows)


def get_links(conn, target, spotify_ids):
    """{spotify_id: target_id} for previously matched tracks."""
    out = {}
    ids = [i for i in spotify_ids if i]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT spotify_id, target_id FROM links WHERE target = ? AND spotify_id IN ({marks})",
            [target, *chunk],
        )
        out.update(dict(rows.fetchall()))
    return out


def set_links(conn, target, mapping):
    # ponytail: links are trusted forever; delete a row to force re-resolution
    # if a linked id ever goes stale (e.g. a regional catalog pull).
    rows = [(sid, target, tid, _now()) for sid, tid in mapping.items() if sid and tid]
    if rows:
        conn.executemany("INSERT OR REPLACE INTO links VALUES (?, ?, ?, ?)", rows)
        conn.commit()


def delete_links(conn, target, spotify_ids):
    """Forget proven-bad Spotify mappings so the next pass resolves again."""
    ids = [spotify_id for spotify_id in spotify_ids if spotify_id]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        conn.execute(
            f"DELETE FROM links WHERE target = ? AND spotify_id IN ({marks})",
            [target, *chunk],
        )
    if ids:
        conn.commit()


def get_state(conn, pair, target):
    return conn.execute(
        "SELECT snapshot_id, target_count FROM sync_state WHERE pair = ? AND target = ?", (pair, target)
    ).fetchone()


def set_state(conn, pair, target, snapshot_id, target_count):
    conn.execute(
        "INSERT OR REPLACE INTO sync_state VALUES (?, ?, ?, ?, ?)",
        (pair, target, snapshot_id, target_count, _now()),
    )
    conn.commit()


def _in_chunks(conn, sql, prefix, ids):
    out = {}
    ids = [i for i in ids if i]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(sql.format(marks=marks), [*prefix, *chunk])
        out.update(dict(rows.fetchall()))
    return out


def get_reverse_links(conn, target, target_ids):
    """{target_id: spotify_id} — the inverse of get_links, so a non-Spotify
    track can be traced back to its canonical Spotify identity."""
    return _in_chunks(
        conn, "SELECT target_id, spotify_id FROM links WHERE target = ? AND target_id IN ({marks})",
        [target], target_ids)


def get_isrcs(conn, source, ids):
    """{id: isrc} from the songs archive for a source (only rows that have one)."""
    got = _in_chunks(
        conn, "SELECT id, isrc FROM songs WHERE source = ? AND isrc IS NOT NULL AND id IN ({marks})",
        [source], ids)
    return {k: v for k, v in got.items() if v}


def get_isrcs_from_sources(conn, sources, ids):
    """ISRCs for globally stable track ids seen through any selected account.

    Spotify catalog ids are shared by its accounts, but a track may only have
    been archived through a custom profile. Preserve source order on the rare
    conflicting row and stop querying once every requested id is satisfied.
    """
    wanted = [track_id for track_id in ids if track_id]
    out = {}
    for source in dict.fromkeys(source for source in sources if source):
        remaining = [track_id for track_id in wanted if track_id not in out]
        if not remaining:
            break
        for track_id, isrc in get_isrcs(conn, source, remaining).items():
            out.setdefault(track_id, isrc)
    return out


def get_snapshots(conn, source, ids):
    """{id: last archived snapshot dict} for a source's tracks.

    `meta` holds the provider row exactly as a previous read returned it, so a
    catalog entry the provider can no longer describe is still identifiable by
    what it was. Rows without a usable title are dropped: reconcile ignores
    them anyway, and an unnamed entry cannot carry a canonical identity."""
    rows = _in_chunks(
        conn, "SELECT id, meta FROM songs WHERE source = ? AND meta IS NOT NULL "
              "AND id IN ({marks})", [source], ids)
    out = {}
    for song_id, meta in rows.items():
        try:
            snapshot = json.loads(meta)
        except (TypeError, ValueError):
            continue
        if isinstance(snapshot, dict) and str(snapshot.get("name") or "").strip():
            out[song_id] = snapshot
    return out


def get_identities(conn, source, track_ids):
    """{track_id: canonical_id} recorded for this provider's existing tracks."""
    return _in_chunks(
        conn, "SELECT track_id, canonical_id FROM track_identity WHERE source = ? "
              "AND track_id IN ({marks})", [source], track_ids)


def get_identity_crosswalk(conn, source, target, source_track_ids):
    """{source_track_id: target_track_id} joined through a proven hard identity.

    This deliberately reads the current identity table, including tracks last
    seen in a playlist that has since been deleted. That history is the fastest
    and most precise way to rebuild a replacement without catalog searches.
    When one recording has several target catalog ids, prefer the most recently
    proven one deterministically.
    """
    out = {}
    ids = [track_id for track_id in source_track_ids if track_id]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT src.track_id, dst.track_id "
            f"FROM track_identity AS src "
            f"JOIN track_identity AS dst ON dst.canonical_id = src.canonical_id "
            f"WHERE src.source = ? AND dst.source = ? "
            f"AND src.canonical_id LIKE 'i:%' AND src.track_id IN ({marks}) "
            f"ORDER BY dst.updated DESC, dst.track_id",
            [source, target, *chunk],
        )
        for source_id, target_id in rows:
            out.setdefault(source_id, target_id)
    return out


def get_song_history(conn, source):
    """Provider tracks seen before, newest evidence first, in target-like shape."""
    rows = conn.execute(
        "SELECT id, isrc, name, artist, album, duration_ms, meta, last_seen "
        "FROM songs WHERE source = ? ORDER BY last_seen DESC, id",
        (source,),
    )
    out = []
    for track_id, isrc, name, artist, album, duration_ms, meta, last_seen in rows:
        try:
            track = json.loads(meta) if meta else {}
        except (TypeError, json.JSONDecodeError):
            track = {}
        track.setdefault("id", track_id)
        track.setdefault("isrc", isrc)
        track.setdefault("name", name or "")
        track.setdefault("artist", artist or "")
        track.setdefault("artists", [artist] if artist else [])
        track.setdefault("album", album)
        track.setdefault("duration_ms", duration_ms)
        track["_archive_id"] = track_id
        track["_archive_last_seen"] = last_seen
        out.append(track)
    return out


def get_identity_history(conn, source, track_ids):
    """{track_id: {canonical_ids}} retained across hard-identity corrections."""
    out = {}
    ids = [track_id for track_id in track_ids if track_id]
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT track_id, canonical_id FROM track_identity_history "
            f"WHERE source = ? AND track_id IN ({marks})",
            [source, *chunk],
        )
        for track_id, canonical_id in rows:
            out.setdefault(track_id, set()).add(canonical_id)
    return out


def set_identities(conn, source, mapping):
    """Remember what each track resolved to. Only hard ids are ever stored, so a
    later degraded read yields to the identity the entry already earned."""
    rows = [(source, tid, cid, _now()) for tid, cid in mapping.items() if tid and cid]
    if rows:
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO track_identity_history VALUES (?, ?, ?, ?)", rows)
            conn.executemany("INSERT OR REPLACE INTO track_identity VALUES (?, ?, ?, ?)", rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


ORDER_HISTORY_KEEP = 12


def record_order(conn, playlist, source, entries):
    """Append one ordered snapshot ([[track_id, name, artist], ...]) of a
    provider's playlist — skipped when identical to the newest stored one, and
    pruned to the last ORDER_HISTORY_KEEP per (playlist, source)."""
    payload = json.dumps(entries, ensure_ascii=False)
    last = conn.execute(
        "SELECT tracks FROM playlist_order WHERE playlist = ? AND source = ? "
        "ORDER BY captured_at DESC LIMIT 1", (playlist, source)).fetchone()
    if last and last[0] == payload:
        return
    conn.execute("INSERT OR REPLACE INTO playlist_order VALUES (?, ?, ?, ?)",
                 (playlist, source, _now(), payload))
    conn.execute(
        "DELETE FROM playlist_order WHERE playlist = ? AND source = ? AND captured_at NOT IN ("
        "SELECT captured_at FROM playlist_order WHERE playlist = ? AND source = ? "
        "ORDER BY captured_at DESC LIMIT ?)",
        (playlist, source, playlist, source, ORDER_HISTORY_KEEP))
    conn.commit()


def get_order_history(conn, playlist, source):
    """[(captured_at, [[track_id, name, artist], ...]), ...] newest first."""
    rows = conn.execute(
        "SELECT captured_at, tracks FROM playlist_order WHERE playlist = ? AND source = ? "
        "ORDER BY captured_at DESC", (playlist, source))
    return [(ts, json.loads(t)) for ts, t in rows.fetchall()]


def get_playlist_state(conn, playlist, source):
    rows = conn.execute("SELECT canonical_id FROM playlist_state WHERE playlist = ? AND source = ?",
                        (playlist, source))
    return {r[0] for r in rows.fetchall()}


def has_playlist_state(conn, playlist, source):
    """Whether this provider has an initialized N-way baseline, including an
    intentionally empty one. Membership rows are accepted for compatibility
    with databases created before playlist_state_meta existed."""
    row = conn.execute(
        "SELECT 1 FROM playlist_state_meta WHERE playlist = ? AND source = ? "
        "UNION ALL "
        "SELECT 1 FROM playlist_state WHERE playlist = ? AND source = ? LIMIT 1",
        (playlist, source, playlist, source),
    ).fetchone()
    return row is not None


def get_playlist_physical_id(conn, playlist, source):
    """Provider playlist id associated with this baseline, if recorded."""
    row = conn.execute(
        "SELECT physical_playlist_id FROM playlist_state_meta "
        "WHERE playlist = ? AND source = ?",
        (playlist, source),
    ).fetchone()
    return row[0] if row and row[0] else None


def get_pending_removals(conn, playlist, source):
    """Canonical ids absent on one prior trusted N-way pass for this source."""
    rows = conn.execute(
        "SELECT canonical_id FROM playlist_pending_removal "
        "WHERE playlist = ? AND source = ?",
        (playlist, source),
    )
    return {row[0] for row in rows.fetchall()}


def commit_reconcile_membership(conn, playlist, state_updates, pending_updates,
                                physical_playlist_ids=None):
    """Atomically replace selected baselines and pending removal observations.

    A source absent from either mapping is untouched. An empty set explicitly
    clears that side. This runs only after provider writes succeed, keeping a
    crash or exception retry-safe: state never claims an external write landed
    when it did not, and a failed pass never confirms a deletion.
    """
    now = _now()
    physical_playlist_ids = physical_playlist_ids or {}
    try:
        for source, canonical_ids in state_updates.items():
            conn.execute(
                "INSERT INTO playlist_state_meta "
                "(playlist, source, initialized_at, physical_playlist_id) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(playlist, source) DO UPDATE SET "
                "initialized_at = excluded.initialized_at, "
                "physical_playlist_id = COALESCE(excluded.physical_playlist_id, "
                "playlist_state_meta.physical_playlist_id)",
                (playlist, source, now, physical_playlist_ids.get(source)),
            )
            conn.execute(
                "DELETE FROM playlist_state WHERE playlist = ? AND source = ?",
                (playlist, source),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO playlist_state VALUES (?, ?, ?)",
                [(playlist, source, cid) for cid in canonical_ids],
            )
        for source, canonical_ids in pending_updates.items():
            canonical_ids = set(canonical_ids)
            existing = get_pending_removals(conn, playlist, source)
            conn.executemany(
                "DELETE FROM playlist_pending_removal "
                "WHERE playlist = ? AND source = ? AND canonical_id = ?",
                [(playlist, source, cid) for cid in existing - canonical_ids],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO playlist_pending_removal VALUES (?, ?, ?, ?)",
                [(playlist, source, cid, now) for cid in canonical_ids],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def set_playlist_state(conn, playlist, source, canonical_ids):
    """Replace one provider's baseline and clear obsolete pending removals."""
    commit_reconcile_membership(
        conn, playlist, {source: canonical_ids}, {source: set()})


def set_reconcile_identities(conn, playlist, repaired_states, learned_identities):
    """Atomically persist identity learning and any source-local baseline repair.

    A stable physical entry can move from one hard canonical id to another as
    provider metadata improves. Committing the new ``track_identity`` without
    remapping its old playlist baseline loses the evidence of that transition
    and makes the next pass look like a deletion. Keep both sides in one SQLite
    transaction, after every provider read has succeeded.
    """
    now = _now()
    try:
        for source, canonical_ids in repaired_states.items():
            conn.execute(
                "INSERT INTO playlist_state_meta (playlist, source, initialized_at) VALUES (?, ?, ?) "
                "ON CONFLICT(playlist, source) DO UPDATE SET initialized_at = excluded.initialized_at",
                (playlist, source, now),
            )
            conn.execute(
                "DELETE FROM playlist_state WHERE playlist = ? AND source = ?",
                (playlist, source),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO playlist_state VALUES (?, ?, ?)",
                [(playlist, source, cid) for cid in canonical_ids],
            )
            conn.execute(
                "DELETE FROM playlist_pending_removal WHERE playlist = ? AND source = ?",
                (playlist, source),
            )
        rows = [
            (source, track_id, canonical_id, now)
            for source, mapping in learned_identities.items()
            for track_id, canonical_id in mapping.items()
            if track_id and canonical_id
        ]
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO track_identity_history VALUES (?, ?, ?, ?)", rows)
            conn.executemany("INSERT OR REPLACE INTO track_identity VALUES (?, ?, ?, ?)", rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def clear_playlist_state(conn, playlist):
    """Drop a playlist's stored N-way baselines (every source) — the next pass
    re-bootstraps from what's actually on each provider, so out-of-band edits
    (e.g. the duplicate cleanup) are never read back as user deletions."""
    conn.execute("DELETE FROM playlist_state WHERE playlist = ?", (playlist,))
    conn.execute("DELETE FROM playlist_state_meta WHERE playlist = ?", (playlist,))
    conn.execute("DELETE FROM playlist_pending_removal WHERE playlist = ?", (playlist,))
    conn.commit()


def get_playlist_detail_cache(conn, provider, playlist_id):
    """Return the last complete normalized playlist read, or ``None``.

    Tracks are always returned in provider playlist order. A header without its
    declared number of rows is treated as an interrupted/corrupt cache miss.
    """
    row = conn.execute(
        "SELECT name, description, count, image, owned, editable, external_url "
        "FROM playlist_cache WHERE provider = ? AND playlist_id = ?",
        (str(provider), str(playlist_id)),
    ).fetchone()
    if row is None:
        return None
    tracks = conn.execute(
        "SELECT position, track_id, isrc, occurrence_id, name, artist, album, "
        "duration_ms, image, added_at, external_url "
        "FROM playlist_track_cache WHERE provider = ? AND playlist_id = ? "
        "ORDER BY position",
        (str(provider), str(playlist_id)),
    ).fetchall()
    if len(tracks) != int(row[2]):
        return None
    return {
        "provider": str(provider),
        "id": str(playlist_id),
        "name": row[0],
        "description": row[1],
        "count": int(row[2]),
        "image": row[3],
        "owned": bool(row[4]),
        "editable": bool(row[5]),
        "external_url": row[6],
        "tracks": [
            {
                "position": int(track[0]),
                "id": track[1],
                "isrc": track[2],
                "occurrence_id": track[3],
                "name": track[4],
                "artist": track[5],
                "album": track[6],
                "duration_ms": track[7],
                "image": track[8],
                "added_at": track[9],
                "external_url": track[10],
            }
            for track in tracks
        ],
    }


def set_playlist_detail_cache(conn, detail):
    """Atomically replace one playlist ledger and archive its provider songs."""
    provider = str(detail["provider"])
    playlist_id = str(detail["id"])
    tracks = list(detail.get("tracks") or [])
    now = _now()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO playlist_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                provider,
                playlist_id,
                str(detail.get("name") or ""),
                str(detail.get("description") or ""),
                len(tracks),
                str(detail.get("image") or ""),
                int(bool(detail.get("owned", True))),
                int(bool(detail.get("editable", False))),
                str(detail.get("external_url") or ""),
                now,
            ),
        )
        conn.execute(
            "DELETE FROM playlist_track_cache WHERE provider = ? AND playlist_id = ?",
            (provider, playlist_id),
        )
        conn.executemany(
            "INSERT INTO playlist_track_cache "
            "(provider, playlist_id, position, track_id, isrc, occurrence_id, "
            "name, artist, album, duration_ms, image, added_at, external_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    provider,
                    playlist_id,
                    int(track["position"]),
                    str(track["id"]),
                    str(track.get("isrc") or ""),
                    str(track.get("occurrence_id") or ""),
                    str(track.get("name") or "Unknown track"),
                    str(track.get("artist") or ""),
                    track.get("album"),
                    track.get("duration_ms"),
                    str(track.get("image") or ""),
                    str(track.get("added_at") or ""),
                    str(track.get("external_url") or ""),
                )
                for track in tracks
            ],
        )
        # A playlist read is also authoritative evidence that these provider
        # songs exist. Feed the same rows into the durable all-provider archive
        # instead of maintaining a disconnected UI-only cache.
        conn.executemany(
            UPSERT,
            [
                (
                    provider,
                    str(track["id"]),
                    track.get("isrc"),
                    str(track.get("name") or "Unknown track"),
                    str(track.get("artist") or ""),
                    track.get("album"),
                    track.get("duration_ms"),
                    json.dumps(track, ensure_ascii=False),
                    now,
                    now,
                )
                for track in tracks
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def invalidate_playlist_detail_cache(conn, provider, playlist_id):
    """Drop one cached ledger before/after a write whose result may be partial."""
    conn.execute(
        "DELETE FROM playlist_track_cache WHERE provider = ? AND playlist_id = ?",
        (str(provider), str(playlist_id)),
    )
    conn.execute(
        "DELETE FROM playlist_cache WHERE provider = ? AND playlist_id = ?",
        (str(provider), str(playlist_id)),
    )
    conn.commit()


def prune_playlist_detail_cache(conn, provider, playlist_ids):
    """Discard cached ledgers for provider playlists that no longer exist."""
    provider = str(provider)
    keep = {str(playlist_id) for playlist_id in playlist_ids if playlist_id is not None}
    cached = {
        row[0]
        for row in conn.execute(
            "SELECT playlist_id FROM playlist_cache WHERE provider = ?", (provider,)
        ).fetchall()
    }
    stale = cached - keep
    if not stale:
        return
    conn.executemany(
        "DELETE FROM playlist_track_cache WHERE provider = ? AND playlist_id = ?",
        [(provider, playlist_id) for playlist_id in stale],
    )
    conn.executemany(
        "DELETE FROM playlist_cache WHERE provider = ? AND playlist_id = ?",
        [(provider, playlist_id) for playlist_id in stale],
    )
    conn.commit()


def reset_playlist_peer_state(conn, playlist, source):
    """Forget one provider's state after its physical playlist is recreated.

    Playlist state is keyed by logical pairing so it survives ordinary provider
    metadata changes. A newly created playlist is the exception: carrying the
    deleted playlist's baseline forward makes an empty replacement look like a
    collapsed API read. Clear both N-way membership and the one-way snapshot so
    the replacement bootstraps from the current source instead of being skipped.
    """
    conn.execute(
        "DELETE FROM playlist_state WHERE playlist = ? AND source = ?",
        (playlist, source),
    )
    conn.execute(
        "DELETE FROM playlist_state_meta WHERE playlist = ? AND source = ?",
        (playlist, source),
    )
    conn.execute(
        "DELETE FROM playlist_pending_removal WHERE playlist = ? AND source = ?",
        (playlist, source),
    )
    conn.execute(
        "DELETE FROM sync_state WHERE pair = ? AND target = ?",
        (playlist, source),
    )
    conn.commit()
