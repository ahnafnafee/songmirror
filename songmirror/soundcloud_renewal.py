"""Refresh a user-provided SoundCloud session through the signed-in website."""

import os
import re
import time
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Error as BrowserError, sync_playwright

from .browser_session import selected_headers, urls_in
from .soundcloud import SoundCloudAuthError, SoundCloudTransient

PAGE = "https://soundcloud.com/you/sets"
ORIGIN = "https://soundcloud.com"
_API_HOST = "api-v2.soundcloud.com"
_TIMEOUT_MS = 15_000


def _cookie_name(name):
    return (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name)
            and not name.startswith(("_ga", "_gid", "_fbp", "datadome")))


def parse_page_request(raw):
    if not isinstance(raw, str) or not raw or len(raw) > 128_000:
        raise ValueError("Paste the SoundCloud playlist page request for renewal.")
    pages = [urlsplit(url) for url in urls_in(raw)]
    if not any((url.scheme, url.netloc, url.path) == ("https", "soundcloud.com", "/you/sets")
               for url in pages):
        raise ValueError("Copy the document request from https://soundcloud.com/you/sets.")
    cookie = selected_headers(raw, {"cookie"}).get("cookie")
    if not cookie:
        match = re.search(r"(?:^|\s)(?:-b|--cookie)\s+(?:'([^']*)'|\"([^\"]*)\")", raw)
        if match:
            cookie = next(group for group in match.groups() if group is not None)
    cookies = {}
    for part in (cookie or "").split(";"):
        name, _, value = part.strip().partition("=")
        if _cookie_name(name) and re.fullmatch(r"[!-~]{1,4096}", value):
            cookies[name] = {"name": name, "value": value, "url": ORIGIN + "/", "secure": True}
    if not cookies:
        raise ValueError("The SoundCloud playlist page request contains no cookies.")
    return list(cookies.values())


def renew_on_site(cookies, old_authorization, client_id):
    found = []

    def observe(request):
        url = urlsplit(request.url)
        if url.scheme != "https" or url.netloc != _API_HOST:
            return
        authorization = request.header_value("authorization") or ""
        if authorization.startswith("OAuth ") and authorization != old_authorization:
            client = parse_qs(url.query).get("client_id", [client_id])[0]
            found.append((authorization, client))

    names = ("PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "LOCALAPPDATA",
             "TMP", "TEMP", "TMPDIR", "LANG", "PLAYWRIGHT_BROWSERS_PATH")
    env = {name: os.environ[name] for name in names if name in os.environ}
    try:
        with TemporaryDirectory(prefix="songmirror-soundcloud-") as scratch, sync_playwright() as driver:
            env.update(XDG_CONFIG_HOME=scratch, XDG_CACHE_HOME=scratch)
            browser = driver.chromium.launch(
                channel="chromium", headless=True, env=env, timeout=_TIMEOUT_MS,
                chromium_sandbox=os.getenv("SONGMIRROR_CONTAINER") != "1",
            )
            try:
                context = browser.new_context(accept_downloads=False)
                context.add_cookies(cookies)
                context.on("request", observe)
                page = context.new_page()
                response = page.goto(PAGE, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
                if response is not None and (response.status == 429 or response.status >= 500):
                    raise SoundCloudTransient("SoundCloud could not load the playlist page for renewal.")
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    parts = urlsplit(page.url)
                    if ((parts.scheme, parts.netloc) != ("https", "soundcloud.com")
                            or parts.path.startswith(("/signin", "/login"))
                            or (response is not None and response.status in (401, 403))
                            or "captcha" in page.title().casefold()):
                        raise SoundCloudAuthError("Sign in to SoundCloud again and paste fresh browser requests.")
                    state = [cookie for cookie in context.cookies(ORIGIN) if _cookie_name(cookie["name"])]
                    if found:
                        return (*found[-1], state)
                    for cookie in state:
                        authorization = "OAuth " + cookie["value"]
                        if cookie["name"] == "oauth_token" and authorization != old_authorization:
                            return authorization, client_id, state
                    page.wait_for_timeout(250)
            finally:
                browser.close()
    except BrowserError:
        raise SoundCloudTransient("Chromium could not complete SoundCloud session renewal.") from None
    raise SoundCloudAuthError("SoundCloud did not renew the session. Sign in again and paste fresh browser requests.")
