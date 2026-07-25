"""Analytics router — dashboard endpoints for pipeline, trends, and KPIs."""

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_service(request: Request) -> AnalyticsService | None:
    return getattr(request.app.state, "analytics_service", None)


def _service_unavailable() -> JSONResponse:
    return JSONResponse(
        content={"detail": "Analytics service not available."},
        status_code=503,
    )


@router.get("/summary")
async def analytics_summary(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_full_summary()
    return JSONResponse(content=data)


@router.get("/pipeline")
async def pipeline_stats(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_pipeline_summary()
    return JSONResponse(content=data)


@router.get("/trends")
async def daily_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365),
) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_daily_trends(days=days)
    return JSONResponse(content=data)


@router.get("/customers")
async def customer_profile(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_customer_profile()
    return JSONResponse(content=data)


@router.get("/credits")
async def credit_stats(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_credit_stats()
    return JSONResponse(content=data)


@router.get("/insurance")
async def insurance_analytics(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_insurance()
    return JSONResponse(content=data)


@router.get("/efficiency")
async def ai_efficiency(request: Request) -> JSONResponse:
    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_ai_efficiency()
    return JSONResponse(content=data)


@router.get("/supervision")
async def supervision(request: Request) -> JSONResponse:
    """Return all sessions with conversations for human-in-the-loop monitoring.

    Requires admin authentication via ``Authorization: Bearer admin-token``.
    """
    from app.routers.auth import require_admin

    auth_header = request.headers.get("Authorization")
    require_admin(authorization=auth_header)  # type: ignore[arg-type]

    svc = _get_service(request)
    if svc is None:
        return _service_unavailable()
    data = await svc.get_supervision()
    return JSONResponse(content=data)
