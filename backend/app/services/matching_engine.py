from sqlalchemy.orm import Session

from app.core.responses import raise_not_found
from app.core.vertical_guards import require_tenant_feature
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.match_result import MatchResult
from app.models.match_run import MatchRun
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.matching import FeedbackRequest, RecommendRequest
from app.services.matching.plugins.registry import get_matching_plugin


class MatchingEngine:

    @staticmethod
    def _get_elder(db: Session, elder_id: int, tenant_id: int | None) -> Elder | None:
        query = db.query(Elder).filter(Elder.id == elder_id)
        if tenant_id is not None:
            query = query.filter(Elder.tenant_id == tenant_id)
        return query.first()

    @classmethod
    def recommend(
        cls,
        db: Session,
        request: RecommendRequest,
        user: User,
    ) -> dict:
        require_tenant_feature(db, user, "elder_matching")
        elder = cls._get_elder(db, request.elder_id, user.tenant_id)
        if not elder:
            raise_not_found("Elder not found")

        tenant = db.query(Tenant).filter(Tenant.id == elder.tenant_id).first()
        vertical = tenant.vertical if tenant else None
        plugin = get_matching_plugin(vertical)
        return plugin.recommend(
            db,
            request.elder_id,
            user,
            request.limit,
        )

    @staticmethod
    def get_results(
        db: Session,
        elder_id: int,
        user: User,
    ) -> dict:
        require_tenant_feature(db, user, "elder_matching")
        tenant_id = user.tenant_id
        query = (
            db.query(MatchRun)
            .filter(MatchRun.elder_id == elder_id)
            .order_by(MatchRun.created_at.desc())
        )
        if tenant_id is not None:
            query = query.filter(MatchRun.tenant_id == tenant_id)

        match_run = query.first()
        if not match_run:
            return {"elder_id": elder_id, "match_run_id": None, "recommendations": []}

        results = (
            db.query(MatchResult)
            .filter(MatchResult.match_run_id == match_run.id)
            .order_by(MatchResult.rank)
            .all()
        )

        caregivers = {
            c.id: c
            for c in db.query(Caregiver).filter(
                Caregiver.id.in_([r.caregiver_id for r in results])
            )
        }

        recommendations = []
        for row in results:
            caregiver = caregivers.get(row.caregiver_id)
            name = (
                f"{caregiver.first_name} {caregiver.last_name}"
                if caregiver
                else "Unknown"
            )
            recommendations.append(
                {
                    "match_result_id": row.id,
                    "rank": row.rank,
                    "caregiver_id": row.caregiver_id,
                    "caregiver_name": name,
                    "match_score": row.match_score,
                    "confidence_score": row.confidence_score,
                    "component_scores": row.component_scores,
                    "reasons": row.reasons,
                }
            )

        return {
            "elder_id": elder_id,
            "match_run_id": match_run.id,
            "created_at": match_run.created_at.isoformat(),
            "algorithm_version": match_run.algorithm_version,
            "recommendations": recommendations,
        }

    @staticmethod
    def submit_feedback(
        db: Session,
        feedback: FeedbackRequest,
        user: User,
    ) -> dict:
        require_tenant_feature(db, user, "elder_matching")
        result = (
            db.query(MatchResult)
            .filter(MatchResult.id == feedback.match_result_id)
            .first()
        )
        if not result:
            raise_not_found("Match result not found")

        entry = RecommendationFeedback(
            match_result_id=result.id,
            user_id=user.id,
            rating=feedback.rating,
            comments=feedback.comments,
            decision=feedback.decision,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        return {
            "id": entry.id,
            "match_result_id": entry.match_result_id,
            "rating": entry.rating,
            "decision": entry.decision,
        }

    @staticmethod
    def get_history(
        db: Session,
        elder_id: int | None,
        user: User,
        limit: int = 20,
    ) -> dict:
        require_tenant_feature(db, user, "elder_matching")
        query = db.query(MatchRun).order_by(MatchRun.created_at.desc())

        if elder_id is not None:
            query = query.filter(MatchRun.elder_id == elder_id)

        if user.tenant_id is not None:
            query = query.filter(MatchRun.tenant_id == user.tenant_id)

        runs = query.limit(limit).all()

        return {
            "elder_id": elder_id,
            "runs": [
                {
                    "match_run_id": run.id,
                    "elder_id": run.elder_id,
                    "algorithm_version": run.algorithm_version,
                    "status": run.status,
                    "created_at": run.created_at.isoformat(),
                }
                for run in runs
            ],
        }
