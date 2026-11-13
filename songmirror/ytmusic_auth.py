"""Shared authentication helpers for the YouTube Music wizard and engine."""

import os


DEFAULT_AUTH_FILE = "data/ytmusic_oauth.json"
LEGACY_AUTH_FILE = "ytmusic_oauth.json"


def browser_session_alive(api, *, playlists=None):
    """Confirm library access before consulting the less reliable account menu.

    Headless browser sessions can read their private library even when
    account/account_menu returns a guest menu (ytmusicapi#962). That menu's
    missing header raises KeyError in get_account_info, so it must not veto a
    successful library read. An empty library still needs account confirmation:
    the signed-out library stub also parses as [].
    """
    if playlists is None:
        playlists = api.get_library_playlists(limit=1)
    if playlists:
        return True
    try:
        return bool((api.get_account_info() or {}).get("accountName"))
    except (KeyError, IndexError):
        # A guest menu has no active-account header. Do not expose the parser's
        # error, which may contain the complete account response.
        return False


def oauth_token_path(configured=None):
    # Explicit paths include Docker mounts and isolated account profiles.
    # Never fall back to another account's token when one is configured.
    if path := os.getenv("YTMUSIC_AUTH_FILE") or configured:
        return path
    if os.path.exists(DEFAULT_AUTH_FILE):
        return DEFAULT_AUTH_FILE
    if os.path.exists(LEGACY_AUTH_FILE):
        return LEGACY_AUTH_FILE
    return DEFAULT_AUTH_FILE
