"""Last.fm client, signed auth, and the read-plus-loves target adapter."""

import hashlib

import pytest

from songmirror import lastfm as lf
from songmirror.engine.matching import track_key
from songmirror.engine.targets.base import (
    TargetAuthError,
    TargetCapabilityError,
    TargetTransientError,
)
from songmirror.engine.targets.lastfm import (
    ID_SEP,
    LastfmTarget,
    compose_id,
    split_id,
)


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Session:
    """Stand-in for `requests` returning a scripted (status, payload) sequence."""

    def __init__(self, *pages):
        self._pages = list(pages)
        self.calls = []
        self.posts = []

    def _next(self):
        status, payload = self._pages.pop(0) if self._pages else (200, {})
        return _Response(status, payload)

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append(dict(params or {}))
        return self._next()

    def post(self, url, data=None, timeout=None, headers=None):
        self.posts.append(dict(data or {}))
        return self._next()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(lf, "polite_sleep", lambda base: None)


def _client(*pages, secret="", sk=""):
    return lf.Lastfm(api_key="k", api_secret=secret, user="u", session_key=sk,
                     session=_Session(*pages))


def _loved(tracks, total_pages=1):
    return (200, {"lovedtracks": {"track": tracks,
                                  "@attr": {"totalPages": str(total_pages), "total": "9"}}})


# -- client reads ------------------------------------------------------------


def test_loved_tracks_walk_every_page():
    first = _loved([{"name": "A", "artist": {"name": "X"}, "date": {"uts": "1700000000"}},
                    {"name": "B", "artist": {"name": "Y"}}], total_pages=2)
    second = _loved([{"name": "C", "artist": {"name": "Z"}}], total_pages=2)
    client = _client(first, second)

    rows = client.loved_tracks()

    assert [r["name"] for r in rows] == ["A", "B", "C"]
    assert [call["page"] for call in client._session.calls] == [1, 2]
    assert rows[0]["added_at"].startswith("2023-11-14")
    assert rows[1]["added_at"] is None


def test_single_track_collection_is_not_wrapped_in_a_list():
    client = _client(_loved({"name": "Only", "artist": {"name": "X"}}))

    assert [r["name"] for r in client.loved_tracks()] == ["Only"]


def test_recent_tracks_artist_uses_text_key_and_skips_nowplaying():
    payload = (200, {"recenttracks": {"track": [
        {"name": "Live", "artist": {"#text": "Band"}, "@attr": {"nowplaying": "true"}},
        {"name": "Done", "artist": {"#text": "Band"}, "date": {"uts": "1700000000"}},
    ], "@attr": {"totalPages": "1"}}})

    rows = _client(payload).recent_tracks()

    assert [r["name"] for r in rows] == ["Done"]
    assert rows[0]["artist"] == "Band"


def test_top_tracks_are_ranked_undated_and_carry_duration():
    payload = (200, {"toptracks": {"track": [
        {"name": "Hit", "artist": {"name": "X"}, "duration": "215"},
        {"name": "Nodur", "artist": {"name": "X"}, "duration": "0"},
    ], "@attr": {"totalPages": "1"}}})

    rows = _client(payload).top_tracks("7day")

    assert rows[0]["duration_ms"] == 215_000
    assert rows[1]["duration_ms"] is None
    assert all(r["added_at"] is None for r in rows)


def test_no_row_ever_carries_an_isrc():
    """Last.fm has no ISRC anywhere in user.*; matching must not expect one."""
    rows = _client(_loved([{"name": "A", "artist": {"name": "X"}}])).loved_tracks()

    assert "isrc" not in rows[0]


def test_unknown_period_is_rejected_before_any_request():
    client = _client()

    with pytest.raises(lf.LastfmError):
        client.top_tracks("2week")
    assert client._session.calls == []


def test_total_reads_the_envelope_without_walking():
    client = _client(_loved([{"name": "A", "artist": {"name": "X"}}], total_pages=7))

    assert client.loved_total() == 9
    assert client._session.calls[0]["limit"] == 1


# -- client errors -----------------------------------------------------------


@pytest.mark.parametrize("code", sorted(lf._AUTH_CODES))
def test_auth_error_envelopes_raise_auth_and_keep_the_code(code):
    with pytest.raises(lf.LastfmAuthError) as caught:
        _client((200, {"error": code, "message": "nope"})).loved_tracks()
    assert caught.value.code == code


@pytest.mark.parametrize("code", sorted(lf._RETRY_CODES))
def test_retryable_error_envelopes_raise_transient(code):
    with pytest.raises(lf.LastfmTransient):
        _client((200, {"error": code, "message": "later"})).loved_tracks()


@pytest.mark.parametrize("status", sorted(lf._RETRY_STATUS))
def test_retryable_status_codes_raise_transient(status):
    with pytest.raises(lf.LastfmTransient):
        _client((status, {})).loved_tracks()


def test_invalid_track_stays_a_plain_error_not_an_auth_failure():
    """Code 6 means a bad track name on a write, so it must not be fatal auth."""
    with pytest.raises(lf.LastfmError) as caught:
        _client((200, {"error": lf.INVALID_TRACK, "message": "bad"})).loved_tracks()
    assert not isinstance(caught.value, lf.LastfmAuthError)
    assert caught.value.code == lf.INVALID_TRACK


def test_non_json_body_raises_plain_error():
    with pytest.raises(lf.LastfmError):
        _client((200, None)).loved_tracks()


# -- signing and the session flow --------------------------------------------


def test_signature_orders_params_and_appends_the_secret():
    params = {"method": "auth.getSession", "api_key": "k", "token": "t"}

    expected = hashlib.md5(b"api_keykmethodauth.getSessiontokentsecret").hexdigest()

    assert lf.sign(params, "secret") == expected


def test_signature_excludes_format_and_the_signature_itself():
    base = {"method": "m", "api_key": "k"}

    assert lf.sign(base, "s") == lf.sign({**base, "format": "json", "api_sig": "x"}, "s")


def test_auth_url_carries_the_key_and_callback():
    url = lf.auth_url("abc", "http://127.0.0.1:8888/callback")

    assert url.startswith(lf.AUTH_URL + "?")
    assert "api_key=abc" in url
    assert "cb=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback" in url


def test_get_session_returns_key_and_username_and_signs_the_call():
    session = _Session((200, {"session": {"key": "sk-1", "name": "ahnaf"}}))

    assert lf.get_session("k", "secret", "tok", session=session) == ("sk-1", "ahnaf")
    sent = session.calls[0]
    assert sent["token"] == "tok"
    assert sent["api_sig"] == lf.sign(
        {"method": "auth.getSession", "api_key": "k", "token": "tok"}, "secret")


def test_get_session_rejects_a_response_without_a_key():
    session = _Session((200, {"session": {"name": "ahnaf"}}))

    with pytest.raises(lf.LastfmError):
        lf.get_session("k", "secret", "tok", session=session)


def test_unauthenticated_reads_send_no_session_key():
    client = _client(_loved([]))
    assert client.authenticated is False

    client.loved_tracks()

    assert "sk" not in client._session.calls[0]
    assert "api_sig" not in client._session.calls[0]


def test_authenticated_reads_are_signed_so_a_private_profile_is_readable():
    client = _client(_loved([]), secret="secret", sk="sk-1")
    assert client.authenticated is True

    client.loved_tracks()

    sent = client._session.calls[0]
    assert sent["sk"] == "sk-1"
    assert sent["api_sig"]
    assert sent["format"] == "json"


# -- client writes -----------------------------------------------------------


def test_love_posts_a_signed_body():
    client = _client((200, {"status": "ok"}), secret="secret", sk="sk-1")

    client.love("X", "Song")

    assert client._session.calls == []  # a write is never a GET
    body = client._session.posts[0]
    assert body["method"] == "track.love"
    assert (body["artist"], body["track"]) == ("X", "Song")
    assert body["sk"] == "sk-1"
    assert body["api_sig"]


def test_unlove_posts_too():
    client = _client((200, {}), secret="secret", sk="sk-1")

    client.unlove("X", "Song")

    assert client._session.posts[0]["method"] == "track.unlove"


def test_writes_without_a_session_key_fail_before_any_request():
    client = _client(secret="secret")

    with pytest.raises(lf.LastfmAuthError):
        client.love("X", "Song")
    assert client._session.posts == []


def test_track_info_returns_the_canonical_spelling():
    payload = (200, {"track": {"name": "Song", "artist": {"name": "The X"}}})

    assert _client(payload).track_info("x", "song") == ("The X", "Song")


def test_track_info_returns_none_for_an_unknown_track():
    payload = (200, {"error": lf.INVALID_TRACK, "message": "Invalid track name"})

    assert _client(payload).track_info("x", "nope") is None


# -- target ------------------------------------------------------------------


class _Api:
    def __init__(self, rows=(), error=None, authenticated=True, corrected=None):
        self._rows = list(rows)
        self._error = error
        self.authenticated = authenticated
        self._corrected = corrected
        self.periods = []
        self.loved = []
        self.unloved = []
        self.info_calls = []

    def _answer(self):
        if self._error:
            raise self._error
        return list(self._rows)

    def loved_tracks(self):
        return self._answer()

    def recent_tracks(self):
        return self._answer()

    def top_tracks(self, period):
        self.periods.append(period)
        return self._answer()

    def track_info(self, artist, name):
        self.info_calls.append((artist, name))
        if self._error:
            raise self._error
        return self._corrected

    def love(self, artist, name):
        if self._error:
            raise self._error
        self.loved.append((artist, name))

    def unlove(self, artist, name):
        if self._error:
            raise self._error
        self.unloved.append((artist, name))


def _target(api=None):
    return LastfmTarget(client=api if api is not None else _Api())


def test_id_round_trips_artist_and_title():
    assert split_id(compose_id("X", "Song")) == ("X", "Song")
    assert split_id("no separator") == ("", "")
    assert ID_SEP not in "X" + "Song"


def test_seven_virtual_playlists_and_loved_is_the_favorites_resource():
    """Loved Tracks is the native favorites collection, as on every other
    provider, so it is not also listed as a playlist."""
    target = _target()
    playlists = target.list_playlists()

    ids = {p["id"] for p in playlists.values()}
    assert len(playlists) == 7
    assert "recent" in ids
    assert sum(1 for i in ids if i.startswith("top:")) == 6
    assert target.favorite_tracks_id not in ids
    assert target.favorite_tracks_resource()["name"] == "Loved Tracks"
    assert all(not target.is_editable(p) for p in playlists.values())


def test_playlist_writes_still_raise_because_lastfm_has_no_playlists():
    target = _target()
    playlist = {"id": "recent", "name": "Recent Scrobbles"}

    assert target.supports_playlists is False
    with pytest.raises(TargetCapabilityError):
        target.create(playlist)
    with pytest.raises(TargetCapabilityError):
        target.add(playlist, ["x"])
    with pytest.raises(TargetCapabilityError):
        target.remove(playlist, {"id": "x"})


def test_tracks_are_identified_by_artist_and_title_not_mbid():
    """track.love addresses a track by artist and title, so the id has to
    round-trip to those even when an mbid is present."""
    api = _Api([{"name": "A", "artist": "X", "mbid": "mb-1"}])

    rows = _target(api).favorite_tracks()

    assert rows[0]["id"] == compose_id("X", "A")
    assert rows[0]["mbid"] == "mb-1"


def test_top_collection_id_selects_the_period():
    api = _Api([{"name": "A", "artist": "X"}])

    _target(api).playlist_tracks({"id": "top:3month"})

    assert api.periods == ["3month"]


def test_unknown_collection_raises_capability_error():
    with pytest.raises(TargetCapabilityError):
        _target().playlist_tracks({"id": "top:2week"})
    with pytest.raises(TargetCapabilityError):
        _target().playlist_tracks({"id": "nope"})


def test_client_failures_translate_to_engine_errors():
    with pytest.raises(TargetTransientError):
        _target(_Api(error=lf.LastfmTransient("429"))).favorite_tracks()
    with pytest.raises(TargetAuthError):
        _target(_Api(error=lf.LastfmAuthError("bad key"))).favorite_tracks()


def test_counts_are_best_effort_on_browse():
    class _Counts(_Api):
        def recent_total(self):
            raise lf.LastfmTransient("429")

        def top_total(self, period):
            return 5

    target = _target(_Counts())
    rows = target.hydrate_playlist_counts(target.browse_playlists())
    by_id = {row["id"]: row.get("count") for row in rows}

    assert by_id["recent"] is None
    assert by_id["top:overall"] == 5


# -- target: loves writing ---------------------------------------------------


def test_loving_requires_an_authorized_session():
    unauthorized = _target(_Api(authenticated=False))

    unauthorized.validate_favorite_tracks(write=False)  # reads stay allowed
    with pytest.raises(TargetCapabilityError):
        unauthorized.validate_favorite_tracks(write=True)
    with pytest.raises(TargetCapabilityError):
        unauthorized.validate_favorite_tracks(remove=True)

    _target(_Api()).validate_favorite_tracks(write=True, remove=True)


def test_add_favorite_tracks_loves_each_id():
    api = _Api()

    _target(api).add_favorite_tracks([compose_id("X", "Song"), compose_id("Y", "Two")])

    assert api.loved == [("X", "Song"), ("Y", "Two")]


def test_add_favorite_tracks_skips_an_unaddressable_id():
    api = _Api()

    _target(api).add_favorite_tracks(["legacy-id", compose_id("X", "Song")])

    assert api.loved == [("X", "Song")]


def test_remove_favorite_track_unloves_by_artist_and_title():
    api = _Api()

    _target(api).remove_favorite_track({"id": compose_id("X", "Song")})
    # A row carrying names but no composed id is still addressable.
    _target(api).remove_favorite_track({"name": "Two", "artist": "Y"})

    assert api.unloved == [("X", "Song"), ("Y", "Two")]


def test_a_rejected_title_is_skipped_rather_than_failing_the_collection():
    api = _Api(error=lf.LastfmError("Invalid track name", lf.INVALID_TRACK))

    _target(api).add_favorite_tracks([compose_id("X", "Ghost")])  # must not raise

    assert api.loved == []


def test_a_transient_write_failure_still_propagates():
    api = _Api(error=lf.LastfmTransient("429"))

    with pytest.raises(TargetTransientError):
        _target(api).add_favorite_tracks([compose_id("X", "Song")])


# -- target: resolve ---------------------------------------------------------


def test_resolve_uses_the_canonical_spelling_and_caches_it():
    api = _Api(corrected=("The X", "Song"))
    target = _target(api)
    cache = {"search": {}, "dirty": False}

    found, method = target.resolve({"name": "song", "artists": ["x"]}, cache)

    assert (found, method) == (compose_id("The X", "Song"), "search")
    assert api.info_calls == [("x", "song")]
    assert cache["search"][track_key("song", "x")] == found
    assert cache["dirty"] is True


def test_resolve_reuses_a_cached_answer_without_calling_out():
    api = _Api(corrected=("The X", "Song"))
    target = _target(api)
    key = track_key("song", "x")
    cache = {"search": {key: compose_id("The X", "Song")}, "dirty": False}

    found, _ = target.resolve({"name": "song", "artists": ["x"]}, cache)

    assert found == compose_id("The X", "Song")
    assert api.info_calls == []


def test_resolve_caches_a_miss_as_none():
    api = _Api(corrected=None)
    cache = {"search": {}, "dirty": False}

    found, _ = _target(api).resolve({"name": "ghost", "artists": ["nobody"]}, cache)

    assert found is None
    assert cache["search"][track_key("ghost", "nobody")] is None


def test_resolve_needs_both_a_title_and_an_artist():
    api = _Api(corrected=("X", "Song"))

    assert _target(api).resolve({"name": "", "artists": ["x"]}, {"search": {}})[0] is None
    assert _target(api).resolve({"name": "Song", "artists": []}, {"search": {}})[0] is None
    assert api.info_calls == []


# -- registry ----------------------------------------------------------------


def test_lastfm_is_registered_but_holds_no_playlists():
    from songmirror.engine import targets

    assert "lastfm" in targets._REGISTRY
    assert "lastfm" in targets._CLASSES
    assert targets.supports_playlists("lastfm") is False
    assert targets.supports_playlists("spotify") is True
    assert targets.is_peer("lastfm") is False
    assert targets.is_peer("tidal") is True
    # ISRC-rich providers seed identity first; Last.fm carries none, so it sorts last.
    assert targets.provider_ids()[-1] == "lastfm"


def test_lastfm_is_only_a_target_for_a_liked_tracks_job():
    """It has no playlists, so it belongs in a target list only when the job
    actually writes its favorites collection."""
    from songmirror.engine import targets

    playlists_only = type("O", (), {"liked_tracks": False, "account_profiles": None})()
    likes = type("O", (), {"liked_tracks": True, "account_profiles": None})()

    assert targets._writable("lastfm", playlists_only) is False
    assert targets._writable("lastfm", likes) is True
    assert targets._writable("tidal", playlists_only) is True


def test_a_dropped_playlistless_participant_is_announced(monkeypatch):
    """A job that names Last.fm among its providers must not lose it in
    silence: the pass says why it cannot mirror playlists there, or it looks like a sync that quietly does nothing."""
    from songmirror.engine import logs, targets
    from songmirror.engine.config import parse_args

    seen = []
    logs.set_sink(seen.append)
    try:
        opts = parse_args([])
        opts.providers = "spotify,lastfm"
        opts.sync_source = "spotify"
        assert targets.build_targets(opts) == []
        monkeypatch.setattr(targets, "build_one", lambda *args, **kwargs: None)
        targets.build_peers(opts, sp=None)
    finally:
        logs.set_sink(None)

    warns = [e for e in seen if e.kind == "warn" and e.tag == "lastfm"]
    assert len(warns) == 2  # once for the one-way target list, once for peers
    assert "left out of this pass" in warns[0].message
    assert "cannot receive playlist changes" in warns[0].message
    # A playlists-only job has no loved-tracks consolation to offer.
    assert "loved tracks still sync" not in warns[0].message


def test_run_target_skips_the_playlist_phase_for_a_playlistless_target(tmp_path):
    """A playlist-less participant that survives into the per-target loop (a
    combined playlists-plus-liked-tracks job) gets one skip note instead of a
    create failure per selected playlist."""
    from songmirror.engine import logs, runner
    from songmirror.engine.config import parse_args

    class Playlistless:
        name = "Last.fm"
        tag = "lastfm"
        source = "lastfm"
        cache_file = str(tmp_path / "cache.json")

        @classmethod
        def supports_playlists(cls):
            return False

    calls = []
    seen = []
    logs.set_sink(seen.append)
    try:
        opts = parse_args([])
        agg = runner.run_target(
            Playlistless(), [{"name": "Drive", "id": "p1"}],
            lambda playlist: calls.append(playlist), None, opts,
            source=type("S", (), {"source": "spotify", "name": "Spotify"})(),
        )
    finally:
        logs.set_sink(None)

    assert calls == []
    assert agg["failed"] == 0
    notes = [e for e in seen if e.kind == "note" and e.tag == "lastfm"]
    assert notes and "no playlists" in notes[0].message
    assert "1 skipped" in notes[0].message
