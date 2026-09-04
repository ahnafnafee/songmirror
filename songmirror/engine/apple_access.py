"""Apple Music access-tier response classification.

Apple uses error code 40015 when otherwise-valid credentials do not include
the paid CloudLibrary privilege. Keep the parser shared by account validation
and the target transport so both paths distinguish that one capability denial
from expired credentials and unrelated request failures.
"""


def is_cloud_library_denial(response) -> bool:
    """Return True only for Apple's HTTP 400 error code 40015 response."""

    if getattr(response, "status_code", None) != 400:
        return False
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return False
    return any(
        isinstance(error, dict) and str(error.get("code") or "") == "40015"
        for error in errors
    )
