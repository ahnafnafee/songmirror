"""Local-library-first mirror resolver: index, match, place, serve."""

import pytest

from songmirror.engine import local_library as ll
from songmirror.engine.matching import track_key


class _Tags(dict):
    """Easy-mode mutagen tags: every value is a list."""

    def __init__(self, **fields):
        super().__init__({k: [v] for k, v in fields.items() if v is not None})


@pytest.fixture(autouse=True)
def _clear_cache():
    ll._INDEX_CACHE.clear()
    yield
    ll._INDEX_CACHE.clear()


def _library(tmp_path, monkeypatch, files):
    """Write `files` as {relative path: _Tags} and tag-map them by path."""
    root = tmp_path / "library"
    by_path = {}
    for rel, tags in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
        by_path[str(path)] = tags
    monkeypatch.setattr(ll, "_tags", lambda p: by_path.get(str(p)))
    return root


def test_index_maps_isrc_and_fuzzy_key(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "X/Album/one.flac": _Tags(title="One", artist="X", isrc="gb-smu-26-29433"),
        "Y/Album/two.mp3": _Tags(title="Two", artist="Y"),
    })

    idx = ll.index(root)

    assert idx["by_isrc"]["GBSMU2629433"].endswith("one.flac")
    assert idx["by_key"][track_key("Two", "Y")].endswith("two.mp3")


def test_index_skips_non_audio_and_unreadable_tags(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "cover.jpg": _Tags(title="Not audio"),
        "X/broken.flac": None,
        "X/good.flac": _Tags(title="Good", artist="X"),
    })

    idx = ll.index(root)

    assert list(idx["by_key"]) == [track_key("Good", "X")]


def test_missing_root_yields_an_empty_index(tmp_path):
    idx = ll.index(tmp_path / "nope")

    assert idx == {"by_isrc": {}, "by_key": {}}


def test_index_is_cached_per_root(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {"X/a.flac": _Tags(title="A", artist="X")})
    walked = []
    real = ll._tags
    monkeypatch.setattr(ll, "_tags", lambda p: walked.append(p) or real(p))

    ll.index(root)
    ll.index(root)

    assert len(walked) == 1


def test_find_prefers_isrc_over_the_name_key(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "right.flac": _Tags(title="Different Title", artist="Q", isrc="GBSMU2629433"),
        "wrong.flac": _Tags(title="Song", artist="X"),
    })
    idx = ll.index(root)

    hit = ll.find({"name": "Song", "artist": "X", "isrc": "GB-SMU-26-29433"}, idx)

    assert hit.endswith("right.flac")


def test_find_falls_back_to_the_name_key_without_an_isrc(tmp_path, monkeypatch):
    idx = ll.index(_library(tmp_path, monkeypatch,
                            {"a.flac": _Tags(title="Song", artist="X")}))

    assert ll.find({"name": "Song", "artist": "X"}, idx).endswith("a.flac")
    assert ll.find({"name": "Song", "artists": ["X"]}, idx).endswith("a.flac")


def test_find_returns_none_on_a_miss(tmp_path, monkeypatch):
    idx = ll.index(_library(tmp_path, monkeypatch,
                            {"a.flac": _Tags(title="Song", artist="X")}))

    assert ll.find({"name": "Absent", "artist": "Nobody"}, idx) is None
    assert ll.find({"name": "", "artist": "X"}, idx) is None
    assert ll.find(None, idx) is None


def test_place_copies_into_the_spotdl_layout(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "src.flac": _Tags(title="Song", artist="X", albumartist="AA", album="Alb"),
    })
    folder = tmp_path / "playlist"
    src = str(root / "src.flac")

    rel = ll.place(src, folder, {"name": "Song", "artist": "X"})

    assert rel == "AA/Alb/X - Song.flac"
    assert (folder / rel).read_bytes() == b"audio"


def test_place_sanitizes_path_components(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "src.flac": _Tags(title="A/B", artist="X:Y", albumartist="A?A", album="Al*b"),
    })
    folder = tmp_path / "playlist"

    rel = ll.place(str(root / "src.flac"), folder, {"name": "A/B", "artist": "X:Y"})

    assert rel == "A_A/Al_b/X_Y - A_B.flac"
    assert (folder / rel).is_file()


def test_place_is_idempotent(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch,
                    {"src.flac": _Tags(title="Song", artist="X", album="Alb")})
    folder = tmp_path / "playlist"
    track = {"name": "Song", "artist": "X"}

    first = ll.place(str(root / "src.flac"), folder, track)
    (folder / first).write_bytes(b"edited")
    second = ll.place(str(root / "src.flac"), folder, track)

    assert first == second
    # An already-placed file is left alone rather than re-copied.
    assert (folder / first).read_bytes() == b"edited"


def test_place_reports_failure_without_raising(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch,
                    {"src.flac": _Tags(title="Song", artist="X", album="Alb")})
    monkeypatch.setattr(ll.shutil, "copy2",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("full")))

    assert ll.place(str(root / "src.flac"), tmp_path / "pl",
                    {"name": "Song", "artist": "X"}) is None


def test_serve_places_hits_and_returns_only_the_gaps(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {
        "have.flac": _Tags(title="Have", artist="X", album="Alb"),
    })
    monkeypatch.setenv("LOCAL_LIBRARY_DIR", str(root))
    folder = tmp_path / "playlist"
    tracks = [{"id": "1", "name": "Have", "artist": "X"},
              {"id": "2", "name": "Missing", "artist": "Y"}]

    pending = ll.serve(folder, tracks, ["1", "2"])

    assert pending == ["2"]
    assert (folder / "X/Alb/X - Have.flac").is_file()


def test_serve_is_off_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_LIBRARY_DIR", raising=False)

    assert ll.serve(tmp_path, [{"id": "1", "name": "A"}], ["1"]) == ["1"]
    assert not ll.configured()


def test_serve_degrades_to_downloading_when_the_library_breaks(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_LIBRARY_DIR", str(tmp_path / "lib"))
    monkeypatch.setattr(ll, "index",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    assert ll.serve(tmp_path, [{"id": "1", "name": "A"}], ["1"]) == ["1"]


def test_serve_ignores_ids_with_no_matching_track(tmp_path, monkeypatch):
    root = _library(tmp_path, monkeypatch, {"a.flac": _Tags(title="A", artist="X")})
    monkeypatch.setenv("LOCAL_LIBRARY_DIR", str(root))

    assert ll.serve(tmp_path / "pl", [], ["ghost"]) == ["ghost"]
