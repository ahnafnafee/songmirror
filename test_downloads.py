"""Offline self-check for the local download mirror: `uv run python test_downloads.py`."""

import os
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

from spotify_mirror import downloads as lm


class FakeSp:
    def __init__(self, items):
        self._items = items

    def playlist_items(self, playlist_id, additional_types=("track",), limit=100):
        return {"items": self._items, "next": None}

    def next(self, page):
        raise AssertionError("no pagination expected")


def fake_item(name, artists, isrc, added_at, shape="track"):
    track = {"name": name, "type": "track", "is_local": False,
             "external_ids": {"isrc": isrc} if isrc else {},
             "artists": [{"name": a} for a in artists]}
    return {"added_at": added_at, shape: track}


def test_norm_and_sanitize():
    assert lm._norm(" The-Track  Name! ") == "the track name"
    assert not (set('<>:"/\\|?*') & set(lm.sanitize_folder('A/B: C*?')))
    assert lm.sanitize_folder("...") == "playlist" and lm.sanitize_folder(None) == "playlist"


def test_read_tracks_and_indexes():
    a, b = "2024-01-05T10:00:00Z", "2024-03-09T20:30:00Z"
    sp = FakeSp([
        fake_item("Song One", ["Alpha", "Beta"], "USUM71900001", a),
        fake_item("Song Two", ["Gamma"], None, b),
        {"added_at": None, "track": {"name": "skip"}},
        fake_item("Song Three", ["Delta"], None, "2024-05-01T00:00:00Z", shape="item"),  # current Web API shape
    ])
    tracks = lm.read_tracks(sp, "pl1")
    assert [t["name"] for t in tracks] == ["Song One", "Song Two", "Song Three"]  # playlist order preserved
    by_isrc, by_key = lm.added_at_indexes(tracks)
    assert by_isrc["USUM71900001"] == datetime(2024, 1, 5, 10, 0, tzinfo=timezone.utc)
    assert "delta|song three" in by_key and "alpha beta|song one" in by_key
    assert lm.match_added_at(["usum71900001 "], "?", [], by_isrc, by_key) == by_isrc["USUM71900001"]
    assert lm.match_added_at([], "Song One", ["Alpha, Beta"], by_isrc, by_key) == by_isrc["USUM71900001"]
    assert lm.match_added_at([], "nope", ["nobody"], by_isrc, by_key) is None


def test_build_m3u_newest_first():
    def tk(name, isrc, when, dur=180000):
        return {"when": datetime.fromisoformat(when), "isrc": isrc, "keys": {f"artist|{name.lower()}"},
                "name": name, "artist": "Artist", "duration_ms": dur}
    tracks = [tk("Old", "I1", "2023-01-01T00:00:00+00:00"),
              tk("New", "I2", "2026-07-01T00:00:00+00:00"),
              tk("Mid", None, "2024-06-01T00:00:00+00:00")]  # no ISRC -> matched by key
    files = {"I1": "A/Old.mp3", "I2": "A/New.mp3"}
    keys = {"artist|mid": "A/Mid.mp3"}
    lines = lm.build_m3u(tracks, files, keys, ["A/Old.mp3", "A/New.mp3", "A/Mid.mp3", "A/Stray.mp3"], newest_first=True)
    order = [ln for ln in lines if ln.endswith(".mp3")]
    assert order == ["A/New.mp3", "A/Mid.mp3", "A/Old.mp3", "A/Stray.mp3"]  # newest first, stray kept last
    assert lines[0] == "#EXTM3U" and any(ln.startswith("#EXTINF:180,Artist - New") for ln in lines)
    # oldest-first flips the tracks (stray still trails)
    order = [ln for ln in lm.build_m3u(tracks, files, keys, [], newest_first=False) if ln.endswith(".mp3")]
    assert order == ["A/Old.mp3", "A/Mid.mp3", "A/New.mp3"]


def test_build_sync_cmd():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        save, url = folder / ".sync.spotdl", "https://open.spotify.com/playlist/abc"
        cmd = lm.build_sync_cmd(folder, save, url)
        assert "sync" in cmd and url in cmd and "--save-file" in cmd
        assert cmd[cmd.index("--output") + 1] == "{album-artist}/{album}/{artists} - {title}.{output-ext}"
        assert cmd[cmd.index("--overwrite") + 1] == "skip"  # existing files skipped
        assert "--m3u" not in cmd  # we generate the m3u ourselves, in date-added order
        ai = cmd.index("--audio")
        assert cmd[ai + 1:ai + 3] == ["youtube-music", "youtube"]  # YT fallback for OST/instrumentals
        save.write_text("{}")
        os.environ["LOCAL_MIRROR_FORMAT"] = "flac"
        try:
            cmd = lm.build_sync_cmd(folder, save, url)
        finally:
            del os.environ["LOCAL_MIRROR_FORMAT"]
        assert str(save) in cmd and "--save-file" not in cmd and url not in cmd
        assert cmd[cmd.index("--format") + 1] == "flac"


def test_stream_parsing():
    lines = [
        "Processing query: abc\n",
        'Downloaded "Artist - Title": https://youtu.be/x\n',
        "Skipping Artist - Old (file already exists)\n",
        "LookupError: No results found for song: Weird Track\n",
        "\n",
    ]
    proc = types.SimpleNamespace(stdout=iter(lines), returncode=0, wait=lambda: None,
                                 poll=lambda: 0, kill=lambda: None)
    real = lm.subprocess.Popen
    lm.subprocess.Popen = lambda *a, **k: proc
    try:
        with tempfile.TemporaryDirectory() as tmp:
            downloaded, skipped, code = lm._stream_spotdl(["x"], Path(tmp), 5)
    finally:
        lm.subprocess.Popen = real
    assert (downloaded, skipped, code) == (1, 1, 0)


def test_fill_missing_tags():
    track = {"name": "T", "artist": "A, B", "album": "Alb", "isrc": "US1"}
    audio = {}
    assert lm._fill_missing(audio, track) is True
    assert audio["title"] == ["T"] and audio["artist"] == ["A, B"] and audio["album"] == ["Alb"]
    assert audio["albumartist"] == ["A"] and audio["isrc"] == ["US1"]  # albumartist = primary artist
    existing = {"title": ["Keep"], "isrc": ["OLD"]}
    lm._fill_missing(existing, track)
    assert existing["title"] == ["Keep"] and existing["isrc"] == ["OLD"]  # never overwritten
    full = {k: ["x"] for k in ("title", "artist", "album", "albumartist", "isrc")}
    assert lm._fill_missing(full, track) is False  # nothing to add


def test_match_track():
    def tk(name, artist, isrc):
        keys = set()
        title = lm._norm(name)
        for a in {lm._norm(artist.split(",")[0]), lm._norm(artist)}:
            if a:
                keys.add(f"{a}|{title}")
        return {"name": name, "artist": artist, "isrc": isrc, "keys": keys}

    t1, t2 = tk("Song One", "Alpha", "US1"), tk("Song Two", "Beta, Gamma", None)
    by_isrc, by_key, by_stem = lm._track_lookups([t1, t2])
    assert lm._match_track(["us1 "], "", [], "", by_isrc, by_key, by_stem) is t1  # ISRC
    assert lm._match_track([], "Song Two", ["Beta"], "", by_isrc, by_key, by_stem) is t2  # artist|title
    assert lm._match_track([], "", [], "Alpha - Song One", by_isrc, by_key, by_stem) is t1  # filename stem
    assert lm._match_track([], "Nope", ["X"], "x - y", by_isrc, by_key, by_stem) is None


def test_needs_spotdl():
    assert lm._needs_spotdl(["a", "b"], [], [])[0]  # first run downloads everything
    assert not lm._needs_spotdl(["a", "b"], ["a", "b"], ["b"])[0]  # only known-unavailable "missing" -> no run
    run, new, _ = lm._needs_spotdl(["a", "b", "c"], ["a", "b"], ["b"])
    assert run and new == {"c"}  # a genuinely new track triggers a run
    run, _, removed = lm._needs_spotdl(["a"], ["a", "b"], [])
    assert run and removed == {"b"}  # a removal triggers a run
    assert not lm._needs_spotdl(["b", "a"], ["a", "b"], [])[0]  # reorder alone does not


def test_tracks_without_file():
    def tk(name, artist, tid):
        keys = set()
        title = lm._norm(name)
        for a in {lm._norm(artist), lm._norm(artist.split(",")[0])}:
            if a:
                keys.add(f"{a}|{title}")
        return {"id": tid, "name": name, "artist": artist, "isrc": None, "keys": keys}

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "A").mkdir()
        (folder / "A" / "Alpha - Song One.mp3").write_bytes(b"x")  # untagged -> matched by filename stem
        missing = lm._tracks_without_file(folder, [tk("Song One", "Alpha", "id1"), tk("Song Two", "Beta", "id2")])
        assert [t["id"] for t in missing] == ["id2"]  # present one covered, absent one flagged


def test_fetch_image_cache():
    calls, real = [], lm.requests.get
    lm.requests.get = lambda *a, **k: (calls.append(1), types.SimpleNamespace(content=b"IMG", raise_for_status=lambda: None))[1]
    try:
        cache = {}
        assert lm._fetch_image("http://x/a.jpg", cache) == b"IMG"
        assert lm._fetch_image("http://x/a.jpg", cache) == b"IMG"  # served from cache
    finally:
        lm.requests.get = real
    assert len(calls) == 1


def test_save_cover():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        real = lm.requests.get
        lm.requests.get = lambda *a, **k: types.SimpleNamespace(content=b"JPEGDATA", raise_for_status=lambda: None)
        try:
            lm.save_cover({"images": [{"url": "http://x/big.jpg"}]}, folder)
            first = (folder / "cover.jpg").read_bytes()
            lm.requests.get = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should be cached"))
            lm.save_cover({"images": [{"url": "http://x/big.jpg"}]}, folder)  # unchanged URL -> no refetch
        finally:
            lm.requests.get = real
        assert first == b"JPEGDATA"
        assert (folder / "folder.jpg").read_bytes() == b"JPEGDATA"


def test_run_skips_without_spotdl():
    real = lm.importlib.util.find_spec
    lm.importlib.util.find_spec = lambda name: None
    try:
        lm.run(None, [{"id": "x", "name": "X"}], tempfile.mkdtemp())  # must not raise
    finally:
        lm.importlib.util.find_spec = real


def test_run_name_collision():
    calls, real = [], (lm.importlib.util.find_spec, lm.ffmpeg_available, lm._sync_one, lm.read_tracks)
    lm.importlib.util.find_spec = lambda name: object()
    lm.ffmpeg_available = lambda: True
    lm.read_tracks = lambda sp, pid: []
    lm._sync_one = lambda sp, pl, folder, t, tracks, run, unavail: (calls.append(folder.name), (True, set()))[1]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DOWNLOAD_STATE_FILE"] = os.path.join(tmp, "state.json")  # don't pollute cwd
            try:
                lm.run(None, [{"id": "id111111a", "name": "Mix"}, {"id": "id222222b", "name": "Mix"},
                              {"id": "id333333c", "name": "Chill"}], tmp)
            finally:
                del os.environ["DOWNLOAD_STATE_FILE"]
    finally:
        lm.importlib.util.find_spec, lm.ffmpeg_available, lm._sync_one, lm.read_tracks = real
    assert calls == ["Mix", "Mix [id222222]", "Chill"]


def test_jellyfin_push_covers():
    import base64

    from spotify_mirror import jellyfin

    calls = {"post": []}

    def fake_get(u, headers=None, params=None, timeout=None):
        if "/Items" in u:
            return types.SimpleNamespace(json=lambda: {"Items": [{"Id": "p1", "Name": "Aurora"}]},
                                         raise_for_status=lambda: None)
        return types.SimpleNamespace(content=b"IMG", raise_for_status=lambda: None)  # image download

    def fake_post(u, headers=None, data=None, timeout=None):
        calls["post"].append((u, headers, data))
        return types.SimpleNamespace(ok=True, status_code=200)

    real = (jellyfin.requests.get, jellyfin.requests.post)
    jellyfin.requests.get, jellyfin.requests.post = fake_get, fake_post
    os.environ["JELLYFIN_URL"], os.environ["JELLYFIN_API_KEY"] = "http://jf:8096", "k"
    try:
        jellyfin.push_covers([
            {"name": "Aurora", "images": [{"url": "http://img/a.jpg"}]},
            {"name": "NotInJellyfin", "images": [{"url": "http://img/b.jpg"}]},  # skipped, not found
        ])
    finally:
        jellyfin.requests.get, jellyfin.requests.post = real
        del os.environ["JELLYFIN_URL"], os.environ["JELLYFIN_API_KEY"]

    assert len(calls["post"]) == 1  # only the matched playlist
    u, headers, data = calls["post"][0]
    assert u.endswith("/Items/p1/Images/Primary")
    assert headers.get("Content-Type") == "image/jpeg"
    assert data == base64.b64encode(b"IMG")  # base64 body


def test_jellyfin_skips_without_env():
    from spotify_mirror import jellyfin

    for k in ("JELLYFIN_URL", "JELLYFIN_API_KEY"):
        os.environ.pop(k, None)
    jellyfin.push_covers([{"name": "X", "images": [{"url": "u"}]}])  # no env -> no-op, no network


if __name__ == "__main__":
    for name in sorted(k for k in dict(globals()) if k.startswith("test_")):
        globals()[name]()
        print(f"ok {name}")
    print("all download checks passed")
