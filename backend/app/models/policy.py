"""Policy model — issued insurance contracts linked to customers."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Policy(Base):
    """An issued insurance policy binding a customer to an insurance product."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    insurance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insurances.id"), nullable=False
    )
    numero_poliza: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prima: Mapped[float] = mapped_column(Float, nullable=False)
    estado: Mapped[str] = mapped_column(String(50), default="activo")
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Policy #{self.numero_poliza} — {self.estado}>"
