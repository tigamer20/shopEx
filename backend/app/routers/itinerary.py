"""Fastest route between the chosen stores (ARCHITECTURE.md section 4, "Itinerary")."""

from fastapi import APIRouter, HTTPException, status

from app import schemas
from app.deps import AppSettings, CurrentUser, DbSession
from app.services.itinerary import UnknownStoresError, plan_itinerary

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.post("", response_model=schemas.ItineraryResponse)
def create_itinerary(
    body: schemas.ItineraryRequest,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> schemas.ItineraryResponse:
    """Order the chosen stores to minimise total travel time and describe the route.

    Stores are shared, public data (not user-owned), so any signed-in user may route to them.
    Unknown store ids are a 404 that lists every missing id.
    """
    try:
        return plan_itinerary(db, user, body, settings=settings)
    except UnknownStoresError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
