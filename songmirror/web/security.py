"""Browser-origin admission and request limits for the local control plane."""

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

MAX_REQUEST_BYTES = 10 * 1024 * 1024 + 64 * 1024


class RequestSecurity:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

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
        headers = {}
        for key, value in scope["headers"]:
            headers.setdefault(key.lower(), []).append(value.decode("latin-1"))
        hosts = headers.get(b"host", [])
        if len(hosts) != 1 or not self._allowed_host(hosts[0]):
            return await JSONResponse({"detail": "Unrecognized request host."}, status_code=400)(scope, receive, send)
        mutation = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if mutation:
            origins = headers.get(b"origin", [])
            expected = {f"{scope['scheme']}://{hosts[0]}".lower()}
            public = urlsplit(self._public_url())
            if public.scheme in {"http", "https"} and public.netloc:
                expected.add(f"{public.scheme}://{public.netloc}".lower())
            cross_site = headers.get(b"sec-fetch-site", [""])[0] in {"cross-site", "same-site"}
            if (origins and (len(origins) != 1 or origins[0].lower() not in expected)) or (
                not origins and cross_site
            ):
                return await JSONResponse({"detail": "Cross-origin control requests are not allowed."}, status_code=403)(scope, receive, send)
            # Buffer only a bounded body before FastAPI resolves File/Form dependencies.
            try:
                lengths = headers.get(b"content-length", [])
                if len(lengths) > 1 or (lengths and (int(lengths[0]) < 0 or int(lengths[0]) > MAX_REQUEST_BYTES)):
                    raise ValueError
                body = bytearray()
                async with asyncio.timeout(60):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                            raise ValueError
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except (ValueError, TimeoutError):
                return await JSONResponse({"detail": "Request body too large or incomplete."}, status_code=413)(scope, receive, send)
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)
