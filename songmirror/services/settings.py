"""SettingsStore — the UI's single source of truth for engine config.

`settings.json` holds everything the wizard and settings page manage (provider
app credentials, sync options, download/Jellyfin config). On save it also
regenerates a managed env file (`app.env`) and updates `os.environ`.

Why a managed env file: the engine reads `os.getenv(...)` and reloads its env
each pass via `load_dotenv(..., override=True)`. `override=True` makes the file
win over the process environment, so a stale hand-edited `.env` would clobber a
freshly wizard-saved token. Pointing the engine at THIS file (via SONGMIRROR_ENV_FILE,
wired in the app factory) makes wizard saves authoritative instead.
"""

import json
import os
import threading
from pathlib import Path

from .private_files import owner_only


# Provider adapters still inherit part of their runtime configuration through
# ``os.environ``.  Root settings projection and account-profile activation must
# therefore serialize on the same lock: otherwise a settings request can swap
# credentials while a target call is in flight.
_ENV_LOCK = threading.RLock()


def _scalar(v):
    return v is not None and not isinstance(v, (dict, list))


# Default source mode for Create Playlist. Options: "text", "file", "url".
CREATE_PLAYLIST_DEFAULT_SOURCE = "file"
VALID_CREATE_PLAYLIST_DEFAULT_SOURCES = frozenset({"text", "file", "url"})

# Non-secret UI defaults applied when a key is absent from settings.json.
# Keep this narrow: only values the Settings page / Create Playlist wizard
# expect to exist without an explicit save.
DEFAULT_SETTINGS = {
    "create_playlist_default_source": CREATE_PLAYLIST_DEFAULT_SOURCE,
}


def _open_private(path):
    """Open for writing with owner-only perms (0o600) from creation — these files
    hold OAuth secrets and service tokens. Windows also receives a protected
    DACL for the current process user, SYSTEM and Administrators."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        owner_only(path)
    except BaseException:
        os.close(fd)
        raise
    return os.fdopen(fd, "w", encoding="utf-8")


class SettingsStore:
    def __init__(self, dir=None, *, project_env=True):
        # Default to $SONGMIRROR_DATA_DIR (Docker points it at the /data bind mount) so
        # wizard-saved config + OAuth secrets land on the persistent volume, not
        # the container's ephemeral filesystem. Falls back to a local ./data.
        self._dir = Path(dir or os.getenv("SONGMIRROR_DATA_DIR") or "data")
        self._dir.mkdir(parents=True, exist_ok=True)
        owner_only(self._dir, directory=True)
        self._json = self._dir / "settings.json"
        self.env_path = str(self._dir / "app.env")
        self._project_env = project_env
        self._allowed_keys = None
        self._data = self._read()

    @property
    def allowed_keys(self):
        return self._allowed_keys

    def restrict_to(self, keys):
        """Treat stored web settings as data, never arbitrary process options.

        Keep unsupported legacy values in JSON for operator review, but do not
        return, export or reactivate them. apply_to_env regenerates app.env
        before the engine can reload an older, unsafe managed file.
        """
        self._allowed_keys = frozenset(keys)

    def _values(self):
        return {key: value for key, value in self._data.items()
                if self._allowed_keys is None or key in self._allowed_keys}

    @property
    def data_dir(self):
        """Persistent application-data directory for sibling service caches."""
        return self._dir

    def _read(self):
        try:
            with open(self._json, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load(self):
        data = dict(DEFAULT_SETTINGS)
        data.update(self._values())
        return data

    def has_persisted_values(self):
        """True only when settings.json actually contained data.

        ``load()`` always merges effective UI defaults, so callers that need to
        distinguish "empty store" from "defaults only" must use this instead of
        truthiness of ``load()``.
        """
        return bool(self._values())

    def get(self, key, default=None):
        if key in self._values():
            return self._data[key]
        if default is not None:
            return default
        return DEFAULT_SETTINGS.get(key)

    def save(self, values):
        """Merge non-None `values`, persist json + env file, apply to os.environ."""
        if self._allowed_keys is not None and set(values) - self._allowed_keys:
            raise ValueError("Unsupported managed setting.")
        self._data.update({k: v for k, v in values.items() if v is not None})
        with _open_private(self._json) as f:
            json.dump(self._data, f, indent=2)
        self._render_env()
        if self._project_env:
            self.apply_to_env()

    def _render_env(self):
        # Shell quote concatenation is not dotenv syntax. JSON double-quoted
        # strings keep embedded quotes/newlines within one physical assignment.
        lines = [f"{k}={json.dumps(str(v), ensure_ascii=False)}" for k, v in self._values().items() if _scalar(v)]
        with _open_private(self.env_path) as f:
            f.write("\n".join(lines) + "\n")

    def apply_to_env(self):
        """Project scalar settings into the process env (engine reads os.getenv)."""
        with _ENV_LOCK:
            self._render_env()
            for k, v in self._values().items():
                if _scalar(v):
                    os.environ[k] = str(v)
