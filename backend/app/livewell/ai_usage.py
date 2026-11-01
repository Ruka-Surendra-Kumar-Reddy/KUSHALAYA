"""Shared AI usage counter (daily caps + owner dashboard "AI usage" card).

Any AI feature records one row per provider call or cache hit:

    record_ai_usage(db, tenant_id=..., feature="room_preview", provider="gemini",
                    model="...", cache_hit=False, user_id=..., ref="job id")

Rows are added to the session; the caller commits.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_usage import AiUsageEvent

IST = timezone(timedelta(hours=5, minutes=30))


def record_ai_usage(
    db: Session,
    *,
    tenant_id: int | None,
    feature: str,
    provider: str | None = None,
    model: str | None = None,
    cache_hit: bool = False,
    status: str = "ok",
    user_id: int | None = None,
    ref: str | None = None,
) -> AiUsageEvent:
    row = AiUsageEvent(
        tenant_id=tenant_id,
        feature=feature,
        provider=provider,
        model=model,
        cache_hit=bool(cache_hit),
        status=status,
        user_id=user_id,
        ref=(ref or None),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    return row


def start_of_today_utc() -> datetime:
    """Midnight in India, as a naive UTC datetime (how rows are stored)."""
    now_ist = datetime.now(IST)
    midnight = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).replace(tzinfo=None)


def provider_calls_today(db: Session, tenant_id: int, feature: str) -> int:
    """Real provider calls today (cache hits are free and not counted)."""
    return int(
        db.query(func.count(AiUsageEvent.id))
        .filter(
            AiUsageEvent.tenant_id == tenant_id,
            AiUsageEvent.feature == feature,
            AiUsageEvent.cache_hit.is_(False),
            AiUsageEvent.created_at >= start_of_today_utc(),
        )
        .scalar()
        or 0
    )


def usage_summary(db: Session, tenant_id: int, *, days: int = 30) -> dict:
    """{feature: {calls, cache_hits, failed, today}} over the last `days` days."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    today = start_of_today_utc()
    out: dict[str, dict] = {}
    rows = (
        db.query(AiUsageEvent.feature, AiUsageEvent.cache_hit, AiUsageEvent.status, AiUsageEvent.created_at)
        .filter(AiUsageEvent.tenant_id == tenant_id, AiUsageEvent.created_at >= since)
        .all()
    )
    for feature, cache_hit, status, created_at in rows:
        bucket = out.setdefault(feature, {"calls": 0, "cache_hits": 0, "failed": 0, "today": 0})
        if cache_hit:
            bucket["cache_hits"] += 1
        else:
            bucket["calls"] += 1
            if created_at and created_at >= today:
                bucket["today"] += 1
        if status != "ok":
            bucket["failed"] += 1
    return {"days": days, "features": out}
