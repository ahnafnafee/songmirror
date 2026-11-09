"""Two-way removal propagation: unmatchable songs and delisted songs.

A deletion propagates only when the song left a provider that still offers it.
A song a provider can never match must not block unrelated deletions, and a
song a provider delisted is not a user deletion.
"""

from songmirror.engine import archive
from songmirror.engine.targets.base import reconcile


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
        self.added, self.removed, self.searched = [], [], []

    def search_candidates(self, query, *, limit=5):
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
                 "duration_ms": 1000, "isrc": f"ISRC{song}", "added_at": "2020"} for song in self.songs]

    def track_id(self, track):
        return track.get("id")

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
    assert archive.get_playlist_unavailable(conn, "mix", "spotify") == {"i:ISRCC"}
    conn.close()


def test_deleting_a_song_the_service_still_offers_propagates(tmp_path):
    conn = archive.connect(str(tmp_path / "s.db"))
    spotify, tidal = Peer("spotify", "ABC"), Peer("tidal", "ABC")
    _sync(conn, [spotify, tidal], passes=2)
    spotify.songs.remove("C")  # still in Spotify's catalog: a user deletion
    _sync(conn, [spotify, tidal], passes=2)
    assert sorted(tidal.songs) == ["A", "B"]
    assert "C" in spotify.searched, "the deletion was checked against Spotify's catalog"
    assert archive.get_playlist_unavailable(conn, "mix", "spotify") == set()
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
    assert archive.get_playlist_unavailable(conn, "mix", "jellyfin") == set()
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
    assert archive.get_playlist_unavailable(conn, "mix", "listenbrainz") == {"i:ISRCC"}
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
    assert archive.get_playlist_unavailable(conn, "mix", "spotify") == set()
    spotify.songs.remove("C")  # a later deletion of the offered song propagates normally
    _sync(conn, [spotify, tidal], passes=2)
    assert sorted(tidal.songs) == ["A", "B"]
    conn.close()
