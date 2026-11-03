"""User account (ARCHITECTURE.md section 3)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, get_args

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db import Base, check_one_of, utcnow
from app.schemas import Language, TravelMode

if TYPE_CHECKING:
    from app.models.lists import GroceryList


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(check_one_of("language", get_args(Language)), name="ck_users_language"),
        CheckConstraint(
            check_one_of("travel_mode", get_args(TravelMode)), name="ck_users_travel_mode"
        ),
        # Access tokens identify the user by id, so an id must never be handed out twice.
        # PostgreSQL sequences never reuse ids; SQLite does unless AUTOINCREMENT is set.
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(60))
    language: Mapped[Language] = mapped_column(String(2), default="fr")
    search_radius_km: Mapped[float] = mapped_column(default=10.0)
    travel_mode: Mapped[TravelMode] = mapped_column(String(16), default="driving")
    tutorial_completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    lists: Mapped[list[GroceryList]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return value.strip().lower()

    def __repr__(self) -> str:
        return f"User(id={self.id!r})"
