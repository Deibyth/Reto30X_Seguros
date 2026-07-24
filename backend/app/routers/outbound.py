"""Outbound messaging router — endpoints consumed by the WhatsApp bot."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update

from app.database import get_db
from app.models.customer import Customer
from app.models.notification import Notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outbound", tags=["outbound"])


# --- Response models ---


class PendingItem(BaseModel):
    notification_id: str
    phone: str
    content: str
    customer_name: Optional[str] = None
    audio_url: Optional[str] = None


class PendingResponse(BaseModel):
    items: list[PendingItem]


class StatusResponse(BaseModel):
    status: str = "ok"


# --- Endpoints ---


@router.get("/pending", response_model=PendingResponse)
async def get_pending(request: Request, limit: int = 20) -> PendingResponse:
    """Return pending outbound WhatsApp notifications.

    Queries Notification records with ``estado="pendiente"`` and
    ``tipo="wpp"``, joined with Customer to provide phone and name.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be 1–50")

    items: list[PendingItem] = []
    async for db in get_db():
        stmt = (
            select(Notification, Customer)
            .join(Customer, Notification.customer_id == Customer.id)
            .where(
                Notification.estado == "pendiente",
                Notification.tipo == "wpp",
                Notification.scheduled_at <= datetime.utcnow(),
            )
            .order_by(Notification.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

        for notification, customer in rows:
            items.append(
                PendingItem(
                    notification_id=notification.id,
                    phone=customer.telefono or "",
                    content=notification.contenido,
                    customer_name=customer.nombre_completo,
                    audio_url=notification.audio_url,
                )
            )
        break

    return PendingResponse(items=items)


@router.post("/{notification_id}/sent", response_model=StatusResponse)
async def mark_sent(notification_id: str, request: Request) -> StatusResponse:
    """Mark a notification as sent."""
    async for db in get_db():
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.estado = "enviado"
        notification.sent_at = datetime.utcnow()
        await db.commit()
        break

    return StatusResponse(status="ok")


@router.post("/{notification_id}/responded", response_model=StatusResponse)
async def mark_responded(
    notification_id: str, request: Request
) -> StatusResponse:
    """Mark a notification as responded (customer replied)."""
    async for db in get_db():
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.estado = "respondido"
        notification.responded_at = datetime.utcnow()
        await db.commit()
        break

    return StatusResponse(status="ok")


class FailedBody(BaseModel):
    error: str = ""


@router.post("/{notification_id}/failed", response_model=StatusResponse)
async def mark_failed(
    notification_id: str, body: FailedBody, request: Request
) -> StatusResponse:
    """Mark a notification as failed delivery.

    Increments ``intento_actual`` and stores the error message.
    If remaining attempts are exhausted, sets estado to ``fallido``.
    Otherwise resets estado to ``pendiente`` for re-scheduling.
    """
    async for db in get_db():
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.intento_actual += 1
        notification.error_log = body.error

        if notification.intento_actual >= notification.max_intentos:
            notification.estado = "fallido"
        else:
            # Keep it pending for a re-attempt
            notification.estado = "pendiente"

        await db.commit()
        break

    return StatusResponse(status="ok")
