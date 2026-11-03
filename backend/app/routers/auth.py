"""Authentication endpoints (ARCHITECTURE.md section 4, "Auth & user").

- ``POST /auth/register``: create an account and sign it in (201); 409 when the email is taken.
- ``POST /auth/login``: exchange email + password for an access token; a generic 401 whatever
  went wrong, and 429 once an (email, client IP) pair has failed too often.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import schemas
from app.deps import AppSettings, DbSession
from app.models import User
from app.security import (
    LoginRateLimiter,
    create_access_token,
    hash_password,
    login_rate_key,
    login_rate_limiter,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_login_rate_limiter() -> LoginRateLimiter:
    """The process-wide login limiter (a dependency so tests can swap in their own clock)."""
    return login_rate_limiter


RateLimiter = Annotated[LoginRateLimiter, Depends(get_login_rate_limiter)]


def _token_response(user: User, settings: AppSettings) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_access_token(user.id, settings=settings),
        user=schemas.User.model_validate(user),
    )


def _email_taken() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")


def _invalid_credentials() -> HTTPException:
    # Same answer for an unknown email and a wrong password: accounts cannot be enumerated.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.TokenResponse)
def register(
    body: schemas.RegisterRequest, db: DbSession, settings: AppSettings
) -> schemas.TokenResponse:
    """Create an account; the response signs the new user in straight away."""
    # Emails are lower-cased by the schema and the model, so equality is case-insensitive.
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise _email_taken()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        language=body.language,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent registration of the same email (unique index).
        db.rollback()
        raise _email_taken() from None
    return _token_response(user, settings)


@router.post("/login", response_model=schemas.TokenResponse)
def login(
    body: schemas.LoginRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    limiter: RateLimiter,
) -> schemas.TokenResponse:
    """Check the credentials and issue a token (rate-limited per email and client IP)."""
    client_ip = request.client.host if request.client else None
    rate_key = login_rate_key(body.email, client_ip)

    # Checked before verifying the password, so a blocked caller learns nothing new.
    retry_after = limiter.retry_after(rate_key)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        verify_dummy_password(body.password)
        authenticated = False
    else:
        authenticated = verify_password(body.password, user.password_hash)

    if user is None or not authenticated:
        limiter.record_failure(rate_key)
        raise _invalid_credentials()

    limiter.reset(rate_key)
    if password_needs_rehash(user.password_hash):
        # The hashing parameters were strengthened since this hash was made: upgrade it now
        # that the plain password is at hand.
        user.password_hash = hash_password(body.password)
        db.commit()
    return _token_response(user, settings)
