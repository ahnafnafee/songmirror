"""Use Audiomack's signed-in web player for playlist and catalog requests."""

import os
import re
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright

from .base import TargetAuthError, TargetDirectoryIncompleteError, TargetTransientError
from .music_server import rows

ORIGIN = "https://audiomack.com"
LIBRARY_URL = ORIGIN + "/my-library/playlists"
SESSION_COOKIES = ("otoken", "osecret")
_API_HOST = "api.audiomack.com"
_TIMEOUT = 15_000
_PAGE_SIZE = 20

_REQUEST = """
async ({ endpoint, method, params, data }) => {
  // Reuse the live web player's OAuth request helper. Discover its module
  // from the installed bundle so chunk hashes and module IDs can change.
  const chunks = globalThis.webpackChunk_N_E;
  if (!Array.isArray(chunks)) return false;
  let runtime;
  chunks.push([[crypto.randomUUID()], {}, require => { runtime = require; }]);
  const matchesSigner = value => {
    if (typeof value !== 'function') return false;
    const source = Function.prototype.toString.call(value);
    return ['oauth_signature_method', 'cloudfrontHeaders', 'fetchOptions'].every(key => source.includes(key));
  };
  const matches = Object.entries(runtime?.m ?? {}).filter(([, factory]) => matchesSigner(factory));
  if (matches.length !== 1) return false;
  const request = Object.values(runtime(matches[0][0])).find(matchesSigner);
  if (!request) return false;
  // The response listener handles HTTP status codes, including empty replies.
  try {
    await request({ endpoint, params, bodyParams: data, noResponse: method === 'DELETE',
                    fetchOptions: { method, redirect: 'error' } });
  } catch (_) {}
  return true;
}
"""


def _signed_response(response, endpoint, token, *, method="GET"):
    url = urlsplit(response.url)
    return (response.request.method == method and (url.scheme, url.netloc) == ("https", _API_HOST)
            and url.path.removesuffix("/") == f"/v1/{endpoint}".removesuffix("/")
            and parse_qs(url.query).get("oauth_token") == [token])


def _check_status(response):
    if response.status in (401, 403):
        raise TargetAuthError("Audiomack rejected the signed-in browser session.")
    if response.status == 429 or response.status >= 500:
        raise TargetTransientError(f"Audiomack returned HTTP {response.status}.")
    if not response.ok:
        raise TargetDirectoryIncompleteError(f"Audiomack returned HTTP {response.status} for the request.")


def _body(response):
    _check_status(response)
    payload = response.json()
    if not isinstance(payload, dict):
        raise TargetDirectoryIncompleteError("Audiomack returned an invalid playlist response.")
    return payload


def _signed_call(page, token, endpoint, *, method="GET", params=None, data=None):
    with page.expect_response(lambda reply: _signed_response(reply, endpoint, token, method=method)) as result:
        if not page.evaluate(_REQUEST, {"endpoint": endpoint, "method": method,
                                       "params": params or {}, "data": data or {}}):
            raise TargetTransientError("SongMirror could not find the signing function in Audiomack's web player.")
    return result.value


def _open_library(context, token):
    page = context.new_page()
    page.set_default_timeout(_TIMEOUT)
    with page.expect_response(lambda response: _signed_response(response, "user/playlists/page/1", token)) as first:
        page.goto(LIBRARY_URL, wait_until="domcontentloaded")
    return page, _body(first.value)


def _browse(context, token):
    page, response = _open_library(context, token)
    viewer = _body(_signed_call(page, token, "user"))
    owner = str(viewer.get("id") or "")
    if not re.fullmatch(r"[1-9][0-9]{0,23}", owner):
        raise TargetAuthError("Audiomack could not verify the current account.")
    message = "Audiomack returned an incomplete playlist directory."
    batch = rows(response.get("results"), message)
    entries = list(batch)

    for page_number in range(2, 202):
        if len(batch) < _PAGE_SIZE:
            return [dict(entry, _owned=str(entry.get("artist_id")) == owner) for entry in entries]
        endpoint = f"user/playlists/page/{page_number}"
        with page.expect_response(lambda response: _signed_response(response, endpoint, token)) as next_page:
            page.get_by_role("button", name="Load More", exact=True).click()
        batch = rows(_body(next_page.value).get("results"), message)
        entries.extend(batch)
    raise TargetDirectoryIncompleteError("Audiomack returned too many playlist pages.")


@contextmanager
def _web_player(session):
    if not all(session.get(name) for name in SESSION_COOKIES):
        raise TargetAuthError("Connect Audiomack with a signed-in web page request.")
    env_keys = ("PATH", "SYSTEMROOT", "WINDIR", "USERPROFILE", "LOCALAPPDATA",
                "TMP", "TEMP", "TMPDIR", "LANG", "PLAYWRIGHT_BROWSERS_PATH")
    env = {name: os.environ[name] for name in env_keys if name in os.environ}
    try:
        with TemporaryDirectory(prefix="songmirror-audiomack-") as scratch, sync_playwright() as driver:
            env.update(XDG_CONFIG_HOME=scratch, XDG_CACHE_HOME=scratch)
            browser = driver.chromium.launch(
                channel="chromium", headless=True, env=env, timeout=_TIMEOUT,
                chromium_sandbox=os.getenv("SONGMIRROR_CONTAINER") != "1",
            )
            try:
                context = browser.new_context(locale="en-US", accept_downloads=False)
                context.add_cookies([{"name": name, "value": session[name], "url": ORIGIN}
                                     for name in SESSION_COOKIES])
                yield context
            finally:
                browser.close()
    except BrowserTimeout:
        raise TargetTransientError("The Audiomack web player did not finish the signed-in request.") from None
    except (BrowserError, ValueError):
        raise TargetTransientError("The Audiomack web player could not complete the signed-in request.") from None


def read_library(session):
    with _web_player(session) as context:
        return _browse(context, session["otoken"])


def read_playlist(session, identifier):
    if not re.fullmatch(r"[1-9][0-9]{0,23}", identifier):
        raise ValueError("Audiomack returned an invalid playlist ID.")
    endpoint = f"playlist/{identifier}/"
    token = session.get("otoken")
    with _web_player(session) as context:
        page, _ = _open_library(context, token)
        detail = _signed_call(page, token, endpoint)
        if detail.status == 404:
            return None
        result = _body(detail).get("results")
        if not isinstance(result, dict):
            raise TargetDirectoryIncompleteError("Audiomack did not return signed-in playlist details.")
        return result


def search_music(session, query, limit):
    token = session.get("otoken")
    with _web_player(session) as context:
        page, _ = _open_library(context, token)
        response = _signed_call(page, token, "search", params={"q": query, "show": "songs", "limit": limit})
        return rows(_body(response).get("results"), "Audiomack returned incomplete search results.")


def write_playlist(session, method, endpoint, *, data=None):
    token = session.get("otoken")
    with _web_player(session) as context:
        page, _ = _open_library(context, token)
        response = _signed_call(page, token, endpoint, method=method, data=data)
        _check_status(response)
        if endpoint == "playlist" and method == "POST":
            return _body(response)
