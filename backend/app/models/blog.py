"""Blog posts for the public website (www /blog) and the images they use.

Posts belong to a tenant; the public site reads the site tenant (the first
tenant, same as Settings → Website). Body is Markdown, cleaned on save
(app/livewell/blog.py) and rendered without raw HTML on the site.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

BLOG_STATUSES = ("draft", "published", "scheduled")


class BlogPost(TimestampMixin, Base):
    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("uq_blog_posts_tenant_slug", "tenant_id", "slug", unique=True),
        Index("ix_blog_posts_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120))
    excerpt: Mapped[str] = mapped_column(String(160), default="")
    body_md: Mapped[str] = mapped_column(Text, default="")
    cover_image_url: Mapped[str] = mapped_column(String(500), default="")
    cover_image_alt: Mapped[str] = mapped_column(String(200), default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    author_name: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seo_title: Mapped[str] = mapped_column(String(70), default="")
    og_image_url: Mapped[str] = mapped_column(String(500), default="")
    canonical_url: Mapped[str] = mapped_column(String(500), default="")
    # FAQ pairs [{"q": ..., "a": ...}] — rendered as FAQPage JSON-LD on the article.
    faq: Mapped[list] = mapped_column(JSON, default=list)
    reading_minutes: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class BlogImage(TimestampMixin, Base):
    """An uploaded cover or inline picture. Served publicly by id."""

    __tablename__ = "blog_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(40), default="image/jpeg")
    alt: Mapped[str] = mapped_column(String(200), default="")
