"""SettingsStore — the UI's single source of truth for engine config.

`settings.json` holds everything the wizard and settings page manage (provider
app credentials, sync options, download/Jellyfin config). On save it also
regenerates a managed env file (`app.env`) and updates `os.environ`.

Why a managed env file: the engine reads `os.getenv(...)` and reloads its env
each pass via `load_dotenv(..., override=True)`. `override=True` makes the file
win over the process environment, so a stale hand-edited `.env` would clobber a
freshly wizard-saved token. Pointing the engine at THIS file (via OMNI_ENV_FILE,
wired in the app factory) makes wizard saves authoritative instead.
"""

import json
import os
import shlex
from pathlib import Path


def _scalar(v):
    return v is not None and not isinstance(v, (dict, list))


class SettingsStore:
    def __init__(self, dir="data"):
        self._dir = Path(dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._json = self._dir / "settings.json"
        self.env_path = str(self._dir / "app.env")
        self._data = self._read()

    def _read(self):
        try:
            with open(self._json, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load(self):
        return dict(self._data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def save(self, values):
        """Merge non-None `values`, persist json + env file, apply to os.environ."""
        self._data.update({k: v for k, v in values.items() if v is not None})
        with open(self._json, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        self._render_env()
        self.apply_to_env()

    def _render_env(self):
        lines = [f"{k}={shlex.quote(str(v))}" for k, v in self._data.items() if _scalar(v)]
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def apply_to_env(self):
        """Project scalar settings into the process env (engine reads os.getenv)."""
        for k, v in self._data.items():
            if _scalar(v):
                os.environ[k] = str(v)
