"""Multi-layer validation for assessor recommendation chat LLM answers."""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.schemas.recommendation_chat import AssessorChatLlmAnswer

logger = logging.getLogger(__name__)

PROHIBITED_PHRASES = (
    "stop taking your medication",
    "stop your medication",
    "guaranteed cure",
    "guaranteed approval",
    "diagnose you with",
    "you have dementia",
    "prescribe ",
    "increase the dose",
    "decrease the dose",
)

EMERGENCY_HINTS = (
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "suicidal",
    "unconscious",
    "stroke",
    "heart attack",
    "call 911",
    "call 108",
    "medical emergency",
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise ValueError("The AI returned an empty response.")
    fence = _JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The AI returned invalid JSON.") from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("The AI returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("The AI response must be a JSON object.")
    return parsed


def validate_schema(raw_response: str) -> AssessorChatLlmAnswer:
    try:
        parsed = extract_json_object(raw_response)
        return AssessorChatLlmAnswer.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError(f"The AI response failed schema validation: {exc}") from exc


def validate_safety(text: str) -> None:
    normalized = (text or "").lower()
    for phrase in PROHIBITED_PHRASES:
        if phrase in normalized:
            raise ValueError(f"Potentially unsafe content detected: {phrase}")


def validate_allowed_ids(
    result: AssessorChatLlmAnswer,
    *,
    allowed_product_ids: set[str],
    allowed_solution_ids: set[str],
    allowed_rubric_ids: set[str],
) -> AssessorChatLlmAnswer:
    cleaned: list = []
    for rec in result.recommendations:
        product_id = (rec.product_id or "").strip() or None
        solution_id = (rec.solution_id or "").strip() or None
        if product_id and product_id not in allowed_product_ids:
            raise ValueError(f"Unsupported product_id: {product_id}")
        if solution_id and solution_id not in allowed_solution_ids:
            raise ValueError(f"Unsupported solution_id: {solution_id}")
        if not product_id and not solution_id:
            raise ValueError(
                "Each recommendation must include a product_id and/or solution_id "
                "from the allowlisted catalog."
            )
        linked = []
        for rid in rec.linked_rubric_item_ids or []:
            rid_s = str(rid).strip()
            if not rid_s:
                continue
            if allowed_rubric_ids and rid_s not in allowed_rubric_ids:
                # Drop invented rubric ids rather than failing the whole turn.
                continue
            linked.append(rid_s)
        cleaned.append(
            rec.model_copy(update={"product_id": product_id, "solution_id": solution_id, "linked_rubric_item_ids": linked})
        )

    cited = []
    for rid in result.cited_rubric_item_ids or []:
        rid_s = str(rid).strip()
        if not rid_s:
            continue
        if allowed_rubric_ids and rid_s not in allowed_rubric_ids:
            continue
        cited.append(rid_s)

    return result.model_copy(update={"recommendations": cleaned, "cited_rubric_item_ids": cited})


def validate_business_rules(result: AssessorChatLlmAnswer) -> AssessorChatLlmAnswer:
    if result.confidence < 0.0 or result.confidence > 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if result.requires_human_review and not (result.reason_for_review or "").strip():
        result = result.model_copy(
            update={"reason_for_review": "Model flagged this answer for human review."}
        )
    for rec in result.recommendations:
        if not (rec.reason or "").strip():
            raise ValueError("Each recommendation must include a reason.")
        if rec.requires_human_review and not (rec.review_reason or "").strip():
            raise ValueError("Recommendations needing review must include review_reason.")
    return result


def apply_review_policy(
    result: AssessorChatLlmAnswer,
    *,
    user_question: str,
) -> AssessorChatLlmAnswer:
    q = (user_question or "").lower()
    answer = result.answer or ""
    needs_review = result.requires_human_review
    reason = result.reason_for_review

    if result.confidence < 0.7:
        needs_review = True
        reason = reason or "Model confidence below 0.7."

    if any(h in q or h in answer.lower() for h in EMERGENCY_HINTS):
        needs_review = True
        reason = reason or "Possible emergency or medical situation — escalate to a human."

    structural = ("electrical", "rewire", "structural", "load-bearing", "gas line")
    if any(s in answer.lower() for s in structural):
        needs_review = True
        reason = reason or "Suggestion involves electrical/structural work — verify on site."

    if any(r.requires_human_review for r in result.recommendations):
        needs_review = True
        reason = reason or "One or more recommendations require human verification."

    return result.model_copy(
        update={
            "requires_human_review": needs_review,
            "reason_for_review": reason if needs_review else None,
        }
    )


def validate_full_response(
    raw_response: str,
    *,
    user_question: str,
    allowed_product_ids: set[str],
    allowed_solution_ids: set[str],
    allowed_rubric_ids: set[str],
) -> AssessorChatLlmAnswer:
    result = validate_schema(raw_response)
    validate_safety(result.answer)
    for rec in result.recommendations:
        validate_safety(f"{rec.reason} {rec.review_reason or ''}")
    result = validate_business_rules(result)
    result = validate_allowed_ids(
        result,
        allowed_product_ids=allowed_product_ids,
        allowed_solution_ids=allowed_solution_ids,
        allowed_rubric_ids=allowed_rubric_ids,
    )
    result = apply_review_policy(result, user_question=user_question)
    return result


def build_repair_prompt(original_response: str, validation_error: str) -> str:
    return (
        "Your previous response failed validation.\n\n"
        f"Validation error:\n{validation_error}\n\n"
        f"Previous response:\n{original_response}\n\n"
        "Return corrected JSON only. Do not add commentary."
    )
