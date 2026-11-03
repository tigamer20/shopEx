"""Current-user endpoints (ARCHITECTURE.md section 4, "Auth & user").

- ``GET /users/me``: the signed-in user's profile.
- ``PATCH /users/me``: update preferences (display name, language, radius, travel mode,
  tutorial flag). Email and password cannot be changed here: unknown fields are rejected.
- ``DELETE /users/me``: delete the account together with every grocery list it owns.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app import schemas
from app.deps import CurrentUser, DbSession

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=schemas.User)
def read_me(user: CurrentUser) -> schemas.User:
    return schemas.User.model_validate(user)


@router.patch("/me", response_model=schemas.User)
def update_me(body: schemas.UserUpdate, user: CurrentUser, db: DbSession) -> schemas.User:
    """Apply the fields sent with a non-null value; the others are left untouched."""
    for field, value in body.changes().items():
        setattr(user, field, value)
    db.commit()
    return schemas.User.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: DbSession) -> None:
    """Delete the account; its lists go with it (ON DELETE CASCADE)."""
    db.delete(user)
    db.commit()
