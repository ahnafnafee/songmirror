"""Sync against Spotify's real playlist target with provider requests stubbed."""

from unittest.mock import Mock

import pytest

from songmirror.engine import archive, runner, spotify, spotify_cookie
from songmirror.engine.config import parse_args
from songmirror.engine.matching import track_key
from songmirror.engine.runner import load_cache, save_cache
from songmirror.engine.targets import base
from songmirror.engine.targets.spotify_target import SpotifyTarget
from songmirror.engine.targets.tidal import TidalTarget


def test_tidal_and_spotify_adapters_sync_same_name_playlist_in_both_directions(tmp_path, monkeypatch):
    recordings = {
        "1": ("Morning Light", "USAAA2600001", "0123456789abcdefghijkl"),
        "2": ("Midnight Drive", "USAAA2600002", "0123456789abcdefghijkm"),
        "3": ("Ocean Breeze", "USAAA2600003", "0123456789abcdefghijkn"),
    }
    spotify_members, tidal_members = ["1"], ["1"]
    spotify_writes, tidal_writes = [], []
    spotify_playlist = {"id": "spotify-mix", "name": "Mix", "_editable": True}
    tidal_playlist = {"id": "tidal-mix", "attributes": {"name": "Mix"}}

    def spotify_tracks(_playlist_id, **_kwargs):
        return [
            {"id": recordings[key][2], "name": recordings[key][0], "artists": ["Artist"],
             "isrc": recordings[key][1], "duration_ms": 180_000, "added_at": f"2026-11-0{key}T00:00:00Z"}
            for key in spotify_members
        ]

    def spotify_search(query, **_kwargs):
        return [
            {"id": track_id, "name": title, "artists": [{"name": "Artist"}], "duration_ms": 180_000}
            for title, isrc, track_id in recordings.values() if query == f"isrc:{isrc}"
        ]

    def spotify_add(playlist_id, track_ids):
        assert playlist_id == spotify_playlist["id"]
        spotify_writes.extend(track_ids)
        spotify_members.extend(key for key, row in recordings.items() if row[2] in track_ids)

    def tidal_track(key):
        return {"type": "tracks", "id": key,
                "attributes": {"title": recordings[key][0], "isrc": recordings[key][1], "duration": "PT3M"},
                "relationships": {"artists": {"data": [{"type": "artists", "id": "artist"}]}}}

    def tidal_pages(path, params, **_kwargs):
        artist = {"type": "artists", "id": "artist", "attributes": {"name": "Artist"}}
        if path == "playlists":
            yield {"data": [tidal_playlist]}
        elif path == "tracks":
            isrcs = params["filter[isrc]"].split(",")
            yield {"data": [tidal_track(key) for key, row in recordings.items() if row[1] in isrcs],
                   "included": [artist]}
        else:
            assert path == "playlists/tidal-mix/relationships/items"
            yield {"data": [{"type": "tracks", "id": key, "meta": {
                "itemId": f"entry-{key}", "addedAt": f"2026-11-0{key}T00:00:00Z",
            }} for key in tidal_members], "included": [artist, *(tidal_track(key) for key in tidal_members)]}

    def tidal_request(method, path, *, json_body):
        assert method == "POST" and path == "playlists/tidal-mix/relationships/items"
        keys = [item["id"] for item in json_body["data"]]
        tidal_writes.extend(keys)
        tidal_members.extend(keys)

    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    monkeypatch.setattr(runner, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(spotify_cookie, "configured", lambda: True)
    monkeypatch.setattr(spotify_cookie, "library_directory", lambda: spotify_cookie.LibraryDirectory([spotify_playlist], False))
    monkeypatch.setattr(spotify_cookie, "playlist_tracks", spotify_tracks)
    monkeypatch.setattr(spotify_cookie, "search_tracks", spotify_search)
    monkeypatch.setattr(spotify_cookie, "add", spotify_add)
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.polite_sleep", lambda *_: None)
    monkeypatch.setattr("songmirror.engine.targets.tidal.polite_sleep", lambda *_: None)

    spotify_target = SpotifyTarget(None, str(tmp_path / "spotify.json"), sync_peer=True)
    tidal_target = TidalTarget.__new__(TidalTarget)
    tidal_target.country = "US"
    tidal_target.cache_file = str(tmp_path / "tidal.json")
    tidal_target._pages = tidal_pages
    tidal_target._request = tidal_request
    monkeypatch.setattr(runner, "build_one", lambda *args, **kwargs: spotify_target)
    monkeypatch.setattr(runner, "build_peers", lambda *args, **kwargs: [spotify_target, tidal_target])
    opts = parse_args(["--execute", "--sync-mode", "nway", "--providers", "spotify,tidal", "--playlists", "Mix"])
    opts.song_cache_file = str(tmp_path / "songs.db")
    opts.download_dir = ""

    assert runner.run_pass(opts)["per_target"][0]["added"] == 0
    tidal_members.append("2")
    assert runner.run_pass(opts)["per_target"][0]["added"] == 1
    spotify_members.append("3")
    assert runner.run_pass(opts)["per_target"][0]["added"] == 1
    assert runner.run_pass(opts)["per_target"][0]["added"] == 0
    assert spotify_writes == [recordings["2"][2]]
    assert tidal_writes == ["3"]


@pytest.mark.parametrize("execute", [False, True], ids=["preview", "execute"])
@pytest.mark.parametrize("outcome", ["remove", "uncertain", "capped", "matched"])
def test_spotify_target_sync_accepts_plural_artists(tmp_path, monkeypatch, execute, outcome):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "api")
    uncertain = outcome == "uncertain"
    existing_name = "Sound of Silence Original" if uncertain else "Old Song"
    artists = ["Disturbed"] if uncertain else ["First Artist", "Second Artist"]
    items = [{
        "added_at": "2026-09-01T00:00:00Z",
        "track": {
            "id": "spotify-existing",
            "name": existing_name,
            "artists": [{"name": artist} for artist in artists],
            "duration_ms": 200_000,
        },
    }]
    # Exercise the actual SpotifyTarget read and parser; only provider IO and
    # catalog resolution are stubbed. The parser intentionally has no `artist`.
    client = Mock()
    client.playlist_items.return_value = {"items": items, "next": None}
    target = SpotifyTarget(client, str(tmp_path / "spotify-cache.json"))
    monkeypatch.setattr(target, "prefetch", Mock())
    monkeypatch.setattr(target, "expected_ids", Mock(return_value={}))
    resolve = Mock(side_effect=lambda track, cache: (
        ("spotify-new", "search") if track["id"] == "tidal-new" else (None, None)
    ))
    monkeypatch.setattr(target, "resolve", resolve)
    add = Mock(return_value=None)
    remove = Mock(return_value=None)
    monkeypatch.setattr(target, "add", add)
    monkeypatch.setattr(target, "remove", remove)
    remove_log, hold_log = Mock(), Mock()
    monkeypatch.setattr(base, "log_remove", remove_log)
    monkeypatch.setattr(base, "log_hold", hold_log)

    source_tracks = []
    if outcome in {"uncertain", "matched"}:
        source_tracks.append({
            "id": "tidal-existing",
            "name": "The Sound of Silence" if uncertain else existing_name,
            "artists": artists,
            "duration_ms": 200_000,
            "added_at": "2026-09-01T00:00:00Z",
        })
    source_tracks.append({
        "id": "tidal-new",
        "name": "New Arrival",
        "artists": ["Another Performer"],
        "duration_ms": 180_000,
        "added_at": "2026-09-02T00:00:00Z",
    })
    playlist = {"id": "spotify-playlist", "name": "Mix"}
    songs = archive.connect(str(tmp_path / "songs.db"))
    try:
        stats = base.mirror_pair(
            target, source_tracks, {"name": "Mix"}, playlist,
            {"isrc": {}, "search": {}, "dirty": False}, songs,
            execute=execute, max_removals=0 if outcome == "capped" else 25,
            max_adds=200, source_key="tidal", source_name="TIDAL",
        )

        assert stats["added"] == 1
        assert stats["removed"] == int(outcome == "remove")
        assert stats["held"] == int(uncertain)
        assert stats["missing"] == int(uncertain)
        assert stats["removals_skipped"] == int(outcome == "capped")
        assert stats["clean"] == (execute and outcome in {"remove", "matched"})
        if execute:
            add.assert_called_once_with(playlist, ["spotify-new"])
        else:
            add.assert_not_called()
        if execute and outcome == "remove":
            # Removal retains the raw provider record, including its id and
            # date, instead of receiving a lossy normalization for display.
            remove.assert_called_once_with(playlist, spotify._playlist_item_tracks(items)[0])
        else:
            remove.assert_not_called()
        if outcome == "remove":
            remove_log.assert_called_once_with(
                "Old Song - First Artist, Second Artist", dry=not execute, tag="spotify",
            )
        if uncertain:
            hold_log.assert_called_once_with(
                "kept (no Spotify match for its TIDAL twin): Sound of Silence Original - Disturbed",
                tag="spotify",
            )
            assert stats["uncertain_matches"] == 1
            assert stats["change_diagnostics"][0]["evidence"] == (
                'kept "Sound of Silence Original" — Disturbed; unresolved source track '
                '"The Sound of Silence" — Disturbed'
            )
        if outcome == "capped":
            assert stats["held_removals"][0]["artist"] == "First Artist, Second Artist"
        if outcome == "matched":
            # Identical artist lists must still match without a cached id;
            # replacing the missing field with an empty string is not enough.
            assert resolve.call_count == 1
        history = archive.get_order_history(songs, "mix", "spotify")
        assert history[0][1] == [["spotify-existing", existing_name, ", ".join(artists)]]
        assert songs.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 0
    finally:
        songs.close()


@pytest.mark.parametrize("backend", ["cookie", "api"])
@pytest.mark.parametrize("reference", [
    "https://open.spotify.com/track/6pHtgTMzsmP6ccN2ocv7XN?si=shared",
    "spotify:track:6pHtgTMzsmP6ccN2ocv7XN",
])
def test_saved_manual_spotify_reference_adds_once(tmp_path, monkeypatch, backend, reference):
    """An old mapping must emit a track URI and diff against its id next pass."""
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", backend)
    monkeypatch.setattr(spotify_cookie, "polite_sleep", lambda *_: None)
    monkeypatch.setattr(spotify_cookie, "metadata_isrcs",
                        lambda *_args, **_kwargs: pytest.fail("destination read must not fetch Spotify metadata"))
    monkeypatch.setattr("songmirror.engine.targets.spotify_target.polite_sleep", lambda *_: None)
    source = {
        "id": "apple-source", "name": "Darlin' (Stereo Mix)",
        "artists": ["The Beach Boys"], "duration_ms": 130_000,
        "added_at": "2026-10-01T00:00:00Z",
    }
    key = track_key(source["name"], " ".join(source["artists"]))
    path = str(tmp_path / "spotify-cache.json")
    cache = load_cache(path)
    cache["search"][key] = reference
    cache["manual"].add(key)
    cache["dirty"] = True
    save_cache(path, cache)
    landed, writes = [], []

    def write(playlist_id, uris):
        assert playlist_id == "destination"
        assert uris == ["spotify:track:6pHtgTMzsmP6ccN2ocv7XN"]
        writes.append(uris)
        landed.append({
            "id": "6pHtgTMzsmP6ccN2ocv7XN", "name": "Darlin' (Stereo Mix)",
            "artists": ["The Beach Boys"], "duration_ms": 130_000,
        })

    def pathfinder(operation, variables):
        assert operation == "addToPlaylist"
        write(variables["playlistUri"].removeprefix("spotify:playlist:"),
              variables["playlistItemUris"])
        return {}

    client = Mock()
    client.playlist_add_items.side_effect = write
    monkeypatch.setattr(spotify_cookie, "_pf", pathfinder)
    target = SpotifyTarget(client, path)
    monkeypatch.setattr(target, "playlist_tracks", lambda _: list(landed))
    monkeypatch.setattr(target, "_search", lambda *_: pytest.fail("manual choice was searched again"))
    songs = archive.connect(str(tmp_path / "songs.db"))
    try:
        stats = []
        for _ in range(2):
            cache = load_cache(path)
            stats.append(base.mirror_pair(
                target, [source], {"name": "Mix"}, {"id": "destination", "name": "Mix"},
                cache, songs, execute=True, max_removals=25, max_adds=200,
                source_key="apple", source_name="Apple Music",
            ))
            save_cache(path, cache)
        assert [row["added"] for row in stats] == [1, 0]
        assert [row["removed"] for row in stats] == [0, 0]
        assert [row["missing"] for row in stats] == [0, 0]
        assert len(writes) == 1
        assert load_cache(path)["search"][key] == "6pHtgTMzsmP6ccN2ocv7XN"
        assert load_cache(path)["manual"] == {key}
    finally:
        songs.close()


@pytest.mark.parametrize("normalized", [False, True], ids=["raw", "normalized"])
def test_mirror_pair_holds_removals_and_preserves_archived_metadata_for_unavailable_source(
    tmp_path, normalized,
):
    class _Target:
        tag = "apple"
        name = "Apple Music"
        source = "apple"
        provider = "apple"

        def track_id(self, track):
            return track.get("id")

        def playlist_tracks(self, _pl):
            return [{"id": "apple-1", "name": "Bright Lake", "artists": ["A"], "duration_ms": 1000}]

        def prefetch(self, _tracks, _cache):
            pass

        def expected_ids(self, _tracks, _links, _cache):
            return {}

        def resolve(self, _track, _cache):
            raise AssertionError("must not search for blank unavailable source entry")

        def add(self, _pl, _ids):
            raise AssertionError("must not add unavailable source entry")

        def remove(self, _pl, _track):
            raise AssertionError("must not remove destination track when source has unavailable entry")

    target = _Target()

    source_tracks = [
        {"id": "sp-hidden", "name": "", "artists": [""], "duration_ms": 0, "unavailable": True},
    ]
    if normalized:
        source_tracks = [{**base._normalize(row, "spotify"), "id": row["id"]} for row in source_tracks]
    previous = {
        "id": "sp-hidden", "name": "Alpha Road", "artists": ["A"],
        "duration_ms": 1000, "isrc": "USAAA2600001",
    }
    songs = archive.connect(str(tmp_path / "oneway-hidden.db"))
    try:
        archive.upsert_many(songs, "spotify", [previous])
        stats = base.mirror_pair(
            target, source_tracks, {"name": "Mix"}, {"id": "dest", "name": "Mix"},
            {"isrc": {}, "search": {}, "dirty": False}, songs,
            execute=True, max_removals=25, max_adds=200,
            source_key="spotify", source_name="Spotify",
        )
        assert stats["removed"] == 0
        assert stats["removals_skipped"] == 1
        assert archive.get_snapshots(songs, "spotify", ["sp-hidden"]) == {"sp-hidden": previous}
        assert archive.get_isrcs(songs, "spotify", ["sp-hidden"]) == {"sp-hidden": "USAAA2600001"}
    finally:
        songs.close()


@pytest.mark.parametrize("has_live_occurrence", [False, True], ids=["missing", "present"])
def test_restored_spotify_track_keeps_live_occurrence_fields(tmp_path, monkeypatch, has_live_occurrence):
    monkeypatch.setenv("SPOTIFY_WRITE_BACKEND", "cookie")
    remove_uids, remove_positions = Mock(), Mock()
    monkeypatch.setattr(spotify_cookie, "remove_uids", remove_uids)
    monkeypatch.setattr(spotify_cookie, "remove_positions", remove_positions)
    target = SpotifyTarget(None, "unused")
    track_id = "sp-hidden"
    archived = {
        "id": track_id, "name": "Alpha Road", "artists": ["A"], "isrc": "USAAA2600001",
        "playlistItemId": "archived-uid", "added_at": "2025-01-01T00:00:00Z",
    }
    live = {"id": track_id, "name": "", "unavailable": True}
    if has_live_occurrence:
        live.update(playlistItemId="live-uid", added_at="2026-01-01T00:00:00Z")

    songs = archive.connect(str(tmp_path / "restored-occurrence.db"))
    try:
        archive.upsert_many(songs, "spotify", [archived])
        rows, preserved, unidentified = base._partition_reconcile_rows(
            songs, target, [{"name": ""}, {"id": "sp-other", "name": "Bright Lake"}, live],
        )
        assert not preserved and unidentified == 1
        assert list(rows) == [1, 2]
        restored = rows[2]
        assert restored["name"] == archived["name"]
        assert restored["isrc"] == archived["isrc"]
        assert restored.get("playlistItemId") == live.get("playlistItemId")
        assert restored.get("added_at") == live.get("added_at")

        target.remove_occurrences({"id": "live-playlist"}, [(2, restored)])
        if has_live_occurrence:
            remove_uids.assert_called_once_with("live-playlist", ["live-uid"])
            remove_positions.assert_not_called()
        else:
            remove_positions.assert_called_once_with("live-playlist", [2], expected_track_ids=[track_id])
            remove_uids.assert_not_called()
    finally:
        songs.close()
