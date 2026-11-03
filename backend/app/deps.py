"""FastAPI dependencies shared by the routers (ARCHITECTURE.md section 4)."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.security import TokenError, decode_access_token

# auto_error=False so every authentication failure goes through the same 401 below.
_bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: DbSession,
    settings: AppSettings,
) -> User:
    """Resolve ``Authorization: Bearer <jwt>`` to the user it was issued for (401 otherwise)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials, settings=settings)
    except TokenError:
        raise _unauthorized() from None
    user = db.get(User, user_id)
    if user is None:
        # Token is valid but the account was deleted.
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin_token(
    settings: AppSettings,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Guard admin endpoints with the ``X-Admin-Token`` header.

    The endpoint does not exist (404) while ``ADMIN_TOKEN`` is unset; a wrong or missing
    token gets 403. Tokens are compared in constant time.
    """
    if settings.admin_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    expected = settings.admin_token.get_secret_value().encode()
    provided = (x_admin_token or "").encode()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
