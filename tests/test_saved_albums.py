"""Saved albums are native library objects, never playlists or liked tracks."""

from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from songmirror.engine import albums, spotify_cookie
from songmirror.engine.albums import compatible_albums
from songmirror.engine.config import parse_args
from songmirror.engine.runner import run_pass
from songmirror.engine.targets.base import TargetAuthError
from songmirror.engine.targets.spotify_target import SpotifyTarget
from songmirror.engine.targets.tidal import TidalTarget
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.events import EventBus
from songmirror.services.settings import SettingsStore
from songmirror.services.sync_service import SyncService
from songmirror.services.syncs import SyncJob, SyncStore, validate_sync_job
from songmirror.web import create_app


def album(identity="a", **changes):
    return {"id": identity, "name": "Record", "artists": ["Artist"], "upc": "0123456789012",
            "release_date": "2024-01-01", "total_tracks": 10, **changes}


def job(**changes):
    return SyncJob(name="Albums", providers="spotify,tidal", source="spotify", saved_albums=True,
                   sync_playlists=False, max_removals=0, **changes)


@pytest.mark.parametrize("changes", [
    {"name": "Record (Deluxe)"}, {"artists": ["Other artist"]}, {"total_tracks": 12},
    {"release_date": "2025-01-01"}, {"upc": "9999999999999"},
])
def test_album_metadata_matching_preserves_editions(changes):
    source = album(upc=None) if "upc" not in changes else album()
    assert compatible_albums(source, [album("b", **changes)]) == []


def test_upc_ean_identity_and_ambiguous_metadata():
    assert compatible_albums(album(), [album("b", upc="123456789012")])[0]["id"] == "b"
    assert compatible_albums(album(upc=None, total_tracks=None), [album("b")]) == []
    assert len(compatible_albums(album(upc=None), [album("b"), album("c")])) == 2


@pytest.mark.parametrize("change", [
    {"mode": "nway"}, {"sync_playlists": True}, {"liked_tracks": True}, {"download": True},
    {"max_removals": 1}, {"providers": "spotify,unknown"}, {"providers": "tidal"},
])
def test_invalid_album_jobs_are_rejected(change):
    with pytest.raises(ValueError):
        validate_sync_job(replace(job(), **change))


def test_album_job_roundtrip_and_scheduler_options(tmp_path):
    settings = SettingsStore(dir=tmp_path)
    store = SyncStore(dir=tmp_path)
    saved = store.upsert(job())
    opts = SyncService(settings, EventBus(), store)._opts_for(store.get(saved.id), execute=False)
    assert opts.saved_albums and not opts.sync_playlists and not opts.liked_tracks
    assert opts.providers == "spotify,tidal"
    assert not opts.download_dir and opts.max_removals == 0
    assert not SyncJob().saved_albums  # legacy jobs retain playlist behavior


def test_album_job_supports_custom_account_profiles(tmp_path):
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    other = profiles.create("tidal", "Second TIDAL")
    saved = replace(job(), providers=f"spotify,{other.id}")
    assert validate_sync_job(saved, profiles).providers.endswith(other.id)


class Peer:
    def __init__(self, provider, library=(), candidates=()):
        self.source = self.tag = provider
        self.name = provider.title()
        self.library = list(library)
        self.candidates = list(candidates)
        self.writes = []
        self.searches = []
        self.fail_read = False
        self.fail_write = False

    def validate_saved_albums(self, *, write=False):
        pass

    def saved_albums(self):
        if self.fail_read:
            raise RuntimeError("incomplete library")
        return list(self.library)

    def find_albums(self, source):
        self.searches.append(source["id"])
        return self.candidates

    def add_saved_albums(self, identifiers):
        if self.fail_write:
            raise RuntimeError("write rejected")
        self.writes.extend(identifiers)
        self.library.extend(candidate for candidate in self.candidates if candidate["id"] in identifiers)


@pytest.fixture
def peers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    source = Peer("spotify", [album()])
    target = Peer("tidal", candidates=[album("b")])
    monkeypatch.setattr(albums, "build_one", lambda identity, *args, **kwargs:
                        source if identity == "spotify" else target)
    opts = parse_args([])
    opts.saved_albums, opts.sync_playlists = True, False
    opts.providers, opts.sync_source = "spotify,tidal", "spotify"
    opts.download_dir, opts.max_removals = "", 0
    return source, target, opts


def test_preview_execute_and_repeat_run_do_not_duplicate_saved_albums(peers):
    source, target, opts = peers
    preview = run_pass(opts)
    assert preview["ok"] and preview["per_target"][0]["added"] == 1
    assert not target.writes and not source.writes
    opts.execute = True
    assert run_pass(opts)["per_target"][0]["added"] == 1
    assert target.writes == ["b"]
    repeated = run_pass(opts)["per_target"][0]
    assert repeated["added"] == 0 and repeated["skipped"] == 1
    assert target.writes == ["b"] and not source.writes


def test_addition_cap_and_ambiguous_albums(peers):
    source, target, opts = peers
    source.library.append(album("a2", name="Another", upc="9999999999999"))
    target.candidates.append(album("b2", name="Another", upc="9999999999999"))
    opts.max_adds, opts.execute = 1, True
    row = run_pass(opts)["per_target"][0]
    assert row["added"] == 1 and row["deferred"] == 1
    assert len(target.writes) == 1
    assert target.searches == ["a"]  # no catalog work beyond this pass's cap
    target.writes.clear()
    target.library.clear()
    source.library = [album(upc=None)]
    target.candidates = [album("b"), album("c")]
    row = run_pass(opts)["per_target"][0]
    assert row["uncertain_matches"] == 1 and row["missing"] == 1 and not target.writes


@pytest.mark.parametrize("side", ["source", "destination"])
def test_read_failures_prevent_writes(peers, side):
    source, target, opts = peers
    (source if side == "source" else target).fail_read = True
    opts.execute = True
    with pytest.raises(RuntimeError, match="incomplete"):
        run_pass(opts)
    assert not source.writes and not target.writes


def test_stop_and_mutation_failure_keep_honest_counts(peers):
    _, target, opts = peers
    opts.execute = True
    stopped = run_pass(opts, should_continue=lambda: "stop")
    assert stopped["interrupted"] == "stop" and not target.writes
    target.fail_write = True
    failed = run_pass(opts)
    assert not failed["ok"] and failed["per_target"][0]["added"] == 0
    assert failed["per_target"][0]["failed"] == 1


def test_catalog_failure_prevents_all_album_writes(peers):
    source, target, opts = peers
    opts.execute = True
    def unavailable(_album):
        raise RuntimeError("catalog temporarily unavailable")
    target.find_albums = unavailable
    with pytest.raises(RuntimeError, match="catalog temporarily unavailable"):
        run_pass(opts)
    assert not source.writes and not target.writes


def test_tidal_to_spotify_direction(peers, monkeypatch):
    source, target, opts = peers
    source.source = source.tag = "tidal"
    target.source = target.tag = "spotify"
    opts.sync_source, opts.providers, opts.execute = "tidal", "tidal,spotify", True
    monkeypatch.setattr(albums, "build_one", lambda identity, *args, **kwargs:
                        source if identity == "tidal" else target)
    assert run_pass(opts)["per_target"][0]["added"] == 1
    assert target.writes == ["b"] and not source.writes


def spotify_album(identity="spotify1"):
    return {"id": identity, "name": "Record", "artists": [{"name": "Artist"}],
            "release_date": "2024-01-01", "total_tracks": 10,
            "external_ids": {"upc": "0123456789012"}}


def test_spotify_oauth_album_pagination_search_and_save(monkeypatch):
    calls = []
    def read(*, limit, offset):
        calls.append(("read", offset))
        return {"items": [{"album": spotify_album(str(offset))}], "total": 2}
    api = SimpleNamespace(current_user_saved_albums=read,
                          current_user_saved_albums_add=lambda ids: calls.append(("save", ids)),
                          search=lambda **kw: {"albums": {"items": [spotify_album("found")]}},
                          album=lambda identity: spotify_album(identity))
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "oauth")
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.polite_sleep", lambda _: None)
    target = SpotifyTarget(api, "unused")
    assert [row["id"] for row in target.saved_albums()] == ["0", "1"]
    assert target.find_albums(album())[0]["upc"] == "0123456789012"
    target.add_saved_albums(["new"])
    assert calls == [("read", 0), ("read", 1), ("save", ["new"])]
    api.current_user_saved_albums = lambda **kw: {"items": [], "total": 10}
    with pytest.raises(RuntimeError, match="pagination"):
        target.saved_albums()


def test_spotify_cookie_album_library_and_native_save(monkeypatch):
    calls = []
    def pf(operation, variables):
        calls.append((operation, variables))
        if operation != "libraryV3":
            return {}
        assert variables["filters"] == ["Albums"]
        return {"me": {"libraryV3": {"totalCount": 2, "items": [{"item": {"data": {
            "__typename": "Album", "uri": f"spotify:album:{variables['offset']}",
        }}}]}}}
    monkeypatch.setattr(spotify_cookie, "_pf", pf)
    monkeypatch.setattr(spotify_cookie, "_web_album", lambda identity: spotify_album(identity))
    monkeypatch.setattr(spotify_cookie, "polite_sleep", lambda _: None)
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    target = SpotifyTarget(None, "unused")
    assert [row["id"] for row in target.saved_albums()] == ["0", "1"]
    target.add_saved_albums(["new"])
    assert calls[-1] == ("addToLibrary", {"libraryItemUris": ["spotify:album:new"]})
    monkeypatch.setattr(spotify_cookie, "_pf", lambda *args: {"me": {"libraryV3": {
        "items": [], "totalCount": 10,
    }}})
    with pytest.raises(RuntimeError, match="pagination"):
        target.saved_albums()


def tidal_album_body(identity="tidal1"):
    return {"data": [{"type": "albums", "id": identity}], "included": [{
        "type": "albums", "id": identity, "attributes": {
            "title": "Record", "barcodeId": "123456789012", "releaseDate": "2024-01-01", "numberOfItems": 10,
        }, "relationships": {"artists": {"data": [{"type": "artists", "id": "artist"}]}},
    }, {"type": "artists", "id": "artist", "attributes": {"name": "Artist"}}]}


def test_tidal_saved_album_relationship_and_barcode_search(monkeypatch):
    target = TidalTarget.__new__(TidalTarget)
    target.country, target._token_scopes = "US", {"r_usr", "w_usr"}
    calls = []
    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        body = {"data": kwargs["json_body"]["data"]} if method == "POST" else tidal_album_body()
        return SimpleNamespace(json=lambda: body)
    target._request = request
    target._pages = lambda path, params: iter([tidal_album_body("first"), tidal_album_body("last")])
    monkeypatch.setattr("songmirror.engine.targets.tidal.polite_sleep", lambda _: None)
    assert [row["id"] for row in target.saved_albums()] == ["first", "last"]
    assert target.find_albums(album())[0]["upc"] == "123456789012"
    assert calls[-1][2]["params"]["filter[barcodeId]"] == "0123456789012"
    target.add_saved_albums(["found"])
    assert calls[-1] == ("POST", "userCollectionAlbums/me/relationships/items",
                         {"json_body": {"data": [{"type": "albums", "id": "found"}]}})
    target._token_scopes = {"r_usr"}
    with pytest.raises(TargetAuthError, match="Saved Albums"):
        target.add_saved_albums(["other"])


def test_tidal_unconfirmed_album_write_is_not_reported_successful():
    target = TidalTarget.__new__(TidalTarget)
    target._token_scopes = {"r_usr", "w_usr"}
    target._request = lambda *args, **kwargs: SimpleNamespace(json=lambda: {
        "data": [], "meta": {"skipped": [{"id": "missing", "type": "albums", "reason": "notFound"}]},
    })
    with pytest.raises(RuntimeError, match="did not confirm"):
        target.add_saved_albums(["missing"])


def test_album_api_create_update_and_legacy_defaults(tmp_path):
    settings = SettingsStore(dir=tmp_path)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        response = client.post("/api/syncs", json={"name": "Albums", "source": "spotify",
            "providers": "spotify,tidal", "saved_albums": True, "sync_playlists": False, "max_removals": 0})
        assert response.status_code == 200, response.text
        identity = response.json()["id"]
        assert client.get("/api/syncs").json()[0]["saved_albums"]
        assert client.put(f"/api/syncs/{identity}", json={"interval": "1h"}).json()["saved_albums"]
        assert client.put(f"/api/syncs/{identity}", json={"mode": "nway"}).status_code == 422
        assert client.post("/api/syncs", json={"name": "Legacy"}).json()["saved_albums"] is False


def test_custom_album_accounts_keep_reads_and_writes_in_their_own_runtime(tmp_path, monkeypatch):
    import os
    from songmirror.engine.targets import _REGISTRY

    monkeypatch.chdir(tmp_path)
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path / "data"))
    destination = profiles.create("tidal", "Second account")
    profiles.settings_for("tidal").save({"TIDAL_TOKEN_FILE": str(tmp_path / "source-token")})
    profiles.settings_for(destination.id).save({"TIDAL_TOKEN_FILE": str(tmp_path / "destination-token")})
    writes = []

    class ScopedPeer(Peer):
        cache_file = "unused"

        def __init__(self):
            super().__init__("tidal")
            self.expected = os.environ["TIDAL_TOKEN_FILE"]

        def saved_albums(self):
            assert os.environ["TIDAL_TOKEN_FILE"] == self.expected
            return [album("native")] if self.expected.endswith("source-token") else []

        def add_saved_albums(self, identifiers):
            assert os.environ["TIDAL_TOKEN_FILE"] == self.expected
            writes.append((self.expected, identifiers))

        def find_albums(self, source):
            raise AssertionError("same-provider copies use the album id directly")

    monkeypatch.setitem(_REGISTRY, "tidal", lambda *args, **kwargs: ScopedPeer())
    opts = parse_args([])
    opts.account_profiles = profiles
    opts.saved_albums, opts.sync_playlists, opts.execute = True, False, True
    opts.sync_source, opts.providers = "tidal", f"tidal,{destination.id}"
    opts.download_dir, opts.max_removals = "", 0

    assert run_pass(opts)["ok"]
    assert writes == [(str(tmp_path / "destination-token"), ["native"])]
