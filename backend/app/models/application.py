"""Application model — polymorphic form submission for credits and insurances."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Application(Base):
    """A form submission representing a credit or insurance application."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(
        String(50), nullable=False, comment='"credito" / "seguro"'
    )
    estado: Mapped[str] = mapped_column(String(50), default="iniciada")
    form_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Application {self.tipo} — {self.estado}>"
