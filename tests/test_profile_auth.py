"""Owner sign-in protects the app's HTTP and streaming entry points."""

import asyncio
import json
import os
import re
from urllib.parse import urlencode

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from songmirror.engine.logs import Event
from songmirror.services.settings import SettingsStore
from songmirror.web import create_app, profile_auth
from songmirror.web.routers.events import events
from songmirror.web.security import RequestSecurity


HEADERS = {"X-SongMirror-Request": "1"}
CREDENTIALS = {"username": "owner", "password": "test owner passphrase"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head></head><body>SongMirror</body></html>")
    (dist / "favicon.png").write_bytes(b"public asset")
    monkeypatch.setattr("songmirror.web._DIST", dist)
    monkeypatch.setenv(profile_auth.USERNAME_KEY, CREDENTIALS["username"])
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, CREDENTIALS["password"])
    return create_app(settings=SettingsStore(dir=tmp_path / "data", project_env=False))


def _sign_in(client, credentials=CREDENTIALS):
    return client.post("/api/auth/login", headers=HEADERS, json=credentials)


def test_disabled_mode_keeps_legacy_api_available(tmp_path, monkeypatch):
    monkeypatch.setenv(profile_auth.USERNAME_KEY, "")
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, "")
    with TestClient(create_app(settings=SettingsStore(dir=tmp_path, project_env=False))) as client:
        assert client.get("/api/auth/session").json() == {"enabled": False, "authenticated": False}
        assert client.get("/api/settings").status_code == 200
        assert client.put("/api/settings", json={"DISPLAY_NAME": "Owner"}).status_code == 200
        assert client.post("/api/auth/login", json=CREDENTIALS).status_code == 404


def test_partial_configuration_stops_startup(tmp_path, monkeypatch):
    monkeypatch.setenv(profile_auth.USERNAME_KEY, "owner")
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, "")
    with pytest.raises(RuntimeError, match="Set SONGMIRROR_AUTH_USERNAME and SONGMIRROR_AUTH_PASSWORD together"):
        create_app(settings=SettingsStore(dir=tmp_path))


def test_public_shell_and_health_but_private_data(app):
    with TestClient(app) as client:
        marker = '<meta name="songmirror-auth" content="required">'
        for path in ("/", "/playlists", "/index.html"):
            shell = client.get(path)
            assert marker in shell.text
            assert shell.headers["cache-control"] == "no-store"
        assert client.get("/favicon.png").content == b"public asset"
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/api/auth/session").json() == {"enabled": True, "authenticated": False}
        assert client.post("/api/auth/setup", headers=HEADERS, json=CREDENTIALS).status_code == 409

        for method, path in (
            ("GET", "/api/accounts"),
            ("PUT", "/api/settings"),
            ("DELETE", "/api/playlists/spotify/playlist-1/tracks"),
            ("GET", "/api/playlists/spotify/export?format=json"),
            ("GET", "/api/playlist-backups/spotify/latest"),
            ("GET", "/events"),
            ("GET", "/oauth/spotify/callback?error=access_denied"),
            ("GET", "/oauth/spotify/start"),
            ("GET", "/openapi.json"),
        ):
            response = client.request(method, path, headers=HEADERS)
            assert response.status_code == 401, path
            assert response.headers["x-songmirror-auth-required"] == "1"
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-frame-options"] == "DENY"


def test_registered_routes_require_a_session_unless_explicitly_public(app):
    with TestClient(app) as client:
        assert _sign_in(client).status_code == 204
        paths = client.get("/openapi.json").json()["paths"]
        client.cookies.clear()
        public = profile_auth.PUBLIC_AUTH_ROUTES | {("GET", "/health"), ("GET", "/{full_path}")}
        for template, operations in paths.items():
            path = re.sub(r"\{[^}]+\}", "route-check", template)
            for method in operations:
                method = method.upper()
                if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"} or (method, template) in public:
                    continue
                result = client.request(method, path, headers=HEADERS)
                assert result.status_code == 401, (method, template)
                assert result.headers["x-songmirror-auth-required"] == "1"


def test_sign_in_issues_secure_cookie_and_sign_out_revokes_it(app):
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/api/auth/login", json=CREDENTIALS).status_code == 403
        failure = _sign_in(client, {"username": "owner", "password": "incorrect"})
        assert failure.status_code == 401
        assert "x-songmirror-auth-required" not in failure.headers
        assert "set-cookie" not in failure.headers

        success = _sign_in(client)
        assert success.status_code == 204
        cookie = success.headers["set-cookie"]
        for attribute in ("HttpOnly", "Max-Age=86400", "Path=/", "SameSite=lax", "Secure"):
            assert attribute in cookie
        assert client.get("/api/auth/session").json() == {"enabled": True, "authenticated": True}
        settings = client.get("/api/settings")
        assert settings.status_code == 200 and settings.headers["cache-control"] == "no-store"
        docs = client.get("/docs")
        assert docs.status_code == 404 and "cdn.jsdelivr.net" not in docs.headers["content-security-policy"]
        assert client.get("/openapi.json").status_code == 200
        assert profile_auth.PASSWORD_KEY not in settings.json()
        assert client.put("/api/settings", json={"DISPLAY_NAME": "Owner"}).status_code == 403
        assert client.put("/api/settings", headers=HEADERS, json={"DISPLAY_NAME": "Owner"}).status_code == 200
        assert client.put("/api/settings", headers=HEADERS, json={profile_auth.PASSWORD_KEY: "changed"}).status_code == 422
        token = client.cookies.get(profile_auth.COOKIE)
        assert client.post("/api/auth/logout").status_code == 403
        assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204
        assert client.cookies.get(profile_auth.COOKIE) is None
        client.cookies.set(profile_auth.COOKIE, token)
        assert client.get("/api/settings").status_code == 401


def test_provider_redirect_requires_same_owner_session_and_browser(app):
    with TestClient(app, base_url="https://testserver") as client:
        assert _sign_in(client).status_code == 204
        owner = client.cookies.get(profile_auth.COOKIE)
        profile = app.state.account_profiles.resolve("spotify").id
        attempts = app.state.connection_attempts
        # An authorization begun before owner sign-in was enabled cannot be claimed
        # through the start bridge, even by a currently signed-in browser.
        legacy = attempts.begin(profile, "redirect")
        assert client.get(f"/oauth/spotify/start?attempt={legacy}").status_code == 400
        nonce = attempts.begin(
            profile, "redirect", owner_session=owner,
            redirect_uri="https://testserver/oauth/spotify/callback",
        )
        attempts.configure(nonce, url="https://provider.invalid/authorize")
        start = f"/oauth/spotify/start?attempt={nonce}"
        callback = "/oauth/spotify/callback?" + urlencode({"state": nonce, "error": "access_denied"})
        assert client.get(callback).status_code == 400  # no bound browser cookie yet
        assert client.get(start, follow_redirects=False).status_code == 303

        # A separate valid owner session cannot finish someone else's attempt,
        # even if the same browser still has the provider-authorization cookie.
        assert _sign_in(client).status_code == 204
        assert client.get(callback).status_code == 400

        active_owner = client.cookies.get(profile_auth.COOKIE)
        fresh = attempts.begin(
            profile, "redirect", owner_session=active_owner,
            redirect_uri="https://testserver/oauth/spotify/callback",
        )
        attempts.configure(fresh, url="https://provider.invalid/authorize")
        assert client.get(f"/oauth/spotify/start?attempt={fresh}", follow_redirects=False).status_code == 303
        callback = "/oauth/spotify/callback?" + urlencode({"state": fresh, "error": "access_denied"})
        assert client.get(callback).status_code == 200
        assert client.get(callback).status_code == 400  # one-time OAuth state


def test_attempt_limit_and_session_expiry(app, monkeypatch):
    now = 0
    monkeypatch.setattr(profile_auth, "monotonic", lambda: now)
    with TestClient(app) as client:
        for _ in range(profile_auth.LOGIN_ATTEMPTS):
            assert _sign_in(client, {"username": "other", "password": "invalid"}).status_code == 401
        blocked = _sign_in(client)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == str(profile_auth.LOGIN_WINDOW)

        now += profile_auth.LOGIN_WINDOW
        signed_in = _sign_in(client)
        assert signed_in.status_code == 204
        assert "Secure" not in signed_in.headers["set-cookie"]
        now += profile_auth.SESSION_SECONDS
        assert client.get("/api/auth/session").json() == {"enabled": True, "authenticated": False}
        assert client.get("/api/settings").status_code == 401


def test_logout_ends_already_open_event_stream(app):
    async def scenario():
        async def receive():
            await asyncio.Event().wait()

        auth = app.state.profile_auth
        bus = app.state.bus
        bus.bind_loop(asyncio.get_running_loop())
        token = await auth.login("test", CREDENTIALS["username"], CREDENTIALS["password"])
        request = Request({
            "type": "http", "app": app, "headers": [(b"cookie", f"{profile_auth.COOKIE}={token}".encode())],
        }, receive)
        response = await events(request)
        stream = response.body_iterator
        assert await anext(stream) == ": connected\n\n"
        bus.publish(Event(0, "note", "sync", "visible while signed in"))
        assert "visible while signed in" in await anext(stream)
        auth.logout(request)
        bus.publish(Event(1, "note", "sync", "private after sign-out"))
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert not bus._subs

    asyncio.run(scenario())


def test_web_setup_issues_session_and_persists_only_password_hash(tmp_path, monkeypatch):
    monkeypatch.setenv(profile_auth.USERNAME_KEY, "")
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, "")
    store = SettingsStore(dir=tmp_path, project_env=False)
    app = create_app(settings=store)
    record = tmp_path / profile_auth.OWNER_FILE
    setup_code = app.state.profile_auth._setup_code
    setup_data = {**CREDENTIALS, "setup_code": setup_code}

    with TestClient(app) as client:
        assert client.get("/api/settings").status_code == 200
        assert client.post("/api/auth/setup", json=setup_data).status_code == 403
        assert setup_code not in client.get("/api/auth/session").text
        assert client.post("/api/auth/setup", headers=HEADERS, json=CREDENTIALS).status_code == 403
        assert client.post("/api/auth/setup", headers=HEADERS, content=b" " * 8193).status_code == 413
        assert client.post(
            "/api/auth/setup", headers={**HEADERS, "Origin": "http://elsewhere.invalid"}, json=setup_data,
        ).status_code == 403
        assert client.post(
            "/api/auth/setup", headers=HEADERS, json={**setup_data, "password": "short"},
        ).status_code == 400
        bad_input = client.post("/api/auth/setup", headers=HEADERS, json={"username": "", "password": CREDENTIALS["password"]})
        assert bad_input.status_code == 400
        assert CREDENTIALS["password"] not in bad_input.text
        assert not record.exists()

        setup = client.post("/api/auth/setup", headers=HEADERS, json=setup_data)
        assert setup.status_code == 204 and "HttpOnly" in setup.headers["set-cookie"]
        assert client.get("/api/auth/session").json() == {"enabled": True, "authenticated": True}
        assert client.get("/api/settings").status_code == 200
        cookie = client.cookies.get(profile_auth.COOKIE)
        client.cookies.clear()
        assert client.get("/api/settings").status_code == 401
        assert client.get("/events").status_code == 401
        assert client.post("/api/auth/setup", headers=HEADERS, json=CREDENTIALS).status_code == 409

    saved = record.read_text(encoding="utf-8")
    config = json.loads(saved)
    assert CREDENTIALS["password"] not in saved
    assert setup_code not in saved
    assert config["username"] == CREDENTIALS["username"]
    assert len(bytes.fromhex(config["password_hash"])) == 64
    if os.name != "nt":
        assert record.stat().st_mode & 0o077 == 0
    assert not store.load().get(profile_auth.PASSWORD_KEY)

    with TestClient(create_app(settings=store)) as restarted:
        restarted.cookies.set(profile_auth.COOKIE, cookie)
        assert restarted.get("/api/settings").status_code == 401
        assert _sign_in(restarted).status_code == 204
        assert restarted.get("/api/settings").status_code == 200


def test_only_one_overlapping_setup_can_create_owner(tmp_path, monkeypatch):
    monkeypatch.setenv(profile_auth.USERNAME_KEY, "")
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, "")
    workers = [profile_auth.ProfileAuth(tmp_path), profile_auth.ProfileAuth(tmp_path)]

    async def scenario():
        results = await asyncio.gather(
            *(worker.setup(f"owner{index}", CREDENTIALS["password"], worker._setup_code)
              for index, worker in enumerate(workers)),
            return_exceptions=True,
        )
        winner, = [index for index, result in enumerate(results) if isinstance(result, str)]
        assert results[1 - winner].status_code == 409
        for worker in workers:
            assert worker.enabled
            assert await worker.login("test", f"owner{winner}", CREDENTIALS["password"])
            assert await worker.login("test", f"owner{1 - winner}", CREDENTIALS["password"]) is None

    asyncio.run(scenario())


def test_invalid_saved_owner_file_blocks_startup(tmp_path, monkeypatch):
    monkeypatch.setenv(profile_auth.USERNAME_KEY, "")
    monkeypatch.setenv(profile_auth.PASSWORD_KEY, "")
    record = tmp_path / profile_auth.OWNER_FILE
    record.parent.mkdir()
    record.write_text('{"username":"owner"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Could not load the owner sign-in record"):
        create_app(settings=SettingsStore(dir=tmp_path))


@pytest.mark.parametrize("transition", ["setup", "sign-out"])
def test_waiting_mutation_is_rechecked_after_session_changes(tmp_path, transition):
    store = SettingsStore(dir=tmp_path, project_env=False)

    async def scenario():
        owner = None
        if transition == "sign-out":
            owner = profile_auth._Owner.create(CREDENTIALS["username"], CREDENTIALS["password"])
        auth = profile_auth.ProfileAuth(tmp_path, owner)
        headers = [(b"host", b"testserver"), (b"x-songmirror-request", b"1")]
        if owner:
            token = await auth.login("test", CREDENTIALS["username"], CREDENTIALS["password"])
            headers.append((b"cookie", f"{profile_auth.COOKIE}={token}".encode()))
        scope = {
            "type": "http", "method": "PUT", "scheme": "http",
            "path": "/api/settings", "headers": headers,
        }
        sent = []

        async def app(*_args):
            pytest.fail("A newly unauthorized mutation reached the app")

        async def receive():
            if owner:
                auth.logout(Request(scope))
            else:
                await auth.setup(CREDENTIALS["username"], CREDENTIALS["password"], auth._setup_code)
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message):
            sent.append(message)

        await RequestSecurity(app, store, auth)(scope, receive, send)
        assert sent[0]["status"] == 401
        assert (b"cache-control", b"no-store") in sent[0]["headers"]

    asyncio.run(scenario())
