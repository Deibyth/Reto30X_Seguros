"""Customer model — core entity for all customer data."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Customer(Base):
    """Represents a bank customer with personal and financial information."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    documento_identidad: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salario: Mapped[float | None] = mapped_column(Float, nullable=True)
    tipo_contrato: Mapped[str | None] = mapped_column(String(50), nullable=True)
    antiguedad_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_crediticio: Mapped[float | None] = mapped_column(Float, nullable=True)
    categoria_afiliacion: Mapped[str | None] = mapped_column(
        String(1),
        CheckConstraint("categoria_afiliacion IN ('A','B','C')"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Customer {self.documento_identidad} — {self.nombre_completo}>"
