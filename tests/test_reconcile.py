"""Offline self-check for the N-way reconcile core + its archive state:
`uv run test_reconcile.py`. Covers the per-provider merge logic (the part that
decides adds vs removes across providers) and the persistence helpers."""

import os
import sqlite3
import tempfile

import pytest

from songmirror.engine import archive
from songmirror.engine.matching import spotify_track_keys, track_key
from songmirror.engine.targets.base import TargetTransientError, _entry_cids, _merge, reconcile


# --- merge: the safety-critical set logic (per-provider prev + cur) ----------
def test_steady_state_is_noop():
    prev = {"spotify": {"a", "b"}, "apple": {"a", "b"}}
    cur = {"spotify": {"a", "b"}, "apple": {"a", "b"}}
    _, plan = _merge(prev, cur, set())
    assert all(plan[s] == (set(), set()) for s in plan)


def test_add_propagates():
    prev = {"spotify": {"a"}, "apple": {"a"}}
    cur = {"spotify": {"a", "b"}, "apple": {"a"}}  # b added on spotify
    desired, plan = _merge(prev, cur, set())
    assert desired == {"a", "b"}
    assert plan["spotify"] == (set(), set())        # already has b
    assert plan["apple"] == ({"b"}, set())          # must add b


def test_user_removal_propagates():
    prev = {"spotify": {"a", "t"}, "apple": {"a", "t"}, "ytmusic": {"a", "t"}}
    cur = {"spotify": {"a"}, "apple": {"a", "t"}, "ytmusic": {"a", "t"}}  # user removed t on spotify
    desired, plan = _merge(prev, cur, set())
    assert "t" not in desired
    assert plan["apple"] == (set(), {"t"})          # propagate removal
    assert plan["ytmusic"] == (set(), {"t"})


def test_established_removal_beats_an_uninitialized_peers_bootstrap_presence():
    # A provider added to an existing N-way job has no baseline yet. Its current
    # library is bootstrap state, not a concurrent user add, so it must not
    # resurrect a track explicitly removed from an established peer.
    prev = {"spotify": {"a", "t"}, "apple": {"a", "t"}}
    cur = {"spotify": {"a"}, "apple": {"a", "t"}, "tidal": {"a", "t"}}
    desired, plan = _merge(prev, cur, set())
    assert "t" not in desired
    assert plan["spotify"] == (set(), set())
    assert plan["apple"] == (set(), {"t"})
    assert plan["tidal"] == (set(), {"t"})


def test_unmatchable_on_one_provider_is_never_deleted():
    # u lives on spotify + apple but was NEVER matchable on yt (absent from yt's
    # own prev). Its absence from yt must NOT read as a deletion. (The bug that
    # caused this test to exist deleted real tracks across every provider.)
    prev = {"spotify": {"a", "u"}, "apple": {"a", "u"}, "ytmusic": {"a"}}
    cur = {"spotify": {"a", "u"}, "apple": {"a", "u"}, "ytmusic": {"a"}}
    desired, plan = _merge(prev, cur, set())
    assert "u" in desired
    assert plan["spotify"] == (set(), set())        # NOT removed from spotify
    assert plan["apple"] == (set(), set())          # NOT removed from apple
    assert plan["ytmusic"] == ({"u"}, set())        # yt only re-attempts the add (will not_found), never removes


def test_first_pass_only_adds():
    cur = {"spotify": {"a", "b", "c"}, "apple": {"a"}}
    desired, plan = _merge({}, cur, set())          # no stored state yet
    assert desired == {"a", "b", "c"}
    assert plan["apple"] == ({"b", "c"}, set())     # adds only, never removes on first pass


def test_collapsed_provider_is_skipped_no_massdelete():
    prev = {"spotify": {"a", "b", "c", "d"}, "apple": {"a", "b", "c", "d"}}
    cur = {"spotify": {"a", "b", "c", "d"}, "apple": set()}  # apple read collapsed to empty
    desired, plan = _merge(prev, cur, {"apple"})
    assert desired == {"a", "b", "c", "d"}          # apple's emptiness removed nothing
    assert plan["spotify"] == (set(), set())


def test_subcollapse_removal_requires_two_trusted_reads(tmp_path):
    # A small partial provider read can stay above the collapse ratio. One such
    # read is not enough evidence to delete those songs everywhere; the exact
    # source-local absences must survive a second trusted executing pass.
    conn = archive.connect(str(tmp_path / "pending-removals.db"))
    all_ids = list("ABCDEFGHIJ")
    remaining = list("ABCDEFGH")
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {f"i:{cid}" for cid in all_ids})
    spotify, apple = _P("spotify", all_ids), _P("apple", remaining)
    peers = [spotify, apple]
    args = (peers, "Mix", {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)), conn)

    first = reconcile(*args, execute=True, max_removals=25, max_adds=200)

    assert first["clean"] is False
    assert first["added"] == 0 and first["removed"] == 0
    assert first["removals_skipped"] == 2
    assert first["unconfirmed_absences"] == 2
    assert first["confirmed_absences"] == 0
    assert {d["category"] for d in first["change_diagnostics"]} == {"unconfirmed_absence"}
    assert spotify.removed == [] and apple.added == []
    assert archive.get_pending_removals(conn, "mix", "apple") == {"i:I", "i:J"}
    assert archive.get_playlist_state(conn, "mix", "apple") == {
        f"i:{cid}" for cid in all_ids}

    second = reconcile(*args, execute=True, max_removals=25, max_adds=200)

    assert second["clean"] is True
    assert second["added"] == 0 and second["removed"] == 2
    assert set(spotify.removed) == {"I", "J"}
    assert second["unconfirmed_absences"] == 0
    assert second["confirmed_absences"] == 2
    assert "confirmed_absence" in {d["category"] for d in second["change_diagnostics"]}
    assert archive.get_pending_removals(conn, "mix", "apple") == set()
    assert archive.get_playlist_state(conn, "mix", "spotify") == {
        f"i:{cid}" for cid in remaining}
    assert archive.get_playlist_state(conn, "mix", "apple") == {
        f"i:{cid}" for cid in remaining}
    conn.close()


def test_pending_removal_reappearance_resets_confirmation(tmp_path):
    conn = archive.connect(str(tmp_path / "pending-reappears.db"))
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {"i:A", "i:B", "i:C"})
    spotify, apple = _P("spotify", ["A", "B", "C"]), _P("apple", ["A", "B"])
    peers = [spotify, apple]
    args = (peers, "Mix", {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)), conn)

    reconcile(*args, execute=True, max_removals=25, max_adds=200)
    assert archive.get_pending_removals(conn, "mix", "apple") == {"i:C"}

    apple._isrcs.append("C")
    reconcile(*args, execute=True, max_removals=25, max_adds=200)
    assert archive.get_pending_removals(conn, "mix", "apple") == set()
    assert spotify.removed == []

    apple._isrcs.remove("C")
    third = reconcile(*args, execute=True, max_removals=25, max_adds=200)
    assert third["removed"] == 0
    assert archive.get_pending_removals(conn, "mix", "apple") == {"i:C"}
    assert spotify.removed == []
    conn.close()


def test_dry_run_neither_creates_nor_consumes_pending_removal(tmp_path):
    conn = archive.connect(str(tmp_path / "pending-dry-run.db"))
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {"i:A", "i:B"})
    spotify, apple = _P("spotify", ["A", "B"]), _P("apple", ["A"])
    peers = [spotify, apple]
    args = (peers, "Mix", {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)), conn)

    reconcile(*args, execute=False, max_removals=25, max_adds=200)
    assert archive.get_pending_removals(conn, "mix", "apple") == set()

    first_execute = reconcile(*args, execute=True, max_removals=25, max_adds=200)
    assert first_execute["removed"] == 0
    assert archive.get_pending_removals(conn, "mix", "apple") == {"i:B"}
    assert spotify.removed == []
    conn.close()


def test_confirmed_removal_stays_pending_while_removal_mirroring_is_off(tmp_path):
    conn = archive.connect(str(tmp_path / "pending-removals-off.db"))
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {"i:A", "i:B"})
    spotify, apple = _P("spotify", ["A", "B"]), _P("apple", ["A"])
    peers = [spotify, apple]
    args = (peers, "Mix", {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)), conn)

    reconcile(*args, execute=True, max_removals=0, max_adds=200)
    second = reconcile(*args, execute=True, max_removals=0, max_adds=200)
    third = reconcile(*args, execute=True, max_removals=0, max_adds=200)

    assert second["removals_skipped"] == 1 and third["removals_skipped"] == 1
    assert spotify.removed == []
    assert archive.get_pending_removals(conn, "mix", "apple") == {"i:B"}
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:A", "i:B"}
    conn.close()


def test_adds_and_removes_always_disjoint():
    prev = {"spotify": {"a", "b", "c"}, "apple": {"a", "b", "c"}}
    cur = {"spotify": {"a", "b", "x"}, "apple": {"b", "c", "y"}}
    _, plan = _merge(prev, cur, set())
    for src, (add_ids, rem_ids) in plan.items():
        assert not (add_ids & rem_ids), f"{src}: add/remove overlap"


def test_authoritative_group_ignores_mirror_additions_and_repairs_mirror_deletions():
    prev = {
        "spotify": {"a", "b"},
        "apple": {"a", "b"},
        "ytmusic": {"a", "b"},
    }
    cur = {
        "spotify": {"a", "b"},
        "apple": {"a", "b"},
        "ytmusic": {"a", "mirror-only"},
    }

    desired, plan = _merge(prev, cur, set(), {"spotify", "apple"})

    assert desired == {"a", "b"}
    assert plan["spotify"] == (set(), set())
    assert plan["apple"] == (set(), set())
    assert plan["ytmusic"] == ({"b"}, {"mirror-only"})


def test_authoritative_group_accepts_additions_from_either_authority():
    prev = {"spotify": {"a"}, "apple": {"a"}, "tidal": {"a"}}
    cur = {
        "spotify": {"a", "from-spotify"},
        "apple": {"a", "from-apple"},
        "tidal": {"a"},
    }

    desired, plan = _merge(prev, cur, set(), {"spotify", "apple"})

    assert desired == {"a", "from-spotify", "from-apple"}
    assert plan["spotify"][0] == {"from-apple"}
    assert plan["apple"][0] == {"from-spotify"}
    assert plan["tidal"][0] == {"from-spotify", "from-apple"}


def test_authoritative_group_removal_does_not_need_a_mirror_vote():
    prev = {
        "spotify": {"a", "removed"},
        "apple": {"a", "removed"},
        "deezer": {"a", "removed"},
    }
    cur = {
        "spotify": {"a"},
        "apple": {"a", "removed"},
        "deezer": {"a", "removed", "mirror-only"},
    }

    desired, plan = _merge(prev, cur, set(), {"spotify", "apple"})

    assert desired == {"a"}
    assert plan["apple"][1] == {"removed"}
    assert plan["deezer"][1] == {"removed", "mirror-only"}


# --- archive: the per-provider persistence helpers ---------------------------
def test_playlist_state_roundtrip_per_source():
    conn = archive.connect(os.path.join(tempfile.mkdtemp(), "s.db"))
    assert archive.get_playlist_state(conn, "aurora", "spotify") == set()
    archive.set_playlist_state(conn, "aurora", "spotify", {"i:A", "i:B"})
    archive.set_playlist_state(conn, "aurora", "apple", {"i:A"})
    assert archive.get_playlist_state(conn, "aurora", "spotify") == {"i:A", "i:B"}
    assert archive.get_playlist_state(conn, "aurora", "apple") == {"i:A"}   # scoped per source
    archive.set_playlist_state(conn, "aurora", "spotify", {"i:A"})          # replaces, not merges
    assert archive.get_playlist_state(conn, "aurora", "spotify") == {"i:A"}
    conn.close()


def test_empty_playlist_state_remains_initialized_until_cleared(tmp_path):
    conn = archive.connect(str(tmp_path / "empty-state.db"))
    assert not archive.has_playlist_state(conn, "empty", "spotify")
    archive.set_playlist_state(conn, "empty", "spotify", set())
    archive.commit_reconcile_membership(
        conn, "empty", {}, {"spotify": {"i:PENDING"}})
    assert archive.has_playlist_state(conn, "empty", "spotify")
    assert archive.get_playlist_state(conn, "empty", "spotify") == set()
    archive.clear_playlist_state(conn, "empty")
    assert not archive.has_playlist_state(conn, "empty", "spotify")
    assert archive.get_pending_removals(conn, "empty", "spotify") == set()
    conn.close()


def test_existing_nonempty_baseline_is_marked_initialized_on_connect(tmp_path):
    path = str(tmp_path / "state-migration.db")
    conn = archive.connect(path)
    archive.set_playlist_state(conn, "mix", "spotify", {"i:A"})
    conn.execute("DELETE FROM playlist_state_meta")
    conn.commit()
    conn.close()

    conn = archive.connect(path)

    assert archive.has_playlist_state(conn, "mix", "spotify")
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:A"}
    conn.close()


def test_playlist_state_meta_migrates_and_preserves_physical_id(tmp_path):
    path = str(tmp_path / "physical-id-migration.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE playlist_state_meta ("
        "playlist TEXT NOT NULL, source TEXT NOT NULL, initialized_at TEXT NOT NULL, "
        "PRIMARY KEY (playlist, source))"
    )
    conn.commit()
    conn.close()

    conn = archive.connect(path)
    assert "physical_playlist_id" in {
        row[1] for row in conn.execute("PRAGMA table_info(playlist_state_meta)")
    }
    archive.commit_reconcile_membership(
        conn, "mix", {"apple": {"i:A"}}, {"apple": set()},
        {"apple": "apple-playlist-v1"},
    )
    assert archive.get_playlist_physical_id(conn, "mix", "apple") == "apple-playlist-v1"

    archive.set_reconcile_identities(conn, "mix", {"apple": {"i:A"}}, {})
    assert archive.get_playlist_physical_id(conn, "mix", "apple") == "apple-playlist-v1"
    conn.close()


def test_identity_and_baseline_repair_roll_back_together(tmp_path):
    conn = archive.connect(str(tmp_path / "atomic-repair.db"))
    archive.set_playlist_state(conn, "mix", "tidal", {"i:OLD"})
    archive.set_identities(conn, "tidal", {"stable": "i:OLD"})
    conn.execute(
        "CREATE TRIGGER reject_new_identity BEFORE INSERT ON track_identity "
        "WHEN NEW.canonical_id = 'i:NEW' BEGIN SELECT RAISE(ABORT, 'rejected'); END"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="rejected"):
        archive.set_reconcile_identities(
            conn, "mix", {"tidal": {"i:NEW"}}, {"tidal": {"stable": "i:NEW"}})

    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:OLD"}
    assert archive.get_identities(conn, "tidal", ["stable"]) == {"stable": "i:OLD"}
    assert archive.get_identity_history(conn, "tidal", ["stable"]) == {
        "stable": {"i:OLD"}}
    conn.close()


def test_membership_and_pending_removals_roll_back_together(tmp_path):
    conn = archive.connect(str(tmp_path / "atomic-membership.db"))
    archive.set_playlist_state(conn, "mix", "spotify", {"i:OLD"})
    archive.commit_reconcile_membership(
        conn, "mix", {}, {"spotify": {"i:OLD"}})
    conn.execute(
        "CREATE TRIGGER reject_pending BEFORE INSERT ON playlist_pending_removal "
        "WHEN NEW.canonical_id = 'i:NEW' BEGIN SELECT RAISE(ABORT, 'rejected'); END"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="rejected"):
        archive.commit_reconcile_membership(
            conn, "mix", {"spotify": {"i:NEW"}}, {"spotify": {"i:NEW"}})

    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD"}
    assert archive.get_pending_removals(conn, "mix", "spotify") == {"i:OLD"}
    conn.close()


def test_retained_pending_removal_keeps_its_first_seen_timestamp(tmp_path):
    conn = archive.connect(str(tmp_path / "pending-first-seen.db"))
    archive.commit_reconcile_membership(
        conn, "mix", {}, {"spotify": {"i:OLD"}})
    conn.execute(
        "UPDATE playlist_pending_removal SET first_seen_at = 'original' "
        "WHERE playlist = 'mix' AND source = 'spotify'"
    )
    conn.commit()

    archive.commit_reconcile_membership(
        conn, "mix", {}, {"spotify": {"i:OLD", "i:NEW"}})

    rows = dict(conn.execute(
        "SELECT canonical_id, first_seen_at FROM playlist_pending_removal "
        "WHERE playlist = 'mix' AND source = 'spotify'"
    ).fetchall())
    assert rows["i:OLD"] == "original"
    assert rows["i:NEW"] != "original"
    conn.close()


def test_existing_identity_is_seeded_and_retained_as_history(tmp_path):
    path = str(tmp_path / "identity-history-migration.db")
    conn = archive.connect(path)
    archive.set_identities(conn, "tidal", {"stable": "i:OLD"})
    conn.execute("DELETE FROM track_identity_history")  # simulate the pre-history schema
    conn.commit()
    conn.close()

    conn = archive.connect(path)
    assert archive.get_identity_history(conn, "tidal", ["stable"]) == {
        "stable": {"i:OLD"}}
    archive.set_identities(conn, "tidal", {"stable": "i:NEW"})
    assert archive.get_identity_history(conn, "tidal", ["stable"]) == {
        "stable": {"i:OLD", "i:NEW"}}
    conn.close()


def test_reverse_links_and_isrcs():
    conn = archive.connect(os.path.join(tempfile.mkdtemp(), "s.db"))
    archive.set_links(conn, "apple", {"sp1": "cat1", "sp2": "cat2"})
    assert archive.get_reverse_links(conn, "apple", ["cat1", "cat2", "catX"]) == {"cat1": "sp1", "cat2": "sp2"}
    archive.upsert_many(conn, "spotify", [
        {"id": "sp1", "isrc": "ISRCA", "name": "A", "artists": ["X"], "duration_ms": 1},
        {"id": "sp2", "isrc": None, "name": "B", "artists": ["Y"], "duration_ms": 1}])
    assert archive.get_isrcs(conn, "spotify", ["sp1", "sp2"]) == {"sp1": "ISRCA"}  # sp2 has no ISRC -> excluded
    conn.close()


def test_dupe_guard_catches_same_song_variant():
    # The exact shape that duplicated Aurora: Spotify lists all artists; Apple
    # shows the primary with the feature in the title. They MUST share a
    # track_key so reconcile's guard skips the add rather than duplicating the
    # song under a second catalog id.
    present = spotify_track_keys({"name": "Drowning (feat. Kodak Black)", "artists": ["BMike"]})
    incoming = spotify_track_keys({"name": "Drowning", "artists": ["BMike", "Kodak Black"]})
    assert incoming & present, "same song across providers must share a key -> guarded against duplicate add"


class _FakePeer:
    """Minimal MirrorTarget for a state-keying test: two peers already holding
    the same ISRC track, so reconcile writes state without any add/remove."""

    def __init__(self, source):
        self.source = self.tag = self.name = source

    def playlist_tracks(self, pl):
        return [{"id": f"{self.source}1", "name": "Song", "artists": ["A"], "artist": "A",
                 "duration_ms": 1000, "isrc": "ISRCX", "added_at": "2020"}]

    def track_id(self, t):
        return t.get("id")

    def prefetch(self, norms, cache):
        pass

    def native_isrc_map(self, cache):
        return {}

    def resolve(self, norm, cache):
        return None, None

    def add(self, pl, ids):
        pass

    def remove(self, pl, raw):
        pass


def test_reconcile_uses_link_key_for_state():
    conn = archive.connect(os.path.join(tempfile.mkdtemp(), "s.db"))
    peers = [_FakePeer("spotify"), _FakePeer("apple")]
    playlists = {"spotify": {"id": "s1"}, "apple": {"id": "a1"}}
    caches = {s: {"isrc": {}, "search": {}, "dirty": False} for s in ("spotify", "apple")}
    reconcile(peers, "Different Display Name", playlists, caches, conn,
              execute=True, max_removals=25, max_adds=200, link_key="LINKED")
    # canonical state persists under the link key, not the display name
    assert archive.get_playlist_state(conn, "LINKED", "spotify") == {"i:ISRCX"}
    assert archive.get_playlist_state(conn, "different display name", "spotify") == set()
    conn.close()


class _P:
    """Reconcile peer with a controllable ISRC set that reflects adds/removes —
    for exercising the persist gate + removal draining across passes."""

    def __init__(self, source, isrcs):
        self.source = self.tag = self.name = source
        self._isrcs = list(isrcs)
        self.added = []
        self.removed = []

    def playlist_tracks(self, pl):
        return [{"id": f"{self.source}-{i}", "name": f"Song {i}", "artists": ["A"], "artist": "A",
                 "duration_ms": 1000, "isrc": i, "added_at": "2020"} for i in self._isrcs]

    def track_id(self, t):
        return t.get("id")

    def prefetch(self, norms, cache):
        pass

    def native_isrc_map(self, cache):
        return {}

    def resolve(self, norm, cache):
        return f"{self.source}-{norm['isrc']}", "search"

    def add(self, pl, ids):
        for tid in ids:
            isrc = tid.split("-", 1)[1]
            self.added.append(isrc)
            if isrc not in self._isrcs:
                self._isrcs.append(isrc)

    def remove(self, pl, raw):
        self.removed.append(raw["isrc"])
        if raw["isrc"] in self._isrcs:
            self._isrcs.remove(raw["isrc"])


def test_reconcile_uses_the_collection_resource_boundary(tmp_path):
    class LikedPeer(_P):
        def _rows(self):
            return [
                {
                    "id": f"{self.source}-{isrc}", "name": f"Song {isrc}",
                    "artists": ["A"], "artist": "A", "duration_ms": 1000,
                    "isrc": isrc, "added_at": "2020",
                }
                for isrc in self._isrcs
            ]

        def playlist_tracks(self, _playlist):
            raise AssertionError("liked collections must not use playlist reads")

        def resource_tracks(self, _resource):
            return self._rows()

        def resource_add(self, _resource, ids):
            return super().add(None, ids)

        def resource_remove(self, _resource, raw):
            return super().remove(None, raw)

        @staticmethod
        def resource_id(resource):
            return resource["id"]

    spotify = LikedPeer("spotify", ["A", "B"])
    apple = LikedPeer("apple", ["A"])
    resources = {
        "spotify": {"id": "liked-tracks", "_kind": "liked_tracks"},
        "apple": {"id": "liked-tracks", "_kind": "liked_tracks"},
    }
    conn = archive.connect(str(tmp_path / "liked-reconcile.db"))

    stats = reconcile(
        [spotify, apple], "Liked Songs", resources,
        _caches("spotify", "apple"), conn,
        execute=True, max_removals=25, max_adds=200,
        link_key="collection:liked-tracks",
    )

    assert stats["added"] == 1
    assert apple.added == ["B"]
    conn.close()


def _caches(*sources):
    return {s: {"isrc": {}, "search": {}, "dirty": False} for s in sources}


def test_reconcile_saves_baseline_when_only_adds_deferred(tmp_path):
    # The bootstrap fix: a pass that merely DEFERS adds (max_adds hit) is not
    # "clean", yet its per-provider removal baseline must still be recorded — else
    # removals can never activate until the whole add backlog drains.
    conn = archive.connect(str(tmp_path / "s.db"))
    sp, ap = _P("spotify", ["A", "B", "C"]), _P("apple", ["A"])  # apple missing B, C
    stats = reconcile([sp, ap], "Mix", {"spotify": {"id": "s"}, "apple": {"id": "a"}},
                      _caches("spotify", "apple"), conn, execute=True, max_removals=25, max_adds=1)
    assert stats["deferred"] >= 1 and stats["clean"] is False   # add backlog deferred
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:A", "i:B", "i:C"}  # baseline still saved
    conn.close()


def test_authoritative_group_bootstrap_is_scoped_and_non_destructive(tmp_path):
    conn = archive.connect(str(tmp_path / "group-baseline.db"))
    spotify = _P("spotify", ["A", "SPOTIFY"])
    apple = _P("apple", ["A", "APPLE"])
    mirror = _P("ytmusic", ["A", "MIRROR_ONLY"])
    peers = [spotify, apple, mirror]
    playlists = {p.source: {"id": p.source} for p in peers}
    caches = _caches(*(p.source for p in peers))
    kwargs = dict(
        execute=True, max_removals=25, max_adds=200,
        authority_sources={"spotify", "apple"},
    )

    first = reconcile(peers, "Mix", playlists, caches, conn, **kwargs)

    assert first["clean"] is False
    assert first["removed"] == 0
    assert first["removals_skipped"] == 1
    assert "authority_baseline" in {d["category"] for d in first["change_diagnostics"]}
    assert spotify.added == ["APPLE"]
    assert apple.added == ["SPOTIFY"]
    assert set(mirror.added) == {"APPLE", "SPOTIFY"}
    assert mirror.removed == []
    key = "group:apple,spotify:mix"
    assert archive.has_playlist_state(conn, key, "spotify")
    assert not archive.has_playlist_state(conn, "mix", "spotify")

    second = reconcile(peers, "Mix", playlists, caches, conn, **kwargs)

    assert second["removed"] == 1
    assert mirror.removed == ["MIRROR_ONLY"]
    assert "MIRROR_ONLY" not in spotify.added
    assert "MIRROR_ONLY" not in apple.added
    conn.close()


def test_authoritative_group_skips_an_unreadable_mirror_without_blocking_authorities(tmp_path):
    class UnreadableMirror(_P):
        def playlist_tracks(self, pl):
            raise RuntimeError("incomplete TIDAL relationship 305553517")

    conn = archive.connect(str(tmp_path / "unreadable-mirror.db"))
    key = "group:apple,spotify:aurora"
    baseline = {"i:A"}
    archive.commit_reconcile_membership(
        conn,
        key,
        {source: baseline for source in ("spotify", "apple", "tidal", "ytmusic")},
        {source: set() for source in ("spotify", "apple", "tidal", "ytmusic")},
        {source: source for source in ("spotify", "apple", "tidal", "ytmusic")},
    )
    spotify = _P("spotify", ["A"])
    apple = _P("apple", ["A", "NEW"])
    tidal = UnreadableMirror("tidal", ["A"])
    tidal.name = "TIDAL"
    ytmusic = _P("ytmusic", ["A"])
    peers = [spotify, apple, tidal, ytmusic]

    stats = reconcile(
        peers,
        "Aurora",
        {p.source: {"id": p.source} for p in peers},
        _caches(*(p.source for p in peers)),
        conn,
        execute=True,
        max_removals=25,
        max_adds=200,
        authority_sources={"spotify", "apple"},
    )

    assert spotify.added == ["NEW"]
    assert apple.added == []
    assert ytmusic.added == ["NEW"]
    assert tidal.added == []
    assert stats["added"] == 2
    assert stats["failed"] == 1
    assert stats["failures"] == [{
        "playlist": "Aurora",
        "error": "TIDAL mirror read failed: incomplete TIDAL relationship 305553517",
    }]
    assert "mirror_read_failed" in {
        diagnostic["category"] for diagnostic in stats["change_diagnostics"]
    }
    assert stats["clean"] is False
    assert archive.get_playlist_state(conn, key, "tidal") == baseline
    conn.close()


def test_authoritative_group_still_fails_closed_when_an_authority_is_unreadable(tmp_path):
    class UnreadableAuthority(_P):
        def playlist_tracks(self, pl):
            raise RuntimeError("Apple Music snapshot unavailable")

    conn = archive.connect(str(tmp_path / "unreadable-authority.db"))
    spotify = _P("spotify", ["A"])
    apple = UnreadableAuthority("apple", ["A", "NEW"])
    mirror = _P("ytmusic", ["A"])
    peers = [spotify, apple, mirror]

    with pytest.raises(RuntimeError, match="Apple Music snapshot unavailable"):
        reconcile(
            peers,
            "Aurora",
            {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)),
            conn,
            execute=True,
            max_removals=25,
            max_adds=200,
            authority_sources={"spotify", "apple"},
        )

    assert spotify.added == []
    assert mirror.added == []
    conn.close()


def test_authoritative_group_recognizes_a_same_name_recreated_playlist(tmp_path):
    conn = archive.connect(str(tmp_path / "group-recreated.db"))
    key = "group:apple,spotify:aurora"
    baseline = {"i:A", "i:B", "i:C"}
    archive.commit_reconcile_membership(
        conn,
        key,
        {"spotify": baseline, "apple": baseline},
        {"spotify": set(), "apple": set()},
        {"spotify": "spotify-aurora", "apple": "deleted-apple-aurora"},
    )
    spotify = _P("spotify", ["A", "B", "C"])
    apple = _P("apple", ["A"])

    stats = reconcile(
        [spotify, apple],
        "Aurora",
        {
            "spotify": {"id": "spotify-aurora"},
            "apple": {"id": "replacement-apple-aurora"},
        },
        _caches("spotify", "apple"),
        conn,
        execute=True,
        max_removals=25,
        max_adds=200,
        authority_sources={"spotify", "apple"},
    )

    assert stats["read_anomalies"] == 0
    assert stats["removed"] == 0
    assert apple.added == ["B", "C"]
    assert {d["category"] for d in stats["change_diagnostics"]} >= {
        "playlist_recreated", "authority_baseline",
    }
    assert archive.get_playlist_physical_id(conn, key, "apple") == "replacement-apple-aurora"
    conn.close()


def test_reconcile_does_not_search_for_blank_catalog_entries(tmp_path):
    """Provider tombstones/placeholder rows must never become empty searches."""

    class BlankAuthority(_P):
        def playlist_tracks(self, pl):
            return [{
                "id": "blank-row",
                "name": "",
                "artists": [],
                "artist": "",
                "duration_ms": 0,
                "isrc": None,
                "added_at": "2020",
            }]

    class QueryRecordingMirror(_P):
        def __init__(self):
            super().__init__("tidal", [])
            self.resolve_queries = []

        def resolve(self, norm, cache):
            self.resolve_queries.append((norm["name"], norm["artist"]))
            return None, None

    conn = archive.connect(str(tmp_path / "blank-catalog-entry.db"))
    authority = BlankAuthority("spotify", [])
    mirror = QueryRecordingMirror()

    reconcile(
        [authority, mirror],
        "Mix",
        {"spotify": {"id": "s"}, "tidal": {"id": "t"}},
        _caches("spotify", "tidal"),
        conn,
        execute=False,
        max_removals=25,
        max_adds=200,
    )

    assert mirror.resolve_queries == []
    conn.close()


def test_reconcile_adds_in_origin_playlist_order_even_if_plan_set_is_scrambled(tmp_path, monkeypatch):
    """N-way membership is set-based, but writes must follow source position.

    The custom set makes the otherwise hash-seed-dependent failure deterministic:
    reconcile must not inherit whatever order a plan set happens to expose.
    """
    from songmirror.engine.targets import base as base_module

    class ReverseIterationSet(set):
        def __iter__(self):
            return iter(sorted(list(set.__iter__(self)), reverse=True))

    real_merge = base_module._merge

    def scrambled_merge(*args, **kwargs):
        desired, plan = real_merge(*args, **kwargs)
        return desired, {
            source: (ReverseIterationSet(add_ids), remove_ids)
            for source, (add_ids, remove_ids) in plan.items()
        }

    monkeypatch.setattr(base_module, "_merge", scrambled_merge)
    conn = archive.connect(str(tmp_path / "ordered.db"))
    for source in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", source, set())
    spotify = _P("spotify", ["A", "B", "C"])
    apple = _P("apple", [])

    reconcile(
        [spotify, apple],
        "Mix",
        {"spotify": {"id": "s"}, "apple": {"id": "a"}},
        _caches("spotify", "apple"),
        conn,
        execute=True,
        max_removals=0,
        max_adds=200,
    )

    assert apple.added == ["A", "B", "C"]
    conn.close()


def test_reconcile_stops_ordered_adds_at_a_transient_resolution_error(tmp_path):
    """A later song must not leapfrog a rate-limited earlier source entry."""

    class RateLimitedPeer(_P):
        def resolve(self, norm, cache):
            if norm["isrc"] == "B":
                raise TargetTransientError("catalog search returned 429", retry_after=10)
            return super().resolve(norm, cache)

    conn = archive.connect(str(tmp_path / "rate-limited-order.db"))
    for source in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", source, set())
    spotify = _P("spotify", ["A", "B", "C"])
    apple = RateLimitedPeer("apple", [])

    stats = reconcile(
        [spotify, apple],
        "Mix",
        {"spotify": {"id": "s"}, "apple": {"id": "a"}},
        _caches("spotify", "apple"),
        conn,
        execute=True,
        max_removals=0,
        max_adds=200,
    )

    assert apple.added == ["A"]
    assert stats["deferred"] == 2
    assert stats["clean"] is False
    conn.close()


def test_reconcile_counts_only_provider_confirmed_adds(tmp_path):
    class RejectingPeer(_P):
        def add(self, playlist, ids):
            self.requested = list(ids)
            confirmed = [target_id for target_id in ids if not target_id.endswith("-B")]
            for target_id in confirmed:
                isrc = target_id.split("-", 1)[1]
                self.added.append(isrc)
                self._isrcs.append(isrc)
            return confirmed

    conn = archive.connect(str(tmp_path / "provider-rejection-nway.db"))
    archive.set_links(conn, "apple", {"spotify-B": "apple-B"})
    for source in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", source, set())
    spotify = _P("spotify", ["A", "B", "C"])
    apple = RejectingPeer("apple", [])

    stats = reconcile(
        [spotify, apple],
        "Mix",
        {"spotify": {"id": "s"}, "apple": {"id": "a"}},
        _caches("spotify", "apple"),
        conn,
        execute=True,
        max_removals=0,
        max_adds=200,
    )

    assert apple.requested == ["apple-A", "apple-B", "apple-C"]
    assert apple.added == ["A", "C"]
    assert stats["added"] == 2
    assert stats["missing"] == 1
    assert stats["clean"] is False
    assert archive.get_links(conn, "apple", ["spotify-A", "spotify-B", "spotify-C"]) == {
        "spotify-A": "apple-A",
        "spotify-C": "apple-C",
    }
    conn.close()


def test_nonempty_pagination_collapse_never_plans_mass_removal(tmp_path):
    # A truncated provider read is often non-empty (for example 55 -> 5), so the
    # collapse guard must not only protect the zero-track case.
    conn = archive.connect(str(tmp_path / "collapsed.db"))
    ids = [str(i) for i in range(10)]
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {f"i:{i}" for i in ids})
    sp, apple = _P("spotify", ids), _P("apple", ids[:3])

    stats = reconcile([sp, apple], "Mix", {"spotify": {"id": "s"}, "apple": {"id": "a"}},
                      _caches("spotify", "apple"), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False and stats["removed"] == 0
    assert sp.removed == [] and apple.removed == []
    conn.close()


def test_large_removals_held_back_by_default_then_drain_when_opted_in(tmp_path):
    isrcs = list("ABCDEFGHIJ")

    def fresh():
        conn = archive.connect(str(tmp_path.joinpath(f"s{len(isrcs)}.db")))
        for src in ("spotify", "apple"):
            archive.set_playlist_state(conn, "mix", src, {f"i:{i}" for i in isrcs})
        archive.commit_reconcile_membership(
            conn, "mix", {}, {"spotify": {f"i:{i}" for i in "DEFG"}})
        sp = _P("spotify", ["A", "B", "C", "H", "I", "J"])  # user dropped D,E,F,G (keeps 6/10 -> no collapse)
        ap = _P("apple", list(isrcs))
        return conn, sp, ap

    playlists = {"spotify": {"id": "s"}, "apple": {"id": "a"}}

    # Default: 4 removals > max_removals=2 -> held back entirely, surfaced, baseline frozen.
    conn, sp, ap = fresh()
    stats = reconcile([sp, ap], "Mix", playlists, _caches("spotify", "apple"), conn,
                      execute=True, max_removals=2, max_adds=200, drain_removals=False)
    assert stats["removals_skipped"] == 4 and ap.removed == []
    assert archive.get_playlist_state(conn, "mix", "apple") == {f"i:{i}" for i in isrcs}  # not advanced
    conn.close()

    # Opt-in: drains 2/pass across two passes, advancing the baseline only once cleared.
    conn, sp, ap = fresh()
    reconcile([sp, ap], "Mix", playlists, _caches("spotify", "apple"), conn,
              execute=True, max_removals=2, max_adds=200, drain_removals=True)
    assert len(ap.removed) == 2 and archive.get_playlist_state(conn, "mix", "apple") == {f"i:{i}" for i in isrcs}
    reconcile([sp, ap], "Mix", playlists, _caches("spotify", "apple"), conn,
              execute=True, max_removals=2, max_adds=200, drain_removals=True)
    assert len(ap.removed) == 4  # fully drained
    assert archive.get_playlist_state(conn, "mix", "apple") == {f"i:{i}" for i in ("A", "B", "C", "H", "I", "J")}
    conn.close()


def test_removals_never_propagate_at_cap_zero(tmp_path):
    # max_removals=0 is the "removals off" switch (the default): a track gone
    # from one provider (user delete or a licensing pull) is kept everywhere
    # else, surfaced as skipped, and the baseline stays frozen so the held
    # removal can't resurrect or silently apply later.
    conn = archive.connect(str(tmp_path / "z.db"))
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {f"i:{i}" for i in "ABCD"})
    archive.commit_reconcile_membership(conn, "mix", {}, {"spotify": {"i:D"}})
    sp, ap = _P("spotify", ["A", "B", "C"]), _P("apple", ["A", "B", "C", "D"])  # D dropped on spotify
    stats = reconcile([sp, ap], "Mix", {"spotify": {"id": "s"}, "apple": {"id": "a"}},
                      _caches("spotify", "apple"), conn, execute=True, max_removals=0, max_adds=200)
    assert stats["removals_skipped"] == 1 and ap.removed == []
    assert archive.get_playlist_state(conn, "mix", "apple") == {f"i:{i}" for i in "ABCD"}  # frozen
    conn.close()


def test_held_removal_still_initializes_a_new_peer_without_resurrection(tmp_path):
    # Exact production failure: TIDAL was added to an established Spotify/Apple
    # job while removals were disabled. An unrelated held removal froze every
    # baseline, leaving TIDAL in perpetual bootstrap; its mere possession of D
    # then re-added D each time the user removed it from Spotify.
    conn = archive.connect(str(tmp_path / "bootstrap.db"))
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {f"i:{i}" for i in "ADX"})
    sp = _P("spotify", ["A", "X"])       # D explicitly removed here
    ap = _P("apple", ["A", "D"])         # X explicitly removed here -> cap trips
    tidal = _P("tidal", ["A", "D"])      # new peer, no stored baseline
    peers = [sp, ap, tidal]
    playlists = {p.source: {"id": p.source} for p in peers}

    stats = reconcile(peers, "Mix", playlists, _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=0, max_adds=200)

    assert stats["removals_skipped"] > 0
    assert sp.added == []                    # bootstrap presence must not resurrect D
    assert archive.has_playlist_state(conn, "mix", "tidal")
    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:A", "i:D"}
    assert archive.get_playlist_state(conn, "mix", "spotify") == {f"i:{i}" for i in "ADX"}
    assert archive.get_playlist_state(conn, "mix", "apple") == {f"i:{i}" for i in "ADX"}

    # The initialized peer remains harmless on later capped passes too.
    reconcile(peers, "Mix", playlists, _caches(*(p.source for p in peers)), conn,
              execute=True, max_removals=0, max_adds=200)
    assert sp.added == []
    conn.close()


class _VariantPeer:
    """Peer holding ONE copy of a song under provider-flavored metadata
    (decorated title, partial or embellished artist credits). resolve() returns
    a catalog id different from the library id already in the playlist — the
    real-world shape that let re-adds slip past the seen-id guard."""

    def __init__(self, source, track, resolve_id):
        self.source = self.tag = self.name = source
        self._track = track
        self._resolve_id = resolve_id
        self.added, self.removed = [], []

    def playlist_tracks(self, pl):
        return [dict(self._track)]

    def track_id(self, t):
        return t.get("id")

    def prefetch(self, norms, cache):
        pass

    def native_isrc_map(self, cache):
        return {}

    def resolve(self, norm, cache):
        return self._resolve_id, "search"

    def add(self, pl, ids):
        self.added.extend(ids)

    def remove(self, pl, raw):
        self.removed.append(raw)


class _ManyPeer:
    """Multi-entry peer with a test-supplied resolver."""

    def __init__(self, source, tracks, resolver):
        self.source = self.tag = self.name = source
        self._tracks = list(tracks)
        self._resolver = resolver
        self.added, self.removed = [], []

    def playlist_tracks(self, pl):
        return [dict(track) for track in self._tracks]

    def track_id(self, track):
        return track.get("id")

    def prefetch(self, norms, cache):
        pass

    def native_isrc_map(self, cache):
        return {}

    def resolve(self, norm, cache):
        return self._resolver(norm), "search"

    def add(self, pl, ids):
        self.added.extend(ids)

    def remove(self, pl, raw):
        self.removed.append(raw)


def _replacement_peers(*, same_metadata=False, spotify_resolve="sp-new"):
    old_name = "Same Title" if same_metadata else "Old Recording"
    new_name = "Same Title" if same_metadata else "Replacement Recording"
    sp = _VariantPeer("spotify", {
        "id": "sp-old", "name": old_name, "artists": ["Same Artist"],
        "artist": "Same Artist", "duration_ms": 180_000, "isrc": "OLD", "added_at": "2020",
    }, spotify_resolve)
    tidal = _VariantPeer("tidal", {
        "id": "tidal-new", "name": new_name, "artists": ["Same Artist"],
        "artist": "Same Artist", "duration_ms": 240_000, "isrc": "NEW", "added_at": "2020",
    }, "tidal-old")
    return sp, tidal


def _seed_replacement_baseline(conn):
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:OLD"})
    archive.commit_reconcile_membership(conn, "mix", {}, {"tidal": {"i:OLD"}})


def _arcane_peers():
    """One song, three provider-flavored copies: Spotify lists every artist plus
    the ISRC; Apple joins the artists into one embellished string; YT credits
    only the primary. Without alias unification each shape becomes its own
    canonical id."""
    name = "To Ashes and Blood (from the series Arcane League of Legends)"
    sp = _VariantPeer("spotify", {"id": "sp-lib", "name": name,
                                  "artists": ["Woodkid", "Arcane", "League of Legends"],
                                  "artist": "Woodkid, Arcane, League of Legends",
                                  "duration_ms": 246000, "isrc": "X1", "added_at": "2020"}, "sp-cat")
    ap = _VariantPeer("apple", {"id": "ap-lib", "name": name,
                                "artist": "Woodkid, Arcane, League of Legends Music",
                                "duration_ms": 246000, "isrc": None, "added_at": "2020"}, "ap-cat")
    yt = _VariantPeer("ytmusic", {"id": "yt-lib", "name": name, "artists": ["Woodkid"],
                                  "artist": "Woodkid", "duration_ms": 246000, "isrc": None,
                                  "added_at": "2020"}, "yt-cat")
    return sp, ap, yt


def test_alias_variants_do_not_duplicate_across_providers(tmp_path):
    # Every provider already HAS the song; a pass must be a no-op. Before alias
    # unification, the k: identities from Apple/YT metadata sat in `desired`
    # and were re-added elsewhere via search — duplicating the song on services
    # that already had it, every pass.
    conn = archive.connect(str(tmp_path / "s.db"))
    sp, ap, yt = _arcane_peers()
    stats = reconcile([sp, ap, yt], "Mix", {p.source: {"id": p.source} for p in (sp, ap, yt)},
                      _caches("spotify", "apple", "ytmusic"), conn,
                      execute=True, max_removals=25, max_adds=200)
    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and ap.added == [] and yt.added == []
    for src in ("spotify", "apple", "ytmusic"):  # baseline stores ONE unified identity, not three
        assert archive.get_playlist_state(conn, "mix", src) == {"i:X1"}
    conn.close()


def test_catalog_release_variants_do_not_duplicate_across_providers(tmp_path):
    # Live Spotify shape: the destination already has the ordinary release while
    # a newly connected provider exposes a remaster under another hard ISRC.
    # Hard ids intentionally do not alias globally, but the destination guard
    # must recognize this as the same recording and avoid a second catalog copy.
    conn = archive.connect(str(tmp_path / "catalog-variant.db"))
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Bedshaped", "artists": ["Keane"],
        "artist": "Keane", "duration_ms": 277_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-remaster")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-remaster", "name": "Bedshaped (Remastered 2024)", "artists": ["Keane"],
        "artist": "Keane", "duration_ms": 277_400, "isrc": "REMASTER", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 0
    assert sp.added == [] and tidal.added == []
    conn.close()


def test_catalog_recording_guard_is_conservative():
    from songmirror.engine.matching import same_catalog_recording

    base = {"name": "Love Me Like You Do", "artists": ["Ellie Goulding"],
            "artist": "Ellie Goulding", "duration_ms": 252_000}
    assert same_catalog_recording(
        {**base, "name": 'Love Me Like You Do - From "Fifty Shades Of Grey"'}, base)
    assert same_catalog_recording(
        {**base, "name": "Love Me Like You Do [Clean]", "duration_ms": 252_600}, base)
    assert same_catalog_recording(
        {**base, "name": "Love Me Like You Do (Remastered 2024)"}, base)
    assert not same_catalog_recording(
        {**base, "name": "Love Me Like You Do - Acoustic", "duration_ms": 252_000}, base)
    assert not same_catalog_recording(
        {**base, "name": "Love Me Like You Do", "duration_ms": 280_000}, base)
    assert not same_catalog_recording(
        {**base, "name": "Love Me Like You Do", "artists": ["Cover Band"],
         "artist": "Cover Band"}, base)


def test_isrc_format_drift_does_not_remove_a_present_song(tmp_path):
    # Live false-removal shape: Spotify/YouTube learned a lowercase, punctuated
    # ISRC while newer peers report the standard uppercase compact form. The
    # physical song never left either playlist, so this must be a no-op.
    conn = archive.connect(str(tmp_path / "isrc-format.db"))
    old = "i:gb-smu-26-29433"
    for src in ("spotify", "apple"):
        archive.set_playlist_state(conn, "mix", src, {old})
    sp = _VariantPeer("spotify", {
        "id": "spotify-track", "name": "We've Never Met but Can We Have a Cup of Coffee or Something",
        "artists": ["In Love With a Ghost"], "artist": "In Love With a Ghost",
        "duration_ms": 208_000, "isrc": "gb-smu-26-29433", "added_at": "2020",
    }, "spotify-replacement")
    apple = _VariantPeer("apple", {
        "id": "apple-track", "name": "We've Never Met but Can We Have a Cup of Coffee or Something",
        "artists": ["In Love With a Ghost"], "artist": "In Love With a Ghost",
        "duration_ms": 208_300, "isrc": "GBSMU2629433", "added_at": "2020",
    }, "apple-replacement")
    peers = [sp, apple]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and sp.removed == []
    assert apple.added == [] and apple.removed == []
    conn.close()


def test_equivalent_catalog_alias_does_not_remove_the_existing_copy(tmp_path):
    # Different hard ISRCs can still identify interchangeable catalog releases.
    # If the replacement add is suppressed as a duplicate, its obsolete alias
    # removal must be suppressed symmetrically or the existing copy is lost.
    conn = archive.connect(str(tmp_path / "catalog-removal.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:ORIGINAL"})
    archive.commit_reconcile_membership(conn, "mix", {}, {"tidal": {"i:ORIGINAL"}})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Bedshaped", "artists": ["Keane"],
        "artist": "Keane", "duration_ms": 277_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-remaster")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-remaster", "name": "Bedshaped (Remastered 2024)", "artists": ["Keane"],
        "artist": "Keane", "duration_ms": 277_400, "isrc": "REMASTER", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and sp.removed == []
    conn.close()


def test_exact_key_satisfying_an_add_protects_that_current_track_from_removal(tmp_path):
    # Title/artist equality can satisfy a desired add even when duration proves
    # the two hard identities are not catalog-equivalent. The existing entry is
    # then the add's explicit stand-in and cannot be removed in the same pass.
    conn = archive.connect(str(tmp_path / "key-satisfied-replacement.db"))
    _seed_replacement_baseline(conn)
    sp, tidal = _replacement_peers(same_metadata=True)
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and sp.removed == []
    conn.close()


def test_resolving_an_add_to_a_present_track_protects_that_track_from_removal(tmp_path):
    # A resolver can identify the desired recording as the physical entry that
    # is already present. Treating that as a duplicate add must also protect the
    # same entry from the pass's obsolete-canonical removal plan.
    conn = archive.connect(str(tmp_path / "resolved-present-replacement.db"))
    _seed_replacement_baseline(conn)
    sp, tidal = _replacement_peers(spotify_resolve="sp-old")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False
    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and sp.removed == []
    conn.close()


def test_two_additions_resolving_to_one_new_track_hold_all_removals(tmp_path):
    conn = archive.connect(str(tmp_path / "resolver-collision.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:OLD1", "i:OLD2"})
    archive.commit_reconcile_membership(
        conn, "mix", {}, {"tidal": {"i:OLD1", "i:OLD2"}})
    old_tracks = [
        {"id": f"sp-old-{i}", "name": f"Old {i}", "artists": ["Artist"],
         "artist": "Artist", "duration_ms": 100_000 * i, "isrc": f"OLD{i}", "added_at": "2020"}
        for i in (1, 2)
    ]
    new_tracks = [
        {"id": f"tidal-new-{i}", "name": f"New {i}", "artists": ["Artist"],
         "artist": "Artist", "duration_ms": 100_000 * i, "isrc": f"NEW{i}", "added_at": "2020"}
        for i in (1, 2)
    ]
    sp = _ManyPeer("spotify", old_tracks, lambda norm: "sp-collision")
    tidal = _ManyPeer("tidal", new_tracks, lambda norm: f"tidal-{norm['isrc']}")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False
    assert stats["added"] == 1 and stats["removed"] == 0
    assert sp.added == ["sp-collision"] and sp.removed == []
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD1", "i:OLD2"}
    conn.close()


def test_same_key_queued_additions_stay_distinct_when_audio_differs(tmp_path):
    conn = archive.connect(str(tmp_path / "queued-key-collision.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:OLD1", "i:OLD2"})
    archive.commit_reconcile_membership(
        conn, "mix", {}, {"tidal": {"i:OLD1", "i:OLD2"}})
    old_tracks = [
        {"id": f"sp-old-{i}", "name": f"Old {i}", "artists": ["Artist"],
         "artist": "Artist", "duration_ms": 100_000 * i, "isrc": f"OLD{i}", "added_at": "2020"}
        for i in (1, 2)
    ]
    new_tracks = [
        {"id": f"tidal-new-{i}", "name": "Same Title", "artists": ["Artist"],
         "artist": "Artist", "duration_ms": 100_000 * i, "isrc": f"NEW{i}", "added_at": "2020"}
        for i in (1, 2)
    ]
    sp = _ManyPeer("spotify", old_tracks, lambda norm: f"sp-{norm['isrc']}")
    tidal = _ManyPeer("tidal", new_tracks, lambda norm: f"tidal-{norm['isrc']}")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 2 and stats["removed"] == 2
    assert set(sp.added) == {"sp-NEW1", "sp-NEW2"}
    assert len(sp.removed) == 2
    conn.close()


def test_deferred_replacement_addition_holds_all_provider_removals(tmp_path):
    conn = archive.connect(str(tmp_path / "deferred-replacement.db"))
    _seed_replacement_baseline(conn)
    sp, tidal = _replacement_peers()
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=0)

    assert stats["clean"] is False
    assert stats["added"] == 0 and stats["removed"] == 0 and stats["deferred"] == 1
    assert sp.added == [] and sp.removed == []
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD"}
    conn.close()


def test_unresolved_replacement_addition_holds_all_provider_removals(tmp_path):
    conn = archive.connect(str(tmp_path / "unresolved-replacement.db"))
    _seed_replacement_baseline(conn)
    sp, tidal = _replacement_peers(spotify_resolve=None)
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False
    assert stats["missing"] == 1 and stats["removed"] == 0
    assert sp.removed == []
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD"}
    conn.close()


def test_interrupted_replacement_addition_holds_removal_and_marks_unclean(tmp_path):
    conn = archive.connect(str(tmp_path / "interrupted-replacement.db"))
    _seed_replacement_baseline(conn)
    sp, tidal = _replacement_peers()
    peers = [sp, tidal]
    control = iter(["run", "stop"])

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200,
                      should_continue=lambda: next(control, "stop"))

    assert stats["clean"] is False
    assert stats["added"] == 0 and stats["removed"] == 0
    assert sp.added == [] and sp.removed == []
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD"}
    conn.close()


def test_stable_physical_hard_rebinding_does_not_emit_a_removal(tmp_path):
    # A provider can enrich an unchanged playlist entry with a better hard id.
    # Even when the corrected metadata describes a creative variant that the
    # catalog-equivalence guard must keep distinct, the stable physical id proves
    # this source did not perform a delete-and-replace operation.
    conn = archive.connect(str(tmp_path / "stable-rebinding.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:ORIGINAL"})
    archive.commit_reconcile_membership(
        conn, "mix", {}, {"tidal": {"i:ORIGINAL"}})
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:ORIGINAL"})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-stable", "name": "Runaway - Piano Version", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 243_000, "isrc": "PIANO", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 2 and stats["removed"] == 0
    assert stats["identity_changes"] == 1
    assert "identity_migration" in {d["category"] for d in stats["change_diagnostics"]}
    assert sp.removed == [] and tidal.removed == []
    assert archive.get_identities(conn, "tidal", ["tidal-stable"]) == {
        "tidal-stable": "i:PIANO"}
    assert archive.get_pending_removals(conn, "mix", "tidal") == set()
    conn.close()


def test_ambiguous_stable_identity_split_holds_the_entire_source_delta(tmp_path):
    # Two unchanged provider entries can historically share one canonical id,
    # then later expose different provider-proven ids. That is not enough
    # evidence to interpret OLD as a user deletion: fail closed instead of
    # propagating +A/+B/-OLD to every established peer.
    conn = archive.connect(str(tmp_path / "ambiguous-rebinding.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:OLD"})
    archive.set_identities(conn, "tidal", {
        "tidal-one": "i:OLD",
        "tidal-two": "i:OLD",
    })
    spotify = _ManyPeer("spotify", [{
        "id": "spotify-old", "name": "Historical", "artists": ["Artist"],
        "artist": "Artist", "duration_ms": 180_000, "isrc": "OLD", "added_at": "2020",
    }], lambda norm: f"spotify-{norm['isrc']}")
    tidal = _ManyPeer("tidal", [
        {
            "id": "tidal-one", "name": "First", "artists": ["Artist"],
            "artist": "Artist", "duration_ms": 180_000, "isrc": "A", "added_at": "2020",
        },
        {
            "id": "tidal-two", "name": "Second", "artists": ["Artist"],
            "artist": "Artist", "duration_ms": 240_000, "isrc": "B", "added_at": "2020",
        },
    ], lambda norm: f"tidal-{norm['isrc']}")
    peers = [spotify, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False
    assert stats["added"] == 0 and stats["removed"] == 0
    assert spotify.added == [] and spotify.removed == []
    assert tidal.added == [] and tidal.removed == []
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:OLD"}
    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:OLD"}
    assert archive.get_identities(conn, "tidal", ["tidal-one", "tidal-two"]) == {
        "tidal-one": "i:OLD", "tidal-two": "i:OLD"}
    conn.close()


def test_stable_rebinding_history_repairs_every_playlist_containing_the_track(tmp_path):
    # Track identity is global by provider track id, while removal baselines are
    # playlist-scoped. Repairing the first playlist must not consume OLD -> NEW
    # before a second playlist containing the same physical track can repair too.
    conn = archive.connect(str(tmp_path / "multi-playlist-rebinding.db"))
    for playlist in ("one", "two"):
        for src in ("spotify", "tidal"):
            archive.set_playlist_state(conn, playlist, src, {"i:ORIGINAL"})
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:ORIGINAL"})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-stable", "name": "Runaway - Piano Version", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 243_000, "isrc": "PIANO", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]
    playlists = {p.source: {"id": p.source} for p in peers}
    caches = _caches(*(p.source for p in peers))

    first = reconcile(peers, "One", playlists, caches, conn,
                      execute=True, max_removals=25, max_adds=200)
    second = reconcile(peers, "Two", playlists, caches, conn,
                       execute=True, max_removals=25, max_adds=200)

    assert first["removed"] == 0 and second["removed"] == 0
    assert archive.get_playlist_state(conn, "two", "tidal") == {"i:PIANO"}
    conn.close()


def test_dry_run_does_not_consume_stable_rebinding_history(tmp_path):
    # A preview must not overwrite the remembered old identity. The subsequent
    # executing pass still needs that old -> new transition to repair the source
    # baseline instead of interpreting the correction as a user deletion.
    conn = archive.connect(str(tmp_path / "dry-rebinding.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:ORIGINAL"})
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:ORIGINAL"})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-stable", "name": "Runaway - Piano Version", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 243_000, "isrc": "PIANO", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]
    args = (peers, "Mix", {p.source: {"id": p.source} for p in peers},
            _caches(*(p.source for p in peers)), conn)

    reconcile(*args, execute=False, max_removals=25, max_adds=200)

    assert archive.get_identities(conn, "tidal", ["tidal-stable"]) == {
        "tidal-stable": "i:ORIGINAL"}
    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:ORIGINAL"}

    stats = reconcile(*args, execute=True, max_removals=25, max_adds=200)

    assert stats["removed"] == 0
    assert tidal.removed == []
    assert archive.get_identities(conn, "tidal", ["tidal-stable"]) == {
        "tidal-stable": "i:PIANO"}
    conn.close()


def test_stable_rebinding_persists_when_an_unrelated_removal_is_held(tmp_path):
    # A zero removal cap freezes ordinary membership snapshots, but a stable-id
    # correction must survive or every later pass will rediscover the same false
    # old-id removal after the identity table has already advanced to the new id.
    conn = archive.connect(str(tmp_path / "held-rebinding.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:ORIGINAL", "i:X"})
    archive.commit_reconcile_membership(conn, "mix", {}, {"spotify": {"i:X"}})
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:ORIGINAL"})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _P("tidal", ["PIANO", "X"])
    original_tracks = tidal.playlist_tracks

    def tracks_with_stable_rebinding(pl):
        tracks = original_tracks(pl)
        tracks[0]["id"] = "tidal-stable"
        tracks[0]["name"] = "Runaway - Piano Version"
        tracks[0]["artist"] = "AURORA"
        tracks[0]["artists"] = ["AURORA"]
        tracks[0]["duration_ms"] = 243_000
        return tracks

    tidal.playlist_tracks = tracks_with_stable_rebinding
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=0, max_adds=200)

    assert stats["removals_skipped"] == 1
    assert archive.get_playlist_state(conn, "mix", "spotify") == {"i:ORIGINAL", "i:X"}
    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:PIANO", "i:X"}
    conn.close()


def test_later_provider_read_failure_cannot_split_identity_from_baseline(tmp_path):
    # Learned identities must not commit peer-by-peer: if a later read fails,
    # the old identity and old baseline must remain together so the next pass can
    # still observe and safely repair the stable OLD -> NEW transition.
    conn = archive.connect(str(tmp_path / "failed-read-rebinding.db"))
    archive.set_playlist_state(conn, "mix", "tidal", {"i:OLD"})
    archive.set_playlist_state(conn, "mix", "apple", {"i:X"})
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:OLD"})
    tidal = _VariantPeer("tidal", {
        "id": "tidal-stable", "name": "Corrected", "artists": ["Artist"],
        "artist": "Artist", "duration_ms": 200_000, "isrc": "NEW", "added_at": "2020",
    }, "tidal-old")

    class _FailingPeer:
        source = tag = name = "apple"

        def playlist_tracks(self, pl):
            raise RuntimeError("provider read failed")

    peers = [tidal, _FailingPeer()]

    with pytest.raises(RuntimeError, match="provider read failed"):
        reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                  _caches(*(p.source for p in peers)), conn,
                  execute=True, max_removals=25, max_adds=200)

    assert archive.get_identities(conn, "tidal", ["tidal-stable"]) == {
        "tidal-stable": "i:OLD"}
    assert archive.get_playlist_state(conn, "mix", "tidal") == {"i:OLD"}
    conn.close()


def test_collapsed_read_cannot_consume_identity_rebinding_history(tmp_path):
    conn = archive.connect(str(tmp_path / "collapsed-rebinding.db"))
    baseline = {"i:OLD", *(f"i:{i}" for i in range(9))}
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, baseline)
    archive.set_identities(conn, "tidal", {"tidal-stable": "i:OLD"})
    spotify = _P("spotify", ["OLD", *(str(i) for i in range(9))])
    tidal = _VariantPeer("tidal", {
        "id": "tidal-stable", "name": "Corrected", "artists": ["Artist"],
        "artist": "Artist", "duration_ms": 200_000, "isrc": "NEW", "added_at": "2020",
    }, "tidal-old")
    peers = [spotify, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["clean"] is False and stats["removed"] == 0
    assert archive.get_identities(conn, "tidal", ["tidal-stable"]) == {
        "tidal-stable": "i:OLD"}
    assert archive.get_playlist_state(conn, "mix", "tidal") == baseline
    conn.close()


def test_creative_replacement_still_propagates_removal(tmp_path):
    # A real replacement (ordinary -> piano version) remains a legitimate N-way
    # delta: add the piano version to Spotify and remove the ordinary recording.
    conn = archive.connect(str(tmp_path / "creative-removal.db"))
    for src in ("spotify", "tidal"):
        archive.set_playlist_state(conn, "mix", src, {"i:ORIGINAL"})
    archive.commit_reconcile_membership(conn, "mix", {}, {"tidal": {"i:ORIGINAL"}})
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-piano", "name": "Runaway - Piano Version", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 243_000, "isrc": "PIANO", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 1 and stats["removed"] == 1
    assert sp.added == ["sp-piano"] and len(sp.removed) == 1
    conn.close()


def test_creative_versions_remain_distinct_across_providers(tmp_path):
    # Stronger duplicate protection must not collapse genuinely different audio.
    conn = archive.connect(str(tmp_path / "creative-version.db"))
    sp = _VariantPeer("spotify", {
        "id": "sp-original", "name": "Runaway", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 309_000, "isrc": "ORIGINAL", "added_at": "2020",
    }, "sp-piano")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-piano", "name": "Runaway - Piano Version", "artists": ["AURORA"],
        "artist": "AURORA", "duration_ms": 243_000, "isrc": "PIANO", "added_at": "2020",
    }, "tidal-original")
    peers = [sp, tidal]

    stats = reconcile(peers, "Mix", {p.source: {"id": p.source} for p in peers},
                      _caches(*(p.source for p in peers)), conn,
                      execute=True, max_removals=25, max_adds=200)

    assert stats["added"] == 2
    assert sp.added == ["sp-piano"] and tidal.added == ["tidal-original"]
    conn.close()


def test_alias_flip_never_removes_the_real_track(tmp_path):
    # A provider's canonical for a song can FLIP between passes (an ISRC or link
    # appears where only a fuzzy key existed). The retired alias then reads as a
    # user deletion and the very-much-present song gets removed from the other
    # providers. Unification maps the stored alias forward instead.
    conn = archive.connect(str(tmp_path / "s.db"))
    name = "Ma Meilleure Ennemie"
    stale = "k:ma meilleure ennemie|stromae pomme arcane"
    archive.set_playlist_state(conn, "mix", "spotify", {"i:Z9"})
    archive.set_playlist_state(conn, "mix", "apple", {stale})
    archive.set_playlist_state(conn, "mix", "ytmusic", {stale})
    sp = _VariantPeer("spotify", {"id": "sp-lib", "name": name, "artists": ["Stromae", "Pomme"],
                                  "artist": "Stromae, Pomme", "duration_ms": 178000,
                                  "isrc": "Z9", "added_at": "2020"}, "sp-cat")
    ap = _VariantPeer("apple", {"id": "ap-lib", "name": name,
                                "artist": "Stromae, Pomme, Arcane", "duration_ms": 178000,
                                "isrc": None, "added_at": "2020"}, "ap-cat")
    yt = _VariantPeer("ytmusic", {"id": "yt-lib", "name": name, "artists": ["Stromae", "Pomme"],
                                  "artist": "Stromae, Pomme", "duration_ms": 178000,
                                  "isrc": "Z9",  # the flip: yt now reads an ISRC it didn't have
                                  "added_at": "2020"}, "yt-cat")
    stats = reconcile([sp, ap, yt], "Mix", {p.source: {"id": p.source} for p in (sp, ap, yt)},
                      _caches("spotify", "apple", "ytmusic"), conn,
                      execute=True, max_removals=25, max_adds=200)
    assert stats["removed"] == 0 and ap.removed == [] and yt.removed == []
    assert stats["added"] == 0
    conn.close()


def test_degraded_artist_read_never_removes_the_real_track(tmp_path):
    # YouTube serves one unchanging video with either its artist or its
    # auto-generated channel, and for the generic "Release - Topic" channel there
    # is no artist left to match on: too little overlap for alias unification to
    # fold it back. The entry's canonical then drops from the ISRC it shares with
    # the other providers to a fuzzy key, which reads as a user deletion and
    # deletes a song all three services still have. Sticky per-entry identity
    # pins the entry to the id it already earned.
    conn = archive.connect(str(tmp_path / "s.db"))
    name = "Can't Behave"

    def peer(source, artist, isrc):
        return _VariantPeer(source, {"id": f"{source}-lib", "name": name, "artists": [artist],
                                     "artist": artist, "duration_ms": 213000, "isrc": isrc,
                                     "added_at": "2020"}, f"{source}-cat")

    sp = peer("spotify", "Courtney Jaye", "USIR20500202")
    ap, yt = peer("apple", "Courtney Jaye", None), peer("ytmusic", "Courtney Jaye", None)
    peers = [sp, ap, yt]
    args = ({p.source: {"id": p.source} for p in peers}, _caches("spotify", "apple", "ytmusic"), conn)
    reconcile(peers, "Mix", *args, execute=True, max_removals=25, max_adds=200)
    assert archive.get_playlist_state(conn, "mix", "ytmusic") == {"i:USIR20500202"}

    yt._track["artists"], yt._track["artist"] = ["Release"], "Release"  # the degraded read
    stats = reconcile(peers, "Mix", *args, execute=True, max_removals=25, max_adds=200)
    assert stats["removed"] == 0 and sp.removed == [] and ap.removed == [] and yt.removed == []
    assert stats["added"] == 0                       # nor a phantom re-add of the "missing" copy
    assert archive.get_playlist_state(conn, "mix", "ytmusic") == {"i:USIR20500202"}
    conn.close()


def test_a_subset_credit_earns_a_hard_id_worth_remembering(tmp_path):
    # Providers credit differently: Spotify lists every artist, YT often just one.
    # Alias unification already folds that copy in, but it folds too late to be
    # remembered: only a hard id from _entry_cids is. Seeding the ISRC under
    # every key the song answers to (not just the joined credit) is what lets the
    # entry survive a later read too degraded to match on anything.
    conn = archive.connect(str(tmp_path / "s.db"))
    sp = _VariantPeer("spotify", {"id": "sp-lib", "name": "Hona Tha Pyar",
                                  "artists": ["Atif Aslam", "Hadiqa Kiani"],
                                  "artist": "Atif Aslam, Hadiqa Kiani", "duration_ms": 300000,
                                  "isrc": "INT101100022", "added_at": "2020"}, "sp-cat")
    yt = _VariantPeer("ytmusic", {"id": "yt-lib", "name": "Hona Tha Pyar", "artists": ["Hadiqa Kiani"],
                                  "artist": "Hadiqa Kiani", "duration_ms": 300000,
                                  "isrc": None, "added_at": "2020"}, "yt-cat")
    stats = reconcile([sp, yt], "Mix", {p.source: {"id": p.source} for p in (sp, yt)},
                      _caches("spotify", "ytmusic"), conn, execute=True, max_removals=25, max_adds=200)
    assert stats["added"] == 0 and stats["removed"] == 0
    assert archive.get_identities(conn, "ytmusic", ["yt-lib"]) == {"yt-lib": "i:INT101100022"}
    conn.close()


def test_a_fresh_hard_id_overrides_a_remembered_one(tmp_path):
    # The memory must not calcify a wrong binding: whenever a read is good enough
    # to derive an ISRC/link identity, that wins and replaces what was stored.
    conn = archive.connect(str(tmp_path / "s.db"))
    archive.set_identities(conn, "apple", {"ap-lib": "i:WRONG"})
    ap = _VariantPeer("apple", {"id": "ap-lib", "name": "Song", "artists": ["A"], "artist": "A",
                                "duration_ms": 1000, "isrc": "RIGHT", "added_at": "2020"}, "ap-cat")
    assert [cid for cid, _ in _entry_cids(
        ap, ap.playlist_tracks(None), conn, {}, {}, remember=True)] == ["i:RIGHT"]
    assert archive.get_identities(conn, "apple", ["ap-lib"]) == {"ap-lib": "i:RIGHT"}
    conn.close()


def test_isrc_peer_seeds_cookie_spotify_before_canonicalization(tmp_path):
    # Spotify's signed-in web payload has no ISRC. Even when Spotify is first in
    # the peer list, the all-peer read phase must let an ISRC-rich provider seed
    # its stable track identity without a developer-catalog request.
    conn = archive.connect(str(tmp_path / "cookie-peer-isrc.db"))
    sp = _VariantPeer("spotify", {
        "id": "sp-lib", "name": "Show Me How", "artists": ["Men I Trust"],
        "artist": "Men I Trust", "duration_ms": 215000, "isrc": None, "added_at": "2020",
    }, "sp-cat")
    tidal = _VariantPeer("tidal", {
        "id": "tidal-lib", "name": "Show Me How", "artists": ["Men I Trust"],
        "artist": "Men I Trust", "duration_ms": 215000, "isrc": "CAAAA1700123", "added_at": "2020",
    }, "tidal-cat")

    stats = reconcile([sp, tidal], "Mix", {"spotify": {"id": "sp"}, "tidal": {"id": "ti"}},
                      _caches("spotify", "tidal"), conn,
                      execute=True, max_removals=0, max_adds=200)

    assert stats["added"] == 0 and stats["removed"] == 0
    assert archive.get_identities(conn, "spotify", ["sp-lib"]) == {
        "sp-lib": "i:CAAAA1700123"}
    conn.close()


def test_inferred_isrc_cannot_rebind_a_remembered_hard_identity(tmp_path):
    # Same-playlist metadata inference is useful for an unbound entry, but it is
    # not provider proof and must not overwrite an existing hard identity or
    # trigger the stable-entry baseline repair reserved for trusted evidence.
    conn = archive.connect(str(tmp_path / "inferred-rebinding.db"))
    archive.set_identities(conn, "apple", {"ap-lib": "i:PROVEN"})
    track = {"id": "ap-lib", "name": "Song", "artists": ["A"], "artist": "A",
             "duration_ms": 1000, "isrc": None, "added_at": "2020"}
    ap = _VariantPeer("apple", track, "ap-cat")
    changes = {}
    inferred = {track_key("Song", "A"): "INFERRED"}

    entries = _entry_cids(ap, ap.playlist_tracks(None), conn, {}, inferred,
                          rebindings=changes)

    assert [cid for cid, _ in entries] == ["i:PROVEN"]
    assert changes == {}
    assert archive.get_identities(conn, "apple", ["ap-lib"]) == {"ap-lib": "i:PROVEN"}
    conn.close()


def test_unify_uses_every_copys_keys_not_just_the_first():
    # Live-data shape (chai & chill): one identity, two Spotify releases — the
    # decorated title sits FIRST in playlist order. The junk YT copy matches
    # only the plain second copy's keys; unification must consider every
    # entry's keys, not just the first copy folded into canon.
    from songmirror.engine.matching import track_key
    from songmirror.engine.targets.base import _normalize, _unify_aliases

    dec = _normalize({"name": 'Kuch To Hai (From "Do Lafzon Ki Kahani")',
                      "artists": ["Armaan Malik"], "isrc": "I1"}, "spotify")
    plain = _normalize({"name": "Kuch To Hai",
                        "artists": ["Armaan Malik", "Amaal Mallik", "Manoj Muntashir"],
                        "isrc": "I1"}, "spotify")
    junk = _normalize({"name": "KUCH TO HAI", "artists": ["ARMAAN MALIK", "AMAAL MALLIK"]}, "ytmusic")
    kid = f"k:{track_key('KUCH TO HAI', 'ARMAAN MALIK, AMAAL MALLIK')}"
    alias = _unify_aliases({"spotify": [("i:I1", dec), ("i:I1", plain)], "ytmusic": [(kid, junk)]})
    assert alias == {kid: "i:I1"}


def test_unify_folds_ver_abbreviation_into_version():
    # "Twin Ver." vs "Twin Version" — the same release string abbreviated;
    # token-set matching can't bridge ver/version, so loose_name normalizes it.
    from songmirror.engine.matching import track_key
    from songmirror.engine.targets.base import _normalize, _unify_aliases

    sp = _normalize({"name": "Cupid - Twin Ver.", "artists": ["FIFTY FIFTY"], "isrc": "K1"}, "spotify")
    ap = _normalize({"name": "Cupid (Twin Version)", "artist": "FIFTY FIFTY"}, "apple")
    kid = f"k:{track_key('Cupid (Twin Version)', 'FIFTY FIFTY')}"
    alias = _unify_aliases({"spotify": {"i:K1": sp}, "apple": {kid: ap}})
    assert alias == {kid: "i:K1"}


def test_unify_never_merges_different_songs():
    # Same title, different artists (a cover on a label channel) must stay two
    # canonical identities — unification is for provider-flavored metadata of
    # ONE song, never for genuinely different recordings by different artists.
    from songmirror.engine.targets.base import _normalize, _unify_aliases

    orig = _normalize({"name": "Another Day in Paradise", "artists": ["Phil Collins"], "isrc": "P1"}, "spotify")
    cover = _normalize({"name": "Another Day in Paradise",
                        "artists": ["Thriller Records", "Kailee Morgue"]}, "ytmusic")
    alias = _unify_aliases({
        "spotify": {"i:P1": orig},
        "ytmusic": {"k:another day in paradise|thriller records kailee morgue": cover},
    })
    assert alias == {}


def test_unify_folds_reordered_and_embellished_artist_credits():
    # Live-data shape: Spotify credits "Arcane, Woodkid" while Apple credits
    # "Woodkid, Arcane, League of Legends Music" — same song, reordered AND
    # embellished. The composite key's | separator must not block the match by
    # fusing different neighbor tokens together.
    from songmirror.engine.matching import track_key
    from songmirror.engine.targets.base import _normalize, _unify_aliases

    name = "To Ashes and Blood (from the series Arcane League of Legends)"
    sp = _normalize({"name": name, "artist": "Arcane, Woodkid", "isrc": "X1"}, "spotify")
    ap = _normalize({"name": name, "artist": "Woodkid, Arcane, League of Legends Music"}, "apple")
    kid = f"k:{track_key(name, 'Woodkid, Arcane, League of Legends Music')}"
    alias = _unify_aliases({"spotify": {"i:X1": sp}, "apple": {kid: ap}})
    assert alias == {kid: "i:X1"}


def test_order_history_records_dedupes_and_prunes(tmp_path, monkeypatch):
    conn = archive.connect(str(tmp_path / "s.db"))
    stamps = iter(f"2026-01-01T00:00:{i:02d}+00:00" for i in range(60))
    monkeypatch.setattr(archive, "_now", lambda: next(stamps))
    archive.record_order(conn, "mix", "spotify", [["t1", "One", "A"]])
    archive.record_order(conn, "mix", "spotify", [["t1", "One", "A"]])  # unchanged -> no new row
    assert len(archive.get_order_history(conn, "mix", "spotify")) == 1
    for i in range(2, 20):
        archive.record_order(conn, "mix", "spotify", [["t1", "One", "A"]] * i)
    hist = archive.get_order_history(conn, "mix", "spotify")
    assert len(hist) == archive.ORDER_HISTORY_KEEP        # pruned to the retention cap
    assert len(hist[0][1]) == 19                          # newest first, latest snapshot intact
    assert archive.get_order_history(conn, "mix", "apple") == []  # scoped per source
    conn.close()


def test_reconcile_records_order_history(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    peers = [_FakePeer("spotify"), _FakePeer("apple")]
    reconcile(peers, "Mix", {"spotify": {"id": "s1"}, "apple": {"id": "a1"}},
              _caches("spotify", "apple"), conn, execute=True, max_removals=25, max_adds=200)
    hist = archive.get_order_history(conn, "mix", "spotify")
    assert hist and hist[0][1] == [["spotify1", "Song", "A"]]  # ordered [id, name, artist] rows
    conn.close()


def test_reconcile_interrupt_freezes_baseline(tmp_path):
    # A Pause/Stop mid-reconcile must NOT advance the per-provider baseline — a
    # partial advance could resurrect a track via union_prev on the next pass.
    conn = archive.connect(str(tmp_path / "s.db"))
    sp, ap = _P("spotify", ["A", "B", "C"]), _P("apple", ["A"])
    control = iter(["run"])  # allow the first check, then "stop" (default) interrupts the pass
    reconcile([sp, ap], "Mix", {"spotify": {"id": "s"}, "apple": {"id": "a"}},
              _caches("spotify", "apple"), conn, execute=True, max_removals=25, max_adds=200,
              should_continue=lambda: next(control, "stop"))
    assert archive.get_playlist_state(conn, "mix", "spotify") == set()  # frozen, not advanced
    assert archive.get_playlist_state(conn, "mix", "apple") == set()
    conn.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print("\nOK: all checks passed")
