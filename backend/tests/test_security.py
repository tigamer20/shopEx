"""Password hashing, access tokens and the login rate limiter."""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher

from app.config import Settings
from app.security import (
    JWT_ALGORITHM,
    LoginRateLimiter,
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    login_rate_key,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)


def test_password_round_trip() -> None:
    password = secrets.token_urlsafe(12)
    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password(password + "x", password_hash)
    assert not password_needs_rehash(password_hash)


def test_verify_password_rejects_garbage_hash() -> None:
    assert not verify_password(secrets.token_urlsafe(12), "not-a-hash")


def test_weak_hash_needs_rehash() -> None:
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("pw")

    assert password_needs_rehash(weak_hash)


def test_verify_dummy_password_does_not_raise() -> None:
    verify_dummy_password(secrets.token_urlsafe(12))


def test_token_round_trip(settings: Settings) -> None:
    token = create_access_token(42, settings=settings)

    assert decode_access_token(token, settings=settings) == 42


def test_expired_token_is_rejected(settings: Settings) -> None:
    token = create_access_token(1, settings=settings, expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenError):
        decode_access_token(token, settings=settings)


def test_token_signed_with_another_secret_is_rejected(settings: Settings) -> None:
    forged = jwt.encode(
        {"sub": "1", "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)},
        secrets.token_urlsafe(48),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(TokenError):
        decode_access_token(forged, settings=settings)


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "abc"},  # non-numeric subject
        {"sub": "1", "exp": None},  # missing expiry
    ],
)
def test_malformed_claims_are_rejected(settings: Settings, claims: dict[str, object]) -> None:
    now = datetime.now(UTC)
    payload = {"iat": now, "exp": now + timedelta(hours=1), **claims}
    payload = {key: value for key, value in payload.items() if value is not None}
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenError):
        decode_access_token(token, settings=settings)


def test_unsigned_token_is_rejected(settings: Settings) -> None:
    unsigned = jwt.encode({"sub": "1"}, key=None, algorithm="none")

    with pytest.raises(TokenError):
        decode_access_token(unsigned, settings=settings)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_blocks_after_max_failures_then_expires() -> None:
    clock = FakeClock()
    limiter = LoginRateLimiter(max_failures=5, window_seconds=300, clock=clock)
    key = login_rate_key("A@B.com ", "10.0.0.1")

    for _ in range(4):
        limiter.record_failure(key)
        clock.now += 1
    assert not limiter.is_blocked(key)

    limiter.record_failure(key)
    assert limiter.is_blocked(key)
    assert 0 < limiter.retry_after(key) <= 300

    clock.now += 300
    assert not limiter.is_blocked(key)


def test_rate_limiter_reset_and_clear() -> None:
    limiter = LoginRateLimiter(max_failures=1)
    limiter.record_failure("a")
    limiter.record_failure("b")

    limiter.reset("a")
    assert not limiter.is_blocked("a")
    assert limiter.is_blocked("b")

    limiter.clear()
    assert not limiter.is_blocked("b")


def test_rate_limiter_bounds_memory() -> None:
    limiter = LoginRateLimiter(max_failures=1, max_keys=3)
    for index in range(10):
        limiter.record_failure(f"key-{index}")

    assert limiter.is_blocked("key-9")
    assert not limiter.is_blocked("key-0")


def test_login_rate_key_is_case_insensitive_on_email() -> None:
    assert login_rate_key(" User@Example.com", "1.2.3.4") == login_rate_key(
        "user@example.com", "1.2.3.4"
    )
    assert login_rate_key("user@example.com", None).endswith("|unknown")
