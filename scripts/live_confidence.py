"""Live confidence run against your real accounts, on temporary playlists only.

Run it locally before opening a pull request. It cannot run in CI: it needs a
signed-in session for every provider. See docs/live-confidence.md.

    uv run python scripts/live_confidence.py --seed-playlist "Drive" --sessions shared

Songs from an existing playlist on the seed provider (Jellyfin by default) are
read, never changed, and cloned into temporary playlists. For every other
connected provider the real engine then runs:

  one-way   seed clone -> provider mirror: bootstrap, steady state, a deletion
            the source still offers, a simulated delisting, saved-answer reuse
  catalog   the provider's own catalog check against every song it holds
  n-way     provider <-> seed provider: a deletion on each side, final stability
  merge     two providers as merge sources into a seed-provider destination

Every temporary playlist is named with TEMP_PREFIX, deleted afterwards, and
the deletion is verified. `--sweep` removes leftovers from an interrupted run.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMP_PREFIX = "SongMirror confidence"
PLAYLIST_PROVIDERS = ("spotify", "tidal", "qobuz", "deezer", "amazon", "apple", "ytmusic",
                      "listenbrainz", "subsonic", "jellyfin")
# Session files a provider renews while it runs. Renewal can rotate the refresh
# token, which would sign the live app out unless it reads the renewed file.
SESSION_FILES = {"tidal": ("TIDAL_TOKEN_FILE", "tidal_oauth.json"),
                 "deezer": ("DEEZER_WEB_SESSION_FILE", "deezer_web_session.json"),
                 "amazon": ("AMAZON_MUSIC_WEB_SESSION_FILE", "amazon_music_web_session.json")}
# Read-only credential files a scratch copy is enough for.
COPIED_FILES = {"SPOTIFY_SP_DC_FILE": "spotify_sp_dc.private", "YTMUSIC_BROWSER_AUTH": "ytmusic_browser.json"}
WORKER_TIMEOUT = 20 * 60


# --------------------------------------------------------------------------- #
# Preflight decisions (pure, unit-tested in tests/test_live_confidence.py)
# --------------------------------------------------------------------------- #

def schedule_blocker(status, now, quiet_minutes):
    """Why the live app's schedule makes a run unsafe now, or None."""
    if status.get("running"):
        return "a live sync is running"
    next_run = status.get("next_run_at")
    if status.get("scheduled") and next_run and float(next_run) - now < quiet_minutes * 60:
        minutes = max(0, round((float(next_run) - now) / 60))
        return f"a scheduled live sync starts in {minutes} min (quiet window is {quiet_minutes} min)"
    return None


def job_conflicts(jobs, accounts, providers):
    """Live jobs that would pick up a temporary playlist on one of `providers`.

    A job with no playlist filter syncs every same-named playlist, so it could
    copy a temporary playlist to the user's other accounts mid-run.
    """
    provider_of = {account["id"]: account["provider"] for account in accounts}
    wanted, conflicts = set(providers), []
    for job in jobs:
        if not job.get("enabled") or not job.get("sync_playlists") or job.get("mode") == "merge":
            continue
        if str(job.get("playlists") or "").strip():
            continue
        members = [job.get("source") or ""] + str(job.get("providers") or "").split(",")
        touched = {provider_of.get(member.strip(), member.strip()) for member in members if member.strip()}
        if touched & wanted:
            conflicts.append(f"{job.get('name')!r} syncs every playlist on {', '.join(sorted(touched & wanted))}")
    return conflicts


def sessions_at_risk(expiries, providers, now, budget_minutes):
    """Providers whose session would renew during a run of `budget_minutes`."""
    return sorted(provider for provider in providers
                  if provider in expiries and expiries[provider] is not None
                  and expiries[provider] - now < budget_minutes * 60)


def is_temporary(name):
    return str(name or "").startswith(TEMP_PREFIX + " ")


# --------------------------------------------------------------------------- #
# Worker environment
# --------------------------------------------------------------------------- #

def prepare_environment(scratch, data_dir, sessions):
    """Point every file a provider reads or writes at scratch, except the shared sessions."""
    (scratch / "data").mkdir(parents=True, exist_ok=True)
    os.chdir(scratch)  # resolve caches default to the working directory
    settings = json.loads((data_dir / "settings.json").read_text(encoding="utf-8"))
    for key, value in settings.items():
        if key.isupper() and isinstance(value, str):
            os.environ[key] = value
    os.environ.pop("AUTO_SYNC", None)
    for env, name in COPIED_FILES.items():
        if (data_dir / name).exists():
            shutil.copy(data_dir / name, scratch / "data" / name)
        os.environ[env] = str(scratch / "data" / name)
    for env, name in SESSION_FILES.values():
        if sessions == "copy" and (data_dir / name).exists():
            shutil.copy(data_dir / name, scratch / "data" / name)
        os.environ[env] = str((data_dir if sessions == "shared" else scratch / "data") / name)
    os.environ.update({
        "SONGMIRROR_DATA_DIR": str(scratch / "data"),
        "SONG_CACHE_FILE": str(scratch / "songs.db"),
        "SPOTIFY_CACHE_FILE": str(scratch / "spotify_cache.json"),
        "SPOTIFY_TRACKS_CACHE": str(scratch / "spotify_tracks_cache.json"),
        "APPLE_CACHE_FILE": str(scratch / "apple_cache.json"),
    })
    sys.path.insert(0, str(REPO))


class Recorder:
    """Records PASS/FAIL lines a parent process collects."""

    def __init__(self, worker):
        self.worker, self.results = worker, []

    def check(self, label, ok, detail=""):
        ok = bool(ok)
        self.results.append(ok)
        print("RESULT " + json.dumps({"worker": self.worker, "check": label, "ok": ok, "detail": str(detail)}),
              flush=True)
        return ok


def record_writes(target, log):
    """Log the provider writes the engine makes; nested calls count once."""
    from songmirror.engine.matching import catalog_name

    depth = [0]
    for method in ("add", "remove", "remove_occurrences"):
        real = getattr(target, method, None)
        if real is None:
            continue

        def wrapped(*args, _real=real, _method=method, **kwargs):
            if depth[0] == 0:
                if _method == "add":
                    log.extend(("add", str(i)) for i in args[1])
                elif _method == "remove":
                    log.append(("remove", catalog_name(args[1].get("name") or "")))
                else:
                    log.extend(("remove", catalog_name(row.get("name") or "")) for _pos, row in args[1])
            depth[0] += 1
            try:
                return _real(*args, **kwargs)
            finally:
                depth[0] -= 1

        setattr(target, method, wrapped)


def hide_from_catalog(target, hidden, queries=None):
    """Simulate a delisting: every catalog lookup path stops finding `hidden` titles."""
    from songmirror.engine.matching import catalog_name

    search, resolve = target.search_candidates, target.resolve

    def search_candidates(query, *, limit=5):
        if queries is not None:
            queries.append(query)
        return [c for c in search(query, limit=limit) if catalog_name(c.get("name") or "") not in hidden]

    def resolve_hidden(track, cache):
        return (None, None) if catalog_name(track.get("name") or "") in hidden else resolve(track, cache)

    target.search_candidates, target.resolve = search_candidates, resolve_hidden


def delete_playlist(target, playlist):
    """Delete a temporary playlist this run created. Providers have no delete API of their own."""
    from songmirror.engine import jellyfin as jellyfin_api
    from songmirror.engine.config import AMP

    name = target.playlist_name(playlist)
    if not is_temporary(name):
        raise RuntimeError(f"refusing to delete {name!r}: it is not a temporary playlist")
    provider = getattr(target, "provider", None) or target.source
    pid = str(target.playlist_id(playlist))
    if provider == "jellyfin":
        jellyfin_api.send(target._url, target._key, "delete", f"/Items/{pid}")
    elif provider == "listenbrainz":
        target._api._playlist_write(f"/1/playlist/{pid}/delete", {})
    elif provider == "tidal":
        target._request("DELETE", f"playlists/{pid}")
    elif provider == "qobuz":
        target._request("POST", "playlist/delete", params={"playlist_id": pid})
    elif provider == "apple":
        target._request("DELETE", f"{AMP}/me/library/playlists/{pid}")
    elif provider == "ytmusic":
        target._api.delete_playlist(pid)
    elif provider == "amazon":
        target._graphql("SongMirrorConfidenceDelete",
                        "mutation SongMirrorConfidenceDelete($id: String) { deletePlaylist(id: $id) { __typename } }",
                        {"id": pid}, mutation=True)
    elif provider == "deezer":
        result = target._web.execute(
            "SongMirrorConfidenceDelete",
            "mutation SongMirrorConfidenceDelete($input: PlaylistDeleteMutationInput!) "
            "{ deletePlaylist(input: $input) { deleteStatus } }",
            {"input": {"playlistId": pid}}, mutation=True)
        if not ((result or {}).get("deletePlaylist") or {}).get("deleteStatus"):
            raise RuntimeError(f"Deezer did not confirm the delete: {result!r}")
    elif provider == "spotify":
        _delete_spotify_playlist(pid)
    else:
        raise RuntimeError(f"no delete helper for {provider}")


def _delete_spotify_playlist(pid):
    """Remove the playlist from the rootlist, verifying nothing else changed."""
    import requests

    from songmirror.engine import spotify_cookie as sc

    uri = f"spotify:playlist:{pid}"
    rootlist = f"{sc._SPCLIENT}/playlist/v2/user/{sc.current_user_id()}/rootlist"

    def read():
        response = requests.get(rootlist, headers=sc._spc_headers(), params={"decorate": "revision"}, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["revision"], [item["uri"] for item in data["contents"]["items"]]

    revision, before = read()
    if before.count(uri) != 1:
        raise RuntimeError(f"the playlist appears {before.count(uri)} times in the rootlist; not touching it")
    change = {"baseRevision": revision, "wantResultingRevisions": False, "wantSyncResult": False, "nonces": [],
              "deltas": [{"ops": [{"kind": 3, "rem": {"fromIndex": before.index(uri), "length": 1,
                                                      "items": [{"uri": uri}], "itemsAsKey": True}}]}]}
    requests.post(rootlist + "/changes", headers=sc._spc_headers(), data=json.dumps(change),
                  timeout=20).raise_for_status()
    _revision, after = read()
    if after != [item for item in before if item != uri]:
        raise RuntimeError("the Spotify rootlist changed beyond the temporary playlist; check the library")


def list_playlists(target):
    lister = getattr(target, "browse_playlists", None)
    return lister() if lister else list(target.list_playlists().values())


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #

def build(provider):
    from songmirror.engine.config import parse_args
    from songmirror.engine.targets import build_one

    opts = parse_args([])
    opts.execute = True
    return build_one(provider, opts, None, sync_peer=True)


def clone_seed(seed, args, name, created):
    playlist = next((p for p in list_playlists(seed) if seed.playlist_name(p) == args.seed_playlist), None)
    if playlist is None:
        raise RuntimeError(f"seed playlist {args.seed_playlist!r} was not found on {seed.source}")
    original = [seed.track_id(t) for t in seed.playlist_tracks(playlist)]
    songs = seed.playlist_tracks(playlist)[:args.seed_count]
    clone = seed.create({"name": name})
    created.append((seed, clone))
    seed.add(clone, [seed.track_id(t) for t in songs])
    return playlist, original, songs, clone


def source_tracks(seed, playlist):
    from songmirror.engine.targets.base import _normalize

    out = []
    for track in seed.playlist_tracks(playlist):
        norm = _normalize(track, getattr(seed, "provider", None) or seed.source)
        norm["id"] = seed.track_id(track)
        out.append(norm)
    return out


def provider_worker(args, rec):
    from songmirror.engine import archive
    from songmirror.engine.matching import catalog_name as key
    from songmirror.engine.targets.base import _catalog_offers, _normalize, mirror_pair, reconcile

    provider, scratch = args.worker, Path(args.scratch)
    name = f"{TEMP_PREFIX} {args.stamp} {provider}"
    seed, peer = build(args.seed_provider), build(provider)
    if seed is None or peer is None:
        rec.check(f"{args.seed_provider if seed is None else provider} is configured", False)
        return
    created, writes, seed_writes, hidden, seed_queries = [], [], [], set(), []
    hide_from_catalog(seed, hidden, seed_queries)
    record_writes(peer, writes)
    seed_playlist = original = None
    try:
        seed_playlist, original, songs, src = clone_seed(seed, args, f"{name} src", created)
        mirror = peer.create({"name": name})
        created.append((peer, mirror))
        conn = archive.connect(str(scratch / f"{provider}-oneway.db"))
        cache = {"isrc": {}, "search": {}, "dirty": False}
        peers_for_check = {seed.source: (seed, None)}

        def one_way():
            before = len(writes)
            stats = mirror_pair(peer, source_tracks(seed, src), src, mirror, cache, conn, execute=True,
                                max_removals=25, max_adds=200, source_key=seed.source, source_name=seed.name,
                                name=name, catalog_peers=peers_for_check,
                                check_key=archive.MIRROR_CHECK_PREFIX + name.casefold())
            return stats, [key(t.get("name") or "") for t in peer.playlist_tracks(mirror)], writes[before:]

        _, first, _ = one_way()
        matched = [t for t in songs if key(t["name"]) in first]
        rec.check("one-way: bootstrap copies the cloned songs", len(matched) >= 4, f"{len(matched)}/{len(songs)}")
        _, second, new = one_way()
        rec.check("one-way: a steady-state pass writes nothing", not new and second == first, new)
        a, b = key(matched[0]["name"]), key(matched[1]["name"])
        seed.remove(src, next(t for t in seed.playlist_tracks(src) if key(t["name"]) == a))
        _, third, new = one_way()
        rec.check("one-way: a deletion the source still offers reaches the mirror",
                  a not in third and new == [("remove", a)], new)
        hidden.add(b)
        seed.remove(src, next(t for t in seed.playlist_tracks(src) if key(t["name"]) == b))
        stats, fourth, new = one_way()
        rec.check("one-way: a delisted song stays and is reported",
                  b in fourth and not new and "unavailable_on_provider" in
                  [d["category"] for d in stats["change_diagnostics"]], new)
        seed_queries.clear()
        _, fifth, new = one_way()
        rec.check("one-way: the saved answer is reused, with no search and no writes",
                  b in fifth and not new and not any(b in key(q) for q in seed_queries), new)
        hidden.clear()

        rows = peer.playlist_tracks(mirror)
        own = {"isrc": {}, "search": {}, "dirty": False}
        bad = [key(r.get("name") or "") for r in rows if _catalog_offers(peer, r, own) is not True]
        rec.check("catalog: the provider offers every song on its own playlist", rows and not bad, bad)
        bad = [key(t["name"]) for t in matched
               if _catalog_offers(peer, _normalize(t, seed.source), own) is not True]
        rec.check("catalog: it offers them when asked with the seed provider's metadata", not bad, bad)

        nway_pl = seed.create({"name": name})
        created.append((seed, nway_pl))
        record_writes(seed, seed_writes)
        nconn = archive.connect(str(scratch / f"{provider}-nway.db"))
        caches = {peer.source: {"isrc": {}, "search": {}, "dirty": False},
                  seed.source: {"isrc": {}, "search": {}, "dirty": False}}

        def nway():
            before, seed_before = len(writes), len(seed_writes)
            reconcile([peer, seed], name, {peer.source: mirror, seed.source: nway_pl}, caches, nconn,
                      execute=True, max_removals=25, max_adds=200)
            return ([key(t.get("name") or "") for t in peer.playlist_tracks(mirror)],
                    [key(t.get("name") or "") for t in seed.playlist_tracks(nway_pl)],
                    writes[before:], seed_writes[seed_before:])

        p1, s1, _, _ = nway()
        shared = [song for song in p1 if song in s1]
        rec.check("n-way: bootstrap pairs both playlists", len(shared) >= 3, f"{len(shared)} on both")
        p2, s2, new, seed_new = nway()
        rec.check("n-way: a steady-state pass writes nothing", not new and not seed_new and (p2, s2) == (p1, s1),
                  (new, seed_new))
        c, d = shared[0], shared[1]
        _remove_quietly(peer, mirror, c, writes)
        _, s3, _, _ = nway()
        rec.check("n-way: the first read only marks a provider deletion pending", c in s3)
        # A provider whose reads briefly lag restarts the two-read confirmation,
        # so up to two extra reads are allowed before judging.
        readds = []
        for _attempt in range(3):
            p4, s4, new, _ = nway()
            readds += [w for w in new if w[0] == "add"]
            if c not in s4:
                break
        rec.check("n-way: a confirmed provider deletion leaves the seed and never returns",
                  c not in s4 and c not in p4 and not readds, readds)
        _remove_quietly(seed, nway_pl, d, seed_writes)
        p5, s5, _, _ = nway()
        rec.check("n-way: the first read after a seed deletion does not re-add it", d in p5 and d not in s5,
                  (p5, s5))
        for _attempt in range(3):
            p6, s6, _, _ = nway()
            if d not in p6:
                break
        rec.check("n-way: a confirmed seed deletion leaves the provider", d not in p6 and d not in s6, (p6, s6))
        p7, s7, new, seed_new = nway()
        rec.check("n-way: the final state is stable", not new and not seed_new and (p7, s7) == (p6, s6),
                  (new, seed_new))
    except Exception as exc:
        rec.check("the run finished without an exception", False, repr(exc))
    finally:
        cleanup(rec, created)
        if seed_playlist is not None:
            rec.check("the seed playlist is unchanged",
                      [seed.track_id(t) for t in seed.playlist_tracks(seed_playlist)] == original)


def _remove_quietly(target, playlist, song, log):
    """Delete one song as the user would, without logging it as an engine write."""
    from songmirror.engine.matching import catalog_name

    before = len(log)
    target.remove(playlist, next(t for t in target.playlist_tracks(playlist)
                                 if catalog_name(t.get("name") or "") == song))
    del log[before:]


def merge_worker(args, rec):
    from songmirror.engine import archive
    from songmirror.engine.config import parse_args
    from songmirror.engine.matching import catalog_name as key
    from songmirror.engine.runner import _run_merge
    from songmirror.engine.targets.base import mirror_pair

    first_name, second_name = args.merge_sources.split(",")[:2]
    scratch, name = Path(args.scratch), f"{TEMP_PREFIX} {args.stamp} merge"
    seed, first, second = build(args.seed_provider), build(first_name), build(second_name)
    if None in (seed, first, second):
        rec.check("merge sources and seed are configured", False)
        return
    created, hidden, second_queries = [], set(), []
    cls = type(second)
    real_search, real_resolve = cls.search_candidates, cls.resolve
    seed_playlist = original = None
    try:
        # _run_merge builds its own provider objects, so the delisting is simulated on the class.
        def search(self, query, *, limit=5):
            second_queries.append(query)
            return [c for c in real_search(self, query, limit=limit) if key(c.get("name") or "") not in hidden]

        def resolve(self, track, cache):
            return (None, None) if key(track.get("name") or "") in hidden else real_resolve(self, track, cache)

        cls.search_candidates, cls.resolve = search, resolve
        seed_playlist, original, _songs, seed_clone = clone_seed(seed, args, f"{name} seed", created)
        sources = {}
        for target in (first, second):
            playlist = target.create({"name": f"{name} {target.source}"})
            created.append((target, playlist))
            mirror_pair(target, source_tracks(seed, seed_clone), seed_clone, playlist,
                        {"isrc": {}, "search": {}, "dirty": False},
                        archive.connect(str(scratch / f"merge-seed-{target.source}.db")), execute=True,
                        max_removals=0, max_adds=200, source_key=seed.source, source_name=seed.name, name=name)
            sources[target.source] = playlist
        destination = seed.create({"name": name})
        created.append((seed, destination))
        opts = parse_args([])
        for field, value in dict(
            sources=[{"provider": t.source, "playlist_id": str(t.playlist_id(sources[t.source])),
                      "name": t.playlist_name(sources[t.source]), "kind": "library"} for t in (first, second)],
            destination={"provider": seed.source, "playlist_id": str(seed.playlist_id(destination)), "name": name},
            removal_strategy="mirror", execute=True, max_removals=25, max_adds=200, apply_large_removals=False,
            song_cache_file=str(scratch / "merge.db"), sync_job_id=f"confidence-{args.stamp}",
        ).items():
            setattr(opts, field, value)

        def merge():
            per_target, aggregate, ok, error = _run_merge(opts, None)
            return per_target[0], aggregate, ok, error, [key(t["name"]) for t in seed.playlist_tracks(destination)]

        def on(target):
            return [key(t.get("name") or "") for t in target.playlist_tracks(sources[target.source])]

        stats, aggregate, ok, error, d1 = merge()
        both = [song for song in on(first) if song in on(second) and song in d1]
        rec.check("merge: bootstrap writes the union with every source read",
                  ok and not aggregate["removals_guarded"] and len(both) >= 2, f"{error or ''} {len(both)} shared")
        stats, _, _, _, d2 = merge()
        rec.check("merge: a steady-state pass changes nothing", d2 == d1 and not stats["added"] and not stats["removed"])
        m1, m2 = both[0], both[1]
        for target in (first, second):
            _remove_quietly(target, sources[target.source], m1, [])
        stats, _, _, _, d3 = merge()
        rec.check("merge: a song removed from every source leaves the destination", m1 not in d3 and stats["removed"] == 1)
        hidden.add(m2)
        for target in (first, second):
            _remove_quietly(target, sources[target.source], m2, [])
        stats, _, _, _, d4 = merge()
        rec.check("merge: a song one source delisted stays and names that source",
                  m2 in d4 and not stats["removed"] and ("unavailable_on_provider", second.name) in
                  [(d["category"], d["provider"]) for d in stats["change_diagnostics"]], stats["change_diagnostics"])
        second_queries.clear()
        stats, _, _, _, d5 = merge()
        rec.check("merge: the saved answer is reused", m2 in d5 and not stats["removed"]
                  and not any(m2 in key(q) for q in second_queries))
    except Exception as exc:
        rec.check("the merge run finished without an exception", False, repr(exc))
    finally:
        cls.search_candidates, cls.resolve = real_search, real_resolve
        cleanup(rec, created)
        if seed_playlist is not None:
            rec.check("the seed playlist is unchanged",
                      [seed.track_id(t) for t in seed.playlist_tracks(seed_playlist)] == original)


def cleanup(rec, created):
    for target, playlist in reversed(created):
        try:
            delete_playlist(target, playlist)
        except Exception as exc:
            rec.check(f"cleanup deleted {target.source}:{target.playlist_name(playlist)}", False, repr(exc))
    time.sleep(2)
    for target in {id(t): t for t, _ in created}.values():
        # Other workers' playlists carry the same prefix while they run, so only
        # this worker's own playlists are checked here; the final sweep checks all.
        mine = {str(target.playlist_id(p)) for t, p in created if t is target}
        try:
            left = [target.playlist_name(p) for p in list_playlists(target) if str(target.playlist_id(p)) in mine]
            rec.check(f"its temporary playlists are gone from {target.source}", not left, left)
        except Exception as exc:
            rec.check(f"listed {target.source} to verify cleanup", False, repr(exc))


def sweep_worker(args, rec):
    """Delete temporary playlists on the selected providers: this run's, or with --sweep every run's."""
    prefix = f"{TEMP_PREFIX} {args.stamp} " if args.this_run else TEMP_PREFIX + " "
    for provider in args.providers.split(","):
        target = build(provider)
        if target is None:
            continue
        def ours(playlist):
            return str(target.playlist_name(playlist) or "").startswith(prefix)

        try:
            for playlist in [p for p in list_playlists(target) if ours(p)]:
                delete_playlist(target, playlist)
                print(f"deleted {provider}: {target.playlist_name(playlist)}", flush=True)
            left = [target.playlist_name(p) for p in list_playlists(target) if ours(p)]
            rec.check(f"no temporary playlist is left on {provider}", not left, left)
        except Exception as exc:
            rec.check(f"swept {provider}", False, repr(exc))


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _get(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def preflight(args, data_dir):
    """Return (providers to run, notes) or raise SystemExit with the reason."""
    now = time.time()
    providers = [p for p in (args.providers.split(",") if args.providers else PLAYLIST_PROVIDERS)
                 if p and p != args.seed_provider]
    notes = []
    if args.live_url:
        try:
            accounts = _get(f"{args.live_url}/api/accounts")
            status = _get(f"{args.live_url}/api/sync/status")
            jobs = _get(f"{args.live_url}/api/syncs")
        except OSError as exc:
            notes.append(f"live app at {args.live_url} not reachable ({exc}); schedule and job checks skipped")
        else:
            blocker = schedule_blocker(status, now, args.quiet_minutes)
            if blocker:
                raise SystemExit(f"refusing to start: {blocker}")
            conflicts = job_conflicts(jobs, accounts, providers + [args.seed_provider])
            if conflicts:
                raise SystemExit("refusing to start: " + "; ".join(conflicts))
            connected = {a["provider"] for a in accounts if a.get("state") == "connected"
                         and a.get("supports_playlists") and (a.get("capabilities") or {}).get("library_write")}
            if not args.providers:
                skipped = [p for p in providers if p not in connected]
                providers = [p for p in providers if p in connected]
                if skipped:
                    notes.append(f"not connected for playlist writes, skipped: {', '.join(skipped)}")
            if args.seed_provider not in connected:
                raise SystemExit(f"refusing to start: seed provider {args.seed_provider} is not connected")
    if args.sessions == "copy":
        expiries = {}
        for provider, (_env, name) in SESSION_FILES.items():
            try:
                expiries[provider] = float(json.loads((data_dir / name).read_text(encoding="utf-8"))["expires_at"])
            except (OSError, KeyError, ValueError, TypeError):
                expiries[provider] = None
        risky = sessions_at_risk(expiries, providers + [args.seed_provider], now, args.session_budget)
        if args.seed_provider in risky:
            raise SystemExit(f"refusing to start: the {args.seed_provider} session would renew; use --sessions shared")
        if risky:
            providers = [p for p in providers if p not in risky]
            notes.append(f"session would renew during the run, skipped in copy mode: {', '.join(risky)} "
                         "(use --sessions shared to include them)")
    return providers, notes


def spawn(args, worker, scratch, extra=()):
    log = scratch / f"{worker}.log"
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", worker, "--stamp", args.stamp,
               "--scratch", str(scratch / worker), "--data-dir", str(args.data_dir), "--sessions", args.sessions,
               "--seed-provider", args.seed_provider, "--seed-playlist", args.seed_playlist,
               "--seed-count", str(args.seed_count), "--merge-sources", args.merge_sources, *extra]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    handle = log.open("w", encoding="utf-8")
    return subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, env=env), log, handle


def collect(processes):
    results = []
    for worker, (process, log, handle) in processes.items():
        try:
            process.wait(timeout=WORKER_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            results.append({"worker": worker, "check": "finished within the time limit", "ok": False,
                            "detail": f"killed after {WORKER_TIMEOUT}s; run --sweep"})
        handle.close()
        lines = [json.loads(line[7:]) for line in log.read_text(encoding="utf-8").splitlines()
                 if line.startswith("RESULT ")]
        if not lines:
            lines = [{"worker": worker, "check": "reported results", "ok": False, "detail": f"see {log}"}]
        results.extend(lines)
    return results


def run_pool(args, scratch, workers):
    """Run workers with at most --jobs at a time, so the shared seed server is not flooded."""
    pending, running, results = list(workers), {}, []
    while pending or running:
        while pending and len(running) < max(1, args.jobs):
            worker = pending.pop(0)
            running[worker] = spawn(args, worker, scratch)
        time.sleep(1)
        for worker in [w for w, (process, _log, _handle) in running.items() if process.poll() is not None]:
            results += collect({worker: running.pop(worker)})
    return results


def orchestrate(args):
    data_dir = Path(args.data_dir)
    if not (data_dir / "settings.json").exists():
        raise SystemExit(f"no settings.json in {data_dir}; pass --data-dir")
    if not args.sweep and not args.seed_playlist:
        raise SystemExit("--seed-playlist is required (an existing playlist on the seed provider)")
    providers, notes = preflight(args, data_dir)
    scratch = Path(args.scratch or tempfile.mkdtemp(prefix="songmirror-confidence-"))
    scratch.mkdir(parents=True, exist_ok=True)
    for note in notes:
        print("note:", note)
    if args.sweep:
        processes = {"sweep": spawn(args, "sweep", scratch, ("--providers", ",".join(providers + [args.seed_provider])))}
        results = collect(processes)
    else:
        print(f"run {args.stamp}: {', '.join(providers)} against seed {args.seed_provider} "
              f"({args.sessions} sessions); logs in {scratch}", flush=True)
        results = run_pool(args, scratch, providers)
        merge_sources = [p for p in args.merge_sources.split(",") if p] if args.merge_sources else providers[:2]
        if len(merge_sources) >= 2:
            args.merge_sources = ",".join(merge_sources[:2])
            results += collect({"merge": spawn(args, "merge", scratch)})
        # Each worker verified its own playlists; this verifies the whole run, and deletes what it left.
        results += collect({"final sweep": spawn(args, "sweep", scratch, (
            "--providers", ",".join(providers + [args.seed_provider]), "--this-run"))})
    failures = [r for r in results if not r["ok"]]
    for worker in dict.fromkeys(r["worker"] for r in results):
        mine = [r for r in results if r["worker"] == worker]
        print(f"{worker:13} {sum(r['ok'] for r in mine)}/{len(mine)} passed")
    for failure in failures:
        print(f"FAIL {failure['worker']}: {failure['check']}  [{failure['detail']}]")
    report = scratch / "report.json"
    report.write_text(json.dumps({"stamp": args.stamp, "notes": notes, "results": results}, indent=2),
                      encoding="utf-8")
    print(f"report: {report}")
    return 1 if failures else 0


def parse(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed-playlist", default="",
                        help="existing playlist on the seed provider whose songs are cloned (it is only read); "
                             "required unless --sweep")
    parser.add_argument("--sessions", required=True, choices=("shared", "copy"),
                        help="shared: renewed TIDAL, Deezer and Amazon sessions are written back to the data "
                             "directory so the live app keeps working; copy: the data directory is never "
                             "written, and providers whose session would renew are skipped")
    parser.add_argument("--data-dir", default=os.getenv("SONGMIRROR_CONFIDENCE_DATA_DIR") or str(REPO / "data"),
                        help="the data directory holding settings.json (default: the repo's data/)")
    parser.add_argument("--providers", default="", help="comma-separated providers (default: every connected one)")
    parser.add_argument("--seed-provider", default="jellyfin")
    parser.add_argument("--seed-count", type=int, default=8)
    parser.add_argument("--merge-sources", default="", help="two merge source providers (default: the first two run)")
    parser.add_argument("--live-url", default="http://127.0.0.1:8888",
                        help="the live app, checked read-only for its schedule and jobs ('' skips the check)")
    parser.add_argument("--quiet-minutes", type=int, default=15,
                        help="refuse to start this close to a scheduled live sync")
    parser.add_argument("--session-budget", type=int, default=25,
                        help="minutes a run may take; in copy mode, sessions expiring sooner are skipped")
    parser.add_argument("--sweep", action="store_true", help="only delete temporary playlists left by earlier runs")
    parser.add_argument("--jobs", type=int, default=4,
                        help="providers tested at once; each one also loads the shared seed server")
    parser.add_argument("--this-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--scratch", default="")
    parser.add_argument("--stamp", default=time.strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--worker", default="", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv=None):
    if os.getenv("CI"):
        raise SystemExit("live_confidence.py talks to real accounts; it does not run in CI")
    args = parse(argv)
    if not args.worker:
        return orchestrate(args)
    prepare_environment(Path(args.scratch), Path(args.data_dir), args.sessions)
    rec = Recorder(args.worker)
    {"merge": merge_worker, "sweep": sweep_worker}.get(args.worker, provider_worker)(args, rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
