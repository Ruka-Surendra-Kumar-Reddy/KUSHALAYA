from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_entity", "entity_type", "entity_id"),
        Index("ix_documents_tenant_status", "tenant_id", "verification_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=True,
    )

    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(index=True)

    document_type: Mapped[str] = mapped_column(String(100))
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(1000))
    storage_url: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)

    ocr_extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qr_extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qr_validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    verified_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )
