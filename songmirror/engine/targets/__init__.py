"""Mirror targets: the services a playlist is mirrored across.

Adding a provider (Deezer, Tidal, …) is deliberately local:
  1. Write `targets/<svc>.py` with a `MirrorTarget` subclass implementing the
     ~8 methods (see base.py). Carry ISRC in `playlist_tracks` if the API has
     it — that's what makes cross-provider matching reliable and free.
  2. Add one line to `_REGISTRY` below: `source -> builder(opts, sp) -> target|None`.
Everything else — one-way mirroring, N-way reconcile, canonical identity,
caching, safety rails — is provider-agnostic and needs no change.
"""

from .apple import AppleMusicTarget
from .amazon_music import AmazonMusicTarget
from .base import (
    MirrorTarget,
    TargetAuthError,
    TargetDirectoryIncompleteError,
    TargetTransientError,
    mirror_pair,
    reconcile,
)
from .deezer import DeezerTarget
from .qobuz import QobuzTarget
from .spotify_target import SpotifyTarget
from .tidal import TidalTarget
from . import ytmusic

__all__ = ["AppleMusicTarget", "AmazonMusicTarget", "DeezerTarget", "QobuzTarget",
           "SpotifyTarget", "TidalTarget", "MirrorTarget", "TargetAuthError",
           "TargetDirectoryIncompleteError", "TargetTransientError",
           "mirror_pair", "reconcile", "build_targets", "build_peers", "build_one", "is_peer",
           "nway_order_candidates"]


def _apple(opts):
    from ..config import required_env
    from ..logs import log_note
    try:
        required_env("APPLE_BEARER_TOKEN")
        required_env("APPLE_USER_TOKEN")
        return AppleMusicTarget(opts.storefront, opts.cache_file)
    except RuntimeError as e:
        log_note(f"Apple Music skipped: {e}", tag="apple")
        return None


def _rest_provider(target_cls, label, **kwargs):
    """Build an env-configured REST peer, logging a clean skip when absent."""
    from ..logs import log_note
    try:
        return target_cls(**kwargs)
    except RuntimeError as e:
        log_note(f"{label} skipped: {e}", tag=target_cls.tag)
        return None


def _spotify(opts, sp, *, sync_peer=False, songs=None):
    """Build Spotify from OAuth or from a standalone signed-in web session."""
    if sp is None:
        from .. import spotify_cookie
        from ..config import spotify_write_backend

        if spotify_write_backend() != "cookie" or not spotify_cookie.configured():
            return None
    return SpotifyTarget(sp, opts.spotify_cache_file, sync_peer=sync_peer, songs=songs)


# source -> builder(opts, sp) -> a ready MirrorTarget, or None when unconfigured.
# Registry order is presentation order only: reconciliation reads every peer and
# seeds all native ISRCs before it canonicalizes any provider.
# `sp` (the Spotify client) is only needed by legacy OAuth Spotify mode.
_REGISTRY = {
    "spotify": lambda opts, sp, sync_peer=False, songs=None: _spotify(
        opts, sp, sync_peer=sync_peer, songs=songs),
    "tidal": lambda opts, sp, sync_peer=False, songs=None: _rest_provider(
        TidalTarget, "TIDAL", songs=songs),
    "qobuz": lambda opts, sp, sync_peer=False, songs=None: _rest_provider(QobuzTarget, "Qobuz"),
    "deezer": lambda opts, sp, sync_peer=False, songs=None: _rest_provider(DeezerTarget, "Deezer"),
    "amazon": lambda opts, sp, sync_peer=False, songs=None: _rest_provider(AmazonMusicTarget, "Amazon Music"),
    "apple": lambda opts, sp, sync_peer=False, songs=None: _apple(opts),
    "ytmusic": lambda opts, sp, sync_peer=False, songs=None: ytmusic.build(),
}
_SOURCE_ORDER = ["spotify", "tidal", "qobuz", "deezer", "amazon", "apple", "ytmusic"]


def nway_order_candidates(opts):
    """Provider ids to try for N-way order authority, in preference order.

    The caller still decides whether a candidate is configured. Empty
    ``opts.providers`` therefore expands to every known provider rather than
    assuming Spotify is available. Spotify keeps priority when it can be built,
    followed by the job's former source when it participates, then registry
    source order.
    """
    wanted = {s.strip() for s in (opts.providers or "").split(",") if s.strip()}
    participants = [src for src in _SOURCE_ORDER if not wanted or src in wanted]
    preferred = ("spotify", getattr(opts, "sync_source", None))
    return tuple(dict.fromkeys(
        src for src in (*preferred, *participants) if src in participants
    ))


def build_targets(opts, sp=None):
    """One-way mirror targets this run: every opted-in provider except the source
    (opts.sync_source). An empty opts.providers means every configured provider
    (the same 'empty = all' convention as opts.playlists, and what the UI shows).
    `sp` (the Spotify client) is only needed when the source is a non-Spotify
    provider, so Spotify itself becomes a writable target."""
    source = getattr(opts, "sync_source", None) or "spotify"
    wanted = {s.strip() for s in (opts.providers or "").split(",") if s.strip()}
    return [t for src in _SOURCE_ORDER if src != source and (not wanted or src in wanted)
            for t in (_REGISTRY[src](opts, sp, sync_peer=True),) if t]


def build_one(provider_id, opts, sp=None):
    """Construct a single provider by id (None if unknown/unconfigured). Used by
    the web layer to browse or transfer one specific service."""
    builder = _REGISTRY.get(provider_id)
    return builder(opts, sp) if builder else None


def is_peer(provider_id):
    """Whether a provider is a sync/transfer peer — i.e. has a MirrorTarget that
    can read and write tracks. False for browse/output-only services like
    Jellyfin, which the download mirror feeds instead of track-level writes."""
    return provider_id in _REGISTRY


def build_peers(opts, sp, songs=None):
    """N-way peer nodes, limited to opts.providers and to what's configured, in
    ISRC-rich-first order. An empty opts.providers means every configured provider
    (matching the UI, which shows every connected peer when none are explicitly
    chosen) — so a job saved without touching the Services step still syncs rather
    than silently finding zero peers. Needs the Spotify client for the Spotify peer.
    `songs` (the archive conn) backs the Spotify peer's persistent ISRC cache."""
    wanted = {s.strip() for s in (opts.providers or "").split(",") if s.strip()}
    return [peer for src in _SOURCE_ORDER if not wanted or src in wanted
            for peer in (_REGISTRY[src](opts, sp, sync_peer=True, songs=songs),) if peer]
