"""Optional sign-in for the owner of a self-hosted SongMirror instance."""

import asyncio
import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ..services.private_files import owner_only

USERNAME_KEY = "SONGMIRROR_AUTH_USERNAME"
PASSWORD_KEY = "SONGMIRROR_AUTH_PASSWORD"

COOKIE = "songmirror_session"
SESSION_SECONDS = 24 * 60 * 60
MAX_SESSIONS = 128
LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 60
MAX_LOGIN_CLIENTS = 1024
MIN_PASSWORD_LENGTH = 15
MAX_CREDENTIAL_LENGTH = 256
MAX_CREDENTIAL_BODY = 8192
OWNER_FILE = Path("owner-auth", "credentials.json")
PUBLIC_AUTH_ROUTES = {
    ("GET", "/api/auth/session"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/setup"),
}

router = APIRouter(prefix="/api/auth", tags=["Profile"])


def _valid_credential(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_CREDENTIAL_LENGTH


def _derive_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=3, maxmem=64 * 1024**2)


@dataclass(frozen=True)
class _Owner:
    username: str
    salt: bytes
    password_hash: bytes

    @classmethod
    def create(cls, username: str, password: str):
        salt = secrets.token_bytes(16)
        return cls(username, salt, _derive_password(password, salt))

    @classmethod
    def read(cls, path: Path):
        try:
            path.parent.stat()
        except FileNotFoundError:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            username = data["username"]
            salt = bytes.fromhex(data["salt"])
            password_hash = bytes.fromhex(data["password_hash"])
            if (data["version"] != 1 or not _valid_credential(username)
                    or len(salt) != 16 or len(password_hash) != 64):
                raise ValueError
            username.encode()
            return cls(username, salt, password_hash)
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
            raise RuntimeError(f"Could not load the owner sign-in record ({path}).") from exc

    def save(self, path: Path) -> None:
        with TemporaryDirectory(dir=path.parent.parent, prefix=".owner-auth-") as directory:
            owner_only(directory, directory=True)
            temporary_path = Path(directory) / path.name
            temporary_path.touch(mode=0o600, exist_ok=False)
            owner_only(temporary_path)
            with temporary_path.open("w", encoding="utf-8") as temporary:
                json.dump({
                    "version": 1,
                    "username": self.username,
                    "salt": self.salt.hex(),
                    "password_hash": self.password_hash.hex(),
                }, temporary)
                temporary.flush()
                os.fsync(temporary.fileno())
            # A second process cannot replace a nonempty directory. Publish the
            # complete record atomically, including on platforms without hard links.
            os.rename(directory, path.parent)

    def verify(self, username: str, password: str) -> bool:
        password_ok = secrets.compare_digest(self.password_hash, _derive_password(password, self.salt))
        username_ok = secrets.compare_digest(self.username.encode(), username.encode())
        return username_ok and password_ok


class ProfileAuth:
    def __init__(self, data_dir: Path, configured_owner: _Owner | None = None):
        self._path = data_dir / OWNER_FILE
        self._owner = configured_owner or _Owner.read(self._path)
        self._setup_code = None if self.enabled else secrets.token_urlsafe(24)
        self._setup_lock = asyncio.Lock()
        self._sessions: dict[str, float] = {}
        self._attempts: dict[str, tuple[float, int]] = {}
        self._verifying = 0

    @staticmethod
    def owner_from_environment():
        config = dotenv_values(interpolate=False) if {USERNAME_KEY, PASSWORD_KEY} - os.environ.keys() else {}
        username = os.environ.get(USERNAME_KEY, config.get(USERNAME_KEY)) or ""
        password = os.environ.get(PASSWORD_KEY, config.get(PASSWORD_KEY)) or ""
        if not username and not password:
            return None
        if not _valid_credential(username) or not _valid_credential(password) or len(password) < MIN_PASSWORD_LENGTH:
            raise RuntimeError(
                f"Set {USERNAME_KEY} and {PASSWORD_KEY} together. Use a non-blank username of up to "
                f"{MAX_CREDENTIAL_LENGTH} characters and a password of {MIN_PASSWORD_LENGTH} to "
                f"{MAX_CREDENTIAL_LENGTH} characters."
            )
        return _Owner.create(username, password)

    @property
    def enabled(self) -> bool:
        if self._owner is not None:
            return True
        try:
            self._path.parent.stat()
        except FileNotFoundError:
            return False
        return True

    def announce_setup(self) -> None:
        if self._setup_code and not self.enabled:
            # This goes to the web server log, separate from the in-app event feed.
            logging.getLogger("uvicorn.error").warning("SongMirror owner setup code: %s", self._setup_code)

    async def setup(self, username: str, password: str, code: object) -> str:
        async with self._setup_lock:
            if self.enabled:
                raise HTTPException(409, "Owner sign-in is already configured.")
            if (
                not isinstance(code, str) or len(code) != 32 or not code.isascii()
                or self._setup_code is None or not secrets.compare_digest(self._setup_code, code)
            ):
                raise HTTPException(403, "Incorrect owner setup code.")
            if len(password) < MIN_PASSWORD_LENGTH:
                raise HTTPException(400, f"Use a password of at least {MIN_PASSWORD_LENGTH} characters.")
            owner = await run_in_threadpool(_Owner.create, username, password)
            try:
                owner.save(self._path)
            except OSError:
                if self.enabled:
                    raise HTTPException(409, "Owner sign-in is already configured.") from None
                raise HTTPException(503, "Could not save the owner sign-in record.") from None
            self._owner = owner
            self._setup_code = None
            return self._new_session()

    async def login(self, client: str, username: str, password: str) -> str | None:
        if self._owner is None:
            self._owner = _Owner.read(self._path)
        owner = self._owner
        if owner is None:
            raise HTTPException(404, "Profile sign-in is disabled.")
        now = monotonic()
        self._attempts = {key: attempt for key, attempt in self._attempts.items() if attempt[0] > now}
        until, attempts = self._attempts.get(client, (now + LOGIN_WINDOW, 0))
        if attempts >= LOGIN_ATTEMPTS:
            retry_after = ceil(until - now)
        elif self._verifying >= 2 or (not attempts and len(self._attempts) >= MAX_LOGIN_CLIENTS):
            retry_after = 1
        else:
            retry_after = 0
        if retry_after:
            raise HTTPException(429, "Too many sign-in attempts.", headers={"Retry-After": str(retry_after)})

        # Reserve the attempt before yielding so parallel requests share the limit.
        self._attempts[client] = (until, attempts + 1)
        self._verifying += 1
        try:
            valid = await run_in_threadpool(owner.verify, username, password)
        finally:
            self._verifying -= 1
        if not valid:
            return None

        self._attempts.pop(client, None)
        return self._new_session()

    def _new_session(self) -> str:
        now = monotonic()
        self._sessions = {token: expiry for token, expiry in self._sessions.items() if expiry > now}
        if len(self._sessions) >= MAX_SESSIONS:
            self._sessions.pop(next(iter(self._sessions)))
        token = secrets.token_urlsafe(32)
        self._sessions[token] = now + SESSION_SECONDS
        return token

    def signed_in(self, request: Request) -> bool:
        token = request.cookies.get(COOKIE)
        expiry = self._sessions.get(token)
        if expiry is None:
            return False
        if expiry <= monotonic():
            self._sessions.pop(token, None)
            return False
        return True

    def logout(self, request: Request) -> None:
        self._sessions.pop(request.cookies.get(COOKIE), None)


@router.get("/session")
async def session(request: Request, response: Response):
    auth = request.app.state.profile_auth
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": auth.enabled, "authenticated": auth.signed_in(request)}


async def _read_credentials(request: Request) -> tuple[str, str, object]:
    try:
        credentials = await request.json()
        username, password = credentials["username"], credentials["password"]
        if not _valid_credential(username) or not _valid_credential(password):
            raise ValueError
        username.encode()
        password.encode()
    except (TypeError, ValueError, KeyError, RecursionError):
        raise HTTPException(400, "Enter a username and password.") from None
    return username, password, credentials.get("setup_code")


def _set_session_cookie(request: Request, response: Response, token: str):
    response.set_cookie(
        COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
    )


@router.post("/setup", status_code=204)
async def setup(request: Request, response: Response):
    auth = request.app.state.profile_auth
    username, password, code = await _read_credentials(request)
    token = await auth.setup(username, password, code)
    _set_session_cookie(request, response, token)


@router.post("/login", status_code=204)
async def login(request: Request, response: Response):
    auth = request.app.state.profile_auth
    if not auth.enabled:
        raise HTTPException(404, "Profile sign-in is disabled.")
    username, password, _ = await _read_credentials(request)
    token = await auth.login(request.client.host if request.client else "", username, password)
    if token is None:
        raise HTTPException(401, "Incorrect username or password.")
    auth.logout(request)
    _set_session_cookie(request, response, token)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    auth = request.app.state.profile_auth
    if not auth.enabled:
        raise HTTPException(404, "Profile sign-in is disabled.")
    auth.logout(request)
    response.delete_cookie(
        COOKIE, httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )
