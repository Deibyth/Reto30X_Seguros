"""Claim model — customer claims against policies."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Claim(Base):
    """A customer claim filed against an insurance policy."""

    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    policy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("policies.id"), nullable=True
    )
    estado: Mapped[str] = mapped_column(String(50), default="reportado")
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_reclamado: Mapped[float | None] = mapped_column(Float, nullable=True)
    fecha_evento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Claim {self.id[:8]} — {self.estado}>"
