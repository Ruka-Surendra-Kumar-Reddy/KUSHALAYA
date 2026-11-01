"""Unit tests for recommendation chat validators."""

import pytest

from app.livewell.recommendation_chat_validators import (
    validate_full_response,
    validate_schema,
)


def test_schema_accepts_valid_json():
    raw = """
    {
      "answer": "Install a grab bar near the shower.",
      "recommendations": [
        {
          "product_id": "GB-001",
          "solution_id": null,
          "priority": "high",
          "reason": "Unsafe shower entry on assessment.",
          "linked_rubric_item_ids": ["bath.grab"],
          "requires_human_review": false,
          "review_reason": null
        }
      ],
      "confidence": 0.82,
      "requires_human_review": false,
      "reason_for_review": null,
      "cited_rubric_item_ids": ["bath.grab"]
    }
    """
    result = validate_schema(raw)
    assert result.answer.startswith("Install")
    assert result.recommendations[0].product_id == "GB-001"


def test_rejects_unknown_product():
    raw = """
    {
      "answer": "Buy something invented.",
      "recommendations": [
        {
          "product_id": "NOT-REAL",
          "priority": "high",
          "reason": "Because"
        }
      ],
      "confidence": 0.9
    }
    """
    with pytest.raises(ValueError, match="Unsupported product_id"):
        validate_full_response(
            raw,
            user_question="What should I recommend?",
            allowed_product_ids={"GB-001"},
            allowed_solution_ids=set(),
            allowed_rubric_ids={"bath.grab"},
        )


def test_escalates_low_confidence():
    raw = """
    {
      "answer": "Possibly a raised toilet seat.",
      "recommendations": [
        {
          "product_id": "RTS-1",
          "priority": "medium",
          "reason": "Mobility notes suggest transfer difficulty."
        }
      ],
      "confidence": 0.4
    }
    """
    result = validate_full_response(
        raw,
        user_question="Toilet recommendations?",
        allowed_product_ids={"RTS-1"},
        allowed_solution_ids=set(),
        allowed_rubric_ids=set(),
    )
    assert result.requires_human_review is True
