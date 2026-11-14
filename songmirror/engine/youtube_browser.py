"""Signed-in YouTube video reads using the connected browser account.

Music's library and playlist parser omit videos that regular YouTube can play.
Keep these reads separate from the music-only sync adapter.
"""

import hashlib
import json
import re
import time

import requests

from .config import REQUEST_TIMEOUT
from .targets.base import TargetAuthError, TargetTransientError

ORIGIN = "https://www.youtube.com"


def _objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _text(value):
    if not isinstance(value, dict):
        return ""
    return value.get("content") or value.get("simpleText") or "".join(
        run.get("text", "") for run in value.get("runs", [])
    )


def _count(text):
    if text.strip() == "No videos":
        return 0
    match = re.fullmatch(r"([\d,\s]+)(?: videos?| tracks?)?", text.strip())
    return int(re.sub(r"\D", "", match[1])) if match and re.search(r"\d", match[1]) else None


def _image(value):
    for node in _objects(value):
        sources = node.get("sources") or node.get("thumbnails")
        if isinstance(sources, list) and sources and sources[-1].get("url"):
            return sources
    return []


def _embedded(html, pattern, required_key=None):
    for match in re.finditer(pattern, html):
        try:
            value, _ = json.JSONDecoder().raw_decode(html[match.end():])
            if isinstance(value, dict) and (required_key is None or required_key in value):
                return value
        except ValueError:
            continue
    raise TargetTransientError("YouTube did not return a readable page. Retry the request.")


class YouTubeBrowser:
    def __init__(self, music_api):
        self.api = music_api

    def _headers(self):
        headers = dict(self.api.headers)
        # A browser signature is bound to its origin; never reuse Music's hash.
        stamp = str(int(time.time()))
        digest = hashlib.sha1(f"{stamp} {self.api.sapisid} {ORIGIN}".encode()).hexdigest()
        headers.update({"authorization": f"SAPISIDHASH {stamp}_{digest}",
                        "origin": ORIGIN, "x-origin": ORIGIN, "referer": ORIGIN + "/"})
        return headers

    def _response(self, method, path, **kwargs):
        try:
            response = self.api._session.request(
                method, ORIGIN + path, headers=self._headers(), timeout=REQUEST_TIMEOUT,
                allow_redirects=False, **kwargs,
            )
        except requests.RequestException as exc:
            raise TargetTransientError("YouTube could not be reached. Retry the request.") from exc
        if response.status_code in {401, 403} or 300 <= response.status_code < 400:
            raise TargetAuthError("YouTube could not read this account. Reconnect it in Accounts.")
        if response.status_code != 200:
            raise TargetTransientError(f"YouTube returned HTTP {response.status_code}. Retry the request.")
        return response

    def _pages(self, path):
        response = self._response("GET", path, params={"hl": "en"})
        data = _embedded(response.text, r"(?:var\s+)?ytInitialData\s*=\s*")
        config = _embedded(response.text, r"ytcfg\.set\(\s*", "INNERTUBE_CONTEXT")
        context = config.get("INNERTUBE_CONTEXT")
        if not isinstance(context, dict):
            raise TargetTransientError("YouTube did not return its page context. Retry the request.")
        seen = set()
        while True:
            web_context = (data.get("responseContext") or {}).get("mainAppWebResponseContext") or {}
            if web_context.get("loggedOut") is True:
                raise TargetAuthError("YouTube signed this account out. Reconnect it in Accounts.")
            contents = data.get("onResponseReceivedActions") or data.get("onResponseReceivedEndpoints") or data.get("contents")
            if contents is None:
                contents = data.get("contents")
            if not isinstance(contents, (dict, list)):
                raise TargetTransientError("YouTube returned an incomplete playlist page. Retry the request.")
            if path.startswith("/playlist?") and not seen:
                # The outer section continuation loads recommendations, not
                # more playlist entries. Follow only the actual video list.
                for node in _objects(contents):
                    section = node.get("itemSectionRenderer")
                    if isinstance(section, dict):
                        contents = {"itemSectionRenderer": section}
                        break
            yield data, contents
            tokens = []
            for node in _objects(contents):
                item = node.get("continuationItemRenderer") or node.get("continuationItemViewModel")
                if isinstance(item, dict):
                    tokens.extend(child["continuationCommand"].get("token")
                                  for child in _objects(item)
                                  if isinstance(child.get("continuationCommand"), dict))
            tokens = list(dict.fromkeys(token for token in tokens if token))
            if not tokens:
                return
            if len(tokens) != 1 or tokens[0] in seen:
                raise TargetTransientError("YouTube returned an invalid playlist continuation. Retry the request.")
            seen.add(tokens[0])
            try:
                data = self._response("POST", "/youtubei/v1/browse", json={
                    "context": context, "continuation": tokens[0],
                }).json()
            except ValueError as exc:
                raise TargetTransientError("YouTube returned an unreadable playlist page. Retry the request.") from exc

    def playlists(self):
        result, seen = [], set()
        for index, (_data, contents) in enumerate(self._pages("/feed/playlists")):
            recognized, page_entries = False, 0
            for node in _objects(contents):
                modern = node.get("lockupViewModel")
                legacy = node.get("gridPlaylistRenderer") or node.get("playlistRenderer")
                if isinstance(modern, dict) and modern.get("contentType") == "LOCKUP_CONTENT_TYPE_PLAYLIST":
                    recognized = True
                    playlist_id = modern.get("contentId")
                    meta = (modern.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                    title = _text(meta.get("title"))
                    count = next((_count(badge["thumbnailBadgeViewModel"].get("text", ""))
                                  for badge in _objects(modern.get("contentImage"))
                                  if "thumbnailBadgeViewModel" in badge), None)
                    owned = any("deletePlaylistEndpoint" in child for child in _objects(meta.get("menuButton")))
                    thumbnails = _image(modern.get("contentImage"))
                elif isinstance(legacy, dict):
                    recognized = True
                    playlist_id, title = legacy.get("playlistId"), _text(legacy.get("title"))
                    count = _count(str(legacy.get("videoCount") or _text(legacy.get("videoCountText"))))
                    owned = any("deletePlaylistEndpoint" in child for child in _objects(legacy.get("menu")))
                    thumbnails = _image(legacy)
                else:
                    recognized |= any(key in node for key in ("richGridRenderer", "sectionListRenderer", "appendContinuationItemsAction"))
                    continue
                if not playlist_id or not title:
                    raise TargetTransientError("YouTube returned an incomplete library entry. Retry the request.")
                page_entries += 1
                if playlist_id not in seen:
                    seen.add(playlist_id)
                    result.append({"playlistId": playlist_id, "title": title, "count": count,
                                   "thumbnails": thumbnails, "_owned": owned})
            if not recognized or index > 0 and not page_entries:
                raise TargetTransientError("YouTube did not return the playlist library. Retry the request.")
        return result

    def tracks(self, playlist_id, *, limit=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(playlist_id)):
            raise ValueError("Invalid YouTube playlist ID")
        result, expected, hidden = [], None, False
        for data, contents in self._pages("/playlist?list=" + str(playlist_id)):
            hidden |= any(_text(node.get("text")) == "Unavailable videos are hidden"
                          for node in _objects(data.get("alerts")))
            for node in _objects(data.get("sidebar")):
                info = node.get("playlistSidebarPrimaryInfoRenderer")
                if isinstance(info, dict) and info.get("stats"):
                    expected = _count(_text(info["stats"][0]))
                    if limit is not None and expected is not None and expected > limit:
                        raise ValueError(f"too many tracks. Maximum is {limit} tracks per import")
            before = len(result)
            for node in _objects(contents):
                modern = node.get("lockupViewModel")
                legacy = node.get("playlistVideoRenderer")
                if isinstance(modern, dict) and modern.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
                    video_id = modern.get("contentId")
                    meta = (modern.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                    title = _text(meta.get("title"))
                    rows = ((meta.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or []
                    credits = rows[0].get("metadataParts", []) if rows else []
                    artist = _text(credits[0].get("text")) if credits else ""
                    thumbnails = _image(modern.get("contentImage"))
                elif isinstance(legacy, dict):
                    video_id, title = legacy.get("videoId"), _text(legacy.get("title"))
                    artist = _text(legacy.get("shortBylineText"))
                    thumbnails = _image(legacy.get("thumbnail"))
                    if legacy.get("isPlayable") is False:
                        if limit is not None and len(result) >= limit:
                            raise ValueError(f"too many tracks. Maximum is {limit} tracks per import")
                        result.append({"unavailable": True})
                        continue
                else:
                    continue
                if limit is not None and len(result) >= limit:
                    raise ValueError(f"too many tracks. Maximum is {limit} tracks per import")
                if not video_id or not title:
                    raise TargetTransientError("YouTube returned an incomplete video entry. Retry the request.")
                result.append({"id": video_id, "videoId": video_id, "name": title,
                               "artist": artist, "artists": [artist], "added_at": "",
                               "image": thumbnails[-1].get("url", "") if thumbnails else ""})
            if before == len(result) and expected != 0:
                # A real empty playlist has a zero count. A continuation that
                # loses its rows must not be mistaken for hidden videos.
                raise TargetTransientError("YouTube returned no readable video entries. Retry the request.")
        if expected is not None and len(result) < expected:
            if hidden:
                result.extend({"unavailable": True} for _ in range(expected - len(result)))
            else:
                raise TargetTransientError(
                    f"YouTube returned only {len(result)} of {expected} playlist entries. "
                    "Check for hidden or unavailable videos in YouTube, then retry."
                )
        return result
