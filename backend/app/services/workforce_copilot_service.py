"""Workforce Copilot — grounded answers from tenant data + Azure OpenAI."""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.copilot_prompts import get_copilot_pack
from app.core.rbac import resolve_tenant_id
from app.models.tenant import Tenant
from app.models.user import User
from app.services import azure_openai_service
from app.services.workforce_context_service import WorkforceContextService

logger = logging.getLogger(__name__)

class WorkforceCopilotService:

    @staticmethod
    def _tenant_vertical(db: Session, tenant_id: int) -> str | None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return tenant.vertical if tenant else None

    @staticmethod
    def suggested_questions(
        context: dict | None = None,
        vertical: str | None = None,
    ) -> list[str]:
        pack = get_copilot_pack(vertical)
        questions = list(pack.suggested_questions)
        if not context:
            return questions

        bench = context.get("workforce", {}).get("caregivers_on_bench", 0)
        elders_open = context.get("elders", {}).get("without_active_assignment", 0)
        overdue = context.get("pipeline", {}).get("overdue_recruiter_follow_ups", 0)

        extra: list[str] = []
        if bench > 0:
            extra.append(
                f"We have {bench} caregivers on bench — who should we place first?"
            )
        if elders_open > 0:
            extra.append(
                f"Which ready caregivers fit our {elders_open} elders without assignments?"
            )
        if overdue > 0:
            extra.append(
                f"We have {overdue} overdue pipeline follow-ups — what should recruiters do today?"
            )

        return extra[:3] + questions

    @staticmethod
    def resolve_tenant(user: User, tenant_id: int | None) -> int:
        tid = resolve_tenant_id(user, tenant_id)
        if tid is None:
            raise HTTPException(
                status_code=400,
                detail="tenant_id is required for platform administrators",
            )
        return tid

    @staticmethod
    def build_context(db: Session, tenant_id: int) -> dict:
        return WorkforceContextService.build(db, tenant_id)

    @staticmethod
    def _fallback_answer(question: str, context: dict) -> str:
        w = context["workforce"]
        a = context["assignments"]
        e = context["elders"]
        lines = [
            "**Workforce Copilot (summary mode)**",
            "",
            "Azure OpenAI is not configured. Here is a direct summary from your operational data:",
            "",
            f"- **Active caregivers:** {w['caregivers_active']} "
            f"({w['caregivers_on_bench']} on bench, utilization {w.get('utilization_percent')}% )",
            f"- **Elders active:** {e['active']} "
            f"({e['without_active_assignment']} without an active assignment)",
            f"- **Assignments started:** {a['started_this_month']} this month vs "
            f"{a['started_last_month']} last month",
            f"- **Placement starts:** {a['placement_starts_this_month']} this month vs "
            f"{a['placement_starts_last_month']} last month",
            "",
            f"**Your question:** {question}",
            "",
            "Configure `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and "
            "`AZURE_OPENAI_DEPLOYMENT` for AI-generated narratives.",
        ]
        return "\n".join(lines)

    @staticmethod
    def ask(
        db: Session,
        user: User,
        question: str,
        tenant_id: int | None = None,
    ) -> dict:
        question = (question or "").strip()
        if len(question) < 3:
            raise HTTPException(status_code=400, detail="Question is too short")
        if len(question) > 2000:
            raise HTTPException(status_code=400, detail="Question exceeds 2000 characters")

        tid = WorkforceCopilotService.resolve_tenant(user, tenant_id)
        vertical = WorkforceCopilotService._tenant_vertical(db, tid)
        pack = get_copilot_pack(vertical)
        context = WorkforceCopilotService.build_context(db, tid)

        data_sources = [
            "caregivers",
            "elders",
            "assignments",
            "placement_history",
            "readiness_scores",
            "prospects_pipeline",
            "documents",
            "incidents",
            "attendance",
            "visits",
            "matching_runs",
        ]

        provider = "azure_openai" if azure_openai_service.is_configured() else "summary_fallback"
        model_version = (
            settings.AZURE_OPENAI_DEPLOYMENT
            if provider == "azure_openai"
            else "summary-v1"
        )

        if provider == "azure_openai":
            user_content = (
                f"{question}\n\n"
                "OPERATIONAL DATA (JSON — use only these facts):\n"
                f"{json.dumps(context, indent=2, default=str)}"
            )
            messages = [
                {"role": "system", "content": pack.system_prompt},
                {"role": "user", "content": user_content},
            ]
            try:
                answer = azure_openai_service.chat_completion(messages)
            except Exception as exc:
                logger.exception("Workforce Copilot Azure OpenAI failed")
                raise HTTPException(
                    status_code=502,
                    detail=f"AI service error: {exc}",
                ) from exc
        else:
            answer = WorkforceCopilotService._fallback_answer(question, context)

        logger.info(
            "workforce_copilot tenant_id=%s user_id=%s provider=%s q_len=%d",
            tid,
            user.id,
            provider,
            len(question),
        )

        return {
            "answer": answer,
            "question": question,
            "tenant_id": tid,
            "provider": provider,
            "model_version": model_version,
            "data_sources": data_sources,
            "context_as_of": context.get("as_of_utc"),
            "suggested_follow_ups": WorkforceCopilotService.suggested_questions(
                context, vertical
            )[:5],
            "vertical": vertical,
        }
