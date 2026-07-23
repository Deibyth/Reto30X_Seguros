"""Product model — financial products (credits, insurances)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Product(Base):
    """Represents a financial product offered to customers."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False, comment='"credito" / "seguro"'
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_maximo: Mapped[float | None] = mapped_column(Float, nullable=True)
    modalidad: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Product {self.nombre} ({self.tipo})>"
