"""WorkforceOS unstaffed auto-match — pair uncovered demand with bench workers."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.assignment import AssignmentCreate
from app.schemas.matching import UnstaffedAutoMatchRequest
from app.services.assignment_service import AssignmentService
from app.services.auto_scheduling_service import AutoSchedulingService
from app.services.matching.plugins.registry import get_matching_plugin
from app.services.workforce_service import WorkforceService

CARE_LEVEL_PRIORITY = {
    "HIGH": 0,
    "CRITICAL": 0,
    "MEDIUM": 1,
    "MODERATE": 1,
    "LOW": 2,
}


class UnstaffedMatchService:

    @staticmethod
    def _care_priority(elder: Elder) -> int:
        level = (elder.care_level or "").upper()
        return CARE_LEVEL_PRIORITY.get(level, 3)

    @staticmethod
    def _display_name(first: str | None, last: str | None) -> str:
        name = f"{first or ''} {last or ''}".strip()
        return name or "Unknown"

    @staticmethod
    def _load_elders(db: Session, elder_ids: list[int]) -> dict[int, Elder]:
        if not elder_ids:
            return {}
        return {
            e.id: e
            for e in db.query(Elder).filter(Elder.id.in_(elder_ids)).all()
        }

    @classmethod
    def auto_match(
        cls,
        db: Session,
        data: UnstaffedAutoMatchRequest,
        user: User,
    ) -> dict:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant context required for unstaffed auto-match")

        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        plugin = get_matching_plugin(tenant.vertical if tenant else None)

        uncovered = AutoSchedulingService._uncovered_clients(db, tid)
        if not uncovered:
            return {
                "mode": "preview" if data.dry_run else "applied",
                "uncovered_count": 0,
                "bench_available": 0,
                "proposed": 0,
                "created": 0,
                "unmatched_count": 0,
                "proposals": [],
                "unmatched": [],
            }

        _, _, bench = WorkforceService._active_bench(db, tid)
        bench_by_id = {c.id: c for c in bench}
        available_ids = set(bench_by_id.keys())

        elder_map = cls._load_elders(db, [u["elder_id"] for u in uncovered])
        ordered = sorted(
            uncovered,
            key=lambda row: (
                cls._care_priority(elder_map[row["elder_id"]])
                if row["elder_id"] in elder_map
                else 99,
                row["elder_name"],
            ),
        )[: data.limit]

        proposals: list[dict] = []
        unmatched: list[dict] = []
        created = 0

        for row in ordered:
            elder = elder_map.get(row["elder_id"])
            if not elder:
                continue

            if not available_ids:
                unmatched.append(
                    {
                        "elder_id": elder.id,
                        "elder_name": row["elder_name"],
                        "reason": "No bench workers remaining",
                    }
                )
                continue

            candidates = [bench_by_id[cid] for cid in available_ids]
            scored = plugin.score_candidates(db, elder, candidates)
            qualified = [
                s for s in scored if s["match_score"] >= data.min_score
            ]

            if not qualified:
                best_score = scored[0]["match_score"] if scored else None
                unmatched.append(
                    {
                        "elder_id": elder.id,
                        "elder_name": row["elder_name"],
                        "reason": (
                            f"No bench worker met minimum score ({data.min_score})"
                            + (
                                f"; best was {best_score:.1f}"
                                if best_score is not None
                                else ""
                            )
                        ),
                    }
                )
                continue

            best = qualified[0]
            caregiver = bench_by_id[best["caregiver_id"]]
            action = "proposed" if data.dry_run else "assigned"
            proposals.append(
                {
                    "elder_id": elder.id,
                    "elder_name": row["elder_name"],
                    "caregiver_id": caregiver.id,
                    "caregiver_name": cls._display_name(
                        caregiver.first_name,
                        caregiver.last_name,
                    ),
                    "match_score": best["match_score"],
                    "confidence_score": best.get("confidence_score"),
                    "reasons": best.get("reasons", []),
                    "schedule_days": row["schedule_days"],
                    "action": action,
                }
            )

            available_ids.discard(caregiver.id)

            if not data.dry_run:
                AssignmentService.create_manual(
                    db,
                    AssignmentCreate(
                        elder_id=elder.id,
                        caregiver_id=caregiver.id,
                        match_score=best["match_score"],
                        start_date=date.today(),
                        status="ACTIVE",
                    ),
                    user,
                )
                created += 1

        return {
            "mode": "preview" if data.dry_run else "applied",
            "uncovered_count": len(uncovered),
            "bench_available": len(bench),
            "proposed": len(proposals),
            "created": created if not data.dry_run else 0,
            "unmatched_count": len(unmatched),
            "proposals": proposals,
            "unmatched": unmatched,
        }

    @classmethod
    def list_uncovered(cls, db: Session, user: User) -> dict:
        tid = resolve_tenant_id(user)
        rows = AutoSchedulingService._uncovered_clients(db, tid)
        if tid is not None:
            _, _, bench = WorkforceService._active_bench(db, tid)
            bench_count = len(bench)
        else:
            bench_count = 0
        return {
            "uncovered_count": len(rows),
            "bench_available": bench_count,
            "uncovered": rows,
        }
