"""Assessor recommendation chat — conversations grounded in a LiveWell assessment."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.catalog_service import HomeSafetyCatalogService
from app.livewell.recommendation_chat_prompts import build_chat_messages
from app.livewell.recommendation_chat_validators import (
    build_repair_prompt,
    validate_full_response,
)
from app.livewell.solution_service import HomeSafetySolutionService
from app.models.recommendation_chat import RecommendationConversation, RecommendationMessage
from app.models.user import User
from app.schemas.recommendation_chat import AssessorChatLlmAnswer
from app.services import azure_openai_service

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 12
RATE_LIMIT_PER_HOUR = 40
MAX_RETRIES = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tenant_id(user: User) -> int:
    tid = resolve_tenant_id(user)
    if tid is None:
        raise_bad_request("Tenant required")
    assert_tenant_access(user, tid)
    return tid


class RecommendationChatService:

    @staticmethod
    def _assessment_row(db: Session, user: User, assessment_id: str) -> dict:
        return HomeSafetyAssessmentService.get_assessment(db, user, assessment_id)

    @staticmethod
    def _allowlists(db: Session, user: User, assessment: dict) -> tuple[dict, dict, set[str], set[str], set[str]]:
        catalog = HomeSafetyCatalogService.get_catalog(db, user)
        solutions = HomeSafetySolutionService.get_solutions(db, user)
        product_ids = {
            str(p.get("id")).strip()
            for p in (catalog.get("products") or [])
            if isinstance(p, dict) and p.get("id")
        }
        solution_ids = {
            str(s.get("id")).strip()
            for s in (solutions.get("solutions") or [])
            if isinstance(s, dict) and s.get("id")
        }
        rubric_ids: set[str] = set()
        payload = assessment.get("payload") if isinstance(assessment.get("payload"), dict) else {}
        ratings = payload.get("ratings") if isinstance(payload.get("ratings"), dict) else {}
        rubric_ids.update(str(k) for k in ratings.keys())
        for s in solutions.get("solutions") or []:
            if isinstance(s, dict):
                for rid in s.get("rubricItemIds") or []:
                    if rid:
                        rubric_ids.add(str(rid).strip())
        return catalog, solutions, product_ids, solution_ids, rubric_ids

    @staticmethod
    def _assert_rate_limit(db: Session, *, tenant_id: int, user_id: int) -> None:
        since = _utcnow() - timedelta(hours=1)
        count = (
            db.query(RecommendationMessage)
            .join(
                RecommendationConversation,
                RecommendationConversation.id == RecommendationMessage.conversation_id,
            )
            .filter(
                RecommendationConversation.tenant_id == tenant_id,
                RecommendationConversation.user_id == user_id,
                RecommendationMessage.role == "user",
                RecommendationMessage.created_at >= since,
            )
            .count()
        )
        if count >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {RATE_LIMIT_PER_HOUR} chat messages per hour.",
            )

    @staticmethod
    def _to_summary(row: RecommendationConversation) -> dict:
        return {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "elder_id": row.elder_id,
            "prospect_id": row.prospect_id,
            "title": row.title or "",
            "status": row.status,
            "message_count": row.message_count,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _to_message(row: RecommendationMessage) -> dict:
        return {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "structured": row.structured,
            "validation_status": row.validation_status,
            "requires_human_review": bool(row.requires_human_review),
            "latency_ms": row.latency_ms,
            "created_at": row.created_at,
        }

    @staticmethod
    def create_conversation(
        db: Session,
        user: User,
        *,
        assessment_id: str,
        title: str | None = None,
        origin_session_id: str | None = None,
    ) -> dict:
        tid = _tenant_id(user)
        assessment = RecommendationChatService._assessment_row(db, user, assessment_id.strip())
        now = _utcnow()
        client = ""
        payload = assessment.get("payload") if isinstance(assessment.get("payload"), dict) else {}
        if isinstance(payload, dict):
            client = str(payload.get("clientName") or payload.get("residentName") or "").strip()
        row = RecommendationConversation(
            id=str(uuid.uuid4()),
            tenant_id=tid,
            user_id=user.id,
            assessment_id=assessment["assessment_id"],
            elder_id=assessment.get("elder_id"),
            prospect_id=assessment.get("prospect_id"),
            title=(title or f"Recommendations — {client or assessment['assessment_id']}")[:255],
            status="open",
            created_at=now,
            updated_at=now,
            message_count=0,
            origin_session_id=(origin_session_id or "").strip() or None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return RecommendationChatService._to_summary(row)

    @staticmethod
    def list_conversations(
        db: Session,
        user: User,
        *,
        assessment_id: str | None = None,
        limit: int = 40,
    ) -> list[dict]:
        tid = _tenant_id(user)
        q = db.query(RecommendationConversation).filter(
            RecommendationConversation.tenant_id == tid,
            RecommendationConversation.user_id == user.id,
        )
        if assessment_id:
            q = q.filter(RecommendationConversation.assessment_id == assessment_id.strip())
        rows = q.order_by(RecommendationConversation.updated_at.desc()).limit(limit).all()
        return [RecommendationChatService._to_summary(r) for r in rows]

    @staticmethod
    def get_conversation(db: Session, user: User, conversation_id: str) -> dict:
        tid = _tenant_id(user)
        row = (
            db.query(RecommendationConversation)
            .filter(
                RecommendationConversation.id == conversation_id,
                RecommendationConversation.tenant_id == tid,
                RecommendationConversation.user_id == user.id,
            )
            .first()
        )
        if not row:
            raise_not_found("Conversation not found")
        messages = (
            db.query(RecommendationMessage)
            .filter(RecommendationMessage.conversation_id == row.id)
            .order_by(RecommendationMessage.created_at.asc(), RecommendationMessage.id.asc())
            .all()
        )
        summary = RecommendationChatService._to_summary(row)
        summary["messages"] = [RecommendationChatService._to_message(m) for m in messages]
        return summary

    @staticmethod
    def _call_llm(
        messages: list[dict[str, str]],
        *,
        user_question: str,
        product_ids: set[str],
        solution_ids: set[str],
        rubric_ids: set[str],
    ) -> tuple[AssessorChatLlmAnswer, str, float, str]:
        if not azure_openai_service.is_configured():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT on the API server."
                ),
            )

        last_raw = ""
        last_error = "Unknown validation error"
        started = time.perf_counter()
        for attempt in range(MAX_RETRIES + 1):
            try:
                raw = azure_openai_service.chat_completion(
                    messages,
                    temperature=0.2,
                    max_tokens=max(1200, int(settings.AZURE_OPENAI_MAX_TOKENS or 1200)),
                )
            except RuntimeError as exc:
                logger.exception("recommendation_chat_llm_failed")
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            last_raw = raw
            try:
                validated = validate_full_response(
                    raw,
                    user_question=user_question,
                    allowed_product_ids=product_ids,
                    allowed_solution_ids=solution_ids,
                    allowed_rubric_ids=rubric_ids,
                )
                latency = round((time.perf_counter() - started) * 1000, 2)
                status = "ok" if attempt == 0 else "repaired"
                return validated, raw, latency, status
            except ValueError as exc:
                last_error = str(exc)
                logger.warning(
                    "recommendation_chat_validation_failed attempt=%s err=%s",
                    attempt,
                    last_error,
                )
                if attempt >= MAX_RETRIES:
                    break
                messages = list(messages) + [
                    {
                        "role": "user",
                        "content": build_repair_prompt(last_raw, last_error),
                    }
                ]

        raise HTTPException(
            status_code=422,
            detail=f"AI response failed validation after retry: {last_error}",
        )

    @staticmethod
    def send_message(
        db: Session,
        user: User,
        *,
        conversation_id: str,
        content: str,
    ) -> dict:
        tid = _tenant_id(user)
        question = (content or "").strip()
        if not question:
            raise_bad_request("Message content is required")
        if len(question) > 4000:
            raise_bad_request("Message is too long (max 4000 characters)")

        RecommendationChatService._assert_rate_limit(db, tenant_id=tid, user_id=user.id)

        convo = (
            db.query(RecommendationConversation)
            .filter(
                RecommendationConversation.id == conversation_id,
                RecommendationConversation.tenant_id == tid,
                RecommendationConversation.user_id == user.id,
            )
            .first()
        )
        if not convo:
            raise_not_found("Conversation not found")
        if convo.status != "open":
            raise_bad_request("Conversation is archived")

        assessment = RecommendationChatService._assessment_row(db, user, convo.assessment_id)
        catalog, solutions, product_ids, solution_ids, rubric_ids = (
            RecommendationChatService._allowlists(db, user, assessment)
        )

        now = _utcnow()
        user_msg = RecommendationMessage(
            conversation_id=convo.id,
            tenant_id=tid,
            role="user",
            content=question,
            structured=None,
            created_at=now,
            validation_status=None,
            requires_human_review=False,
        )
        db.add(user_msg)
        db.flush()

        prior_rows = (
            db.query(RecommendationMessage)
            .filter(
                RecommendationMessage.conversation_id == convo.id,
                RecommendationMessage.id != user_msg.id,
                RecommendationMessage.role.in_(("user", "assistant")),
            )
            .order_by(RecommendationMessage.created_at.desc(), RecommendationMessage.id.desc())
            .limit(HISTORY_LIMIT)
            .all()
        )
        prior = [{"role": r.role, "content": r.content} for r in reversed(prior_rows)]

        messages = build_chat_messages(
            assessment=assessment,
            catalog=catalog,
            solutions=solutions,
            history=prior,
            user_question=question,
        )

        answer, _raw, latency_ms, validation_status = RecommendationChatService._call_llm(
            messages,
            user_question=question,
            product_ids=product_ids,
            solution_ids=solution_ids,
            rubric_ids=rubric_ids,
        )

        assistant_msg = RecommendationMessage(
            conversation_id=convo.id,
            tenant_id=tid,
            role="assistant",
            content=answer.answer,
            structured=answer.model_dump(),
            model_deployment=settings.AZURE_OPENAI_DEPLOYMENT.strip() or None,
            latency_ms=latency_ms,
            validation_status=validation_status,
            requires_human_review=bool(answer.requires_human_review),
            created_at=_utcnow(),
        )
        db.add(assistant_msg)
        convo.message_count = int(convo.message_count or 0) + 2
        convo.updated_at = _utcnow()
        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        db.refresh(convo)

        logger.info(
            "recommendation_chat ok conversation=%s user=%s latency_ms=%s review=%s validation=%s",
            convo.id,
            user.id,
            latency_ms,
            answer.requires_human_review,
            validation_status,
        )

        return {
            "conversation": RecommendationChatService._to_summary(convo),
            "user_message": RecommendationChatService._to_message(user_msg),
            "assistant_message": RecommendationChatService._to_message(assistant_msg),
            "azure_configured": azure_openai_service.is_configured(),
        }
