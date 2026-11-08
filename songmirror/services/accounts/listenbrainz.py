"""Public reads by username; an optional user token grants favorite and playlist writes."""

from ...listenbrainz import ListenBrainz
from .base import ConnStatus, Connector, Field


class ListenBrainzConnector(Connector):
    id = "listenbrainz"
    name = "ListenBrainz"
    auth_kind = "api_key"
    config_fields = [
        Field("LISTENBRAINZ_USER", "Username"),
        Field("LISTENBRAINZ_TOKEN", "User token", secret=True, required=False,
              help="Optional: copy your user token from https://listenbrainz.org/settings/ to read private playlists and receive loved recordings and playlists."),
    ]

    def status(self):
        user = self._store.get("LISTENBRAINZ_USER")
        if not user:
            return ConnStatus("unconfigured", capabilities=frozenset())
        token = self._store.get("LISTENBRAINZ_TOKEN") or ""
        granted = {"library_read"}
        try:
            client = ListenBrainz(user=user, token=token)
            if token:
                client.validate_token()
                granted |= {"favorites_write", "library_write"}
            client.feedback_page(count=1)
        except RuntimeError as exc:
            return ConnStatus("error", str(exc), capabilities=frozenset())
        return ConnStatus("connected", user, capabilities=frozenset(granted))

    def submit(self, values):
        self._store.save(self.normalize_config(values))
        return self.status()

    def normalize_config(self, values):
        values = {key: str(values[key] or "").strip()
                  for key in ("LISTENBRAINZ_USER", "LISTENBRAINZ_TOKEN") if key in values}
        if ("LISTENBRAINZ_USER" in values and "LISTENBRAINZ_TOKEN" not in values
                and values["LISTENBRAINZ_USER"].casefold() != (self._store.get("LISTENBRAINZ_USER") or "").casefold()):
            values["LISTENBRAINZ_TOKEN"] = ""
        return values
