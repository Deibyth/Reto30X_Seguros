"""Notification model — outbound communications (WhatsApp, email)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # --- Outbound scheduling / delivery fields ---
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    intento_actual: Mapped[int] = mapped_column(Integer, default=0)
    max_intentos: Mapped[int] = mapped_column(Integer, default=1)

    # --- Audio ---
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- FK to Opportunity ---
    opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("opportunities.id"), nullable=True
    )
    opportunity: Mapped["Opportunity | None"] = relationship(
        "Opportunity", back_populates="notifications"
    )

    def __repr__(self) -> str:
        return f"<Notification {self.tipo} — {self.estado}>"
