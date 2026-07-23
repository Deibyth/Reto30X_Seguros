"""Health check router — GET /health returns service and DB status."""

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    """Return service health including database connectivity.

    Returns 200 with ``database: "connected"`` when DB is reachable.
    Returns 503 with ``database: "disconnected"`` when DB is unreachable.
    """
    settings = request.app.state.settings
    start_time: float = request.app.state.start_time  # type: ignore[annotation-unchecked]
    uptime = time.time() - start_time

    db_status = "disconnected"
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            db_status = "connected"
            break
    except Exception as exc:
        logger.warning("Health check — DB unreachable: %s", exc)
        db_status = "disconnected"

    body: dict[str, object] = {
        "status": "ok" if db_status == "connected" else "error",
        "database": db_status,
    }

    # Only expose version/environment info in non-production environments
    env = settings.environment
    if env != "production":
        body["version"] = settings.app_version
        body["environment"] = env
        body["uptime_seconds"] = round(uptime, 2)

    status_code = 200 if db_status == "connected" else 503
    return JSONResponse(content=body, status_code=status_code)
