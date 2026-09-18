"""Account connectors — one per service, keyed to the targets registry.

Adding a service: write a Connector subclass and add one line here (mirrors the
targets registry, where the same service also gets a MirrorTarget).
"""

from .apple import AppleConnector
from .amazon_music import AmazonMusicConnector
from .base import ConnStatus, Connector, DeviceCode, Field
from .deezer import DeezerConnector
from .jellyfin import JellyfinConnector
from .lastfm import LastfmConnector
from .qobuz import QobuzConnector
from .spotify import SpotifyConnector
from .tidal import TidalConnector
from .ytmusic import YTMusicConnector

__all__ = ["CONNECTORS", "Connector", "ConnStatus", "DeviceCode", "Field"]

CONNECTORS = {
    "spotify": SpotifyConnector,
    "tidal": TidalConnector,
    "qobuz": QobuzConnector,
    "deezer": DeezerConnector,
    "amazon": AmazonMusicConnector,
    "apple": AppleConnector,
    "ytmusic": YTMusicConnector,
    # Read-only source: supplies listening history, accepts no writes.
    "lastfm": LastfmConnector,
    "jellyfin": JellyfinConnector,
}
