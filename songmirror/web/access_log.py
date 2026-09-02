"""Redaction for credentials delivered on OAuth callback query strings."""

from __future__ import annotations

import logging
import re

_CALLBACK = re.compile(r"^/oauth/[^/?]+/callback$")


class OAuthCallbackAccessFilter(logging.Filter):
    """Keep callback routes useful in access logs without logging their query."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < 3:
            return True
        target = str(args[2])
        path, marker, _query = target.partition("?")
        if marker and _CALLBACK.fullmatch(path):
            redacted = list(args)
            redacted[2] = f"{path}?[redacted]"
            record.args = tuple(redacted)
        return True


def install_oauth_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, OAuthCallbackAccessFilter) for item in logger.filters):
        logger.addFilter(OAuthCallbackAccessFilter())
