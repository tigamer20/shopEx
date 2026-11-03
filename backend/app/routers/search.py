"""Grocery list search, the core flow (ARCHITECTURE.md section 4, "Search").

``POST /search`` (signed-in user): resolves every item of the list to its cheapest offer plus
two alternatives (``services.matching.search_grocery_list``).

With ``save_to_history`` (the default) the list is saved: ``list_id`` must then be one of the
caller's lists (404 otherwise, like ``/lists/{id}``) and has its items replaced and
``last_used_at`` touched; without ``list_id`` a new, non-bookmarked list is created. The
response carries the saved list's id, or null when nothing was saved.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app import schemas
from app.deps import AppSettings, CurrentUser, DbSession
from app.routers.stores import stores_unavailable
from app.services.matching import ListNotFoundError, search_grocery_list
from app.services.stores import StoresUnavailableError

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=schemas.SearchResponse)
def search(
    body: schemas.SearchRequest, user: CurrentUser, db: DbSession, settings: AppSettings
) -> schemas.SearchResponse:
    try:
        return search_grocery_list(db, user, body, settings=settings)
    except ListNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="List not found"
        ) from None
    except StoresUnavailableError:
        raise stores_unavailable() from None
