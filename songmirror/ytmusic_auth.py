"""Shared OAuth token location for the YouTube Music wizard and engine."""

import os


DEFAULT_AUTH_FILE = "data/ytmusic_oauth.json"
LEGACY_AUTH_FILE = "ytmusic_oauth.json"


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
