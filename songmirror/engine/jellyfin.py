"""Optional: set playlist cover art in Jellyfin via its API.

Jellyfin ignores cover files next to an m3u playlist (it auto-tiles the tracks'
embedded art and honours no filename/`#EXTIMG`), so the ONLY way to give a
playlist a real cover is the API. Opt-in with JELLYFIN_URL + JELLYFIN_API_KEY
(create the key in Jellyfin: Dashboard -> API Keys); skipped otherwise. The
playlist must already exist in Jellyfin (scanned from the m3u) to be matched.
"""

import base64
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from .logs import log_download, log_note, log_warn

TAG = "jelly"
PAGE_SIZE = 200


class JellyfinError(RuntimeError):
    """A connection or response failure safe to show without credentials."""


def server_url(value):
    """Accept a server root or a pasted web-client URL, retaining a base path."""
    try:
        parts = urlsplit(str(value or "").strip())
        valid = (parts.scheme in {"http", "https"} and parts.hostname
                 and parts.username is None and parts.password is None)
        parts.port  # Validate a malformed port before requests sees it.
    except ValueError:
        valid = False
    if not valid:
        raise JellyfinError("Check the Jellyfin server URL; use an http:// or https:// address.")
    path = parts.path.rstrip("/")
    for suffix in ("/web/index.html", "/web"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def auth_headers(key):
    # X-Emby-Token is ignored when legacy authorization is disabled (Jellyfin
    # 12's default). The MediaBrowser scheme also works on older servers.
    # Jellyfin URL-decodes header values; encode delimiters before quoting.
    return {"Authorization": (
        'MediaBrowser Client="SongMirror", Device="SongMirror", '
        f'DeviceId="songmirror", Version="0.1.0", Token="{quote(key.strip(), safe="")}"'
    )}


def get_json(url, key, path, *, params=None, timeout=30):
    """Authenticated JSON read with actionable errors and no token/URL echo."""
    return _call("get", url, key, path, params=params, timeout=timeout)


def send(url, key, method, path, *, params=None, json=None):
    """Authenticated write. Returns the JSON body, or {} for an empty success."""
    return _call(method, url, key, path, params=params, json=json)


def _call(method, url, key, path, *, params=None, json=None, timeout=30):
    extra = {"json": json} if json is not None else {}
    try:
        response = getattr(requests, method)(url + path, headers=auth_headers(key),
                                             params=params, timeout=timeout, **extra)
        response.raise_for_status()
        if method != "get" and (response.status_code == 204 or not response.content):
            return {}
        data = response.json()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        if code in (401, 403):
            detail = "Jellyfin rejected access. Check the API key and user permissions in Accounts."
        elif code == 404:
            detail = "Jellyfin could not find this endpoint or playlist. Check the server URL, base path, and User ID in Accounts."
        else:
            detail = f"Jellyfin returned HTTP {code}. Retry after checking the server."
        raise JellyfinError(detail) from exc
    except ValueError as exc:
        raise JellyfinError("Jellyfin did not return JSON. Check the server URL and reverse proxy.") from exc
    except requests.RequestException as exc:
        raise JellyfinError(
            "Could not reach Jellyfin. Check the server URL and network; in Docker, localhost refers to the SongMirror container."
        ) from exc
    if not isinstance(data, dict):
        raise JellyfinError("Jellyfin returned an invalid response. Check the server URL and reverse proxy.")
    return data


def _playlist_items(url, key, uid, *, fields=None):
    """Read every page using the current /Items endpoint and optional user."""
    start, seen = 0, set()
    while True:
        params = {"IncludeItemTypes": "Playlist", "Recursive": "true",
                  "StartIndex": start, "Limit": PAGE_SIZE,
                  "EnableTotalRecordCount": "true"}
        if uid:
            params["UserId"] = uid
        if fields:
            params["Fields"] = fields
        data = get_json(url, key, "/Items", params=params)
        items = data.get("Items")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise JellyfinError("Jellyfin returned an invalid playlist list. Check the server and retry.")
        if not items:
            return
        page_ids = {item.get("Id") for item in items}
        if page_ids <= seen:
            raise JellyfinError("Jellyfin repeated a playlist page. Refresh the library and retry.")
        seen.update(page_ids)
        yield from items
        start += len(items)
        total = data.get("TotalRecordCount")
        if isinstance(total, int):
            if start >= total:
                return
        elif len(items) < PAGE_SIZE:
            return


def _track_count(url, key, playlist_id, uid=None):
    """A Jellyfin playlist's audio-track count via TotalRecordCount — ChildCount
    isn't populated for playlists in the list query, so this is a per-playlist
    lookup. Returns None on any failure (count is best-effort)."""
    try:
        params = {"ParentId": playlist_id, "Recursive": "true",
                  "IncludeItemTypes": "Audio", "Limit": 0,
                  "EnableTotalRecordCount": "true"}
        if uid:
            params["UserId"] = uid
        return get_json(url, key, "/Items", params=params).get("TotalRecordCount")
    except JellyfinError:
        return None


def playlist_page(playlist_id, *, offset=0, limit=20, config=None):
    """Read playlist metadata and ordered audio children without a sync target.

    /Items supports API keys with or without a User ID across server versions.
    Leave SortBy unset so Jellyfin retains its pre-sorted playlist order.
    """
    values = os.environ if config is None else config
    url, key = values.get("JELLYFIN_URL"), values.get("JELLYFIN_API_KEY")
    if not (url and key):
        raise JellyfinError("Jellyfin is not configured. Connect the account in Accounts and retry.")
    url = server_url(url)
    user = (values.get("JELLYFIN_USER_ID") or "").strip()
    scope = {"UserId": user} if user else {}
    playlist_id = str(playlist_id)
    metadata = get_json(url, key, "/Items", params={
        **scope, "Ids": playlist_id, "IncludeItemTypes": "Playlist", "Fields": "Overview",
    })
    playlists = metadata.get("Items")
    if not isinstance(playlists, list) or any(not isinstance(item, dict) for item in playlists):
        raise JellyfinError("Jellyfin returned invalid playlist metadata. Refresh and retry.")
    playlist = next((item for item in playlists if str(item.get("Id")) == playlist_id), None)
    if playlist is None:
        return None
    data = get_json(url, key, "/Items", params={
        **scope, "ParentId": playlist_id, "Recursive": "true", "IncludeItemTypes": "Audio",
        "StartIndex": offset, "Limit": limit, "EnableTotalRecordCount": "true",
    })
    items = data.get("Items")
    if not isinstance(items, list) or any(not isinstance(item, dict) or not item.get("Id") for item in items):
        raise JellyfinError("Jellyfin returned invalid playlist tracks. Refresh and retry.")
    total = data.get("TotalRecordCount")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        total = None
    end = offset + len(items)
    if not items and total is not None and end < total:
        raise JellyfinError("Jellyfin returned an incomplete playlist page. Refresh and retry.")
    more = end < total if total is not None else len(items) == limit

    def item_url(item_id, *, image=False):
        encoded = quote(str(item_id), safe="")
        return (f"{url}/Items/{encoded}/Images/Primary" if image
                else f"{url}/web/#/details?id={encoded}")

    tracks = []
    for position, item in enumerate(items, start=offset):
        image_id = item["Id"] if (item.get("ImageTags") or {}).get("Primary") else (
            item.get("AlbumId") if item.get("AlbumPrimaryImageTag") else None
        )
        ticks = item.get("RunTimeTicks")
        tracks.append({
            "position": position, "id": str(item["Id"]), "occurrence_id": "", "isrc": "",
            "name": str(item.get("Name") or "Unknown track"),
            "artist": ", ".join(str(name) for name in item.get("Artists") or []),
            "album": item.get("Album"),
            "duration_ms": ticks // 10_000 if isinstance(ticks, int) and ticks >= 0 else None,
            "image": item_url(image_id, image=True) if image_id else "",
            "external_url": item_url(item["Id"]), "added_at": "",
        })
    return {
        "id": playlist_id, "name": str(playlist.get("Name") or "Playlist"),
        "description": str(playlist.get("Overview") or ""),
        "image": item_url(playlist_id, image=True) if (playlist.get("ImageTags") or {}).get("Primary") else "",
        "external_url": item_url(playlist_id), "owned": True, "editable": False,
        "count": total if total is not None else end, "tracks": tracks,
        "next_cursor": str(end) if more else None, "complete": not more,
    }


def push_covers(playlists):
    """Set each matching Jellyfin playlist's Primary image to its Spotify cover
    (matched by name). Never raises out."""
    url, key = os.getenv("JELLYFIN_URL"), os.getenv("JELLYFIN_API_KEY")
    if not (url and key):
        return
    try:
        url = server_url(url)
        headers = auth_headers(key)
        uid = (os.getenv("JELLYFIN_USER_ID") or "").strip()
        by_name = {}
        for item in _playlist_items(url, key, uid):
            by_name.setdefault((item.get("Name") or "").strip().casefold(), item.get("Id"))
        log_note(f"{len(by_name)} playlist(s) visible", tag=TAG)

        img_cache, pushed, missing = {}, 0, []
        for pl in playlists:
            name = pl.get("name", "")
            item_id = by_name.get(name.strip().casefold())
            if not item_id:
                missing.append(name)
                continue
            images = pl.get("images") or []
            img_url = images[0].get("url") if images else None  # Spotify lists largest first
            if not img_url:
                continue
            if img_url not in img_cache:
                ir = requests.get(img_url, timeout=30)
                ir.raise_for_status()
                img_cache[img_url] = ir.content
            # Jellyfin wants the image base64-encoded in the body, with the
            # actual image type as Content-Type (Spotify covers are JPEG).
            pr = requests.post(f"{url}/Items/{item_id}/Images/Primary",
                              headers={**headers, "Content-Type": "image/jpeg"},
                              data=base64.b64encode(img_cache[img_url]), timeout=30)
            if pr.ok:
                pushed += 1
                log_download(f"cover set: {name}", tag=TAG)
            else:
                log_warn(f"cover failed for '{name}': HTTP {pr.status_code}", tag=TAG)
        if missing:
            log_note(f"not yet in Jellyfin (scan the library, then rerun): {', '.join(missing)}", tag=TAG)
        if pushed:
            log_note(f"{pushed} cover(s) set", tag=TAG)
    except JellyfinError as e:
        log_warn(f"cover push failed: {e}", tag=TAG)
    except Exception as e:
        log_warn(f"cover push failed: {e!r}", tag=TAG)


def list_playlists(*, config=None):
    """[{id, name, count, image}] of playlists on the Jellyfin server, for the
    web Browse view. It works without a User ID, which the sync target needs.
    Empty list if unconfigured; configured failures raise JellyfinError so
    Browse can offer a retry."""
    values = os.environ if config is None else config
    url, key = values.get("JELLYFIN_URL"), values.get("JELLYFIN_API_KEY")
    if not (url and key):
        return []
    url = server_url(url)
    uid = (values.get("JELLYFIN_USER_ID") or "").strip()
    rows = []
    for item in _playlist_items(url, key, uid):
        iid, name = item.get("Id"), (item.get("Name") or "").strip()
        if not (iid and name):
            continue
        has_primary = (item.get("ImageTags") or {}).get("Primary")
        # Jellyfin serves item images without a token, so the browser can load
        # this URL directly; omit it when the playlist has no Primary image.
        rows.append({"id": iid, "name": name, "count": None,
                     "image": f"{url}/Items/{iid}/Images/Primary" if has_primary else ""})
    # Counts aren't in the list response, so fetch each concurrently (local
    # server — parallel is cheap; a failed lookup leaves count=None).
    with ThreadPoolExecutor(max_workers=8) as ex:
        counts = list(ex.map(lambda row: _track_count(url, key, row["id"], uid), rows))
    for row, count in zip(rows, counts):
        row["count"] = count
    return rows
