"""build_one registry helper + PlaylistService."""

import pytest

from songmirror.engine import targets
from songmirror.engine.config import parse_args


def test_build_one_unknown_returns_none():
    assert targets.build_one("nope", parse_args([])) is None


def test_build_one_known_dispatches(monkeypatch):
    sentinel = object()
    monkeypatch.setitem(targets._REGISTRY, "spotify", lambda o, sp: sentinel)
    assert targets.build_one("spotify", parse_args([])) is sentinel


def test_find_playlist_normalizes_numeric_provider_ids():
    from songmirror.engine.targets.base import MirrorTarget

    class Target(MirrorTarget):
        def browse_playlists(self):
            return [{"id": 68684835, "name": "Argonaut"}]

    assert Target().find_playlist("68684835")["name"] == "Argonaut"


def test_is_peer_excludes_browse_only():
    # A sync/transfer peer has a MirrorTarget; browse-only Jellyfin does not.
    assert all(targets.is_peer(provider) for provider in (
        "spotify", "tidal", "qobuz", "deezer", "amazon", "apple", "ytmusic"
    ))
    assert not targets.is_peer("jellyfin")
    assert not targets.is_peer("bogus")


def test_build_targets_respects_providers(monkeypatch):
    # Deselecting a provider (via opts.providers) excludes it from one-way targets.
    monkeypatch.setitem(targets._REGISTRY, "apple", lambda o, sp, sync_peer=False, songs=None: "APPLE")
    monkeypatch.setitem(targets._REGISTRY, "ytmusic", lambda o, sp, sync_peer=False, songs=None: "YT")
    opts = parse_args([])
    opts.providers = "spotify,apple"  # ytmusic left out
    assert targets.build_targets(opts) == ["APPLE"]


def test_empty_providers_means_all(monkeypatch):
    # An empty providers list means "every configured provider" (matching the UI +
    # the empty-playlists convention), NOT "none" — so a job saved without touching
    # the Services step still syncs instead of finding zero peers.
    monkeypatch.setitem(targets._REGISTRY, "spotify", lambda o, sp, sync_peer=False, songs=None: "SP")
    monkeypatch.setitem(targets._REGISTRY, "apple", lambda o, sp, sync_peer=False, songs=None: "APPLE")
    monkeypatch.setitem(targets._REGISTRY, "ytmusic", lambda o, sp, sync_peer=False, songs=None: "YT")
    monkeypatch.setattr(targets, "_SOURCE_ORDER", ["spotify", "apple", "ytmusic"])
    opts = parse_args([])
    opts.providers = ""
    opts.sync_source = "spotify"
    assert targets.build_targets(opts) == ["APPLE", "YT"]                  # all except the source
    assert targets.build_peers(opts, sp="client") == ["SP", "APPLE", "YT"]  # every peer


def test_blank_storefront_defaults(monkeypatch):
    # A blank APPLE_STOREFRONT (saved when the Apple connect leaves it empty) must
    # fall back to the default, not go into the URL and yield /catalog//search (400).
    monkeypatch.setenv("APPLE_STOREFRONT", "")
    assert parse_args([]).storefront == "us"


def test_browse_normalizes_rows(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    class FakeTarget:
        def list_playlists(self):
            # Qobuz emits numeric playlist ids. The web contract is string-id
            # based because ids become select values and link-store keys.
            return {"chill": {"id": 1, "name": "Chill", "tracks": {"total": 5}}}

        def browse_playlists(self):
            return list(self.list_playlists().values())

        def playlist_count(self, pl):
            return (pl.get("tracks") or {}).get("total")

    monkeypatch.setattr("songmirror.services.playlists.build_one", lambda pid, opts, sp=None: FakeTarget())
    rows = PlaylistService(SettingsStore(dir=tmp_path)).browse("apple")
    assert rows == [{
        "id": "1",
        "name": "Chill",
        "count": 5,
        "image": "",
        "owned": True,
        "external_url": "https://music.apple.com/library/playlist/1",
    }]


def test_browse_hydrates_counts_before_normalizing_rows(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    class FakeTarget:
        def browse_playlists(self):
            return [{"id": "p1", "name": "Mix"}]

        def hydrate_playlist_counts(self, playlists):
            playlists[0]["items"] = {"total": 42}
            return playlists

        def playlist_count(self, playlist):
            return (playlist.get("items") or {}).get("total")

    monkeypatch.setattr("songmirror.services.playlists.build_one", lambda pid, opts, sp=None: FakeTarget())

    rows = PlaylistService(SettingsStore(dir=tmp_path)).browse("apple")

    assert rows[0]["count"] == 42


def test_browse_lists_followed_spotify_playlists(monkeypatch, tmp_path):
    # Spotify browse lists followed (non-owned) playlists alongside owned ones, via
    # the un-deduped all_playlists(), and labels each with `owned` so the UI can
    # divide Created from Followed.
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    monkeypatch.setattr("songmirror.services.playlists.spotify.client", lambda *a, **k: object())
    monkeypatch.setattr(
        "songmirror.services.playlists.spotify.all_playlists",
        lambda sp: [{"id": "1", "name": "Mine", "owner": {"id": "me"}, "_owned": True},
                    {"id": "2", "name": "Theirs", "owner": {"id": "other"}, "_owned": False}],
    )
    rows = PlaylistService(SettingsStore(dir=tmp_path)).browse("spotify")
    assert {r["name"]: r["owned"] for r in rows} == {"Mine": True, "Theirs": False}


def test_browse_failure_is_not_reported_as_an_empty_library(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistBrowseError, PlaylistService
    from songmirror.services.settings import SettingsStore

    class BrokenTarget:
        name = "Spotify"

        def browse_playlists(self):
            raise RuntimeError("temporary upstream failure")

    monkeypatch.setattr(
        "songmirror.services.playlists.build_one",
        lambda provider, opts, sp=None: BrokenTarget(),
    )
    monkeypatch.setattr("songmirror.services.playlists.spotify.client", lambda: object())

    with pytest.raises(PlaylistBrowseError, match="could not load playlists"):
        PlaylistService(SettingsStore(dir=tmp_path)).browse("spotify")


def test_browse_surfaces_a_missing_library_capability_as_read_only(monkeypatch, tmp_path):
    from songmirror.engine.targets.base import TargetCapabilityError
    from songmirror.services.playlists import PlaylistReadOnlyError, PlaylistService
    from songmirror.services.settings import SettingsStore

    class CatalogOnlyTarget:
        def browse_playlists(self):
            raise TargetCapabilityError(
                "Apple Music library access requires an active Apple Music subscription."
            )

    monkeypatch.setattr(
        "songmirror.services.playlists.build_one",
        lambda provider, opts, sp=None: CatalogOnlyTarget(),
    )

    with pytest.raises(PlaylistReadOnlyError, match="active Apple Music subscription"):
        PlaylistService(SettingsStore(dir=tmp_path)).browse("apple")


def test_playlist_detail_normalizes_tracks_and_external_links(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    class Target:
        name = "Spotify"

        def find_playlist(self, playlist_id):
            assert playlist_id == "playlist-1"
            return {
                "id": playlist_id,
                "name": "Aurora",
                "images": [{"url": "https://img.test/aurora.jpg"}],
                "_owned": True,
            }

        def playlist_tracks(self, playlist):
            return [{
                "id": "track-1",
                "name": "Song",
                "artists": ["Artist", "Guest"],
                "album": "Album",
                "duration_ms": 183000,
                "image": "https://img.test/song.jpg",
                "added_at": "2026-08-15T12:34:56Z",
            }]

        def track_id(self, track):
            return track["id"]

        def playlist_count(self, playlist):
            return 1

        def playlist_name(self, playlist):
            return playlist["name"]

        def playlist_description(self, playlist):
            return 'A description with <a href="spotify:playlist:other">another mix</a>.'

        def is_editable(self, playlist):
            return True

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    detail = service.detail("spotify", "playlist-1")

    assert detail == {
        "provider": "spotify",
        "id": "playlist-1",
        "name": "Aurora",
        "description": "A description with another mix.",
        "count": 1,
        "image": "https://img.test/aurora.jpg",
        "owned": True,
        "editable": True,
        "external_url": "https://open.spotify.com/playlist/playlist-1",
        "tracks": [{
            "position": 0,
            "id": "track-1",
            "isrc": "",
            "occurrence_id": "",
            "name": "Song",
            "artist": "Artist, Guest",
            "album": "Album",
            "duration_ms": 183000,
            "image": "https://img.test/song.jpg",
            "added_at": "2026-08-15T12:34:56Z",
            "external_url": "https://open.spotify.com/track/track-1",
        }],
    }


def test_playlist_detail_cache_is_ordered_persistent_and_archives_songs(tmp_path):
    from songmirror.engine import archive

    conn = archive.connect(str(tmp_path / "songs.db"))
    detail = {
        "provider": "deezer",
        "id": "playlist-1",
        "name": "Argonaut",
        "description": "Mirror",
        "count": 2,
        "image": "https://img.test/playlist.jpg",
        "owned": True,
        "editable": True,
        "external_url": "https://www.deezer.com/playlist/playlist-1",
        "tracks": [
            {
                "position": 0,
                "id": "track-1",
                "isrc": "USAAA2600001",
                "occurrence_id": "",
                "name": "First",
                "artist": "Artist",
                "album": "Album",
                "duration_ms": 180000,
                "image": "https://img.test/first.jpg",
                "added_at": "",
                "external_url": "https://www.deezer.com/track/track-1",
            },
            {
                "position": 1,
                "id": "track-2",
                "isrc": "",
                "occurrence_id": "entry-2",
                "name": "Second",
                "artist": "Artist",
                "album": None,
                "duration_ms": None,
                "image": "",
                "added_at": "2026-08-16T12:00:00Z",
                "external_url": "https://www.deezer.com/track/track-2",
            },
        ],
    }

    archive.set_playlist_detail_cache(conn, detail)

    assert archive.get_playlist_detail_cache(conn, "deezer", "playlist-1") == detail
    assert conn.execute(
        "SELECT name, isrc FROM songs WHERE source = 'deezer' ORDER BY id"
    ).fetchall() == [("First", "USAAA2600001"), ("Second", "")]

    archive.invalidate_playlist_detail_cache(conn, "deezer", "playlist-1")
    assert archive.get_playlist_detail_cache(conn, "deezer", "playlist-1") is None


def test_playlist_detail_reuses_cache_until_explicit_refresh(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    reads = []

    class Target:
        def find_playlist(self, playlist_id):
            return {"id": playlist_id, "name": "Aurora"}

        def playlist_tracks(self, playlist):
            reads.append(playlist["id"])
            return [{"id": "track-1", "name": f"Read {len(reads)}", "artist": "Artist"}]

        def track_id(self, track):
            return track["id"]

        def playlist_id(self, playlist):
            return playlist["id"]

        def playlist_name(self, playlist):
            return playlist["name"]

        def playlist_description(self, playlist):
            return ""

        def is_editable(self, playlist):
            return True

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    first = service.detail("spotify", "playlist-1")
    cached = service.detail("spotify", "playlist-1")
    refreshed = service.detail("spotify", "playlist-1", refresh=True)

    assert first["tracks"][0]["name"] == "Read 1"
    assert cached["tracks"][0]["name"] == "Read 1"
    assert refreshed["tracks"][0]["name"] == "Read 2"
    assert reads == ["playlist-1", "playlist-1"]


def test_playlist_detail_page_returns_one_provider_page_with_total_and_offset(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    calls = []

    class Target:
        def find_playlist(self, playlist_id):
            raise AssertionError("cursor pages must not rescan the provider playlist library")

        def playlist_page_reference(self, playlist_id, expected_count=None):
            return {
                "id": playlist_id,
                "attributes": {"name": "", "numberOfItems": expected_count},
            }

        def playlist_tracks_page(self, playlist, cursor=None):
            calls.append((playlist["id"], cursor))
            return ([{
                "id": "track-21",
                "name": "Next page",
                "artist": "Artist",
                "relationship_id": "entry-21",
            }], "cursor-2")

        def track_id(self, track):
            return track["id"]

        def occurrence_id(self, track):
            return track.get("relationship_id")

        def playlist_id(self, playlist):
            return playlist["id"]

        def playlist_count(self, playlist):
            return playlist["attributes"]["numberOfItems"]

        def playlist_name(self, playlist):
            return playlist["attributes"]["name"]

        def playlist_description(self, playlist):
            return ""

        def is_editable(self, playlist):
            return True

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    detail = service.detail_page(
        "tidal",
        "playlist-1",
        cursor="cursor-1",
        offset=20,
        expected_count=137,
    )

    assert calls == [("playlist-1", "cursor-1")]
    assert detail["count"] == 137
    assert detail["next_cursor"] == "cursor-2"
    assert detail["complete"] is False
    assert detail["tracks"][0]["position"] == 20
    assert detail["tracks"][0]["occurrence_id"] == "entry-21"


def test_playlist_detail_exposes_unavailable_tidal_entries_without_caching_them(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    reads = []

    class Target:
        def find_playlist(self, playlist_id):
            return {"id": playlist_id, "attributes": {"name": "Old mix"}}

        def playlist_tracks(self, playlist):
            raise AssertionError("playlist browsing must use the tolerant reader")

        def playlist_tracks_for_browse(self, playlist):
            reads.append(playlist["id"])
            return [{
                "id": "hidden-1",
                "name": "Unavailable TIDAL track",
                "artist": "Catalog ID hidden-1",
                "relationship_id": "entry-hidden",
                "unavailable": True,
            }]

        def track_id(self, track):
            return track["id"]

        def occurrence_id(self, track):
            return track.get("relationship_id")

        def playlist_id(self, playlist):
            return playlist["id"]

        def playlist_name(self, playlist):
            return playlist["attributes"]["name"]

        def playlist_description(self, playlist):
            return ""

        def is_editable(self, playlist):
            return True

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    first = service.detail("tidal", "playlist-1")
    second = service.detail("tidal", "playlist-1")

    assert reads == ["playlist-1", "playlist-1"]
    assert first == second
    assert first["tracks"] == [{
        "position": 0,
        "id": "hidden-1",
        "isrc": "",
        "occurrence_id": "entry-hidden",
        "name": "Unavailable TIDAL track",
        "artist": "Catalog ID hidden-1",
        "album": None,
        "duration_ms": None,
        "image": "",
        "added_at": "",
        "external_url": "",
        "unavailable": True,
    }]


def test_browse_prunes_cache_for_a_deleted_or_recreated_playlist(monkeypatch, tmp_path):
    from songmirror.engine import archive
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    conn = archive.connect(str(tmp_path / "song_cache.db"))
    archive.set_playlist_detail_cache(conn, {
        "provider": "apple",
        "id": "deleted-id",
        "name": "Aurora",
        "description": "",
        "image": "",
        "owned": True,
        "editable": True,
        "external_url": "",
        "tracks": [],
    })
    conn.close()

    class Target:
        def browse_playlists(self):
            return [{"id": "replacement-id", "attributes": {"name": "Aurora"}}]

        def playlist_count(self, playlist):
            return None

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    assert service.browse("apple")[0]["id"] == "replacement-id"
    conn = archive.connect(str(tmp_path / "song_cache.db"))
    assert archive.get_playlist_detail_cache(conn, "apple", "deleted-id") is None
    conn.close()


def test_remove_track_checks_the_read_position_before_mutating(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistChangedError, PlaylistService
    from songmirror.services.settings import SettingsStore

    removed = []

    class Target:
        name = "Spotify"

        def find_playlist(self, playlist_id):
            return {"id": playlist_id, "name": "Aurora", "_editable": True}

        def playlist_tracks(self, playlist):
            return [{"id": "first", "name": "First"}, {"id": "second", "name": "Second"}]

        def track_id(self, track):
            return track["id"]

        def is_editable(self, playlist):
            return True

        def remove_occurrences(self, playlist, positioned):
            removed.extend(positioned)

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    with pytest.raises(PlaylistChangedError, match="changed since it was opened"):
        service.remove_track("spotify", "playlist-1", position=1, track_id="stale")
    assert removed == []

    result = service.remove_track(
        "spotify", "playlist-1", position=1, track_id="second"
    )
    assert result == {"ok": True}
    assert removed == [(1, {"id": "second", "name": "Second"})]


def test_remove_track_uses_stable_occurrence_without_full_reread(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistService
    from songmirror.services.settings import SettingsStore

    removed = []

    class Target:
        stable_occurrence_ids = True

        def find_playlist(self, playlist_id):
            return {"id": playlist_id, "name": "Argonaut"}

        def is_editable(self, playlist):
            return True

        def playlist_tracks(self, playlist):
            raise AssertionError("stable occurrence removal must not reread every track")

        def remove_occurrence(self, playlist, track_id, occurrence_id):
            removed.append((playlist["id"], track_id, occurrence_id))

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    result = service.remove_track(
        "tidal",
        "playlist-1",
        position=271,
        track_id="track-1",
        occurrence_id="entry-271",
    )

    assert result == {"ok": True}
    assert removed == [("playlist-1", "track-1", "entry-271")]


def test_bulk_remove_validates_every_position_before_mutating(monkeypatch, tmp_path):
    from songmirror.services.playlists import PlaylistChangedError, PlaylistService
    from songmirror.services.settings import SettingsStore

    removed = []

    class Target:
        stable_occurrence_ids = False

        def find_playlist(self, playlist_id):
            return {"id": playlist_id, "name": "Aurora"}

        def is_editable(self, playlist):
            return True

        def playlist_tracks(self, playlist):
            return [{"id": "first"}, {"id": "second"}, {"id": "third"}]

        def track_id(self, track):
            return track["id"]

        def remove_occurrences(self, playlist, positioned):
            removed.extend(positioned)

    service = PlaylistService(SettingsStore(dir=tmp_path))
    monkeypatch.setattr(service, "_target", lambda provider: Target())

    with pytest.raises(PlaylistChangedError, match="changed since it was opened"):
        service.remove_tracks("spotify", "playlist-1", selections=[
            {"position": 0, "track_id": "first", "occurrence_id": ""},
            {"position": 2, "track_id": "stale", "occurrence_id": ""},
        ])
    assert removed == []

    result = service.remove_tracks("spotify", "playlist-1", selections=[
        {"position": 0, "track_id": "first", "occurrence_id": ""},
        {"position": 2, "track_id": "third", "occurrence_id": ""},
    ])
    assert result == {"ok": True, "removed": 2}
    assert removed == [(0, {"id": "first"}), (2, {"id": "third"})]


def test_track_total_reads_both_shapes():
    # Spotify's /me/playlists object moved the count from `tracks.total` to
    # `items.total`; read the current key first, fall back to the legacy one.
    from songmirror.engine.spotify import track_total

    assert track_total({"items": {"total": 212}}) == 212
    assert track_total({"tracks": {"total": 7}}) == 7
    assert track_total({"items": {"total": 3}, "tracks": {"total": 99}}) == 3
    assert track_total({}) is None


def test_pl_image_extraction():
    from songmirror.services.playlists import playlist_image

    assert playlist_image({"images": [{"url": "http://sp/cover.jpg"}]}) == "http://sp/cover.jpg"
    assert playlist_image({"images": ["http://qb/cover.jpg"]}) == "http://qb/cover.jpg"
    assert playlist_image({"image_rectangle": ["http://qb/playlist.jpg"]}) == "http://qb/playlist.jpg"
    assert playlist_image({"picture": {"urls": ["http://dz/small.jpg", "http://dz/large.jpg"]}}) == (
        "http://dz/large.jpg"
    )
    assert playlist_image({"picture_xl": "http://dz/xl.jpg"}) == "http://dz/xl.jpg"
    assert playlist_image({"attributes": {"artwork": {"url": "http://ap/{w}x{h}bb.jpg"}}}) == "http://ap/300x300bb.jpg"
    assert playlist_image({"thumbnails": [{"url": "a"}, {"url": "http://yt/big.jpg"}]}) == "http://yt/big.jpg"
    assert playlist_image({"images": [None, {}, "", {"url": "http://mixed/cover.jpg"}]}) == (
        "http://mixed/cover.jpg"
    )
    assert playlist_image({"name": "no art"}) == ""


def test_linkstore_roundtrip(tmp_path):
    from songmirror.services.playlists import LinkStore, PlaylistLink

    store = LinkStore(dir=tmp_path)
    link = store.upsert(PlaylistLink(name="My Pair", members={"spotify": "s1", "apple": None}))
    assert link.id  # generated
    got = store.list()
    assert len(got) == 1 and got[0].name == "My Pair"
    store.delete(link.id)
    assert store.list() == []
