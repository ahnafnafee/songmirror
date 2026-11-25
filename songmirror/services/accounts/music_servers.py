"""Connect to music servers using the existing Accounts form."""

from ...engine.targets.base import TargetAuthError
from ...engine.targets.emby import EmbyTarget
from ...engine.targets.lyrion import LyrionTarget
from ...engine.targets.mopidy import MopidyTarget
from ...engine.targets.music_server import server_url
from ...engine.targets.plex import PlexTarget
from .base import ConnStatus, Connector, Field


class MusicServerConnector(Connector):
    target_class = None

    def normalize_config(self, values):
        cleaned = {}
        for field in self.config_fields:
            if field.key not in values:
                continue
            value = values[field.key]
            if not isinstance(value, str) or any(char in value for char in "\r\n\0"):
                raise ValueError("Enter a single line of text for each connection field.")
            if field.key.endswith("_URL") and value.strip():
                value = server_url(value)
            cleaned[field.key] = value if field.key.endswith("_PASSWORD") else value.strip()
        return cleaned

    def _check(self, values):
        if not all(values.get(field.key) for field in self.config_fields if field.required):
            return ConnStatus("unconfigured")
        try:
            writable = self.target_class(values).validate_connection()
        except TargetAuthError as exc:
            return ConnStatus("expired", str(exc))
        except (RuntimeError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        grants = {"library_read"}
        if writable:
            grants.add("library_write")
        return ConnStatus("connected", capabilities=frozenset(grants))

    def status(self):
        return self._check({field.key: self._store.get(field.key) for field in self.config_fields})

    def submit(self, values):
        try:
            cleaned = self.normalize_config(values)
        except ValueError as exc:
            return ConnStatus("error", str(exc))
        config = {field.key: cleaned.get(field.key, self._store.get(field.key))
                  for field in self.config_fields}
        status = self._check(config)
        if status.state == "connected":
            self._store.save(cleaned)
        return status


class EmbyConnector(MusicServerConnector):
    id = "emby"
    name = "Emby"
    auth_kind = "token_paste"
    target_class = EmbyTarget
    config_fields = [
        Field("EMBY_URL", "Server URL"),
        Field("EMBY_USER_ID", "User ID"),
        Field("EMBY_TOKEN", "Access token", secret=True, help="Use an Emby user token for the same user ID."),
    ]


class PlexConnector(MusicServerConnector):
    id = "plex"
    name = "Plex"
    auth_kind = "token_paste"
    target_class = PlexTarget
    config_fields = [
        Field("PLEX_URL", "Server URL"),
        Field("PLEX_TOKEN", "Access token", secret=True, help="Use the token for your Plex Media Server user."),
    ]


class MopidyConnector(MusicServerConnector):
    id = "mopidy"
    name = "Mopidy"
    target_class = MopidyTarget
    config_fields = [Field("MOPIDY_URL", "Server URL", help="Enable the HTTP extension on your Mopidy server.")]


class LyrionConnector(MusicServerConnector):
    id = "lyrion"
    name = "Lyrion Music Server"
    target_class = LyrionTarget
    config_fields = [
        Field("LYRION_URL", "Server URL"),
        Field("LYRION_USER", "Username", required=False),
        Field("LYRION_PASSWORD", "Password", secret=True, required=False),
    ]
