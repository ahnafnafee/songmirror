"""QQ Music connections for reading playlists by link."""

import re

from ...engine.targets.qqmusic import QQMusicTarget, browser_mode
from ..playlist_links import parse_playlist_link
from .base import ConnStatus, Connector, Field
from .playlist_browser import PlaylistBrowserConnection


class QQMusicConnector(PlaylistBrowserConnection, Connector):
    id = "qqmusic"
    name = "QQ Music"
    target_class = QQMusicTarget
    config_fields = [
        Field("QQMUSIC_API_KEY", "API key", secret=True, help="Create an API key on the QQ Music Skills page."),
    ]

    @property
    def browser_active(self):
        return browser_mode(self._store.get)

    def status(self):
        if self.playlist_browser["active"]:
            return self.browser_status()
        if not self.browser_active and not self._configured("QQMUSIC_API_KEY"):
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
        self._store.save({"QQMUSIC_API_KEY": key, "QQMUSIC_PREFER_BROWSER": "0"})
        return self.status()

    def enable_browser(self, url):
        try:
            link = parse_playlist_link(url) if isinstance(url, str) else None
            if not link or link[0] != self.id:
                return ConnStatus("error", "Paste a public QQ Music playlist link.")
            if QQMusicTarget(web=True).fetch_playlist(link[1]) is None:
                return ConnStatus("error", "The QQ Music web player could not open that public playlist.")
        except (RuntimeError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        self._store.save({"QQMUSIC_PREFER_BROWSER": "1"})
        return self.status()

    def disable_browser(self):
        self._store.save({"QQMUSIC_PREFER_BROWSER": "0"})
        return self.status()

    def disconnect(self):
        self._store.save({"QQMUSIC_PREFER_BROWSER": "0", self.target_class.session_key(): ""})
        super().disconnect()
