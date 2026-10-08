"""Health check endpoint(s)."""

from fastapi import APIRouter

from app.config import get_settings
from app.database import ping_database
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Liveness + database connectivity check.

    Used by the frontend System Status panel to determine whether the
    backend (and its database) is reachable. `status` reflects the
    database check honestly — it reports "degraded" rather than
    falsely claiming "ok" when MongoDB is unreachable.
    """
    settings = get_settings()
    service_name = f"{settings.APP_NAME.lower().replace(' ', '-')}-backend"

    db_connected = await ping_database()

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        service=service_name,
        database="connected" if db_connected else "disconnected",
    )
