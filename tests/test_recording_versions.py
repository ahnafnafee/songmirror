"""A different recording is not a substitute for a source track."""

import pytest

from songmirror.engine import archive
from songmirror.engine.matching import compute_diff, same_catalog_recording, score_candidate, track_key
from songmirror.engine.targets.base import _normalize, _recover_archived_links, _unify_aliases
from songmirror.engine.targets.amazon_music import AmazonMusicTarget
from songmirror.engine.targets.apple import AppleMusicTarget
from songmirror.engine.targets.deezer import DeezerTarget, _normalized_track
from songmirror.engine.targets.qobuz import QobuzTarget
from songmirror.engine.targets.tidal import TidalTarget


@pytest.mark.parametrize("label", ["Acoustic", "Akustik", "Acústico", "Acoustique", "Unplugged", "Stripped"])
@pytest.mark.parametrize("reverse", [False, True])
def test_studio_and_acoustic_recordings_never_match(label, reverse):
    source, candidate = "A Song", f"A Song ({label})"
    if reverse:
        source, candidate = candidate, source
    assert not score_candidate(source, ["Artist"], 180000, candidate, "Artist", 180000)[1]


def test_featured_credit_does_not_hide_a_recording_version_in_the_cache_key():
    assert track_key("A Song feat. Guest (Acoustic)", "Artist") != track_key(
        "A Song feat. Guest", "Artist"
    )


@pytest.mark.parametrize("label", ["Acoustic", "Akustik"])
@pytest.mark.parametrize("hard_studio", [True, False])
def test_fuzzy_sync_identity_does_not_fold_acoustic_into_studio(label, hard_studio):
    studio = _normalize({"name": "A Song", "artists": ["Artist"]}, "spotify")
    acoustic = _normalize({"name": f"A Song ({label})", "artists": ["Artist"]}, "ytmusic")
    hard, soft = (studio, acoustic) if hard_studio else (acoustic, studio)
    soft_id = "k:" + track_key(soft["name"], "Artist")
    assert _unify_aliases({"spotify": {"i:recording": hard}, "ytmusic": {soft_id: soft}}) == {}


def test_deezer_separate_version_field_is_visible_to_the_matcher():
    track = _normalized_track({
        "id": 1, "title": "A Song", "title_version": "(Acoustic)",
        "artist": {"name": "Artist"}, "duration": 180,
    })
    assert not score_candidate("A Song", ["Artist"], 180000, track["name"], track["artist"], track["duration_ms"])[1]


@pytest.mark.parametrize("target_class", [DeezerTarget, QobuzTarget, TidalTarget, AmazonMusicTarget, AppleMusicTarget])
@pytest.mark.parametrize("qualifier", ["Acoustic", "Dub", "feat. Guest", "First DJ Remix"])
def test_isrc_fallback_does_not_ignore_an_explicit_recording_conflict(target_class, qualifier):
    target = target_class.__new__(target_class)
    target._search = lambda *_args: None  # Apple's search; others use the cached miss.
    cache = {
        "isrc": {"ISRC1": [{"id": "variant", "name": f"A Song ({qualifier})", "artist": "Artist", "duration_ms": 180000}]},
        "search": {track_key("A Song", "Artist"): None},
    }
    track = {"id": "source", "name": "A Song", "artists": ["Artist"], "duration_ms": 180000, "isrc": "ISRC1"}

    assert target.resolve(track, cache)[0] is None
    assert target.expected_ids([track], {}, cache) == {}

    cache["isrc"]["ISRC1"].append({"id": "studio", "name": "A Song", "artist": "Artist", "duration_ms": 180000})
    assert target.resolve(track, cache) == ("studio", "isrc")
    assert target.expected_ids([track], {}, cache) == {"source": {"studio"}}


@pytest.mark.parametrize("label", [
    "Dub", "Club Mix", "Extended Mix", "Radio Edit", "Single Edit", "VIP",
    "A Cappella", "Orchestral", "Re-recorded", "Slowed + Reverb", "Nightcore",
    "Instrumental", "Demo", "Karaoke", "Cover", "Solo Version", "Remix",
])
@pytest.mark.parametrize("reverse", [False, True])
def test_studio_and_other_recording_variants_never_match(label, reverse):
    source, candidate = "A Song", f"A Song ({label})"
    if reverse:
        source, candidate = candidate, source
    assert not score_candidate(source, ["Artist"], 180000, candidate, "Artist", 180000)[1]


@pytest.mark.parametrize(("source", "candidate"), [
    ("A Song (First DJ Remix)", "A Song (Second DJ Remix)"),
    ("A Song (Live at Wembley)", "A Song (Live at Glastonbury)"),
    ("A Song (Version 1)", "A Song (Version 2)"),
    ("A Song (Radio Edit)", "A Song (Single Edit)"),
])
def test_different_variants_within_the_same_family_do_not_match(source, candidate):
    assert not score_candidate(source, ["Artist"], 180000, candidate, "Artist", 180000)[1]


@pytest.mark.parametrize(("source", "source_artists", "candidate", "candidate_artist", "expected"), [
    ("A Song", ["Artist"], "A Song (feat. Guest)", "Artist", False),
    ("A Song (feat. Guest)", ["Artist"], "A Song", "Artist", False),
    ("A Song (feat. First Guest)", ["Artist"], "A Song (feat. Second Guest)", "Artist", False),
    ("A Song (feat. Guest)", ["Artist"], "A Song", "Artist, Guest", True),
    ("A Song", ["Artist", "Guest"], "A Song (feat. Guest)", "Artist", True),
    ("A Song feat. Guest (Acoustic)", ["Artist"], "A Song (Acoustic) [ft. Guest]", "Artist", True),
    ("A Song (feat. Live)", ["Artist"], "A Song", "Artist, Live", True),
    ("A Song (Acoustic Version)", ["Artist"], "A Song - Akustik", "Artist", True),
])
def test_featured_credit_and_variant_spelling_must_describe_the_same_recording(
    source, source_artists, candidate, candidate_artist, expected,
):
    assert score_candidate(source, source_artists, 180000, candidate, candidate_artist, 180000)[1] is expected


def test_featured_recording_has_a_distinct_cache_key_unless_the_artist_credit_agrees():
    assert track_key("A Song (feat. Guest)", "Artist") != track_key("A Song", "Artist")
    assert track_key("A Song (feat. Guest)", "Artist") == track_key("A Song", "Artist, Guest")


def test_featured_variant_does_not_suppress_an_add_or_become_a_duplicate():
    studio = {"id": "studio", "name": "A Song", "artists": ["Artist"], "duration_ms": 180000}
    featured = {"id": "feature", "name": "A Song (feat. Guest)", "artist": "Artist", "artists": ["Artist"], "duration_ms": 180000}
    assert compute_diff([studio], [featured], {}, lambda track: track["id"])[0] == [studio]
    assert not same_catalog_recording(studio, featured)


@pytest.mark.parametrize("qualifier", ["Dub", "feat. Guest", "First DJ Remix"])
def test_sync_identity_does_not_fold_other_recording_variants(qualifier):
    studio = _normalize({"name": "A Song", "artists": ["Artist"]}, "spotify")
    variant = _normalize({"name": f"A Song ({qualifier})", "artists": ["Artist"]}, "ytmusic")
    soft_id = "k:" + track_key(variant["name"], "Artist")
    assert _unify_aliases({"spotify": {"i:recording": studio}, "ytmusic": {soft_id: variant}}) == {}


def test_other_providers_preserve_separate_version_fields():
    from songmirror.engine.targets.qobuz import _normalized_track as qobuz_track
    assert qobuz_track({"id": 1, "title": "A Song", "version": "Dub"})["name"] == "A Song (Dub)"
    track = TidalTarget._tracks_from_body({"data": [{
        "id": "1", "type": "tracks", "attributes": {"title": "A Song", "version": "Acoustic"},
    }]})[0]
    assert track["name"] == "A Song (Acoustic)"
    # A provider may already have included the same label in its display title.
    assert _normalized_track({"title": "A Song (Acoustic)", "title_version": "(Acoustic)"})["name"] == "A Song (Acoustic)"


def test_a_wrong_archived_link_does_not_suppress_the_correct_recording(tmp_path):
    target = DeezerTarget.__new__(DeezerTarget)
    source = {"id": "source", "name": "A Song", "artists": ["Artist"], "duration_ms": 180000}
    variant = {"id": "variant", "name": "A Song (Dub)", "artist": "Artist", "artists": ["Artist"], "duration_ms": 180000}
    conn = archive.connect(str(tmp_path / "songs.db"))
    try:
        archive.upsert_many(conn, "deezer", [variant])
        assert _recover_archived_links(conn, "spotify", target, [source], {"source": "variant"}) == {}
        to_add, to_remove = compute_diff([source], [variant], {"source": {"variant"}}, target.track_id)
        assert to_add == [source]
        assert to_remove == [variant]
    finally:
        conn.close()


def test_apple_catalog_link_validation_rechecks_the_recording_for_each_source():
    from types import SimpleNamespace
    target = AppleMusicTarget.__new__(AppleMusicTarget)
    target.storefront = "us"
    target._request = lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {"data": [{
        "id": "variant", "attributes": {"name": "A Song (Dub)", "artistName": "Artist"},
    }]})
    cache = {"isrc": {"ISRC1": []}}
    source = {"name": "A Song", "artists": ["Artist"], "isrc": "ISRC1"}
    assert target.validate_link(source, "variant", cache) == (None, None)
    assert target.validate_link({**source, "name": "A Song (Dub)"}, "variant", cache) == ("variant", "link")
