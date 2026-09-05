"""Mirror targets: the accounts a playlist is mirrored across.

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
           "target_class", "provider_ids",
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

        if spotify_write_backend() == "cookie" and spotify_cookie.configured():
            pass
        else:
            from .. import spotify
            try:
                sp = spotify.client(writable=bool(getattr(opts, "execute", False) and sync_peer))
            except (RuntimeError, TargetAuthError):
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

# The same providers as _REGISTRY, by class rather than by builder, for the
# class-level facts a caller needs WITHOUT credentials (where the resolution
# cache lives, how a pasted track id is normalized). test_targets_accessors
# asserts the two stay in step. The YT browser backend subclasses YTMusicTarget
# and inherits both, so one entry covers both YT modes.
_CLASSES = {
    "spotify": SpotifyTarget,
    "tidal": TidalTarget,
    "qobuz": QobuzTarget,
    "deezer": DeezerTarget,
    "amazon": AmazonMusicTarget,
    "apple": AppleMusicTarget,
    "ytmusic": ytmusic.YTMusicTarget,
}


def provider_ids():
    """Every sync/transfer provider id, in presentation order."""
    return tuple(_SOURCE_ORDER)


def target_provider(target, default=None):
    """Underlying provider type for an account-bound or legacy target."""
    return getattr(target, "provider", None) or getattr(target, "source", None) or default


class AccountBoundTarget:
    """Bind an existing provider target to one independently-authenticated account.

    ``source`` is the engine's durable identity/archive namespace, so it is the
    profile id. ``provider`` is the protocol/catalog type used by matching.
    Calls enter the profile runtime because mature adapters still read some
    credentials through their inherited environment interface.
    """

    def __init__(self, target, profile, profiles):
        self._target = target
        self._profiles = profiles
        self.account_id = profile.id
        self.profile_label = profile.label
        self.provider = target.source
        self.source = profile.id
        self.archive_source = profile.id
        target.archive_source = profile.id
        self.tag = profile.id
        self.name = profiles.display_name(profile.id, target.name)
        self.cache_file = target.cache_file

    def activate(self):
        return self._profiles.activate(self.account_id)

    def profile_value(self, key, default=None):
        return self._profiles.settings_for(self.account_id).get(key, default)

    def archive_sources(self, provider):
        """Every account namespace that can hold this provider's catalog ids."""
        return tuple(
            profile.id for profile in self._profiles.list()
            if profile.provider == provider
        )

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if not callable(value):
            return value

        def scoped(*args, **kwargs):
            with self.activate():
                return value(*args, **kwargs)

        return scoped


def _profiles(opts):
    return getattr(opts, "account_profiles", None)


def _identity_parts(identity, opts):
    profiles = _profiles(opts)
    if profiles is None:
        return identity, None, None
    profile = profiles.resolve(identity)
    if profile is None:
        return None, None, profiles
    return profile.provider, profile, profiles


def _participant_ids(opts):
    profiles = _profiles(opts)
    raw = [part.strip() for part in (opts.providers or "").split(",") if part.strip()]
    if profiles is None:
        return raw or list(_SOURCE_ORDER)
    if raw:
        return list(dict.fromkeys(profiles.canonical_id(part) for part in raw))
    return [profile.id for profile in profiles.list() if profile.provider in _REGISTRY]


def target_class(provider_id):
    """A provider's MirrorTarget subclass, or None. Unlike build_one this needs
    no configured account, so it answers class-level questions for a service the
    user has not connected."""
    return _CLASSES.get(provider_id)


def nway_order_candidates(opts):
    """Provider ids to try for N-way order authority, in preference order.

    The caller still decides whether a candidate is configured. Empty
    ``opts.providers`` therefore expands to every known provider rather than
    assuming Spotify is available. Spotify keeps priority when it can be built,
    followed by the job's former source when it participates, then registry
    source order.
    """
    profiles = _profiles(opts)
    participants = _participant_ids(opts)
    if profiles is None:
        preferred = ("spotify", getattr(opts, "sync_source", None))
    else:
        spotify = next(
            (identity for identity in participants if profiles.provider_of(identity) == "spotify"),
            None,
        )
        preferred = (spotify, profiles.canonical_id(getattr(opts, "sync_source", None)))
    return tuple(dict.fromkeys(
        src for src in (*preferred, *participants) if src and src in participants
    ))


def build_targets(opts, sp=None):
    """One-way mirror targets this run: every opted-in provider except the source
    (opts.sync_source). An empty opts.providers means every configured provider
    (the same 'empty = all' convention as opts.playlists, and what the UI shows).
    `sp` (the Spotify client) is only needed when the source is a non-Spotify
    provider, so Spotify itself becomes a writable target."""
    profiles = _profiles(opts)
    source = getattr(opts, "sync_source", None) or "spotify"
    if profiles is not None:
        source = profiles.canonical_id(source)
    return [
        target
        for identity in _participant_ids(opts)
        if identity != source
        for target in (build_one(identity, opts, sp, sync_peer=True),)
        if target
    ]


def build_one(provider_id, opts, sp=None, *, sync_peer=False, songs=None):
    """Construct a single provider by id (None if unknown/unconfigured). Used by
    the web layer to browse or transfer one specific service."""
    resolved_provider, profile, profiles = _identity_parts(provider_id, opts)
    builder = _REGISTRY.get(resolved_provider)
    if builder is None:
        return None
    if profile is None:
        # Preserve the historical two-argument builder interface for direct
        # callers and tests. Extended kwargs belong to peer construction only.
        return builder(opts, sp) if not sync_peer and songs is None else builder(
            opts, sp, sync_peer=sync_peer, songs=songs
        )
    with profiles.activate(profile.id):
        # Apple and Spotify inherited their cache/storefront values through the
        # parsed CLI Options object rather than reading them in their constructor.
        # Give those adapters a profile-local copy without mutating the job.
        import copy
        import os

        profile_opts = copy.copy(opts)
        if profile.provider == "spotify":
            profile_opts.spotify_cache_file = os.getenv(
                "SPOTIFY_CACHE_FILE", profile_opts.spotify_cache_file
            )
        elif profile.provider == "apple":
            profile_opts.cache_file = os.getenv("APPLE_CACHE_FILE", profile_opts.cache_file)
            profile_opts.storefront = os.getenv("APPLE_STOREFRONT") or profile_opts.storefront
        target = builder(profile_opts, None, sync_peer=sync_peer, songs=songs)
    return AccountBoundTarget(target, profile, profiles) if target is not None else None


def is_peer(provider_id, opts=None):
    """Whether a provider is a sync/transfer peer — i.e. has a MirrorTarget that
    can read and write tracks. False for browse/output-only services like
    Jellyfin, which the download mirror feeds instead of track-level writes."""
    if opts is not None and _profiles(opts) is not None:
        provider_id = _profiles(opts).provider_of(provider_id)
    return provider_id in _REGISTRY


def build_peers(opts, sp, songs=None):
    """N-way peer nodes, limited to opts.providers and to what's configured, in
    ISRC-rich-first order. An empty opts.providers means every configured provider
    (matching the UI, which shows every connected peer when none are explicitly
    chosen) — so a job saved without touching the Services step still syncs rather
    than silently finding zero peers. Needs the Spotify client for the Spotify peer.
    `songs` (the archive conn) backs the Spotify peer's persistent ISRC cache."""
    return [
        peer
        for identity in _participant_ids(opts)
        for peer in (build_one(identity, opts, sp, sync_peer=True, songs=songs),)
        if peer
    ]
