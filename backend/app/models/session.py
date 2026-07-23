"""Session model — conversation state machine."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Session(Base):
    """Tracks conversation state and collected form data for a customer."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True
    )
    estado_actual: Mapped[str] = mapped_column(String(50), default="inicio")
    campos_diligenciados: Mapped[dict] = mapped_column(JSON, default=dict)
    ultima_intencion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    form_schema_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    insurance_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Session {self.id[:8]} — {self.estado_actual}>"
