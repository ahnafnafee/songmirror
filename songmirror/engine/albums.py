"""Additive native saved-album jobs, separate from track reconciliation."""

import os
import re

from .logs import log_add, log_note, log_warn
from .matching import normalize_text
from .targets import build_one, target_class
from .album_library import AlbumLibrary, AlbumManifest


def album_participants(source, providers, profiles=None):
    identities = list(dict.fromkeys(part.strip() for part in providers.split(",") if part.strip()))
    if profiles is not None:
        source = profiles.canonical_id(source)
        identities = list(dict.fromkeys(profiles.canonical_id(identity) for identity in identities))
    if source not in identities or len(identities) < 2:
        raise ValueError("saved-album sync needs its source and at least one destination account")
    for identity in identities:
        provider = profiles.provider_of(identity) if profiles is not None else identity
        cls = target_class(provider)
        if cls is None or not cls.supports_saved_albums:
            raise ValueError(f"unknown saved-album account: {identity}")
    return source, identities


def barcode(value):
    value = str(value or "").strip()
    return value.lstrip("0") if re.fullmatch(r"\d{8,14}", value) else ""


def compatible_albums(source, candidates):
    """Keep edition differences; metadata alone needs title, artist, year, count.

    UPC/EAN is release identity, unlike a track ISRC. Never strip deluxe/live/
    remaster qualifiers or accept a conflicting known barcode on a title match.
    """
    upc = barcode(source.get("upc"))
    exact = [candidate for candidate in candidates if upc and barcode(candidate.get("upc")) == upc]
    if exact:
        return exact
    primary = normalize_text((source.get("artists") or [""])[0])
    title = normalize_text(source.get("name"))
    year = str(source.get("release_date") or "")[:4]
    count = source.get("total_tracks")
    if not primary or not title or not year or not count:
        return []
    return [candidate for candidate in candidates
            if candidate.get("id")
            and not (upc and barcode(candidate.get("upc")) and barcode(candidate["upc"]) != upc)
            and normalize_text(candidate.get("name")) == title
            and normalize_text((candidate.get("artists") or [""])[0]) == primary
            and str(candidate.get("release_date") or "")[:4] == year
            and candidate.get("total_tracks") == count]


def run_album_pass(opts, should_continue):
    if opts.sync_mode != "oneway" or opts.sync_playlists or opts.liked_tracks or opts.download_dir or opts.max_removals:
        raise ValueError("saved-album jobs must be one-way and album-only, with downloads and removals off")
    if opts.max_adds < 1:
        raise ValueError("max_adds must be at least 1")
    source_id, identities = album_participants(
        opts.sync_source, opts.providers, getattr(opts, "account_profiles", None))
    targets, libraries = {}, {}
    manifest = AlbumManifest(getattr(opts, "saved_album_file", None) or os.path.join(
        os.getenv("SONGMIRROR_DATA_DIR") or "data", "saved_albums.json"))
    # Complete every participating library read and all matching before writes.
    # A transport/parser failure must never look like an empty destination.
    for identity in identities:
        if should_continue() != "run":
            return []
        target = build_one(identity, opts, sync_peer=identity != source_id)
        if target is None:
            raise RuntimeError(f"Saved-album account {identity} is not connected")
        target = AlbumLibrary(target, manifest)
        target.validate(write=opts.execute and identity != source_id)
        targets[identity] = target
        libraries[identity] = target.saved()
        log_note(f"Read {len(libraries[identity])} saved albums ({target.route})", tag=target.tag)
    source = targets[source_id]
    plans = []
    for identity in identities:
        if identity == source_id:
            continue
        target = targets[identity]
        existing = libraries[identity]
        existing_ids = {album["id"] for album in existing}
        planned = {}
        row = dict(name=target.name, added=0, removed=0, skipped=0, missing=0,
                   deferred=0, failed=0, uncertain_matches=0)
        for album in libraries[source_id]:
            if should_continue() != "run":
                return [item[1] for item in plans] + [row]
            same_catalog = source.same_catalog(target)
            if (same_catalog and album["id"] in existing_ids) or compatible_albums(album, existing):
                row["skipped"] += 1
                continue
            if len(planned) >= opts.max_adds:
                row["deferred"] += 1
                continue
            if target.native:
                matches = [album] if same_catalog else compatible_albums(album, target.find(album))
            else:
                portable = target.prepare_portable(album, source)
                matches = [portable] if portable is not None else []
            matches = {item["id"]: item for item in matches}
            if len(matches) != 1:
                row["missing"] += 1
                row["uncertain_matches"] += int(len(matches) > 1)
                log_warn(f"Saved album not uniquely matched: {album['name']}", tag=target.tag)
                continue
            matched = next(iter(matches.values()))
            if matched["id"] in existing_ids or matched["id"] in planned:
                row["skipped"] += 1
                continue
            planned[matched["id"]] = matched
        plans.append((target, row, list(planned.values())))
    for target, row, pending in plans:
        if row["deferred"]:
            log_note(f"{row['deferred']} saved albums deferred by the additions cap", tag=target.tag)
        for album in pending:
            if should_continue() != "run":
                return [item[1] for item in plans]
            album_id = album["id"]
            try:
                if opts.execute:
                    target.add(album)
                row["added"] += 1
                log_add(f"Save album {album['name']} — {', '.join(album.get('artists') or [])}",
                        dry=not opts.execute, tag=target.tag)
            except Exception as exc:
                row.update(failed=row["failed"] + 1, error=str(exc))
                log_warn(f"Could not save album {album_id}: {exc}", tag=target.tag)
                break
    return [item[1] for item in plans]
