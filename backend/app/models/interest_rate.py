"""InterestRate model — differential rates per affiliation category and product."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class InterestRate(Base):
    """Differential interest rate for a customer category + product combination.

    Each row defines a rate range (tasa_min–tasa_max) for a specific
    ``(categoria, product_id, modalidad_pago)`` triple, versioned by
    ``vigencia_desde``.  The unique constraint prevents duplicate
    active rate definitions for the same dimension set.
    """

    __tablename__ = "interest_rates"

    __table_args__ = (
        UniqueConstraint(
            "categoria",
            "product_id",
            "modalidad_pago",
            "vigencia_desde",
            name="uq_rate_version",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    categoria: Mapped[str] = mapped_column(
        String(1),
        CheckConstraint("categoria IN ('A','B','C')"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modalidad_pago: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="'libranza', 'pago_directo', or None"
    )
    tasa_min: Mapped[float] = mapped_column(Float, nullable=False)
    tasa_max: Mapped[float] = mapped_column(Float, nullable=False)
    vigencia_desde: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<InterestRate cat={self.categoria} "
            f"prod={self.product_id} "
            f"modalidad={self.modalidad_pago}>"
        )
