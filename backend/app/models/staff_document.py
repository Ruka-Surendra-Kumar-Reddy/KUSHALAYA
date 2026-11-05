"""Team → Documents: offer letters, relieving letters and other HR papers, per person.

Kept apart from ``documents`` on purpose: any staff role can read that table, and
these files are for owners only.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

#: Office staff are users; caregivers can exist without a login.
PERSON_TYPES = ("staff", "caregiver")
DOC_TYPES = ("offer_letter", "relieving_letter", "id_proof", "other")


class StaffDocument(TimestampMixin, Base):
    __tablename__ = "staff_documents"
    __table_args__ = (Index("ix_staff_documents_person", "tenant_id", "person_type", "person_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    person_type: Mapped[str] = mapped_column(String(12), nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
