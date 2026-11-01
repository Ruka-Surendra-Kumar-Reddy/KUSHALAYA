"""Prompt builder for assessor recommendation chat."""

from __future__ import annotations

import json
from typing import Any

from app.livewell.brand import with_brand

_SYSTEM_PROMPT_TEMPLATE = """You are LiveWell360 Assessor Copilot — a home-safety recommendation assistant for trained assessors in India.

Rules:
1. Answer ONLY using the ASSESSMENT CONTEXT, ALLOWED PRODUCTS, and ALLOWED SOLUTIONS provided. Never invent product_id or solution_id values.
2. You support assessors; you do not diagnose medical conditions or prescribe medication.
3. Prefer practical, on-site verifiable recommendations (grab bars, lighting, slip resistance, decluttering, etc.).
4. If evidence is weak or the question is outside home-safety scope, set requires_human_review=true and explain why.
5. For emergencies or acute medical issues, tell the assessor to escalate to emergency services / clinical care and set requires_human_review=true.
6. LiveWell360 is informed by CDC STEADI / AARP-style guidance but is not CDC- or AARP-endorsed. Do not claim endorsement.
7. Return JSON only matching the required schema. No markdown outside JSON.

Required JSON schema:
{
  "answer": "string — clear guidance for the assessor",
  "recommendations": [
    {
      "product_id": "string|null — must be from ALLOWED PRODUCTS",
      "solution_id": "string|null — must be from ALLOWED SOLUTIONS",
      "priority": "low|medium|high|critical",
      "reason": "string",
      "linked_rubric_item_ids": ["ids from assessment/rubric only"],
      "requires_human_review": false,
      "review_reason": null
    }
  ],
  "confidence": 0.0-1.0,
  "requires_human_review": false,
  "reason_for_review": null,
  "cited_rubric_item_ids": ["ids referenced in the answer"]
}
"""


def system_prompt() -> str:
    return with_brand(_SYSTEM_PROMPT_TEMPLATE)


# Back-compat for imports/tests that still reference SYSTEM_PROMPT
SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE


def _compact_assessment(assessment: dict) -> dict[str, Any]:
    payload = assessment.get("payload") if isinstance(assessment.get("payload"), dict) else {}
    if not payload and assessment.get("id"):
        payload = assessment

    ratings = payload.get("ratings") if isinstance(payload.get("ratings"), dict) else {}
    items_out: list[dict] = []
    for item_id, raw in list(ratings.items())[:80]:
        rating: str | None = None
        note = ""
        if isinstance(raw, str):
            rating = raw
        elif isinstance(raw, dict):
            rating = str(raw.get("rating") or raw.get("value") or "")
            note = str(raw.get("note") or raw.get("notes") or "")[:200]
        else:
            rating = str(raw) if raw is not None else None
        norm = (rating or "").strip().lower()
        if norm in ("excellent", "na", "n/a", "not_applicable", "pass", ""):
            continue
        items_out.append(
            {
                "item_id": str(item_id),
                "rating": rating or "",
                "note": note,
            }
        )
        if len(items_out) >= 40:
            break

    profile = payload.get("residentProfile") if isinstance(payload.get("residentProfile"), dict) else {}
    score = payload.get("independenceScore") or payload.get("independence_score") or payload.get("score")
    return {
        "assessment_id": assessment.get("assessment_id") or payload.get("id"),
        "status": assessment.get("status") or payload.get("status"),
        "elder_id": assessment.get("elder_id") or payload.get("elderId"),
        "prospect_id": assessment.get("prospect_id") or payload.get("prospectId"),
        "client_name": payload.get("clientName")
        or payload.get("residentName")
        or profile.get("name")
        or profile.get("fullName"),
        "independence_score": score,
        "risk_band": payload.get("risk_band") or payload.get("recommended_risk_band"),
        "notes": str(payload.get("notes") or "")[:500],
        "focus_items": items_out,
    }


def _catalog_digest(catalog: dict, *, limit: int = 80) -> list[dict]:
    products = catalog.get("products") if isinstance(catalog, dict) else None
    if not isinstance(products, list):
        return []
    out = []
    for p in products:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        out.append(
            {
                "id": pid,
                "name": str(p.get("name") or p.get("title") or "")[:120],
                "category": str(p.get("category") or p.get("categoryPrefix") or "")[:60],
            }
        )
        if len(out) >= limit:
            break
    return out


def _solutions_digest(solutions: dict, *, limit: int = 80) -> list[dict]:
    rows = solutions.get("solutions") if isinstance(solutions, dict) else None
    if not isinstance(rows, list):
        return []
    out = []
    for s in rows:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid:
            continue
        out.append(
            {
                "id": sid,
                "name": str(s.get("name") or s.get("finding") or "")[:120],
                "priority": s.get("priority"),
                "rubric_item_ids": (s.get("rubricItemIds") or [])[:12],
            }
        )
        if len(out) >= limit:
            break
    return out


def build_context_message(
    *,
    assessment: dict,
    catalog: dict,
    solutions: dict,
) -> str:
    payload = {
        "assessment": _compact_assessment(assessment),
        "allowed_products": _catalog_digest(catalog),
        "allowed_solutions": _solutions_digest(solutions),
        "guidance": (
            "Recommendations must use only allowed_products[].id and/or "
            "allowed_solutions[].id. Prefer linking to focus_items[].item_id when relevant."
        ),
    }
    return (
        "ASSESSMENT CONTEXT + ALLOWED CATALOG (JSON):\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
    )


def build_chat_messages(
    *,
    assessment: dict,
    catalog: dict,
    solutions: dict,
    history: list[dict[str, str]],
    user_question: str,
    repair_note: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt()},
        {"role": "system", "content": build_context_message(
            assessment=assessment, catalog=catalog, solutions=solutions
        )},
    ]
    for turn in history:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_question.strip()})
    if repair_note:
        messages.append({"role": "user", "content": repair_note})
    return messages
