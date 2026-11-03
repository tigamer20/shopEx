"""Grocery list history and bookmarks (ARCHITECTURE.md section 4, "Lists").

- ``GET /lists?bookmarked=true|false``: summaries, most recently used first (omit the filter for
  the whole history).
- ``POST /lists``: save a list (201).
- ``GET /lists/{id}``, ``PATCH /lists/{id}``, ``DELETE /lists/{id}``: one list of the caller.

Every query is scoped to the signed-in user: another user's list answers 404, exactly like a
list that does not exist, so ids of other accounts cannot be probed. ``last_used_at`` is only
touched by a search that reuses the list (``POST /search``); renaming, editing or bookmarking a
list does not move it in the history.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import utcnow
from app.deps import CurrentUser, DbSession
from app.models import GroceryList, User

router = APIRouter(prefix="/lists", tags=["lists"])

# Ids are 32-bit integer primary keys; larger values could never match and would overflow the
# SQLite driver, so they are rejected as invalid input.
MAX_LIST_ID = schemas.MAX_ID

ListId = Annotated[int, Path(ge=1, le=MAX_LIST_ID)]


def _get_owned_list(db: Session, user: User, list_id: int) -> GroceryList:
    """The list ``list_id`` if ``user`` owns it, else 404."""
    grocery_list = db.scalar(
        select(GroceryList).where(GroceryList.id == list_id, GroceryList.user_id == user.id)
    )
    if grocery_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")
    return grocery_list


def _items_to_json(items: list[schemas.GroceryItemInput]) -> list[dict[str, Any]]:
    return [item.model_dump() for item in items]


@router.get("", response_model=list[schemas.GroceryListSummary])
def list_lists(
    user: CurrentUser,
    db: DbSession,
    bookmarked: Annotated[bool | None, Query()] = None,
) -> list[schemas.GroceryListSummary]:
    """History (all lists) or bookmarks only, most recently used first."""
    query = select(GroceryList).where(GroceryList.user_id == user.id)
    if bookmarked is not None:
        query = query.where(GroceryList.bookmarked == bookmarked)
    # The id breaks ties so the order is stable when timestamps are equal.
    query = query.order_by(GroceryList.last_used_at.desc(), GroceryList.id.desc())
    return [schemas.GroceryListSummary.model_validate(row) for row in db.scalars(query)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.GroceryList)
def create_list(
    body: schemas.GroceryListCreate, user: CurrentUser, db: DbSession
) -> schemas.GroceryList:
    now = utcnow()
    grocery_list = GroceryList(
        user_id=user.id,
        name=body.name,
        items=_items_to_json(body.items),
        bookmarked=body.bookmarked,
        created_at=now,
        last_used_at=now,
    )
    db.add(grocery_list)
    db.commit()
    return schemas.GroceryList.model_validate(grocery_list)


@router.get("/{list_id}", response_model=schemas.GroceryList)
def read_list(list_id: ListId, user: CurrentUser, db: DbSession) -> schemas.GroceryList:
    return schemas.GroceryList.model_validate(_get_owned_list(db, user, list_id))


@router.patch("/{list_id}", response_model=schemas.GroceryList)
def update_list(
    list_id: ListId, body: schemas.GroceryListUpdate, user: CurrentUser, db: DbSession
) -> schemas.GroceryList:
    """Apply the fields sent with a non-null value; ``items`` replaces the whole list."""
    grocery_list = _get_owned_list(db, user, list_id)
    if body.name is not None:
        grocery_list.name = body.name
    if body.items is not None:
        # A new list object, so the JSON column is seen as modified.
        grocery_list.items = _items_to_json(body.items)
    if body.bookmarked is not None:
        grocery_list.bookmarked = body.bookmarked
    db.commit()
    return schemas.GroceryList.model_validate(grocery_list)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: ListId, user: CurrentUser, db: DbSession) -> None:
    db.delete(_get_owned_list(db, user, list_id))
    db.commit()
