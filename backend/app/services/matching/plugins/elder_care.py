"""ElderCare vertical — elder client to caregiver worker matching."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.responses import raise_not_found
from app.models.caregiver import Caregiver
from app.models.caregiver_rating import CaregiverRating
from app.models.caregiver_skill import CaregiverSkill
from app.models.elder import Elder
from app.models.elder_requirement import ElderRequirement
from app.models.incident import Incident
from app.models.match_result import MatchResult
from app.models.match_run import MatchRun
from app.models.placement_history import PlacementHistory
from app.models.skill import Skill
from app.models.user import User
from app.services.matching.scoring import score_caregiver

ALGORITHM_VERSION = "rules-v1-elder-care"


class ElderCareMatchingPlugin:
    algorithm_version = ALGORITHM_VERSION

    @staticmethod
    def _get_elder(db: Session, elder_id: int, tenant_id: int | None) -> Elder | None:
        query = db.query(Elder).filter(Elder.id == elder_id)
        if tenant_id is not None:
            query = query.filter(Elder.tenant_id == tenant_id)
        return query.first()

    @staticmethod
    def _caregiver_ratings_map(
        db: Session,
        caregiver_ids: list[int],
    ) -> dict[int, list[float]]:
        if not caregiver_ids:
            return {}

        rows = (
            db.query(
                CaregiverRating.caregiver_id,
                CaregiverRating.rating,
            )
            .filter(CaregiverRating.caregiver_id.in_(caregiver_ids))
            .all()
        )
        result: dict[int, list[float]] = {}
        for caregiver_id, rating in rows:
            result.setdefault(caregiver_id, []).append(rating)
        return result

    @staticmethod
    def _placement_stats(
        db: Session,
        caregiver_id: int,
    ) -> tuple[float | None, int]:
        total = (
            db.query(func.count(PlacementHistory.id))
            .filter(PlacementHistory.caregiver_id == caregiver_id)
            .scalar()
        )
        if not total:
            return None, 0

        successful = (
            db.query(func.count(PlacementHistory.id))
            .filter(
                PlacementHistory.caregiver_id == caregiver_id,
                PlacementHistory.outcome.in_(["SUCCESS", "COMPLETED"]),
            )
            .scalar()
        )
        completion_rate = successful / total if total else None

        incidents = (
            db.query(func.count(Incident.id))
            .filter(Incident.caregiver_id == caregiver_id)
            .scalar()
        )
        return completion_rate, incidents or 0

    def score_candidates(
        self,
        db: Session,
        elder: Elder,
        caregivers: list[Caregiver],
    ) -> list[dict]:
        requirements = (
            db.query(ElderRequirement)
            .filter(ElderRequirement.elder_id == elder.id)
            .all()
        )

        skill_ids = {r.skill_id for r in requirements}
        skills_by_id = {
            s.id: s
            for s in db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
        } if skill_ids else {}

        caregiver_ids = [c.id for c in caregivers]
        ratings_map = self._caregiver_ratings_map(db, caregiver_ids)

        skills_by_caregiver: dict[int, list[CaregiverSkill]] = {}
        if caregiver_ids:
            for cs in (
                db.query(CaregiverSkill)
                .filter(CaregiverSkill.caregiver_id.in_(caregiver_ids))
                .all()
            ):
                skills_by_caregiver.setdefault(cs.caregiver_id, []).append(cs)

        scored: list[dict] = []
        for caregiver in caregivers:
            completion_rate, incident_count = self._placement_stats(
                db,
                caregiver.id,
            )
            scored.append(
                score_caregiver(
                    elder,
                    caregiver,
                    requirements,
                    skills_by_caregiver.get(caregiver.id, []),
                    skills_by_id,
                    ratings_map.get(caregiver.id, []),
                    completion_rate,
                    incident_count,
                )
            )

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored

    def recommend(
        self,
        db: Session,
        elder_id: int,
        user: User,
        limit: int,
    ) -> dict:
        tenant_id = user.tenant_id
        elder = self._get_elder(db, elder_id, tenant_id)

        if not elder:
            raise_not_found("Elder not found")

        caregivers = (
            db.query(Caregiver)
            .filter(
                Caregiver.tenant_id == elder.tenant_id,
                Caregiver.status == "ACTIVE",
            )
            .all()
        )

        scored = self.score_candidates(db, elder, caregivers)
        top = scored[:limit]

        match_run = MatchRun(
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            created_by_user_id=user.id,
            algorithm_version=self.algorithm_version,
            status="COMPLETED",
        )
        db.add(match_run)
        db.flush()

        results = []
        for rank, item in enumerate(top, start=1):
            result = MatchResult(
                match_run_id=match_run.id,
                caregiver_id=item["caregiver_id"],
                rank=rank,
                match_score=item["match_score"],
                confidence_score=item["confidence_score"],
                component_scores=item["component_scores"],
                reasons=item["reasons"],
            )
            db.add(result)
            results.append(
                {
                    "rank": rank,
                    "match_result_id": None,
                    **item,
                }
            )

        db.commit()
        db.refresh(match_run)

        saved = (
            db.query(MatchResult)
            .filter(MatchResult.match_run_id == match_run.id)
            .order_by(MatchResult.rank)
            .all()
        )
        for entry, row in zip(results, saved):
            entry["match_result_id"] = row.id

        return {
            "match_run_id": match_run.id,
            "elder_id": elder.id,
            "algorithm_version": self.algorithm_version,
            "vertical": "ELDER_CARE",
            "total_candidates": len(caregivers),
            "recommendations": results,
        }
