"""Health check and admin endpoints (ARCHITECTURE.md section 4, "Admin & health").

- ``GET /health`` (no auth) -> ``schemas.HealthResponse``.
- ``POST /admin/refresh`` (``X-Admin-Token``, see ``deps.require_admin_token``: 404 while
  ``ADMIN_TOKEN`` is unset, 403 on a wrong token) -> ``schemas.RefreshResult``. Runs the daily
  refresh (``jobs.refresh.refresh_all``); called by the GitHub Actions cron.
"""

from fastapi import APIRouter, Depends

from app import __version__, schemas
from app.deps import AppSettings, DbSession, require_admin_token
from app.jobs.refresh import refresh_all

router = APIRouter(tags=["admin"])


@router.get("/health", response_model=schemas.HealthResponse)
def health() -> schemas.HealthResponse:
    """Liveness probe used by Render and the CI smoke test."""
    return schemas.HealthResponse(version=__version__)


@router.post(
    "/admin/refresh",
    response_model=schemas.RefreshResult,
    dependencies=[Depends(require_admin_token)],
)
def refresh(db: DbSession, settings: AppSettings) -> schemas.RefreshResult:
    """Re-discover stale areas and re-price every store now."""
    return refresh_all(db, settings=settings)
