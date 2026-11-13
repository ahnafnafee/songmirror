"""Every provider pair can carry albums, including playlist/love-only routes."""

from types import SimpleNamespace

import pytest

from songmirror.engine import albums
from songmirror.engine.album_library import AlbumLibrary, AlbumManifest, album_key
from songmirror.engine.album_native import NativeAlbums, native_available
from songmirror.engine.config import parse_args
from songmirror.engine.runner import run_pass
from songmirror.engine.targets import provider_ids


def album(identity="album"):
    return {"id": identity, "name": "Record", "artists": ["Artist"], "upc": "123456789012",
            "release_date": "2024-01-01", "total_tracks": 2}


def tracks():
    return [{"id": str(index), "name": name, "artists": ["Artist"], "album": "Record",
             "duration_ms": 120000} for index, name in enumerate(["One", "Two"])]


class Peer:
    def __init__(self, provider, tmp_path):
        self.source = self.tag = provider
        self.name = provider
        self.cache_file = str(tmp_path / f"{provider}.json")
        self.supports_playlists = provider != "lastfm"
        self.catalog_ids_global = provider not in {"subsonic", "jellyfin"}
        self.library = []
        self.playlists = {}
        self.loves = []
        self.resolved = {}
        self.creates = 0
        self.writes = []
        self.fail_on = None
        self._api = SimpleNamespace(get_library_albums=lambda **kw: []) if provider == "ytmusic" else None

    def validate_saved_albums(self, *, write=False):
        pass

    def validate_favorite_tracks(self, *, write=False):
        pass

    def saved_albums(self):
        return list(self.library)

    def album_tracks(self, _album):
        return tracks()

    def find_albums(self, _album):
        return [album(f"{self.source}-album")]

    def add_saved_albums(self, identifiers):
        self.writes.extend(identifiers)
        self.library.extend(album(identity) for identity in identifiers)

    def resolve(self, track, cache):
        identity = f"Artist␟{track['name']}" if self.source == "lastfm" else f"{self.source}-{track['name']}"
        self.resolved[identity] = {**track, "id": identity}
        return identity, "search"

    def create(self, details):
        self.creates += 1
        identity = f"playlist-{self.creates}"
        self.playlists[identity] = {"id": identity, "name": details["name"], "tracks": []}
        return self.playlists[identity]

    def playlist_id(self, playlist):
        return playlist["id"]

    def find_playlist(self, identity):
        return self.playlists.get(identity)

    def playlist_tracks(self, playlist):
        return list(playlist["tracks"])

    def track_id(self, row):
        return row["id"]

    def add(self, playlist, identifiers):
        for identity in identifiers:
            if identity == self.fail_on:
                raise RuntimeError("test interrupted album write")
            self.writes.append(identity)
            playlist["tracks"].append(self.resolved[identity])

    def favorite_tracks(self):
        return list(self.loves)

    def add_favorite_tracks(self, identifiers):
        self.writes.extend(identifiers)
        self.loves.extend(self.resolved[identity] for identity in identifiers)


@pytest.fixture
def native_protocols(monkeypatch):
    # Transport contracts are covered separately; this matrix verifies the
    # orchestration against the real provider roster and actual route selection.
    monkeypatch.setattr(NativeAlbums, "saved", lambda self: self.target.saved_albums())
    monkeypatch.setattr(NativeAlbums, "find", lambda self, row: self.target.find_albums(row))
    monkeypatch.setattr(NativeAlbums, "add", lambda self, row: self.target.add_saved_albums([row["id"]]))
    monkeypatch.setattr(NativeAlbums, "tracks", lambda self, row: self.target.album_tracks(row))
    monkeypatch.setattr(NativeAlbums, "validate", lambda self, **kwargs: None)


def seed_source(source, manifest):
    if native_available(source):
        source.library = [album()]
        return
    row = album()
    key = album_key(row)
    identifiers = [f"Artist␟{track['name']}" if source.source == "lastfm" else f"{source.source}-{track['name']}" for track in tracks()]
    copied = [{**track, "id": identity} for track, identity in zip(tracks(), identifiers)]
    record = {"album": row, "track_ids": identifiers, "tracks": tracks(), "complete": True}
    if source.supports_playlists:
        source.playlists["imported-album"] = {"id": "imported-album", "name": "Record", "tracks": copied}
        record["playlist_id"] = "imported-album"
    else:
        source.loves = copied
    manifest.put(source.source, key, record)


@pytest.mark.parametrize("source_id,target_id", [
    (source, target) for source in provider_ids() for target in provider_ids() if source != target
])
def test_all_provider_pairs_transfer_albums_without_repeat_writes(
    source_id, target_id, tmp_path, monkeypatch, native_protocols,
):
    monkeypatch.chdir(tmp_path)
    source, target = Peer(source_id, tmp_path), Peer(target_id, tmp_path)
    manifest_path = tmp_path / "saved_albums.json"
    seed_source(source, AlbumManifest(manifest_path))
    monkeypatch.setattr(albums, "build_one", lambda identity, *args, **kwargs:
                        source if identity == source_id else target)
    opts = parse_args([])
    opts.saved_album_file = str(manifest_path)
    opts.saved_albums, opts.sync_playlists, opts.execute = True, False, True
    opts.sync_source, opts.providers = source_id, f"{source_id},{target_id}"
    opts.download_dir, opts.max_removals = "", 0

    result = run_pass(opts)
    assert result["ok"] and result["per_target"][0]["added"] == 1
    assert target.writes and not source.writes
    writes = list(target.writes)
    assert run_pass(opts)["per_target"][0]["added"] == 0
    assert target.writes == writes
    assert target.creates <= 1


def test_interrupted_portable_album_reuses_playlist_and_resumes_missing_tracks(tmp_path, monkeypatch, native_protocols):
    monkeypatch.chdir(tmp_path)
    source, target = Peer("spotify", tmp_path), Peer("amazon", tmp_path)
    source.library = [album()]
    target.fail_on = "amazon-Two"
    manifest_path = tmp_path / "albums.json"
    monkeypatch.setattr(albums, "build_one", lambda identity, *args, **kwargs:
                        source if identity == "spotify" else target)
    opts = parse_args([])
    opts.saved_album_file = str(manifest_path)
    opts.saved_albums, opts.sync_playlists, opts.execute = True, False, True
    opts.sync_source, opts.providers, opts.download_dir, opts.max_removals = "spotify", "spotify,amazon", "", 0
    assert not run_pass(opts)["ok"]
    assert target.creates == 1 and target.writes == ["amazon-One"]
    assert AlbumLibrary(target, AlbumManifest(manifest_path)).saved() == []
    target.fail_on = None
    assert run_pass(opts)["ok"]
    assert target.creates == 1 and target.writes == ["amazon-One", "amazon-Two"]
    assert len(AlbumLibrary(target, AlbumManifest(manifest_path)).saved()) == 1


def test_missing_portable_track_does_not_create_partial_album(tmp_path, monkeypatch, native_protocols):
    source, target = Peer("spotify", tmp_path), Peer("amazon", tmp_path)
    source.library = [album()]
    target.resolve = lambda row, cache: (None, "search")
    library = AlbumLibrary(target, AlbumManifest(tmp_path / "state.json"))
    assert library.prepare_portable(album(), AlbumLibrary(source, library.manifest)) is None
    assert target.creates == 0 and not target.writes


def test_corrupt_portable_manifest_is_not_overwritten(tmp_path):
    path = tmp_path / "albums.json"
    path.write_text('{"version": 2}')
    with pytest.raises(RuntimeError, match="invalid"):
        AlbumManifest(path)
    assert path.read_text() == '{"version": 2}'
