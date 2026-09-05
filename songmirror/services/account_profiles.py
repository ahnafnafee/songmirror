"""Persistent provider profiles and their isolated runtime configuration.

The provider registry answers *what kind of service* an adapter speaks.  This
module answers *which signed-in account* it speaks for.  Keeping those identities
separate lets two Spotify (or Apple, TIDAL, etc.) accounts participate in one
operation without teaching every connector and target about profile storage.

``profiles.json`` contains metadata only.  Credentials and renewable session
state live below ``data/profiles/<profile id>/`` in the same owner-private format
as the legacy settings store.  The deterministic default profiles deliberately
retain the old settings/environment and file paths as a compatibility adapter;
old jobs and links that say ``spotify`` resolve to ``profile_default_spotify``.
"""

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from .settings import SettingsStore, _ENV_LOCK, _open_private


PROFILE_ID_PREFIX = "profile_"

# Every provider-owned value read by a connector, target, or authentication
# helper.  A custom profile clears this entire provider slice before applying its
# own values, so an unset field can never fall through to another account's env.
PROVIDER_KEYS = {
    "spotify": {
        "SPOTIFY_AUTH_MODE", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI", "SPOTIFY_TOKEN_CACHE", "SPOTIFY_WRITE_BACKEND",
        "SPOTIFY_SP_DC", "SPOTIFY_SP_DC_FILE", "SPOTIFY_ISRC_CLIENTS",
        "SPOTIFY_CACHE_FILE", "SPOTIFY_TRACKS_CACHE", "SPOTIFY_OAUTH_OPEN_BROWSER",
    },
    "tidal": {
        "TIDAL_WEB_HEADERS", "TIDAL_WEB_CLIENT_ID", "TIDAL_TOKEN_FILE",
        "TIDAL_CACHE_FILE", "TIDAL_COUNTRY_CODE", "TIDAL_CLIENT_ID",
        "TIDAL_OAUTH_STATE", "TIDAL_OAUTH_VERIFIER", "TIDAL_REDIRECT_URI",
        "TIDAL_RENEWAL_REQUEST",
    },
    "qobuz": {
        "QOBUZ_WEB_REQUEST", "QOBUZ_APP_ID", "QOBUZ_USER_AUTH_TOKEN",
        "QOBUZ_USER_ID", "QOBUZ_CACHE_FILE",
    },
    "deezer": {
        "DEEZER_WEB_HEADERS", "DEEZER_REFRESH_TOKEN", "DEEZER_WEB_SESSION_FILE",
        "DEEZER_TOKEN_FILE", "DEEZER_APP_ID", "DEEZER_APP_SECRET", "DEEZER_ARL",
        "DEEZER_CACHE_FILE", "DEEZER_WEB_ENDPOINT",
    },
    "amazon": {
        "AMAZON_MUSIC_WEB_HEADERS", "AMAZON_MUSIC_RENEWAL_REQUEST",
        "AMAZON_MUSIC_WEB_SESSION_FILE", "AMAZON_MUSIC_TOKEN_FILE",
        "AMAZON_MUSIC_API_KEY", "AMAZON_MUSIC_CLIENT_ID",
        "AMAZON_MUSIC_CLIENT_SECRET", "AMAZON_MUSIC_CACHE_FILE",
        "AMAZON_MUSIC_WEB_ENDPOINT",
    },
    "apple": {
        "APPLE_BEARER_TOKEN", "APPLE_USER_TOKEN", "APPLE_STOREFRONT",
        "APPLE_CACHE_FILE",
    },
    "ytmusic": {
        "YTMUSIC_OAUTH_CLIENT_ID", "YTMUSIC_OAUTH_CLIENT_SECRET",
        "YTMUSIC_AUTH_FILE", "YTMUSIC_BROWSER_AUTH", "YTMUSIC_PREFER_BROWSER",
        "YTMUSIC_CACHE_FILE",
    },
    "jellyfin": {"JELLYFIN_URL", "JELLYFIN_API_KEY", "JELLYFIN_USER_ID"},
}

_FILE_DEFAULTS = {
    "spotify": {
        "SPOTIFY_TOKEN_CACHE": "spotify_token_cache",
        "SPOTIFY_SP_DC_FILE": "spotify_sp_dc.private",
        "SPOTIFY_CACHE_FILE": "spotify_resolve_cache.json",
        "SPOTIFY_TRACKS_CACHE": "spotify_tracks_cache.json",
    },
    "tidal": {
        "TIDAL_TOKEN_FILE": "tidal_token.json",
        "TIDAL_CACHE_FILE": "tidal_resolve_cache.json",
    },
    "qobuz": {"QOBUZ_CACHE_FILE": "qobuz_resolve_cache.json"},
    "deezer": {
        "DEEZER_WEB_SESSION_FILE": "deezer_web_session.json",
        "DEEZER_TOKEN_FILE": "deezer_oauth.json",
        "DEEZER_CACHE_FILE": "deezer_resolve_cache.json",
    },
    "amazon": {
        "AMAZON_MUSIC_WEB_SESSION_FILE": "amazon_music_web_session.json",
        "AMAZON_MUSIC_TOKEN_FILE": "amazon_music_oauth.json",
        "AMAZON_MUSIC_CACHE_FILE": "amazon_music_resolve_cache.json",
    },
    "apple": {"APPLE_CACHE_FILE": "apple_resolve_cache.json"},
    "ytmusic": {
        "YTMUSIC_AUTH_FILE": "ytmusic_oauth.json",
        "YTMUSIC_BROWSER_AUTH": "ytmusic_browser.json",
        "YTMUSIC_CACHE_FILE": "ytmusic_resolve_cache.json",
    },
}

_ACTIVE_SPOTIFY_PROFILE: str | None = None


@dataclass(frozen=True)
class AccountProfile:
    id: str
    provider: str
    label: str
    is_default: bool = False


class ProfileSettings:
    """Settings interface presented to an existing account connector."""

    def __init__(self, profiles: "AccountProfileStore", profile: AccountProfile):
        self._profiles = profiles
        self.profile = profile
        self._local = SettingsStore(
            dir=profiles.profile_dir(profile.id),
            project_env=False,
        )

    @property
    def data_dir(self):
        return self._local.data_dir

    @property
    def env_path(self):
        return self._local.env_path

    def load(self):
        values = self._local.load()
        # The legacy root remains authoritative for compatibility profiles.
        # This matters when an existing CLI or deployment edits app.env after
        # profile migration; the one-time local seed must not become stale and
        # shadow that update.
        if self.profile.is_default:
            values.update(self._fallback_values())
        return values

    def get(self, key, default=None):
        if self.profile.is_default:
            fallback = self._fallback_values()
            if key in fallback:
                value = fallback[key]
                return value if value not in (None, "") else default
        value = self._local.get(key)
        if value not in (None, ""):
            return value
        return default

    def save(self, values):
        allowed = PROVIDER_KEYS[self.profile.provider]
        scoped = {key: value for key, value in values.items() if key in allowed}
        if not scoped:
            return
        self._local.save(scoped)
        # Default-profile writes continue feeding the legacy managed env.  This
        # keeps the CLI and pre-profile integrations working after a reconnect.
        if self.profile.is_default:
            self._profiles.settings.save(scoped)

    def apply_to_env(self):
        """Compatibility hook for callers that expect a SettingsStore.

        Long-running code should use ``AccountProfileStore.activate`` so values
        are restored.  Connectors are always invoked inside that context.
        """
        with _ENV_LOCK:
            for key, value in self.environment().items():
                os.environ[key] = str(value)

    def environment(self):
        values = self._local.load()
        if self.profile.is_default:
            values.update(self._fallback_values())
        if not self.profile.is_default:
            root = self.data_dir
            for key, filename in _FILE_DEFAULTS.get(self.profile.provider, {}).items():
                values.setdefault(key, str(root / filename))
        return {key: str(value) for key, value in values.items() if value is not None}

    def _fallback_values(self):
        if not self.profile.is_default:
            return {}
        # Callers such as ``profile_value`` can read a compatibility setting
        # outside ``activate``. Serialize the fallback snapshot itself so it
        # can never observe another account's temporary process environment.
        with _ENV_LOCK:
            keys = PROVIDER_KEYS[self.profile.provider]
            root = self._profiles.settings.load()
            values = {
                key: root[key]
                for key in keys
                if key in root
            }
            for key in keys:
                if key not in values and key in os.environ:
                    values[key] = os.environ[key]
            return values


class AccountProfileStore:
    """The profile persistence, migration, and runtime-selection module."""

    def __init__(self, settings: SettingsStore, providers=None):
        self.settings = settings
        self._providers = tuple(providers or PROVIDER_KEYS)
        self._path = Path(settings.data_dir) / "profiles.json"
        self._profiles_dir = Path(settings.data_dir) / "profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._profiles_dir, 0o700)
        except OSError:
            pass
        self._profiles = self._read_or_migrate()

    @staticmethod
    def default_id(provider):
        return f"{PROFILE_ID_PREFIX}default_{provider}"

    @property
    def providers(self):
        return self._providers

    def archive_aliases(self):
        """Legacy provider archive key -> deterministic compatibility profile."""
        return {provider: self.default_id(provider) for provider in self._providers}

    def list(self):
        order = {provider: index for index, provider in enumerate(self._providers)}
        return sorted(
            self._profiles.values(),
            key=lambda profile: (order.get(profile.provider, 999), not profile.is_default, profile.label.casefold()),
        )

    def get(self, profile_id):
        return self._profiles.get(str(profile_id))

    def canonical_id(self, identity):
        """Resolve a profile id or a legacy provider id to a profile id."""
        identity = str(identity or "")
        if identity in self._profiles:
            return identity
        if identity in self._providers:
            default_id = self.default_id(identity)
            if default_id in self._profiles:
                return default_id
        return identity

    def resolve(self, identity):
        return self.get(self.canonical_id(identity))

    def provider_of(self, identity):
        profile = self.resolve(identity)
        return profile.provider if profile else (identity if identity in self._providers else None)

    def settings_for(self, identity):
        profile = self.resolve(identity)
        if profile is None:
            raise KeyError(f"unknown account profile: {identity}")
        return ProfileSettings(self, profile)

    def create(self, provider, label=None):
        if provider not in self._providers:
            raise ValueError(f"unknown provider: {provider}")
        profile = AccountProfile(
            id=f"{PROFILE_ID_PREFIX}{uuid.uuid4().hex[:12]}",
            provider=provider,
            label=self._clean_label(label) or self._next_label(provider),
        )
        self._profiles[profile.id] = profile
        self._save()
        # Materialize independent file paths before a connector can run.
        local = SettingsStore(dir=self.profile_dir(profile.id), project_env=False)
        local.save({
            key: str(self.profile_dir(profile.id) / filename)
            for key, filename in _FILE_DEFAULTS.get(provider, {}).items()
        })
        return profile

    def rename(self, profile_id, label):
        profile = self.resolve(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        clean = self._clean_label(label)
        if not clean:
            raise ValueError("profile label must not be blank")
        updated = AccountProfile(profile.id, profile.provider, clean, profile.is_default)
        self._profiles[profile.id] = updated
        self._save()
        return updated

    def remove(self, profile_id):
        profile = self.resolve(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        if profile.is_default:
            raise ValueError("the compatibility profile cannot be removed; disconnect it instead")
        del self._profiles[profile.id]
        self._save()
        target = self.profile_dir(profile.id).resolve()
        root = self._profiles_dir.resolve()
        if target.parent != root:
            raise RuntimeError("refusing to remove a profile outside the profiles directory")
        shutil.rmtree(target, ignore_errors=True)

    def expand_ids(self, value):
        return [
            self.canonical_id(part.strip())
            for part in str(value or "").split(",")
            if part.strip()
        ]

    def display_name(self, identity, provider_name=None):
        profile = self.resolve(identity)
        if profile is None:
            return str(provider_name or identity)
        base = str(provider_name or profile.provider)
        return base if profile.label == base else f"{base} · {profile.label}"

    def profile_dir(self, profile_id):
        return self._profiles_dir / str(profile_id)

    @contextmanager
    def activate(self, identity):
        """Temporarily expose exactly one profile's provider configuration.

        The legacy engine reads environment variables in several mature provider
        adapters.  A process-wide re-entrant lock makes that inherited interface
        safe while a profile-bound target call is active.  Spotify's cookie
        adapter also owns process globals, so switching profiles resets them.
        """
        global _ACTIVE_SPOTIFY_PROFILE

        profile = self.resolve(identity)
        if profile is None:
            raise KeyError(f"unknown account profile: {identity}")
        with _ENV_LOCK:
            keys = PROVIDER_KEYS[profile.provider]
            # Compute the default profile's environment only after taking the
            # lock. Its legacy fallback reads the process environment, which
            # may otherwise momentarily contain another active profile.
            values = self.settings_for(profile.id).environment()
            previous = {key: os.environ.get(key) for key in keys}
            for key in keys:
                os.environ.pop(key, None)
            for key, value in values.items():
                if key in keys and value != "":
                    os.environ[key] = value
            if profile.provider == "spotify" and _ACTIVE_SPOTIFY_PROFILE != profile.id:
                from ..engine import spotify_cookie

                spotify_cookie.reset_session()
                _ACTIVE_SPOTIFY_PROFILE = profile.id
            try:
                yield profile
            finally:
                for key in keys:
                    os.environ.pop(key, None)
                for key, value in previous.items():
                    if value is not None:
                        os.environ[key] = value

    def _read_or_migrate(self):
        import json

        profiles = {}
        rewrite = False
        try:
            with open(self._path, encoding="utf-8") as handle:
                rows = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
            rewrite = True
        if not isinstance(rows, list):
            rows = []
            rewrite = True

        # Treat rows independently. A partially damaged metadata file must not
        # erase every valid custom profile merely because one row is malformed.
        for row in rows:
            try:
                if not isinstance(row, dict):
                    raise TypeError("profile row must be an object")
                profile = AccountProfile(**row)
            except (TypeError, ValueError, KeyError):
                rewrite = True
                continue
            valid_types = (
                isinstance(profile.id, str)
                and isinstance(profile.provider, str)
                and isinstance(profile.label, str)
                and isinstance(profile.is_default, bool)
            )
            if not valid_types:
                rewrite = True
                continue
            expected_default = self.default_id(profile.provider)
            safe_id = (
                profile.id.startswith(PROFILE_ID_PREFIX)
                and all(char.isalnum() or char in "_-" for char in profile.id)
            )
            if (
                profile.provider in self._providers
                and profile.label.strip()
                and safe_id
                and profile.is_default == (profile.id == expected_default)
                and profile.id not in profiles
            ):
                profiles[profile.id] = profile
            else:
                rewrite = True

        changed = rewrite
        for provider in self._providers:
            profile_id = self.default_id(provider)
            if profile_id not in profiles:
                profiles[profile_id] = AccountProfile(
                    id=profile_id,
                    provider=provider,
                    label=self._provider_label(provider),
                    is_default=True,
                )
                changed = True
        self._profiles = profiles
        if changed or not self._path.exists():
            self._save()
        self._copy_legacy_settings()
        return profiles

    def _copy_legacy_settings(self):
        """Seed default profile files without removing the legacy source."""
        root_values = self.settings.load()
        for provider in self._providers:
            values = {
                key: root_values[key]
                for key in PROVIDER_KEYS[provider]
                if key in root_values
            }
            if not values:
                continue
            local = SettingsStore(
                dir=self.profile_dir(self.default_id(provider)),
                project_env=False,
            )
            if not local.load():
                local.save(values)

    def _save(self):
        import json

        with _open_private(self._path) as handle:
            json.dump([asdict(profile) for profile in self.list()], handle, indent=2)

    @staticmethod
    def _clean_label(label):
        return " ".join(str(label or "").split())[:80]

    def _next_label(self, provider):
        base = self._provider_label(provider)
        count = sum(profile.provider == provider for profile in self._profiles.values())
        return f"{base} {count + 1}"

    @staticmethod
    def _provider_label(provider):
        return {
            "spotify": "Spotify", "tidal": "TIDAL", "qobuz": "Qobuz",
            "deezer": "Deezer", "amazon": "Amazon Music", "apple": "Apple Music",
            "ytmusic": "YouTube Music", "jellyfin": "Jellyfin",
        }.get(provider, provider)
