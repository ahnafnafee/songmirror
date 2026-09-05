"""Apple Music connector (token_paste) — Apple can't be OAuthed here, so the
wizard guides pasting the web player's bearer + Media-User-Token."""

import requests

from ...engine.apple_access import is_cloud_library_denial
from ...engine.config import AMP
from .base import FULL_PEER_CAPABILITIES, ConnStatus, Connector, Field


CATALOG_ONLY_CAPABILITIES = frozenset({"public_playlist_read"})
CATALOG_ONLY_DETAIL = (
    "Catalog-only access. Public Apple Music playlist links can be transferred "
    "out; library browsing, syncing, and destination writes require an active "
    "Apple Music subscription."
)


class AppleConnector(Connector):
    id = "apple"
    name = "Apple Music"
    auth_kind = "token_paste"
    config_fields = [
        Field("APPLE_BEARER_TOKEN", "Bearer token", secret=True,
              help="Value of the 'authorization' request header"),
        Field("APPLE_USER_TOKEN", "Media-User-Token", secret=True,
              help="Value of the 'media-user-token' request header"),
        Field("APPLE_STOREFRONT", "Storefront", required=False,
              help="Your country code, e.g. us"),
    ]

    def status(self) -> ConnStatus:
        if not self._configured("APPLE_BEARER_TOKEN", "APPLE_USER_TOKEN"):
            return ConnStatus("unconfigured")
        ok, detail, capabilities, storefront = self._validate()
        if ok:
            self._ensure_storefront(storefront)  # one-time: backfill the account's region if it's blank
        return ConnStatus("connected", detail, capabilities) if ok else ConnStatus("expired", detail)

    def submit(self, values: dict) -> ConnStatus:
        self._store.save({k: values.get(k) for k in ("APPLE_BEARER_TOKEN", "APPLE_USER_TOKEN", "APPLE_STOREFRONT")})
        ok, detail, capabilities, storefront = self._validate()
        if ok:
            self._ensure_storefront(storefront)  # auto-detect the account's region when the field was left blank
        return (ConnStatus("connected", detail, capabilities) if ok
                else ConnStatus("error", detail or "token rejected"))

    def _ensure_storefront(self, detected=""):
        """Detect and persist the account's storefront (e.g. 'us', 'bd') from
        /v1/me/storefront when it's blank, so catalog searches hit the right
        region. A user-set value is left untouched; best-effort otherwise (a blank
        storefront falls back to 'us' in the engine). No-op once one is stored, so
        it's a single lookup on connect, not per status poll."""
        if (self._store.get("APPLE_STOREFRONT") or "").strip():
            return
        if str(detected or "").strip():
            self._store.save({"APPLE_STOREFRONT": str(detected).strip()})
            return
        try:
            r = requests.get(
                f"{AMP}/me/storefront",
                headers={"Authorization": f"Bearer {self._bearer()}",
                         "Media-User-Token": self._store.get("APPLE_USER_TOKEN") or "",
                         "Origin": "https://music.apple.com"},
                timeout=15,
            )
            if r.ok:
                data = r.json().get("data") or []
                sf = (data[0].get("id") or "").strip() if data else ""
                if sf:
                    self._store.save({"APPLE_STOREFRONT": sf})
        except Exception:
            pass  # leave blank; the engine defaults to 'us'

    def _bearer(self):
        b = self._store.get("APPLE_BEARER_TOKEN") or ""
        return b[7:] if b.lower().startswith("bearer ") else b

    def _validate(self):
        bearer = self._bearer()
        user = self._store.get("APPLE_USER_TOKEN") or ""
        if not (bearer and user):
            return False, "missing tokens", frozenset(), ""
        headers = {
            "Authorization": f"Bearer {bearer}",
            "Media-User-Token": user,
            "Origin": "https://music.apple.com",
        }
        try:
            r = requests.get(
                f"{AMP}/me/library/playlists?limit=1",
                headers=headers,
                timeout=15,
            )
            if r.ok:
                return True, "", FULL_PEER_CAPABILITIES, ""
            if not is_cloud_library_denial(r):
                return False, f"HTTP {r.status_code}", frozenset(), ""

            storefront_response = requests.get(
                f"{AMP}/me/storefront",
                headers=headers,
                timeout=15,
            )
            if not storefront_response.ok:
                return (
                    False,
                    f"catalog validation failed (HTTP {storefront_response.status_code})",
                    frozenset(),
                    "",
                )
            payload = storefront_response.json()
            data = (payload.get("data") or []) if isinstance(payload, dict) else []
            storefront = (
                str(data[0].get("id") or "").strip()
                if data and isinstance(data[0], dict)
                else ""
            )
            if not storefront:
                return False, "catalog validation returned no storefront", frozenset(), ""
            return True, CATALOG_ONLY_DETAIL, CATALOG_ONLY_CAPABILITIES, storefront
        except requests.RequestException as exc:
            # Request exceptions may include caller-supplied text. Report only
            # the class so pasted bearer and user tokens can never be reflected
            # into an API response or log through validation detail.
            return (
                False,
                f"could not reach Apple Music ({type(exc).__name__})",
                frozenset(),
                "",
            )
        except (AttributeError, TypeError, ValueError):
            return False, "Apple Music returned an invalid validation response", frozenset(), ""
