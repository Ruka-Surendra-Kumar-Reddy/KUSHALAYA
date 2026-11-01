"""Assessor recommendation chat API — assessment-grounded Azure OpenAI Q&A."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import WRITE_ROLES, require_roles
from app.livewell.recommendation_chat_service import RecommendationChatService
from app.models.user import User
from app.schemas.recommendation_chat import (
    ConversationDetailOut,
    ConversationSummaryOut,
    CreateConversationRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.session_activity_service import SessionActivityService

router = APIRouter(
    prefix="/home-safety/recommendation-chat",
    tags=["Safe Home — Recommendation Chat"],
)


@router.post("/conversations", response_model=ConversationSummaryOut)
def create_conversation(
    data: CreateConversationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    result = RecommendationChatService.create_conversation(
        db,
        current_user,
        assessment_id=data.assessment_id,
        title=data.title,
        origin_session_id=SessionActivityService.session_id_from_request(request),
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Started recommendation chat",
        summary=f"Opened recommendation chat for assessment {data.assessment_id}",
        entity_type="assessment",
        entity_id=data.assessment_id,
        meta={"conversation_id": result["id"]},
        commit=True,
    )
    return result


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(
    assessment_id: str | None = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return RecommendationChatService.list_conversations(
        db,
        current_user,
        assessment_id=assessment_id,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return RecommendationChatService.get_conversation(db, current_user, conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
)
def send_message(
    conversation_id: str,
    data: SendMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    result = RecommendationChatService.send_message(
        db,
        current_user,
        conversation_id=conversation_id,
        content=data.content,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Asked recommendation chat",
        summary=(data.content[:160] + ("…" if len(data.content) > 160 else "")),
        entity_type="recommendation_chat",
        entity_id=conversation_id,
        meta={
            "requires_human_review": result["assistant_message"].get("requires_human_review"),
            "validation_status": result["assistant_message"].get("validation_status"),
        },
        commit=True,
    )
    return result
