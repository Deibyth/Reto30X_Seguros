"""Insurance model — insurance product definitions."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Insurance(Base):
    """Represents an insurance product with coverage details."""

    __tablename__ = "insurances"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    cobertura: Mapped[str | None] = mapped_column(Text, nullable=True)
    publico_objetivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insurance_category: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    prima_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Insurance {self.nombre}>"
