"""Authorized feedback, conservative recording matches, and TIDAL love sync."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from songmirror import listenbrainz
from songmirror.engine import archive, runner
from songmirror.engine.config import parse_args
from songmirror.engine.targets.base import TargetAuthError, TargetCapabilityError, TargetTransientError
from songmirror.engine.targets.listenbrainz import ListenBrainzTarget
from songmirror.engine.targets.tidal import TidalTarget
from songmirror.engine.track_references import normalize_track_reference
from songmirror.services.account_profiles import AccountProfileStore
from songmirror.services.accounts.listenbrainz import ListenBrainzConnector
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app

MBID = "8f3471b5-7e6a-48da-86a9-c1c07a0f47ae"
MSID = "d23f4719-9212-49f0-ad08-ddbfbfc50d6f"
SECOND_MBID = "9f24c0f7-a644-4074-8fbd-a1dba03de129"
TOKEN = "private-test-token"


@pytest.fixture(autouse=True)
def isolated_budget(monkeypatch):
    monkeypatch.setenv("LISTENBRAINZ_TOKEN", "")
    monkeypatch.setattr(listenbrainz, "_REQUESTS", listenbrainz._RequestGate(sleep=lambda _: None))


def response(body, status=200, headers=None):
    return SimpleNamespace(status_code=status, ok=200 <= status < 300,
                           headers=headers or {}, json=lambda: body)


def valid_token(user="listener"):
    return response({"valid": True, "user_name": user})


@pytest.mark.parametrize("identifier", [f"mbid:{MBID}", f"msid:{MSID}"])
@pytest.mark.parametrize("score", [0, 1])
def test_feedback_is_authenticated_confirmed_and_never_redirected(identifier, score):
    session = Mock()
    session.get.return_value = valid_token("Listener")
    session.post.return_value = response({"status": "ok"})
    api = listenbrainz.ListenBrainz("listener", session, token=TOKEN)
    api.set_feedback(identifier, score)
    api.set_feedback(identifier, score)
    session.get.assert_called_once()
    kind, value = identifier.split(":")
    assert session.post.call_count == 2
    for call in [session.get.call_args, *session.post.call_args_list]:
        assert call.args[0].startswith(listenbrainz.API + "/1/")
        assert call.kwargs["headers"]["Authorization"] == f"Token {TOKEN}"
        assert call.kwargs["allow_redirects"] is False
        assert "token" not in call.kwargs.get("params", {})
    assert session.post.call_args.args[0].endswith("/feedback/recording-feedback")
    assert session.post.call_args.kwargs["json"] == {f"recording_{kind}": value, "score": score}


@pytest.mark.parametrize("body,error", [
    ({"valid": False}, TargetAuthError),
    ({"valid": True, "user_name": "somebody-else"}, TargetAuthError),
    ({}, TargetTransientError), ({"valid": "true", "user_name": "listener"}, TargetTransientError),
    ({"valid": True, "user_name": ""}, TargetTransientError),
])
def test_writes_require_a_valid_token_for_the_selected_profile(body, error):
    session = Mock()
    session.get.return_value = response(body)
    api = listenbrainz.ListenBrainz("listener", session, token=TOKEN)
    with pytest.raises(error) as caught:
        api.set_feedback(MBID, 1)
    assert TOKEN not in str(caught.value)
    session.post.assert_not_called()


def test_username_only_connections_cannot_write_or_lookup():
    session = Mock()
    api = listenbrainz.ListenBrainz("listener", session, token="")
    target = ListenBrainzTarget(api)
    target.validate_favorite_tracks(write=False)
    for action in [lambda: target.validate_favorite_tracks(write=True),
                   lambda: api.set_feedback(MBID, 1),
                   lambda: api.lookup_recording("Artist", "Song")]:
        with pytest.raises(TargetCapabilityError, match="user token"):
            action()
    assert session.mock_calls == []


@pytest.mark.parametrize("status,body,headers,error", [
    (401, {}, {}, TargetAuthError), (403, {}, {}, TargetAuthError),
    (429, {}, {}, TargetTransientError), (503, {}, {}, TargetTransientError),
    (302, {}, {"Location": "https://other.example"}, RuntimeError),
    (400, {"error": TOKEN}, {}, RuntimeError),
    (200, {}, {}, TargetTransientError), (200, [], {}, TargetTransientError),
    (200, {"status": "ok"}, {"Content-Type": "text/html"}, TargetTransientError),
])
def test_unconfirmed_feedback_fails_without_retry_or_secret_disclosure(status, body, headers, error):
    session = Mock()
    session.get.return_value = valid_token()
    session.post.return_value = response(body, status, headers)
    api = listenbrainz.ListenBrainz("listener", session, token=TOKEN)
    with pytest.raises(error) as caught:
        api.set_feedback(MBID, 1)
    assert TOKEN not in str(caught.value)
    assert session.post.call_count == 1
    if status in {401, 403}:
        assert not api._validated


def test_timeout_does_not_repeat_a_possibly_accepted_write():
    session = Mock()
    session.get.return_value = valid_token()
    session.post.side_effect = requests.Timeout(TOKEN)
    with pytest.raises(TargetTransientError) as caught:
        listenbrainz.ListenBrainz("listener", session, token=TOKEN).set_feedback(MBID, 1)
    assert TOKEN not in str(caught.value)
    assert session.post.call_count == 1


@pytest.mark.parametrize("bad", ["", "mbid:invalid", "msid:" + MBID + "x",
    "https://musicbrainz.org/release/" + MBID, "https://musicbrainz.org/artist/" + MBID,
    "https://musicbrainz.org.evil.example/recording/" + MBID,
    "https://musicbrainz.org/recording/" + MBID + "/edit", True])
def test_invalid_references_never_reach_token_validation_or_feedback(bad):
    session = Mock()
    api = listenbrainz.ListenBrainz("listener", session, token=TOKEN)
    with pytest.raises(ValueError):
        api.set_feedback(bad, 1)
    assert session.mock_calls == []


def test_recording_reference_forms_are_distinct_and_canonical():
    assert normalize_track_reference("listenbrainz", MBID.upper()) == "mbid:" + MBID
    assert normalize_track_reference("listenbrainz", "msid:" + MSID) == "msid:" + MSID
    assert normalize_track_reference("listenbrainz", "https://musicbrainz.org/recording/" + MBID + "?x=1") == "mbid:" + MBID


@pytest.mark.parametrize("body,expected", [
    ({}, None),
    ({"recording_mbid": MBID, "recording_name": "Song", "artist_credit_name": "Artist"}, "mbid:" + MBID),
    ({"recording_mbid": MBID, "recording_name": "Song", "artist_credit_name": "Someone Else"}, None),
    ({"recording_mbid": MBID, "recording_name": "Song (Live)", "artist_credit_name": "Artist"}, None),
    ({"recording_mbid": MBID, "recording_name": "Other Song", "artist_credit_name": "Artist"}, None),
])
def test_resolver_checks_metadata_and_caches_only_confirmed_lookups(body, expected):
    session = Mock()
    session.get.side_effect = [valid_token(), response(body)]
    target = ListenBrainzTarget(listenbrainz.ListenBrainz("listener", session, token=TOKEN))
    cache = {"search": {}, "isrc": {}}
    track = {"name": "Song", "artists": ["Artist"], "_raw": {"album": "Album"}}
    assert target.resolve(track, cache) == (expected, "search")
    assert target.resolve(track, cache) == (expected, "search")
    assert session.get.call_count == 2
    assert session.get.call_args.kwargs["params"] == {
        "recording_name": "Song", "artist_name": "Artist", "release_name": "Album",
    }
    session.post.assert_not_called()


@pytest.mark.parametrize("body", [
    {"recording_mbid": MBID}, {"recording_mbid": "not-an-id", "recording_name": "Song", "artist_credit_name": "Artist"},
    {"recording_mbid": MBID, "recording_name": "", "artist_credit_name": "Artist"},
])
def test_malformed_lookup_is_not_saved_as_a_failed_match(body):
    api = Mock()
    api.lookup_recording.return_value = body
    cache = {"search": {}, "isrc": {}}
    with pytest.raises((RuntimeError, ValueError)):
        ListenBrainzTarget(api).resolve({"name": "Song", "artists": ["Artist"]}, cache)
    assert cache["search"] == {}


def test_source_recording_ids_and_manual_choices_do_not_need_metadata_lookup():
    api = Mock()
    target = ListenBrainzTarget(api)
    cache = {"search": {}, "isrc": {}}
    assert target.resolve({"name": "Song", "artists": ["Artist"],
                           "_raw": {"recording_mbid": MBID}}, cache)[0] == "mbid:" + MBID
    api.lookup_recording.assert_not_called()
    with pytest.raises(ValueError):
        target.add_favorite_tracks([MBID, "broken"])
    api.set_feedback.assert_not_called()


def test_incomplete_source_metadata_does_not_lookup_or_cache_an_empty_key():
    api = Mock()
    target = ListenBrainzTarget(api)
    cache = {"search": {}, "isrc": {}}
    assert target.resolve({"name": "Song", "artists": [""]}, cache) == (None, "search")
    assert target.resolve({"recording_mbid": MBID}, cache)[0] == "mbid:" + MBID
    assert target.resolve({"recording_mbid": SECOND_MBID}, cache)[0] == "mbid:" + SECOND_MBID
    assert cache["search"] == {}
    api.lookup_recording.assert_not_called()


def test_error_envelope_is_not_a_negative_lookup_result():
    session = Mock()
    session.get.side_effect = [valid_token(), response({"error": "temporarily unavailable"})]
    cache = {"search": {}, "isrc": {}}
    target = ListenBrainzTarget(listenbrainz.ListenBrainz("listener", session, token=TOKEN))
    with pytest.raises(TargetTransientError, match="incomplete recording data"):
        target.resolve({"name": "Song", "artists": ["Artist"]}, cache)
    assert cache["search"] == {}


def test_public_reads_validation_lookup_and_feedback_share_the_rate_budget(monkeypatch):
    now, starts = [100.0], []
    def sleep(delay):
        now[0] += delay
    monkeypatch.setattr(listenbrainz, "_REQUESTS", listenbrainz._RequestGate(clock=lambda: now[0], sleep=sleep))
    session = Mock()
    def get(url, **kwargs):
        starts.append(now[0])
        if url.endswith("/validate-token"):
            return valid_token()
        if url.endswith("/lookup/"):
            return response({})
        assert "Authorization" not in kwargs["headers"]
        return response({"feedback": [], "offset": 0, "total_count": 0})
    session.get.side_effect = get
    session.post.side_effect = lambda *a, **kw: starts.append(now[0]) or response({"status": "ok"})
    api = listenbrainz.ListenBrainz("listener", session, token=TOKEN)
    api.feedback_page()
    api.lookup_recording("Artist", "Song")
    api.set_feedback(MBID, 1)
    assert starts == [100, 101, 102, 103]


def test_profile_token_is_optional_private_isolated_and_cleared_on_username_change(tmp_path, monkeypatch):
    monkeypatch.setattr(listenbrainz.ListenBrainz, "feedback_page", lambda *a, **kw: ([], 0))
    checked = []
    def validate(api):
        checked.append((api.user, api.token))
    monkeypatch.setattr(listenbrainz.ListenBrainz, "validate_token", validate)
    settings = SettingsStore(dir=tmp_path)
    profiles = AccountProfileStore(settings)
    first = profiles.create("listenbrainz", "First")
    second = profiles.create("listenbrainz", "Second")
    store = profiles.settings_for(first.id)
    conn = ListenBrainzConnector(store)
    assert conn.submit({"LISTENBRAINZ_USER": "listener"}).capabilities == {"library_read"}
    writer = {"library_read", "library_write", "favorites_write"}
    assert conn.submit({"LISTENBRAINZ_TOKEN": TOKEN}).capabilities == writer
    assert conn.submit({"LISTENBRAINZ_USER": "LISTENER"}).capabilities == writer
    assert checked == [("listener", TOKEN), ("LISTENER", TOKEN)]
    assert settings.get("LISTENBRAINZ_TOKEN") is None
    with profiles.activate(second.id):
        assert listenbrainz.ListenBrainz("second").token == ""
    with TestClient(create_app(settings=settings)) as client:
        row = next(row for row in client.get("/api/accounts").json() if row["id"] == first.id)
        field = next(f for f in row["fields"] if f["key"] == "LISTENBRAINZ_TOKEN")
        assert field["secret"] and field["configured"] and field["value"] == ""
        assert row["capabilities"]["favorites_write"] and row["capabilities"]["library_write"]
        assert row["supports_playlists"] and row["transferable"]
        assert TOKEN not in str(row)
    assert conn.submit({"LISTENBRAINZ_USER": "another"}).capabilities == {"library_read"}
    assert store.get("LISTENBRAINZ_TOKEN") is None
    conn.submit({"LISTENBRAINZ_TOKEN": TOKEN})
    conn.disconnect()
    assert not store.get("LISTENBRAINZ_USER") and not store.get("LISTENBRAINZ_TOKEN")


def test_tidal_favorites_preview_love_repeat_and_optional_unlove(tmp_path):
    # Real provider adapters and reconciliation; the two HTTP boundaries use
    # deterministic protocol responses and never change an external account.
    source = TidalTarget.__new__(TidalTarget)
    source.country, source._token_scopes = "US", {"r_usr"}
    included = [{"type": "tracks", "id": "123", "attributes": {
        "title": "Song", "duration": "PT3M", "isrc": "USAAA2600001"},
        "relationships": {"artists": {"data": [{"type": "artists", "id": "a"}]}}},
        {"type": "artists", "id": "a", "attributes": {"name": "Artist"}}]
    included.append({**included[0], "id": "124", "attributes": {"title": "Keep", "duration": "PT3M"}})
    source_rows = [{"type": "tracks", "id": "123", "meta": {"addedAt": "2026-10-01T00:00:00Z"}}]
    source_rows.append({"type": "tracks", "id": "124", "meta": {"addedAt": "2026-10-02T00:00:00Z"}})
    source._pages = lambda path, params: iter([{"data": list(source_rows), "included": included}])
    source.cache_file = str(tmp_path / "tidal.json")
    # An unliked track TIDAL still offers is a user removal, not a delisting.
    source.search_candidates = lambda query, *, limit=5: [{"id": "123", "name": "Song", "artists": ["Artist"]}]
    stored, writes = [], []
    session = Mock()
    def get(url, **kwargs):
        if url.endswith("/validate-token"):
            return valid_token()
        if url.endswith("/metadata/lookup/"):
            name = kwargs["params"]["recording_name"]
            return response({"recording_mbid": MBID if name == "Song" else SECOND_MBID,
                             "recording_name": name, "artist_credit_name": "Artist"})
        assert url.endswith("/get-feedback")
        return response({"feedback": list(stored), "offset": 0, "total_count": len(stored)})
    def post(url, **kwargs):
        assert url.endswith("/feedback/recording-feedback")
        body = kwargs["json"]
        writes.append(body)
        stored[:] = [row for row in stored if row["recording_mbid"] != body["recording_mbid"]]
        if body["score"] == 1:
            stored.append({"recording_mbid": body["recording_mbid"], "score": 1,
                           "track_metadata": {"track_name": "Song" if body["recording_mbid"] == MBID else "Keep",
                                              "artist_name": "Artist"}})
        return response({"status": "ok"})
    session.get.side_effect, session.post.side_effect = get, post
    target = ListenBrainzTarget(listenbrainz.ListenBrainz("listener", session, token=TOKEN))
    target.cache_file = str(tmp_path / "listenbrainz.json")
    opts = parse_args([])
    opts.sync_playlists, opts.liked_tracks = False, True
    opts.liked_routes = {"listenbrainz": {"kind": "native"}}
    songs = archive.connect(str(tmp_path / "songs.db"))
    def read(resource):
        return [{**runner._normalize(row, "tidal"), "id": row["id"]} for row in source.resource_tracks(resource)]
    def run(execute=True):
        opts.execute = execute
        return runner.run_target(target, [], read, songs, opts, source=source)
    try:
        preview = run(False)
        assert preview["added"] == 2 and writes == []
        first, second = run(), run()
        assert first["added"] == 2 and first["failed"] == first["missing"] == 0
        assert second["added"] == second["removed"] == second["failed"] == 0
        assert writes == [{"recording_mbid": MBID, "score": 1}, {"recording_mbid": SECOND_MBID, "score": 1}]
        source_rows.pop(0)
        opts.max_removals = 0
        assert run()["removed"] == 0 and len(writes) == 2
        opts.max_removals = 5
        assert run()["removed"] == 1
        assert writes[-1] == {"recording_mbid": MBID, "score": 0}
        assert run()["removed"] == 0
    finally:
        songs.close()
