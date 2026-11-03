"""Password hashing, access tokens and login rate limiting (ARCHITECTURE.md sections 2 and 4)."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import Settings, get_settings

JWT_ALGORITHM = "HS256"

# --------------------------------------------------------------------------------------------
# Passwords (argon2id with the library's recommended parameters)
# --------------------------------------------------------------------------------------------

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True when ``password`` matches ``password_hash``; never raises on bad input."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash uses outdated parameters and should be replaced after a login."""
    return _password_hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password("shopex-timing-equaliser")


def verify_dummy_password(password: str) -> None:
    """Spend the same time as a real verification when the account does not exist.

    Call it on the "unknown email" path of login so response times do not reveal which
    email addresses are registered.
    """
    verify_password(password, _dummy_password_hash())


# --------------------------------------------------------------------------------------------
# Access tokens (JWT, HS256)
# --------------------------------------------------------------------------------------------


class TokenError(Exception):
    """The access token is missing, malformed, expired or not signed by us."""


def create_access_token(
    user_id: int,
    *,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Sign a token whose subject is ``user_id``."""
    settings = settings or get_settings()
    issued_at = datetime.now(UTC)
    lifetime = expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "iat": issued_at, "exp": issued_at + lifetime}
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, settings: Settings | None = None) -> int:
    """Return the user id carried by a valid token, else raise ``TokenError``."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc
    subject = payload["sub"]
    if not isinstance(subject, str) or not subject.isdecimal():
        raise TokenError("invalid token subject")
    return int(subject)


# --------------------------------------------------------------------------------------------
# Login rate limiting
# --------------------------------------------------------------------------------------------


def login_rate_key(email: str, client_ip: str | None) -> str:
    """Rate-limit key for a login attempt: one bucket per (email, client IP)."""
    return f"{email.strip().lower()}|{client_ip or 'unknown'}"


class LoginRateLimiter:
    """In-memory sliding window of failed logins per key (thread-safe).

    State is per process: with several workers each one counts separately, which still bounds
    brute force to ``max_failures x workers`` attempts per window.
    """

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 300.0,
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        return self.retry_after(key) > 0

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` may try again (0 when not blocked)."""
        with self._lock:
            now = self._clock()
            failures = self._prune(key, now)
            if len(failures) < self.max_failures:
                return 0
            oldest_counted = failures[-self.max_failures]
            return max(1, math.ceil(oldest_counted + self.window_seconds - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if key not in self._failures and len(self._failures) >= self._max_keys:
                self._evict(now)
            self._prune(key, now)
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        """Forget the failures of ``key`` (call after a successful login)."""
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        """Forget everything (tests)."""
        with self._lock:
            self._failures.clear()

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key)
        if failures is None:
            return deque()
        while failures and failures[0] <= now - self.window_seconds:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def _evict(self, now: float) -> None:
        # Drop expired keys first; if still full, drop the oldest tracked keys.
        for key in list(self._failures):
            self._prune(key, now)
        while len(self._failures) >= self._max_keys:
            self._failures.pop(next(iter(self._failures)))


login_rate_limiter = LoginRateLimiter()
