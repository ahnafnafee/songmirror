"""Browser-origin admission and request limits for the local control plane."""

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlsplit

from starlette._utils import get_route_path
from starlette.requests import Request
from starlette.responses import JSONResponse

from .profile_auth import MAX_CREDENTIAL_BODY, PUBLIC_AUTH_ROUTES

MAX_REQUEST_BYTES = 10 * 1024 * 1024 + 64 * 1024
_PRIVATE_NAMESPACES = {"api", "events", "oauth", "docs", "redoc", "openapi.json"}
_CREDENTIAL_PATHS = {"/api/auth/login", "/api/auth/setup"}
_DOC_UI_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}

RESPONSE_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"no-referrer",
    b"content-security-policy": (
        b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        b"img-src 'self' https: http: data: blob:; font-src 'self'; connect-src 'self'; "
        b"object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    ),
}


class RequestSecurity:
    def __init__(self, app, settings, profile_auth):
        self.app, self.settings = app, settings
        self.profile_auth = profile_auth

    def _public_url(self):
        return self.settings.get("SONGMIRROR_PUBLIC_URL") or os.getenv("SONGMIRROR_PUBLIC_URL", "")

    def _allowed_host(self, host):
        names = {"localhost", socket.gethostname().lower()}
        names.update(part.strip().lower().rstrip(".") for part in
                     os.getenv("SONGMIRROR_ALLOWED_HOSTS", "").split(",") if part.strip())
        try:
            names.add(urlsplit(self._public_url()).hostname or "")
            parsed = urlsplit("//" + host)
            hostname = (parsed.hostname or "").lower().rstrip(".")
            parsed.port
            if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                return False
            if hostname in names:
                return True
            address = ipaddress.ip_address(hostname)
            return address.is_loopback or address in ipaddress.ip_network("10.0.0.0/8") or (
                address.version == 4 and any(address in net for net in (
                    ipaddress.ip_network("172.16.0.0/12"), ipaddress.ip_network("192.168.0.0/16")))) or (
                address.version == 6 and address in ipaddress.ip_network("fc00::/7"))
        except ValueError:
            return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = get_route_path(scope)
        private_path = path.lstrip("/").partition("/")[0] in _PRIVATE_NAMESPACES
        protected = False
        auth_request = path.startswith("/api/auth/")
        docs_ui = path.rstrip("/") in _DOC_UI_PATHS
        original_send = send

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                policies = dict(RESPONSE_HEADERS)
                if protected or auth_request:
                    policies[b"cache-control"] = b"no-store"
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", []) if key.lower() not in policies
                ] + list(policies.items())
            await original_send(message)

        send = secure_send
        headers = {}
        for key, value in scope["headers"]:
            headers.setdefault(key.lower(), []).append(value.decode("latin-1"))
        hosts = headers.get(b"host", [])
        if len(hosts) != 1 or not self._allowed_host(hosts[0]):
            return await JSONResponse({"detail": "Unrecognized request host."}, status_code=400)(scope, receive, send)
        method = scope["method"]
        mutation = method not in {"GET", "HEAD", "OPTIONS"}

        def owner_admission_error():
            nonlocal protected
            protected = private_path and self.profile_auth.enabled
            if protected and (method, path) not in PUBLIC_AUTH_ROUTES and not self.profile_auth.signed_in(Request(scope)):
                return JSONResponse(
                    {"detail": "Sign in to SongMirror to continue."}, status_code=401,
                    headers={"X-SongMirror-Auth-Required": "1"},
                )
            # A docs tab opened before setup would keep running its CDN scripts
            # under the same origin even after that browser gets an owner cookie.
            if docs_ui:
                return JSONResponse({"detail": "Use the OpenAPI schema at /openapi.json."}, status_code=404)
            if mutation and (protected or path == "/api/auth/setup") and headers.get(b"x-songmirror-request") != ["1"]:
                return JSONResponse({"detail": "Missing SongMirror request header."}, status_code=403)
            return None

        denied = owner_admission_error()
        if denied is not None:
            return await denied(scope, receive, send)

        if mutation:
            origins = headers.get(b"origin", [])
            expected = {f"{scope['scheme']}://{hosts[0]}".lower()}
            public = urlsplit(self._public_url())
            if public.scheme in {"http", "https"} and public.netloc:
                expected.add(f"{public.scheme}://{public.netloc}".lower())
            cross_site = any(site in {"cross-site", "same-site"} for site in headers.get(b"sec-fetch-site", []))
            if cross_site or (origins and (len(origins) != 1 or origins[0].lower() not in expected)):
                return await JSONResponse({"detail": "Cross-origin control requests are not allowed."}, status_code=403)(scope, receive, send)
            # Bound the body before resolving any FastAPI dependencies. Auth
            # endpoints only need a small JSON document.
            limit = MAX_CREDENTIAL_BODY if path.rstrip("/") in _CREDENTIAL_PATHS else MAX_REQUEST_BYTES
            try:
                lengths = headers.get(b"content-length", [])
                if len(lengths) > 1 or (lengths and not 0 <= int(lengths[0]) <= limit):
                    raise ValueError
                body = bytearray()
                async with asyncio.timeout(60):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > limit:
                            raise ValueError
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except (ValueError, TimeoutError):
                return await JSONResponse({"detail": "Request body too large or incomplete."}, status_code=413)(scope, receive, send)
            # Setup, sign-out or expiration may occur while a body is in transit.
            denied = owner_admission_error()
            if denied is not None:
                return await denied(scope, receive, send)
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)
