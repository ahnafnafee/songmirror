"""Removal propagation: unmatchable songs and delisted songs.

A deletion propagates only when the song left a provider that still offers it.
A song a provider can never match must not block unrelated deletions, and a
song a provider delisted is not a user deletion, in two-way and one-way syncs.
"""

from songmirror.engine import archive
from songmirror.engine.targets.base import mirror_pair, reconcile


TITLES = {"A": "Alpha Road", "B": "Bright Lake", "C": "Cold Harbor", "U": "Underground Signal"}


class Peer:
    """Fake provider: `catalog` is what its search can find, `songs` its playlist."""

    def __init__(self, source, songs, catalog=None, titles=TITLES):
        self.source = self.tag = self.name = source
        self.titles = titles
        self.songs = list(songs)
        self.catalog = set("ABCDEFGHU") if catalog is None else set(catalog)
        self.search_fails = set()
        self.catalog_duration = 1000
        self.durations = {}  # per-song length this provider reports in playlists
        self.added, self.removed, self.searched, self.queries = [], [], [], []

    def search_candidates(self, query, *, limit=5):
        self.queries.append(query)
        found = []
        for song in sorted(self.catalog | self.search_fails):
            title = self.titles.get(song, f"Song {song}")
            if title.casefold() not in query.casefold():
                continue
            self.searched.append(song)
            if song in self.search_fails:
                raise RuntimeError("search is temporarily failing")
            found.append({"id": f"{self.source}-{song}", "name": title, "artist": "A", "artists": ["A"],
                          "duration_ms": self.catalog_duration})
        return found[:limit]

    def playlist_tracks(self, _playlist):
        return [{"id": f"{self.source}-{song}", "name": self.titles.get(song, f"Song {song}"),
                 "artists": ["A"], "artist": "A",
                 "duration_ms": self.durations.get(song, 1000), "isrc": f"ISRC{song}", "added_at": "2020"}
                for song in self.songs]

    def track_id(self, track):
        return track.get("id")

    def expected_ids(self, _tracks, _links, _cache):
        return {}

    def prefetch(self, _norms, _cache):
        pass

    def native_isrc_map(self, _cache):
        return {}

    def resolve(self, norm, _cache):
        song = norm["isrc"].removeprefix("ISRC")
        self.searched.append(song)
        if song in self.search_fails:
            raise RuntimeError("search is temporarily failing")
        return (f"{self.source}-{song}", "search") if song in self.catalog else (None, None)

    def add(self, _playlist, ids):
        for target_id in ids:
            song = target_id.split("-", 1)[1]
            self.added.append(song)
            self.songs.append(song)

    def remove(self, _playlist, raw):
        song = raw["isrc"].removeprefix("ISRC")
        self.removed.append(song)
        self.songs.remove(song)


def _sync(conn, peers, passes=1, max_removals=25):
    playlists = {peer.source: {"id": peer.source} for peer in peers}
    caches = {peer.source: {"isrc": {}, "search": {}, "dirty": False} for peer in peers}
    stats = None
    for _ in range(passes):
        stats = reconcile(peers, "Mix", playlists, caches, conn, execute=True,
                          max_removals=max_removals, max_adds=200)
    return stats


def test_a_song_one_service_can_never_match_does_not_block_other_deletions(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    jellyfin = Peer("jellyfin", "ABCU")
    listenbrainz = Peer("listenbrainz", "", catalog="ABC")  # U has no ListenBrainz match
    _sync(conn, [jellyfin, listenbrainz], passes=2)
    assert sorted(listenbrainz.songs) == ["A", "B", "C"]
    jellyfin.songs.remove("B")  # the user deletes B on Jellyfin
    _sync(conn, [jellyfin, listenbrainz], passes=2)
    assert sorted(listenbrainz.songs) == ["A", "C"], "the confirmed deletion reaches ListenBrainz"
    assert sorted(jellyfin.songs) == ["A", "C", "U"], "the unmatchable song is never deleted"
    assert "B" not in jellyfin.added
    conn.close()


def test_a_held_deletion_never_comes_back_to_the_provider_where_it_was_made(tmp_path):
    # "Song B" resembles the unmatched "Song U", so the uncertain-match guard
    # holds B's removal on ListenBrainz. The deletion on Jellyfin must survive.
    conn = archive.connect(str(tmp_path / "s.db"))
    jellyfin = Peer("jellyfin", "ABCU", titles={})
    listenbrainz = Peer("listenbrainz", "", catalog="ABC", titles={})
    _sync(conn, [jellyfin, listenbrainz], passes=2)
    jellyfin.songs.remove("B")
    stats = _sync(conn, [jellyfin, listenbrainz], passes=5)
    assert sorted(jellyfin.songs) == ["A", "C", "U"] and "B" not in jellyfin.added
    assert stats["held"] == 1 and not stats["clean"]
    conn.close()


def test_a_new_unmatched_song_still_holds_deletions_as_a_possible_replacement(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    titles = {**TITLES, "R": "Bright Lake (Remastered)"}
    spotify = Peer("spotify", "AB", titles=titles)
    apple = Peer("apple", "AB", catalog="AB", titles=titles)
    _sync(conn, [spotify, apple], passes=2)
    spotify.songs[spotify.songs.index("B")] = "R"  # B replaced by a version Apple cannot match
    for _ in range(4):
        _sync(conn, [spotify, apple])
        assert sorted(apple.songs) == ["A", "B"], "Apple keeps B while the replacement is unmatched"
    conn.close()


def test_a_delisted_song_is_not_a_deletion_and_is_never_re_added(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.songs.remove("C")
    spotify.catalog.discard("C")  # delisted: gone from the playlist and the catalog
    stats = _sync(conn, [spotify, tidal], passes=4)
    assert sorted(tidal.songs) == ["A", "B", "C"], "the other service keeps the delisted song"
    assert "C" not in spotify.added and sorted(spotify.songs) == ["A", "B"]
    assert stats["removed"] == 0 and stats["added"] == 0
    assert archive.get_catalog_checks(conn, "mix", "spotify") == {"i:ISRCC": False}
    conn.close()


def test_deleting_a_song_the_service_still_offers_propagates(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.songs.remove("C")  # still in Spotify's catalog: a user deletion
    _sync(conn, [spotify, tidal], passes=2)
    assert sorted(tidal.songs) == ["A", "B"]
    assert "C" in spotify.searched, "the deletion was checked against Spotify's catalog"
    assert archive.get_catalog_checks(conn, "mix", "spotify") == {}
    conn.close()


def test_a_catalog_copy_with_a_different_length_still_counts_as_offered(tmp_path):
    # The check uses another provider's metadata. A length mismatch with this
    # provider's own copy must not turn a user deletion into a "delisting".
    conn = archive.connect(str(tmp_path / "s.db"))
    jellyfin, listenbrainz = Peer("jellyfin", "ABC"), Peer("listenbrainz", "ABC")
    jellyfin.catalog_duration = 245000
    _sync(conn, [jellyfin, listenbrainz], passes=2)
    jellyfin.songs.remove("C")
    _sync(conn, [jellyfin, listenbrainz], passes=2)
    assert sorted(listenbrainz.songs) == ["A", "B"]
    assert archive.get_catalog_checks(conn, "mix", "jellyfin") == {}
    conn.close()


def test_a_provider_without_catalog_search_falls_back_to_a_fresh_match(tmp_path):
    class NoSearch(Peer):
        def search_candidates(self, query, *, limit=5):
            raise NotImplementedError

    conn = archive.connect(str(tmp_path / "s.db"))
    listenbrainz, jellyfin = NoSearch("listenbrainz", "ABCDEFG"), Peer("jellyfin", "ABCDEFG")
    _sync(conn, [listenbrainz, jellyfin], passes=2)
    listenbrainz.songs.remove("C")
    listenbrainz.catalog.discard("C")
    listenbrainz.songs.remove("B")  # B is still offered: a real deletion
    _sync(conn, [listenbrainz, jellyfin], passes=2)
    assert sorted(jellyfin.songs) == list("ACDEFG"), "B propagates; the delisted C stays"
    assert archive.get_catalog_checks(conn, "mix", "listenbrainz") == {"i:ISRCC": False}
    conn.close()


def test_with_removals_off_no_catalog_search_runs_and_nothing_is_deleted(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2, max_removals=0)
    spotify.songs.remove("C")
    _sync(conn, [spotify, tidal], passes=4, max_removals=0)
    assert "C" not in spotify.searched, "a held removal must not search the catalog on every pass"
    assert sorted(tidal.songs) == ["A", "B", "C"] and "C" not in spotify.added
    conn.close()


def test_a_held_batch_over_the_cap_checks_the_catalog_once(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABCDEFG"), Peer("tidal", "ABCDEFG")
    _sync(conn, [spotify, tidal], passes=2, max_removals=1)
    spotify.songs.remove("B")
    spotify.songs.remove("C")  # two confirmed deletions against a cap of one
    _sync(conn, [spotify, tidal], passes=5, max_removals=1)
    assert sorted(tidal.songs) == list("ABCDEFG"), "the over-cap batch stays held"
    assert (spotify.searched.count("B"), spotify.searched.count("C")) == (1, 1)
    assert archive.get_catalog_checks(conn, "mix", "spotify") == {"i:ISRCB": True, "i:ISRCC": True}
    _sync(conn, [spotify, tidal], passes=1, max_removals=25)
    assert sorted(tidal.songs) == list("ADEFG"), "raising the cap applies the saved answers"
    assert spotify.searched.count("B") == 1 and archive.get_catalog_checks(conn, "mix", "spotify") == {}
    conn.close()


def test_a_failed_catalog_check_keeps_the_deletion_pending(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.songs.remove("C")
    spotify.search_fails.add("C")
    stats = _sync(conn, [spotify, tidal], passes=3)
    assert sorted(tidal.songs) == ["A", "B", "C"] and not stats["clean"]
    assert "C" not in spotify.added
    spotify.search_fails.clear()
    _sync(conn, [spotify, tidal], passes=1)
    assert sorted(tidal.songs) == ["A", "B"], "the deletion applies once the check succeeds"
    conn.close()


def test_re_adding_a_delisted_song_clears_its_marker(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.songs.remove("C")
    spotify.catalog.discard("C")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.catalog.add("C")
    spotify.songs.append("C")  # the song returns and the user adds it back
    _sync(conn, [spotify, tidal], passes=2)
    assert archive.get_catalog_checks(conn, "mix", "spotify") == {}
    spotify.songs.remove("C")  # a later deletion of the offered song propagates normally
    _sync(conn, [spotify, tidal], passes=2)
    assert sorted(tidal.songs) == ["A", "B"]
    conn.close()


ONE_WAY_KEY = archive.MIRROR_CHECK_PREFIX + "mix"


def _mirror(conn, source, mirror, passes=1, max_removals=25):
    stats = []
    for _ in range(passes):
        stats.append(mirror_pair(
            mirror, source.playlist_tracks(None), {"name": "Mix"}, {"id": "mix"},
            {"isrc": {}, "search": {}, "dirty": False}, conn, execute=True,
            max_removals=max_removals, max_adds=200, source_key=source.source,
            source_name=source.name, catalog_peers={source.source: (source, None)}, check_key=ONE_WAY_KEY))
    return stats


def test_one_way_keeps_a_track_the_source_catalog_dropped(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("tidal", "ABC"), Peer("jellyfin", "")
    _mirror(conn, source, mirror)
    source.songs.remove("C")
    source.catalog.discard("C")  # delisted on the source of truth
    first, *later = _mirror(conn, source, mirror, passes=3)
    assert sorted(mirror.songs) == ["A", "B", "C"] and mirror.removed == []
    assert first["clean"] and [row["category"] for row in first["change_diagnostics"]] == ["unavailable_on_provider"]
    assert all(stats["clean"] and not stats["change_diagnostics"] for stats in later)
    assert sum("Cold Harbor" in query for query in source.queries) == 2,         "one check (title with artist, then title) serves every later pass"
    assert archive.get_catalog_checks(conn, ONE_WAY_KEY, "jellyfin") == {"jellyfin-C": False}
    source.catalog.add("C")
    source.songs.append("C")  # back on the source: the answer is dropped
    _mirror(conn, source, mirror)
    assert archive.get_catalog_checks(conn, ONE_WAY_KEY, "jellyfin") == {}
    conn.close()


def test_one_way_removes_a_track_the_source_still_offers(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("tidal", "ABC"), Peer("jellyfin", "")
    _mirror(conn, source, mirror)
    source.songs.remove("C")
    _mirror(conn, source, mirror)
    assert sorted(mirror.songs) == ["A", "B"] and mirror.removed == ["C"]
    assert archive.get_catalog_checks(conn, ONE_WAY_KEY, "jellyfin") == {}
    conn.close()


def test_one_way_checks_a_held_over_cap_batch_once(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("tidal", "ABCD"), Peer("jellyfin", "")
    _mirror(conn, source, mirror)
    source.songs.remove("B")
    source.songs.remove("C")
    _mirror(conn, source, mirror, passes=3, max_removals=1)
    assert sorted(mirror.songs) == list("ABCD")
    assert (source.searched.count("B"), source.searched.count("C")) == (1, 1)
    _mirror(conn, source, mirror, max_removals=25)
    assert sorted(mirror.songs) == ["A", "D"] and source.searched.count("B") == 1
    assert archive.get_catalog_checks(conn, ONE_WAY_KEY, "jellyfin") == {}
    conn.close()


def test_one_way_holds_a_removal_when_the_source_check_fails(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("tidal", "ABC"), Peer("jellyfin", "")
    _mirror(conn, source, mirror)
    source.songs.remove("C")
    source.search_fails.add("C")
    (stats,) = _mirror(conn, source, mirror)
    assert sorted(mirror.songs) == ["A", "B", "C"] and not stats["clean"]
    source.search_fails.clear()
    _mirror(conn, source, mirror)
    assert sorted(mirror.songs) == ["A", "B"]
    conn.close()


def test_one_way_with_removals_off_never_searches_the_source(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("tidal", "ABC"), Peer("jellyfin", "")
    _mirror(conn, source, mirror, max_removals=0)
    source.songs.remove("C")
    _mirror(conn, source, mirror, passes=2, max_removals=0)
    assert "C" not in source.searched and sorted(mirror.songs) == ["A", "B", "C"]
    conn.close()


def test_one_way_keeps_a_mirror_copy_whose_length_disagrees_instead_of_flapping(tmp_path):
    # The mirror matched B without length evidence, then reports a length over
    # the tolerance. Removing it and adding it back on alternate passes is churn.
    conn = archive.connect(str(tmp_path / "s.db"))
    source, mirror = Peer("jellyfin", "ABC"), Peer("listenbrainz", "")
    mirror.durations["B"] = 1000 + 5200
    _mirror(conn, source, mirror)
    passes = _mirror(conn, source, mirror, passes=4)
    assert sorted(mirror.songs) == ["A", "B", "C"]
    assert mirror.removed == [] and mirror.added.count("B") == 1
    assert all(stats["uncertain_matches"] == 1 for stats in passes)
    conn.close()


class NoIsrcPeer(Peer):
    """A provider whose reads carry no ISRC, like Spotify cookie reads and local Jellyfin files."""

    def playlist_tracks(self, _playlist):
        return [{"id": f"{self.source}-{song}", "name": self.titles.get(song, f"Song {song}"),
                 "artists": ["A"], "artist": "A", "duration_ms": 1000, "added_at": "2020"}
                for song in self.songs]

    def resolve(self, norm, _cache):
        song = next((s for s, title in self.titles.items() if title == norm["name"]), None)
        self.searched.append(song)
        return (f"{self.source}-{song}", "search") if song in self.catalog else (None, None)

    def remove(self, _playlist, raw):
        song = raw["id"].split("-", 1)[1]
        self.removed.append(song)
        self.songs.remove(song)


def test_a_deletion_beside_an_isrc_less_spotify_read_is_not_re_added(tmp_path):
    # Spotify's own entries reach a hard identity only by folding into the
    # linked copy on the other provider. Deleting that copy must not turn the
    # Spotify entry into a "new" song that is added straight back.
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, jellyfin = NoIsrcPeer("spotify", "ABC"), NoIsrcPeer("jellyfin", "")
    _sync(conn, [spotify, jellyfin], passes=2)
    assert sorted(jellyfin.songs) == ["A", "B", "C"]
    jellyfin.songs.remove("B")  # the user deletes B on Jellyfin
    _sync(conn, [spotify, jellyfin])
    assert jellyfin.added.count("B") == 1, "the first read only marks the deletion pending"
    _sync(conn, [spotify, jellyfin])
    assert sorted(spotify.songs) == ["A", "C"] and sorted(jellyfin.songs) == ["A", "C"]
    conn.close()
