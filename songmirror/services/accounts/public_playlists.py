"""Credential-free provider profiles validated with a public playlist link."""

from ...engine.targets.public_playlists import PUBLIC_PLAYLIST_TARGETS
from ..playlist_links import external_url, parse_playlist_link
from .base import ConnStatus, Connector, Field


class PublicPlaylistConnector(Connector):
    auth_kind = "public_link"

    def status(self):
        if not self._configured(self.config_fields[0].key):
            return ConnStatus("unconfigured")
        return ConnStatus("connected", capabilities=frozenset({"public_playlist_read"}))

    def submit(self, values):
        key = self.config_fields[0].key
        try:
            link = parse_playlist_link(values.get(key))
            if link is None or link[0] != self.id:
                return ConnStatus("error", f"Paste a public {self.name} playlist link.")
            if PUBLIC_PLAYLIST_TARGETS[self.id]().fetch_playlist(link[1]) is None:
                return ConnStatus("error", "The web player could not open that public playlist.")
        except (RuntimeError, ValueError) as exc:
            return ConnStatus("error", str(exc))
        self._store.save({key: external_url(self.id, "playlist", link[1])})
        return self.status()


PUBLIC_PLAYLIST_CONNECTORS = {
    target.source: type(f"{target.__name__.removesuffix('Target')}Connector", (PublicPlaylistConnector,), {
        "id": target.source, "name": target.name,
        "config_fields": [Field(f"{target.source.upper()}_PUBLIC_PLAYLIST", "Public playlist link")],
    }) for target in PUBLIC_PLAYLIST_TARGETS.values()
}
