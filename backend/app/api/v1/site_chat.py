"""Public website chat: POST /api/v1/public/chat (see app/livewell/site_chat.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell import site_chat
from app.services.login_throttle import client_ip

router = APIRouter(prefix="/public/chat", tags=["Public — website chat"])


class ChatTurn(BaseModel):
    from_: str = Field("me", alias="from", max_length=8)
    text: str = Field("", max_length=1000)


class ChatPlan(BaseModel):
    name: str = Field("", max_length=60)
    annual_inr: int = Field(0, ge=0, le=10_000_000)
    monthly_inr: int = Field(0, ge=0, le=1_000_000)
    summary: str = Field("", max_length=300)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    plans: list[ChatPlan] = Field(default_factory=list, max_length=8)


@router.post("")
def chat(body: ChatRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    if not site_chat.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="Lots of questions at once — please call or WhatsApp us.")
    # A phone number typed into the chat is a call-back request: it must reach the
    # Leads board (owner report 2026-10-29: the bot said "noted" and nothing arrived).
    history = [{"from": t.from_, "text": t.text} for t in body.history]
    lead = site_chat.capture_lead(db, body.message, history, source_ip=client_ip(request))
    if lead:
        return {
            "reply": lead["reply"],
            "link": None,
            "link_label": None,
            "offer_callback": False,
            "source": "lead",
            "reference": lead["reference"],
        }
    out = site_chat.answer(
        body.message,
        [{"from": t.from_, "text": t.text} for t in body.history],
        [p.model_dump() for p in body.plans],
    )
    if out.get("source") == "ai" or out.get("source") == "fallback":
        try:
            from app.livewell.ai_usage import record_ai_usage

            record_ai_usage(
                db,
                tenant_id=None,
                feature="site_chat",
                provider="gemini",
                model=out.get("model"),
                status="ok" if out.get("source") == "ai" else "failed",
            )
            db.commit()
        except Exception:  # usage logging must never break the chat
            db.rollback()
    out.pop("model", None)
    return out
