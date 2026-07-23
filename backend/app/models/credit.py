"""Credit model — extends Application with credit-specific fields."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Credit(Base):
    """Credit-specific details linked to an application."""

    __tablename__ = "credits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), unique=True, nullable=False
    )
    monto_solicitado: Mapped[float] = mapped_column(Float, nullable=False)
    plazo_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    destino: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tasa_interes: Mapped[float | None] = mapped_column(Float, nullable=True)
    modalidad_pago: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Credit ${self.monto_solicitado:.0f} @ {self.plazo_meses}m>"
