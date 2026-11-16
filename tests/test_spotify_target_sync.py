"""One-way sync against Spotify's real parsed playlist-track shape."""

from unittest.mock import Mock

import pytest

from songmirror.engine import archive, spotify, spotify_cookie
from songmirror.engine.matching import track_key
from songmirror.engine.runner import load_cache, save_cache
from songmirror.engine.targets import base
from songmirror.engine.targets.spotify_target import SpotifyTarget


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
