"""Notification model — outbound communications (WhatsApp, email)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Notification(Base):
    """An outbound notification sent to a customer."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False, comment='"wpp" / "email"'
    )
    asunto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(50), default="pendiente")
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Notification {self.tipo} — {self.estado}>"
