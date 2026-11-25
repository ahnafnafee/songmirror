"""QQ Music API credentials for reading playlists by link."""

import re

from ...engine.targets.qqmusic import QQMusicTarget
from .base import ConnStatus, Connector, Field


class QQMusicConnector(Connector):
    id = "qqmusic"
    name = "QQ Music"
    config_fields = [
        Field("QQMUSIC_API_KEY", "API key", secret=True, help="Create an API key on the QQ Music Skills page."),
    ]

    def status(self):
        if not self._configured("QQMUSIC_API_KEY"):
            return ConnStatus("unconfigured")
        return ConnStatus("connected", capabilities=frozenset({"public_playlist_read"}))

    def submit(self, values):
        key = str(values.get("QQMUSIC_API_KEY", self._store.get("QQMUSIC_API_KEY")) or "").strip()
        if not re.fullmatch(r"qmk-[A-Za-z0-9_-]+", key):
            return ConnStatus("error", "Enter an API key from the QQ Music Skills page.")
        try:
            QQMusicTarget(key).validate_connection()
        except RuntimeError as exc:
            return ConnStatus("error", str(exc))
        self._store.save({"QQMUSIC_API_KEY": key})
        return self.status()
