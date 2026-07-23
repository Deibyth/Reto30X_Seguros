"""Document model — uploaded files associated with applications or claims."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Document(Base):
    """An uploaded document linked to an application or claim."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id"), nullable=True
    )
    claim_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("claims.id"), nullable=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    tipo_documento: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Document {self.tipo_documento} — {self.file_path}>"
