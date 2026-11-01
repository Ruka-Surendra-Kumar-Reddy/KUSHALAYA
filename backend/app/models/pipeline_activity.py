from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PipelineActivity(TimestampMixin, Base):
    __tablename__ = "pipeline_activities"
    __table_args__ = (
        Index("ix_pipeline_activities_elder_prospect", "elder_prospect_id"),
        Index("ix_pipeline_activities_caregiver_prospect", "caregiver_prospect_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    elder_prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("elder_prospects.id"),
        nullable=True,
    )
    caregiver_prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregiver_prospects.id"),
        nullable=True,
    )

    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
