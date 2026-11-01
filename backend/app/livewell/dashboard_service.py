"""Ops home counts — clients, open assessments, visits today, catalog SKUs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.livewell.global_catalog_store import load_raw_global_catalog
from app.livewell.visit_service import _parse_dt, _visits_raw
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User

OPEN_ASSESSMENT_STATUSES = frozenset({"draft", "in_progress", "in-progress"})


def _utc_today():
    return datetime.now(timezone.utc).date()


def _visit_utc_date(raw: object):
    if not isinstance(raw, dict):
        return None
    dt = _parse_dt(raw.get("visited_at"))
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _catalog_item_count(db: Session) -> int:
    raw = load_raw_global_catalog(db) or {}
    products = raw.get("products") if isinstance(raw.get("products"), list) else []
    packages = raw.get("packages") if isinstance(raw.get("packages"), list) else []
    return len(products) + len(packages)


class HomeSafetyDashboardService:
    @staticmethod
    def summary(db: Session, user: User) -> dict:
        tid = resolve_tenant_id(user)
        elder_filters = [Elder.tenant_id == tid] if tid is not None else []
        assessment_filters = (
            [HomeSafetyAssessmentRecord.tenant_id == tid] if tid is not None else []
        )

        clients = (
            db.query(func.count(Elder.id)).filter(*elder_filters).scalar() or 0
        )

        status_rows = (
            db.query(
                HomeSafetyAssessmentRecord.status,
                func.count(),
            )
            .filter(*assessment_filters)
            .group_by(HomeSafetyAssessmentRecord.status)
            .all()
        )
        assessments_total = 0
        assessments_open = 0
        for status, count in status_rows:
            n = int(count or 0)
            assessments_total += n
            if str(status or "").lower() in OPEN_ASSESSMENT_STATUSES:
                assessments_open += n

        today = _utc_today()
        visits_total = 0
        visits_today = 0
        elders = db.query(Elder).filter(*elder_filters).all()
        for elder in elders:
            for raw in _visits_raw(elder):
                visits_total += 1
                if _visit_utc_date(raw) == today:
                    visits_today += 1

        return {
            "clients": int(clients),
            "assessments_open": assessments_open,
            "assessments_total": assessments_total,
            "visits_today": visits_today,
            "visits_total": visits_total,
            "catalog_items": _catalog_item_count(db),
        }
