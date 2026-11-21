"""Shared limits enforced while import inputs are parsed."""

MAX_TRACKS_PER_IMPORT = 10_000
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_LINE_LENGTH = 16_384


class ParseLimitError(ValueError):
    pass


def append_track(tracks, track):
    if len(tracks) >= MAX_TRACKS_PER_IMPORT:
        raise ParseLimitError(f"too many tracks. Maximum is {MAX_TRACKS_PER_IMPORT} tracks per import")
    tracks.append(track)
