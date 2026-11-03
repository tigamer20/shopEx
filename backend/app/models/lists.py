"""Grocery lists: history and bookmarks (ARCHITECTURE.md section 3).

History is every list of a user ordered by ``last_used_at`` desc; bookmarks are the lists with
``bookmarked = true``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class GroceryList(Base):
    __tablename__ = "grocery_lists"
    __table_args__ = (
        # Serves both "history" (order by last_used_at) and "bookmarks" listings per user.
        Index("ix_grocery_lists_user_id_last_used_at", "user_id", "last_used_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    # List of GroceryItemInput dicts. Assign a new list to persist changes (no in-place tracking).
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    bookmarked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User] = relationship(back_populates="lists")

    def __repr__(self) -> str:
        return f"GroceryList(id={self.id!r}, user_id={self.user_id!r})"
