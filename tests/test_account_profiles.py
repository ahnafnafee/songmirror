"""Account profile persistence, compatibility migration, and isolation."""

import json
import os
import threading
from pathlib import Path

import pytest

from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.playlists import LinkStore, PlaylistLink
from songmirror.services.settings import SettingsStore
from songmirror.services.syncs import SyncJob, SyncStore


def test_legacy_provider_settings_migrate_to_a_stable_default_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "before-test")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "before-test-secret")
    settings = SettingsStore(dir=tmp_path)
    settings.save({
        "SPOTIFY_CLIENT_ID": "legacy-client",
        "SPOTIFY_CLIENT_SECRET": "legacy-secret",
        "SYNC_INTERVAL": "30m",
    })

    profiles = AccountProfileStore(settings)
    default_id = profiles.default_id("spotify")

    assert profiles.canonical_id("spotify") == default_id
    assert profiles.resolve("spotify").id == default_id
    assert profiles.settings_for(default_id).get("SPOTIFY_CLIENT_SECRET") == "legacy-secret"
    assert settings.get("SPOTIFY_CLIENT_SECRET") == "legacy-secret"
    assert json.loads((tmp_path / "profiles.json").read_text(encoding="utf-8"))[0]["id"].startswith("profile_")
    assert "legacy-secret" not in (tmp_path / "profiles.json").read_text(encoding="utf-8")
    assert (tmp_path / "profiles" / default_id / "settings.json").exists()

    settings.save({"SPOTIFY_CLIENT_SECRET": "updated-by-legacy-cli"})
    assert profiles.settings_for("spotify").get("SPOTIFY_CLIENT_SECRET") == "updated-by-legacy-cli"

    # Re-opening the store is idempotent: deterministic compatibility profiles
    # are not duplicated and the old provider alias remains valid.
    reopened = AccountProfileStore(SettingsStore(dir=tmp_path))
    assert len(reopened.list()) == 8
    assert reopened.canonical_id("spotify") == default_id


def test_custom_profiles_have_disjoint_secrets_sessions_and_cache_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "legacy-secret")
    monkeypatch.setenv("SPOTIFY_TOKEN_CACHE", "legacy-token-cache")
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    alice = profiles.create("spotify", "Alice")
    bob = profiles.create("spotify", "Bob")
    profiles.settings_for(alice.id).save({"SPOTIFY_CLIENT_SECRET": "alice-secret"})
    profiles.settings_for(bob.id).save({"SPOTIFY_CLIENT_SECRET": "bob-secret"})

    alice_values = profiles.settings_for(alice.id).environment()
    bob_values = profiles.settings_for(bob.id).environment()
    assert alice_values["SPOTIFY_TOKEN_CACHE"] != bob_values["SPOTIFY_TOKEN_CACHE"]
    assert profiles.profile_dir(alice.id) in Path(profiles.settings_for(alice.id).env_path).parents
    assert profiles.profile_dir(bob.id) in Path(profiles.settings_for(bob.id).env_path).parents

    with profiles.activate(alice.id):
        assert os.environ["SPOTIFY_CLIENT_SECRET"] == "alice-secret"
        assert os.environ["SPOTIFY_TOKEN_CACHE"] == alice_values["SPOTIFY_TOKEN_CACHE"]
    with profiles.activate(bob.id):
        assert os.environ["SPOTIFY_CLIENT_SECRET"] == "bob-secret"
        assert os.environ["SPOTIFY_TOKEN_CACHE"] == bob_values["SPOTIFY_TOKEN_CACHE"]

    # The process environment is restored after every connector/target call;
    # metadata never contains either account's credentials.
    assert os.environ["SPOTIFY_CLIENT_SECRET"] == "legacy-secret"
    metadata = (tmp_path / "profiles.json").read_text(encoding="utf-8")
    assert "alice-secret" not in metadata and "bob-secret" not in metadata


def test_root_environment_projection_waits_for_active_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "before-test")
    settings = SettingsStore(dir=tmp_path)
    settings.save({"SPOTIFY_WRITE_BACKEND": "cookie"})
    profiles = AccountProfileStore(settings)
    custom = profiles.create("spotify", "OAuth account")
    profiles.settings_for(custom.id).save({"SPOTIFY_WRITE_BACKEND": "oauth"})

    active = threading.Event()
    release = threading.Event()
    projector_started = threading.Event()
    projected = threading.Event()
    observed = {}

    def use_profile():
        with profiles.activate(custom.id):
            observed["active"] = os.environ["SPOTIFY_WRITE_BACKEND"]
            active.set()
            release.wait(timeout=2)
            observed["during"] = os.environ["SPOTIFY_WRITE_BACKEND"]

    def project_root():
        active.wait(timeout=2)
        projector_started.set()
        settings.apply_to_env()
        observed["after"] = os.environ["SPOTIFY_WRITE_BACKEND"]
        projected.set()

    profile_thread = threading.Thread(target=use_profile)
    projection_thread = threading.Thread(target=project_root)
    profile_thread.start()
    projection_thread.start()
    assert active.wait(timeout=2)
    assert projector_started.wait(timeout=2)
    assert not projected.wait(timeout=0.1)
    assert os.environ["SPOTIFY_WRITE_BACKEND"] == "oauth"
    release.set()
    profile_thread.join(timeout=2)
    projection_thread.join(timeout=2)

    assert not profile_thread.is_alive() and not projection_thread.is_alive()
    assert observed == {"active": "oauth", "during": "oauth", "after": "cookie"}


def test_default_profile_reads_fallback_only_after_custom_profile_releases(
    tmp_path, monkeypatch
):
    from songmirror.services.account_profiles import ProfileSettings

    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "root-secret")
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    custom = profiles.create("spotify", "Custom")
    profiles.settings_for(custom.id).save({"SPOTIFY_CLIENT_SECRET": "custom-secret"})
    custom_active = threading.Event()
    release_custom = threading.Event()
    default_environment_started = threading.Event()
    default_finished = threading.Event()
    observed = {}
    original_environment = ProfileSettings.environment

    def tracked_environment(profile_settings):
        if profile_settings.profile.is_default:
            default_environment_started.set()
        return original_environment(profile_settings)

    monkeypatch.setattr(ProfileSettings, "environment", tracked_environment)

    def use_custom():
        with profiles.activate(custom.id):
            custom_active.set()
            release_custom.wait(timeout=2)

    def use_default():
        custom_active.wait(timeout=2)
        with profiles.activate("spotify"):
            observed["secret"] = os.environ.get("SPOTIFY_CLIENT_SECRET")
        default_finished.set()

    custom_thread = threading.Thread(target=use_custom)
    default_thread = threading.Thread(target=use_default)
    custom_thread.start()
    default_thread.start()
    assert custom_active.wait(timeout=2)
    # Environment resolution itself is part of the critical section, not only
    # the later clear/apply/restore sequence.
    assert not default_environment_started.wait(timeout=0.1)
    assert not default_finished.is_set()
    release_custom.set()
    custom_thread.join(timeout=2)
    default_thread.join(timeout=2)

    assert not custom_thread.is_alive() and not default_thread.is_alive()
    assert default_environment_started.is_set() and default_finished.is_set()
    assert observed == {"secret": "root-secret"}


def test_default_profile_direct_get_cannot_read_an_active_custom_profile(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SPOTIFY_TRACKS_CACHE", "root-tracks.json")
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    custom = profiles.create("spotify", "Custom")
    profiles.settings_for(custom.id).save({
        "SPOTIFY_TRACKS_CACHE": "custom-tracks.json"
    })
    custom_active = threading.Event()
    release_custom = threading.Event()
    reader_started = threading.Event()
    reader_finished = threading.Event()
    observed = {}

    def use_custom():
        with profiles.activate(custom.id):
            custom_active.set()
            release_custom.wait(timeout=2)

    def read_default():
        custom_active.wait(timeout=2)
        reader_started.set()
        observed["path"] = profiles.settings_for("spotify").get(
            "SPOTIFY_TRACKS_CACHE"
        )
        reader_finished.set()

    custom_thread = threading.Thread(target=use_custom)
    reader_thread = threading.Thread(target=read_default)
    custom_thread.start()
    reader_thread.start()
    assert custom_active.wait(timeout=2)
    assert reader_started.wait(timeout=2)
    assert not reader_finished.wait(timeout=0.1)
    release_custom.set()
    custom_thread.join(timeout=2)
    reader_thread.join(timeout=2)

    assert not custom_thread.is_alive() and not reader_thread.is_alive()
    assert observed == {"path": "root-tracks.json"}


def test_malformed_metadata_row_does_not_erase_valid_custom_profile(tmp_path):
    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    custom = profiles.create("apple", "Family")
    rows = json.loads((tmp_path / "profiles.json").read_text(encoding="utf-8"))
    rows.insert(1, {"id": 42, "provider": "spotify", "unexpected": True})
    (tmp_path / "profiles.json").write_text(json.dumps(rows), encoding="utf-8")

    reopened = AccountProfileStore(SettingsStore(dir=tmp_path))

    assert reopened.get(custom.id) == custom
    persisted = json.loads((tmp_path / "profiles.json").read_text(encoding="utf-8"))
    assert all(row.get("id") != 42 for row in persisted)


def test_archive_migration_preserves_all_profile_keyed_state_and_is_idempotent(
    tmp_path,
):
    from songmirror.engine import archive

    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    aliases = profiles.archive_aliases()
    db_path = tmp_path / "song_cache.db"
    conn = archive.connect(str(db_path))
    old_group = "group:apple,spotify:mix"
    now = "2025-01-01T00:00:00+00:00"
    conn.executemany(
        "INSERT INTO songs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("spotify", "collision", "OLD", "legacy row", "artist", None, 1, '{"id":"collision","name":"legacy row"}', now, now),
            (aliases["spotify"], "collision", "NEW", "profile row", "artist", None, 2, '{"id":"collision","name":"profile row"}', now, now),
            ("spotify", "legacy-only", "KEEP", "legacy only", "artist", None, 3, '{"id":"legacy-only","name":"legacy only"}', now, now),
        ],
    )
    conn.execute("INSERT INTO links VALUES (?, ?, ?, ?)", ("sp-id", "apple", "apple-id", now))
    conn.execute("INSERT INTO sync_state VALUES (?, ?, ?, ?, ?)", ("mix", "tidal", "snap", 4, now))
    conn.execute("INSERT INTO playlist_state VALUES (?, ?, ?)", (old_group, "spotify", "i:STATE"))
    conn.execute(
        "INSERT INTO playlist_state_meta VALUES (?, ?, ?, ?)",
        (old_group, "apple", now, "apple-playlist"),
    )
    conn.execute(
        "INSERT INTO playlist_pending_removal VALUES (?, ?, ?, ?)",
        (old_group, "tidal", "i:PENDING", now),
    )
    conn.execute(
        "INSERT INTO track_identity VALUES (?, ?, ?, ?)",
        ("qobuz", "qobuz-id", "i:IDENTITY", now),
    )
    conn.execute(
        "INSERT INTO track_identity_history VALUES (?, ?, ?, ?)",
        ("deezer", "deezer-id", "i:HISTORY", now),
    )
    conn.execute(
        "INSERT INTO playlist_order VALUES (?, ?, ?, ?)",
        (old_group, "amazon", now, '[["amazon-id", "Song", "Artist"]]'),
    )

    def detail(provider, playlist_id, name, track_ids):
        return {
            "provider": provider,
            "id": playlist_id,
            "name": name,
            "description": "",
            "image": "",
            "owned": True,
            "editable": True,
            "external_url": "",
            "tracks": [
                {
                    "position": position,
                    "id": track_id,
                    "name": track_id,
                    "artist": "Artist",
                }
                for position, track_id in enumerate(track_ids)
            ],
        }

    archive.set_playlist_detail_cache(
        conn, detail("ytmusic", "legacy-cache", "Legacy cache", ["yt-1"])
    )
    archive.set_playlist_detail_cache(
        conn, detail("spotify", "collision-cache", "Legacy cache", ["old-1", "old-2"])
    )
    archive.set_playlist_detail_cache(
        conn,
        detail(
            aliases["spotify"], "collision-cache", "Profile cache", ["new-1"]
        ),
    )
    conn.close()

    conn = archive.connect(str(db_path), source_aliases=aliases)
    new_group = (
        f"group:{aliases['apple']},{aliases['spotify']}:mix"
    )
    assert archive.get_snapshots(conn, aliases["spotify"], ["legacy-only"])["legacy-only"]["name"] == "legacy only"
    collision = conn.execute(
        "SELECT name, isrc FROM songs WHERE source = ? AND id = 'collision'",
        (aliases["spotify"],),
    ).fetchone()
    assert collision == ("profile row", "NEW")
    assert archive.get_links(conn, aliases["apple"], ["sp-id"]) == {"sp-id": "apple-id"}
    assert archive.get_state(conn, "mix", aliases["tidal"]) == ("snap", 4)
    assert archive.get_playlist_state(conn, new_group, aliases["spotify"]) == {"i:STATE"}
    assert archive.get_playlist_physical_id(conn, new_group, aliases["apple"]) == "apple-playlist"
    assert archive.get_pending_removals(conn, new_group, aliases["tidal"]) == {"i:PENDING"}
    assert archive.get_identities(conn, aliases["qobuz"], ["qobuz-id"]) == {"qobuz-id": "i:IDENTITY"}
    assert archive.get_identity_history(conn, aliases["deezer"], ["deezer-id"]) == {"deezer-id": {"i:HISTORY"}}
    assert archive.get_order_history(conn, new_group, aliases["amazon"])[0][1][0][0] == "amazon-id"
    migrated_cache = archive.get_playlist_detail_cache(
        conn, aliases["ytmusic"], "legacy-cache"
    )
    assert migrated_cache["name"] == "Legacy cache"
    assert [track["id"] for track in migrated_cache["tracks"]] == ["yt-1"]
    collision_cache = archive.get_playlist_detail_cache(
        conn, aliases["spotify"], "collision-cache"
    )
    assert collision_cache["name"] == "Profile cache"
    assert [track["id"] for track in collision_cache["tracks"]] == ["new-1"]

    keyed_columns = [
        *(archive._PROFILE_ID_COLUMNS),
        ("playlist_cache", "provider"),
        ("playlist_track_cache", "provider"),
    ]
    legacy_ids = tuple(aliases)
    marks = ",".join("?" for _ in legacy_ids)
    for table, column in keyed_columns:
        assert conn.execute(
            f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IN ({marks})',
            legacy_ids,
        ).fetchone()[0] == 0
    counts = {
        table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in {table for table, _column in keyed_columns}
    }
    conn.close()

    # Running the migration again changes nothing, while a later legacy CLI
    # write is picked up by the next profile-aware open.
    conn = archive.connect(str(db_path), source_aliases=aliases)
    assert counts == {
        table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in counts
    }
    conn.close()
    legacy = archive.connect(str(db_path))
    archive.upsert_many(legacy, "tidal", [{"id": "late-cli", "name": "Late CLI"}])
    legacy.close()
    conn = archive.connect(str(db_path), source_aliases=aliases)
    assert archive.get_snapshots(conn, aliases["tidal"], ["late-cli"])["late-cli"]["name"] == "Late CLI"
    assert conn.execute(
        "SELECT 1 FROM songs WHERE source = 'tidal' AND id = 'late-cli'"
    ).fetchone() is None
    conn.close()


def test_bound_spotify_and_tidal_targets_read_the_profile_archive_namespace(
    tmp_path, monkeypatch
):
    from songmirror.engine import archive, spotify_cookie
    from songmirror.engine.targets import AccountBoundTarget
    from songmirror.engine.targets.spotify_target import SpotifyTarget
    from songmirror.engine.targets.tidal import TidalTarget

    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    spotify_profile = profiles.create("spotify", "Spotify profile")
    tidal_profile = profiles.create("tidal", "TIDAL profile")
    profiles.settings_for(spotify_profile.id).save({
        "SPOTIFY_WRITE_BACKEND": "cookie"
    })
    songs = archive.connect(":memory:")
    archive.upsert_many(songs, spotify_profile.id, [{
        "id": "spotify-track", "isrc": "US-S1Z-25-00001", "name": "Spotify song"
    }])
    archive.upsert_many(songs, tidal_profile.id, [{
        "id": "tidal-track", "isrc": "US-T1D-25-00001", "name": "TIDAL song"
    }])

    spotify_target = SpotifyTarget(None, "spotify-cache.json", sync_peer=True, songs=songs)
    bound_spotify = AccountBoundTarget(spotify_target, spotify_profile, profiles)
    known = {}

    def spotify_tracks(_playlist_id, *, require_isrc, known_isrc):
        assert require_isrc is False
        known.update(known_isrc(["spotify-track"]))
        return []

    monkeypatch.setattr(spotify_cookie, "playlist_tracks", spotify_tracks)
    assert bound_spotify.playlist_tracks({"id": "spotify-playlist"}) == []
    assert known == {"spotify-track": "US-S1Z-25-00001"}

    tidal_target = object.__new__(TidalTarget)
    tidal_target.cache_file = "tidal-cache.json"
    tidal_target._songs = songs
    AccountBoundTarget(tidal_target, tidal_profile, profiles)
    archived = tidal_target._archived_details(["tidal-track"])
    assert archived["tidal-track"]["name"] == "TIDAL song"
    songs.close()


def test_reverse_links_recover_isrc_from_any_spotify_profile_namespace(tmp_path):
    from songmirror.engine import archive
    from songmirror.engine.targets import AccountBoundTarget
    from songmirror.engine.targets.base import _entry_cids

    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    spotify_custom = profiles.create("spotify", "Custom Spotify")
    apple = profiles.create("apple", "Apple")
    songs = archive.connect(":memory:")
    archive.upsert_many(songs, spotify_custom.id, [{
        "id": "spotify-global-id",
        "isrc": "US-REV-25-00001",
        "name": "Recovered song",
    }])
    archive.set_links(songs, apple.id, {"spotify-global-id": "apple-track"})

    class AppleTarget:
        source = "apple"
        name = "Apple Music"
        cache_file = "apple-cache.json"

        @staticmethod
        def track_id(track):
            return track["id"]

        @staticmethod
        def native_isrc_map(_cache):
            return {}

    target = AccountBoundTarget(AppleTarget(), apple, profiles)
    entries = _entry_cids(
        target,
        [{"id": "apple-track", "name": "Recovered song", "artist": "Artist"}],
        songs,
        {},
        {},
    )

    assert entries[0][0] == "i:USREV2500001"
    songs.close()


def test_target_factory_binds_identity_cache_and_runtime_to_selected_profile(
    tmp_path, monkeypatch
):
    from songmirror.engine.config import parse_args
    from songmirror.engine import targets

    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    alice = profiles.create("apple", "Alice")
    bob = profiles.create("apple", "Bob")
    for profile, token in ((alice, "alice-token"), (bob, "bob-token")):
        profiles.settings_for(profile.id).save({
            "APPLE_BEARER_TOKEN": "shared-app-token",
            "APPLE_USER_TOKEN": token,
        })

    class FakeAppleTarget:
        source = "apple"
        name = "Apple Music"

        def __init__(self, cache_file):
            self.cache_file = cache_file

        @staticmethod
        def current_user_token():
            return os.getenv("APPLE_USER_TOKEN")

    monkeypatch.setitem(
        targets._REGISTRY,
        "apple",
        lambda opts, _sp, **_kwargs: FakeAppleTarget(opts.cache_file),
    )
    opts = parse_args([])
    opts.account_profiles = profiles

    alice_target = targets.build_one(alice.id, opts)
    bob_target = targets.build_one(bob.id, opts)

    assert alice_target.source == alice.id
    assert bob_target.source == bob.id
    assert alice_target.provider == bob_target.provider == "apple"
    assert alice_target.cache_file != bob_target.cache_file
    assert Path(alice_target.cache_file).parent == profiles.profile_dir(alice.id)
    assert Path(bob_target.cache_file).parent == profiles.profile_dir(bob.id)
    assert alice_target.current_user_token() == "alice-token"
    assert bob_target.current_user_token() == "bob-token"


def test_removing_a_custom_profile_deletes_only_its_private_directory(tmp_path):
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))
    custom = profiles.create("apple", "Family")
    profiles.settings_for(custom.id).save({"APPLE_USER_TOKEN": "private-token"})
    custom_dir = profiles.profile_dir(custom.id)

    profiles.remove(custom.id)

    assert profiles.get(custom.id) is None
    assert not custom_dir.exists()
    assert profiles.resolve("apple").is_default is True
    with pytest.raises(ValueError, match="cannot be removed"):
        profiles.remove("apple")


def test_sync_jobs_and_playlist_links_migrate_provider_ids_to_profiles(tmp_path):
    legacy_syncs = SyncStore(dir=tmp_path)
    job = legacy_syncs.upsert(SyncJob(
        name="Legacy household sync",
        source="spotify",
        providers="spotify,apple",
        liked_tracks=True,
        liked_routes={"apple": {"kind": "native"}},
    ))
    legacy_links = LinkStore(dir=tmp_path)
    link = legacy_links.upsert(PlaylistLink(
        name="Shared",
        source="spotify",
        members={"spotify": "source-list", "apple": "dest-list"},
    ))
    profiles = AccountProfileStore(SettingsStore(dir=tmp_path))

    migrated_job = SyncStore(dir=tmp_path, profiles=profiles).get(job.id)
    migrated_link = next(
        item for item in LinkStore(dir=tmp_path, profiles=profiles).list()
        if item.id == link.id
    )

    spotify = profiles.default_id("spotify")
    apple = profiles.default_id("apple")
    assert migrated_job.source == spotify
    assert migrated_job.providers == f"{spotify},{apple}"
    assert migrated_job.liked_routes == {apple: {"kind": "native"}}
    assert migrated_link.source == spotify
    assert migrated_link.members == {spotify: "source-list", apple: "dest-list"}

    persisted_sync = (tmp_path / "syncs.json").read_text(encoding="utf-8")
    persisted_links = (tmp_path / "links.json").read_text(encoding="utf-8")
    assert '"source": "spotify"' not in persisted_sync
    assert '"source": "spotify"' not in persisted_links
