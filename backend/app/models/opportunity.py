"""Opportunity model — cross-sell and up-sell opportunities."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Opportunity(Base):
    """A sales opportunity for a specific product linked to a customer."""

    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    estado: Mapped[str] = mapped_column(String(50), default="pendiente")
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="opportunity"
    )

    def __repr__(self) -> str:
        return f"<Opportunity {self.tipo} — {self.estado}>"
