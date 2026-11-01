"""Bench replacement suggestions when attendance exceptions occur."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.services.matching.plugins.registry import get_matching_plugin
from app.services.scheduling_service import SchedulingService
from app.services.workforce_service import WorkforceService


class ReplacementStaffingService:

    @staticmethod
    def _display_name(first: str | None, last: str | None) -> str:
        name = f"{first or ''} {last or ''}".strip()
        return name or "Unknown"

    @classmethod
    def suggest_replacements(
        cls,
        db: Session,
        tenant_id: int,
        elder_id: int,
        *,
        exclude_caregiver_id: int | None = None,
        limit: int = 5,
        min_score: float = 40.0,
    ) -> dict:
        elder = (
            db.query(Elder)
            .filter(Elder.id == elder_id, Elder.tenant_id == tenant_id)
            .first()
        )
        if not elder:
            return {
                "elder_id": elder_id,
                "elder_name": None,
                "suggestions": [],
                "bench_available": 0,
            }

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        plugin = get_matching_plugin(tenant.vertical if tenant else None)
        _, _, bench = WorkforceService._active_bench(db, tenant_id)

        candidates = [
            c for c in bench if c.id != exclude_caregiver_id
        ]
        if not candidates:
            return {
                "elder_id": elder.id,
                "elder_name": SchedulingService._display_name(
                    elder.first_name,
                    elder.last_name,
                ),
                "exclude_caregiver_id": exclude_caregiver_id,
                "suggestions": [],
                "bench_available": 0,
            }

        scored = plugin.score_candidates(db, elder, candidates)
        qualified = [
            s for s in scored if s["match_score"] >= min_score
        ][:limit]

        caregiver_by_id = {c.id: c for c in candidates}
        suggestions = []
        for item in qualified:
            cg = caregiver_by_id.get(item["caregiver_id"])
            suggestions.append(
                {
                    "caregiver_id": item["caregiver_id"],
                    "caregiver_name": cls._display_name(
                        cg.first_name if cg else None,
                        cg.last_name if cg else None,
                    ),
                    "match_score": item["match_score"],
                    "reasons": item.get("reasons", [])[:4],
                }
            )

        return {
            "elder_id": elder.id,
            "elder_name": SchedulingService._display_name(
                elder.first_name,
                elder.last_name,
            ),
            "exclude_caregiver_id": exclude_caregiver_id,
            "suggestions": suggestions,
            "bench_available": len(candidates),
        }
