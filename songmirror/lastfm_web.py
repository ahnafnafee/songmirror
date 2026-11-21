"""Last.fm history and loves through a signed-in browser."""

import atexit
import json
import os
import re
import select
import subprocess
import sys
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus, unquote, urlencode, urljoin, urlsplit

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import sync_playwright

from .browser_session import header_pairs
from .engine.config import polite_sleep
from .lastfm import INVALID_TRACK, POLITE_BASE, LastfmAuthError, LastfmError, LastfmTransient

ORIGIN = "https://www.last.fm"
SESSION_FILENAME = "lastfm_browser.json"
COOKIE_NAMES = ("sessionid", "csrftoken")
TOP_PRESETS = {
    "7day": "LAST_7_DAYS",
    "1month": "LAST_30_DAYS",
    "3month": "LAST_90_DAYS",
    "6month": "LAST_180_DAYS",
    "12month": "LAST_365_DAYS",
    "overall": "ALL",
}
_PROFILE_LINK = 'a.auth-dropdown-toggle[href^="/user/"]'
_ROW = "table.chartlist .chartlist-row[data-playlist-row]:not(.chartlist__placeholder-row)"
_EXPIRED = "Last.fm browser session expired. Paste fresh headers from your signed-in Last.fm tab."
_VERIFICATION = "Last.fm requested browser verification. Open Last.fm in your browser and try again."
_TIMEOUT = 15_000
_COOKIE_VALUE = re.compile(r"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]{1,4096}")


def browser_session_path(get=os.getenv):
    default = Path(os.getenv("SONGMIRROR_DATA_DIR") or "data") / "profiles" / "profile_default_lastfm"
    return Path(get("LASTFM_BROWSER_SESSION_FILE") or default / SESSION_FILENAME)


def _cookies(values):
    if not isinstance(values, dict) or any(
        not isinstance(values.get(name), str) or not _COOKIE_VALUE.fullmatch(values[name])
        for name in COOKIE_NAMES
    ):
        raise ValueError("The Last.fm request needs its sessionid and csrftoken cookies")
    return {name: values[name] for name in COOKIE_NAMES}


def parse_browser_request(raw):
    """Accept copied request headers or cURL. Retain only two Last.fm cookies."""
    if not isinstance(raw, str) or len(raw) > 128_000:
        raise ValueError("Paste a single signed-in Last.fm request")
    command = re.match(r"""\s*curl(?:\.exe)?\s+['"](https?://[^'"\s]+)['"]""", raw)
    pairs = {str(name).strip().removeprefix(":").lower(): str(value).strip()
             for name, value in header_pairs(raw)}
    authority = re.search(r"(?im)^\s*:authority[ \t]*:[ \t]*([^\r\n]+)", raw)
    if authority:
        pairs["authority"] = authority[1].strip()
    supplied_url = command[1] if command else pairs.get("request url", "")
    if supplied_url:
        parts = urlsplit(supplied_url)
        valid = parts.scheme == "https" and parts.netloc == "www.last.fm"
    else:
        valid = (pairs.get("authority") or pairs.get("host")) == "www.last.fm"
    if not valid:
        raise ValueError("Copy a request to https://www.last.fm from your signed-in tab")
    cookie_header = pairs.get("cookie", "")
    if command and not cookie_header:
        cookie = re.search(r"""(?:^|\s)(?:-b|--cookie)\s+(['"])(.*?)\1""", raw)
        cookie_header = cookie[2] if cookie else ""
    parsed = {}
    for pair in cookie_header.split(";"):
        name, _, value = pair.strip().partition("=")
        if name in COOKIE_NAMES:
            if name in parsed:
                raise ValueError("Paste a single signed-in Last.fm request")
            parsed[name] = value
    return _cookies(parsed)


class _Browser:
    """Run Playwright on one thread. Every operation gets an isolated cookie jar."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lastfm-browser")
        self._driver = None
        self._browser = None
        self._display = None
        self._display_number = None
        self._browser_home = None

    def run(self, cookies, operation):
        try:
            return self._executor.submit(self._run, cookies, operation).result()
        except BrowserError:
            raise LastfmTransient("The Last.fm browser could not complete the request") from None

    def _run(self, cookies, operation):
        if not self._browser or not self._browser.is_connected():
            self._start()
        context = self._browser.new_context(locale="en-GB", timezone_id="UTC", accept_downloads=False)
        try:
            context.add_cookies([
                {"name": name, "value": value, "domain": ".last.fm" if name == "sessionid" else "www.last.fm",
                 "path": "/", "secure": True, "httpOnly": name == "sessionid", "sameSite": "Lax"}
                for name, value in cookies.items()
            ])
            page = context.new_page()
            page.set_default_timeout(_TIMEOUT)
            return operation(page)
        finally:
            context.close()

    def _start(self):
        if self._driver:
            self._driver.stop()
            self._driver = None
        # Browser processes do not need SongMirror's provider credentials.
        names = ("PATH", "HOME", "USERPROFILE", "LOCALAPPDATA", "SYSTEMROOT", "WINDIR",
                 "TEMP", "TMP", "TMPDIR", "LANG", "DISPLAY", "WAYLAND_DISPLAY",
                 "XDG_RUNTIME_DIR", "XAUTHORITY")
        env = {name: os.environ[name] for name in names if name in os.environ}
        if sys.platform.startswith("linux") and not env.get("DISPLAY"):
            env["DISPLAY"] = self._virtual_display()
        in_container = os.getenv("SONGMIRROR_CONTAINER") == "1"
        if in_container:
            if self._browser_home:
                self._browser_home.cleanup()
            self._browser_home = TemporaryDirectory(prefix="songmirror-chromium-")
            directory = self._browser_home.name
            env.update(HOME=directory, XDG_CONFIG_HOME=directory, XDG_CACHE_HOME=directory)
        self._driver = sync_playwright().start()
        try:
            self._browser = self._driver.chromium.launch(
                headless=False, env=env, timeout=_TIMEOUT,
                chromium_sandbox=not in_container,
            )
        except BrowserError:
            self._driver.stop()
            self._driver = None
            raise LastfmTransient("Could not start Chromium for Last.fm. Check the server's browser installation.") from None

    def _virtual_display(self):
        if self._display is not None and self._display.poll() is None:
            return self._display_number
        read_fd, write_fd = os.pipe()
        try:
            try:
                self._display = subprocess.Popen(
                    ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1280x900x24",
                     "-nolisten", "tcp"],
                    pass_fds=(write_fd,), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            finally:
                os.close(write_fd)
            if select.select([read_fd], [], [], 5)[0]:
                number = os.read(read_fd, 16).strip()
                if number.isdigit():
                    self._display_number = f":{int(number)}"
                    atexit.register(self._stop_display)
                    return self._display_number
            self._stop_display()
        except OSError:
            pass
        finally:
            os.close(read_fd)
        raise LastfmTransient("Could not start the virtual display for Last.fm")

    def _stop_display(self):
        if self._display is not None and self._display.poll() is None:
            self._display.terminate()


_BROWSER = _Browser()


def _navigate(page, path, *, referer=None):
    response = page.goto(ORIGIN + path, wait_until="domcontentloaded", referer=referer)
    if page.title().casefold() == "client challenge":
        try:
            page.wait_for_function("document.title.toLowerCase() !== 'client challenge'", timeout=5000)
        except BrowserError:
            raise LastfmAuthError(_VERIFICATION) from None
    origin = urlsplit(page.url)
    if (origin.scheme, origin.netloc) != ("https", "www.last.fm"):
        raise LastfmAuthError(_EXPIRED)
    code = response.status if response else None
    if code in (401, 403):
        raise LastfmAuthError(_EXPIRED)
    if code == 429 or (code and code >= 500):
        raise LastfmTransient(f"Last.fm returned HTTP {code}")
    return code


def _profile(page):
    profile = page.locator(_PROFILE_LINK).first
    link = profile.get_attribute("href") if profile.count() else None
    match = re.fullmatch(r"/user/([^/?#]+)/?", link or "")
    if not match:
        raise LastfmAuthError(_EXPIRED)
    return unquote(match[1])


def _timestamp(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%A %d %b %Y, %I:%M%p").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


_READ_PAGE = """(selector) => ({
    rows: Array.from(document.querySelectorAll(selector), row => ({
        name: row.querySelector('.chartlist-name a[href^="/music/"]')?.textContent.trim(),
        artist: row.querySelector('.chartlist-artist a')?.textContent.trim(),
        timestamp: row.querySelector('.chartlist-timestamp span[title]')?.title,
        nowPlaying: Boolean(row.closest('[class*="now-scrobbling"], [class*="now-playing"]')),
    })),
    next: document.querySelector('.pagination-next a')?.getAttribute('href'),
    total: Array.from(document.querySelectorAll('.metadata-title'))
        .find(label => ['Scrobbles', 'Tracks Scrobbled'].includes(label.textContent.trim()))
        ?.nextElementSibling?.textContent.trim(),
    lovedTitle: document.querySelector('.namespace--user_loved .content-top-header')?.textContent.trim(),
    hasLibrary: Boolean(document.querySelector('.namespace--user_library_overview, .library-fetch')),
})"""


class LastfmBrowser:
    """Same interface as the developer-key Last.fm client."""

    authenticated = True

    def __init__(self, cookies, user=None):
        self._cookies = _cookies(cookies)
        self.user = user

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            user = data["user"]
            if not isinstance(user, str) or not user:
                raise ValueError
            return cls(data["cookies"], user)
        except (OSError, TypeError, ValueError, KeyError):
            raise LastfmAuthError(_EXPIRED) from None

    def _run(self, operation):
        return _BROWSER.run(self._cookies, operation)

    def _check_profile(self, page):
        user = _profile(page)
        if self.user and self.user.casefold() != user.casefold():
            raise LastfmAuthError("This browser session belongs to a different Last.fm account")
        return user

    def display_name(self):
        def read(page):
            _navigate(page, "/home")
            return self._check_profile(page)
        return self._run(read)

    def _collection(self, collection, period=None, count=False):
        root = "/user/" + quote(self.user, safe="")
        if collection == "top":
            if period not in TOP_PRESETS:
                raise LastfmError(f"unknown Last.fm period {period!r}")
            path = root + "/library/tracks?" + urlencode({"date_preset": TOP_PRESETS[period]})
        else:
            path = root + ("/loved" if collection == "loved" else "/library")
        initial = urlsplit(path)

        def read(page):
            rows = []
            seen = set()
            target = path
            while target not in seen:
                seen.add(target)
                _navigate(page, target)
                self._check_profile(page)
                if urlsplit(page.url).path.casefold() != initial.path.casefold():
                    raise LastfmError("Last.fm did not return the requested collection")
                result = page.evaluate(_READ_PAGE, _ROW)
                if not result.get("lovedTitle" if collection == "loved" else "hasLibrary"):
                    raise LastfmError("Last.fm did not return the requested collection")
                if count:
                    value = result.get("total") or result.get("lovedTitle") or ""
                    digits = re.search(r"\d[\d,]*", value)
                    return int(digits[0].replace(",", "")) if digits else (0 if not result["rows"] else None)
                for row in result["rows"]:
                    if row["nowPlaying"]:
                        continue
                    if not row.get("name") or not row.get("artist"):
                        raise LastfmError("Last.fm returned a track without an artist or title")
                    rows.append({
                        "name": row["name"], "artist": row["artist"], "mbid": "",
                        "duration_ms": None, "added_at": _timestamp(row.get("timestamp")),
                    })
                if not result.get("next"):
                    return rows
                more = urlsplit(urljoin(ORIGIN + target, result["next"]))
                if (more.scheme, more.netloc, more.path) != ("https", "www.last.fm", initial.path):
                    raise LastfmError("Last.fm returned an invalid collection page")
                target = more.path + (f"?{more.query}" if more.query else "")
                polite_sleep(POLITE_BASE)
            raise LastfmError("Last.fm returned a repeated collection page")

        return self._run(read)

    def loved_tracks(self):
        return self._collection("loved")

    def loved_total(self):
        return self._collection("loved", count=True)

    def recent_tracks(self):
        return self._collection("recent")

    def recent_total(self):
        return self._collection("recent", count=True)

    def top_tracks(self, period):
        return self._collection("top", period)

    def top_total(self, period):
        return self._collection("top", period, count=True)

    def _track_form(self, page, artist, name):
        track = f"/music/{quote_plus(artist, safe='')}/_/{quote_plus(name, safe='')}"
        # Home initializes the signed-in session for track pages, which can
        # otherwise render their public version without an account's love form.
        _navigate(page, "/home")
        self._check_profile(page)
        if _navigate(page, track, referer=ORIGIN + "/home") == 404:
            return None
        self._check_profile(page)
        path = "/user/" + quote(self.user, safe="") + "/loved"
        form = page.locator(f'form[action="{path}" i][method="post"]').first
        return form if form.count() and form.locator('input[name="track_spelling_id"]').input_value() else None

    def track_info(self, artist, name):
        def read(page):
            form = self._track_form(page, artist, name)
            if form is not None:
                return tuple(form.locator(f'input[name="{field}"]').input_value() for field in ("artist", "track"))
            return None
        return self._run(read)

    def _write(self, artist, name, action):
        def write(page):
            form = self._track_form(page, artist, name)
            if form is None:
                raise LastfmError("Last.fm did not find the track", INVALID_TRACK)
            field = form.locator('input[name="action"]')
            current = field.input_value()
            if current not in ("love", "unlove"):
                raise LastfmError("Last.fm returned an unexpected track action")
            if current != action:
                return
            endpoint = ORIGIN + form.get_attribute("action")
            with page.expect_response(lambda res: res.url == endpoint and res.request.method == "POST") as request:
                form.locator('button[type="submit"]').click()
            status = request.value.status
            if status in (401, 403):
                raise LastfmAuthError(_VERIFICATION if status == 403 else _EXPIRED)
            if status == 429 or status >= 500:
                raise LastfmTransient(f"Last.fm returned HTTP {status}")
            if status >= 400:
                raise LastfmError(f"Last.fm returned HTTP {status}")
            replacement = "unlove" if action == "love" else "love"
            form.locator(f'input[name="action"][value="{replacement}"]').wait_for(state="attached")
        self._run(write)

    def love(self, artist, name):
        self._write(artist, name, "love")

    def unlove(self, artist, name):
        self._write(artist, name, "unlove")
