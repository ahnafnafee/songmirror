"""Credential-safe text for logs, browser diagnostics and persisted failures."""

import re
from dataclasses import replace

_URL = re.compile(r"(?:https?://|/)[^\s'\"()<>]+", re.I)
_HEADER = re.compile(r"(?i)(\b(?:authorization|cookie|set-cookie)\b[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\r\n,}]+)")
_CREDENTIAL = re.compile(
    r"(?i)(\b(?:[a-z0-9]+_)*(?:access_token|refresh_token|user_auth_token|api_key|api_sig|sk|sp_dc|arl|client_secret|session_key|api_secret|bearer_token|user_token|password|token|secret)\b[\"']?\s*[:=]\s*[\"']?)([^\s,;&\"'}]+)"
)


def redact_text(value):
    def safe_url(match):
        url = match.group()
        return url.split("?", 1)[0] + "?[redacted]" if "?" in url else url

    text = _URL.sub(safe_url, str(value))
    text = _HEADER.sub(r"\1[redacted]", text)
    return _CREDENTIAL.sub(r"\1[redacted]", text)


def redact_data(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: ("[redacted]" if _CREDENTIAL.match(str(key) + "=value") or _HEADER.match(str(key) + "=value") else redact_data(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_data(item) for item in value]
    return value


def redact_event(event):
    return replace(event, message=redact_text(event.message), data=redact_data(event.data))
