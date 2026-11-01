"""Publish completed KAA assessments into elder.custom_attributes.safe_home for the family portal."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.livewell.brand import with_brand
from app.livewell.rule_engine_defaults import (
    BAND_DISPLAY,
    MEMBERSHIP_LABELS,
    risk_band_for_score,
)
from app.models.elder import Elder


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def independence_score_from_payload(payload: dict) -> int | None:
    for key in (
        "independenceScore",
        "independence_score",
        "score0to100",
        "normalizedScore",
    ):
        score = _optional_int(payload.get(key))
        if score is not None:
            return max(0, min(100, score))
    results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
    for key in ("independenceScore", "independence_score", "score0to100", "score"):
        score = _optional_int(results.get(key))
        if score is not None:
            return max(0, min(100, score))
    return None


def _plan_items_from_payload(payload: dict) -> list[dict]:
    raw = payload.get("familyImprovementPlan") or payload.get("family_improvement_plan")
    if not isinstance(raw, dict):
        return []
    items = raw.get("items") or raw.get("priorities") or []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or row.get("solution_id") or "").strip()
        title = str(row.get("title") or row.get("name") or "").strip()
        if not item_id and not title:
            continue
        priority = str(row.get("priority") or "medium").strip().lower()
        if priority not in ("critical", "high", "medium", "low"):
            priority = "medium"
        actions = row.get("actions") or row.get("recommended_solutions") or []
        if not isinstance(actions, list):
            actions = []
        out.append(
            {
                "id": item_id or title,
                "title": title or item_id,
                "priority": priority,
                "why": (str(row.get("why") or row.get("risk_description") or "").strip() or None),
                "actions": [str(a).strip() for a in actions if str(a).strip()],
                "score_gain": _optional_int(row.get("score_gain") or row.get("scoreImprovement")) or 0,
                "status": str(row.get("status") or "open").strip().lower() or "open",
                "domain": (str(row.get("domain") or row.get("section") or "").strip() or None),
                "estimated_cost": (
                    str(row.get("estimated_cost") or row.get("estimatedCost") or "").strip() or None
                ),
            }
        )
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda r: (priority_rank.get(r["priority"], 9), -int(r["score_gain"] or 0)))
    return out


def _summary_from_plan(score: int, band_label: str, items: list[dict]) -> str:
    if not items:
        return with_brand(
            f"LiveWell360 Safety Score {score}/100 ({band_label}). "
            "No open improvement items from this assessment."
        )
    titles = [i["title"] for i in items[:3]]
    return with_brand(
        f"LiveWell360 Safety Score {score}/100 ({band_label}). "
        f"Top priorities: {'; '.join(titles)}."
    )


def publish_assessment_to_family(
    db: Session,
    *,
    elder_id: int,
    tenant_id: int,
    payload: dict,
) -> bool:
    """Merge Independence Score + improvement plan into the elder's safe_home block.

    Returns True when a score was published.
    """
    score = independence_score_from_payload(payload)
    if score is None:
        return False

    elder = (
        db.query(Elder)
        .filter(Elder.id == elder_id, Elder.tenant_id == tenant_id)
        .first()
    )
    if not elder:
        return False

    # A critical-scale item rated unsafe caps the band at High Risk (scoring.py).
    critical_findings = payload.get("criticalFindings") or payload.get("critical_findings") or []
    critical_unsafe = isinstance(critical_findings, list) and len(critical_findings) > 0
    band = risk_band_for_score(score, critical_unsafe=critical_unsafe)
    band_key = str(band.get("band") or "moderate").strip().lower()
    grade, grade_label = BAND_DISPLAY.get(
        band_key, ("Moderate Risk", str(band.get("label") or ""))
    )
    band_status = band_key if band_key in BAND_DISPLAY else "moderate"
    assessed_at = (
        payload.get("completedAt")
        or payload.get("completed_at")
        or payload.get("updatedAt")
        or datetime.now(timezone.utc).isoformat()
    )
    plan_items = _plan_items_from_payload(payload)
    plan_meta = payload.get("familyImprovementPlan") if isinstance(
        payload.get("familyImprovementPlan"), dict
    ) else {}
    projected = _optional_int(plan_meta.get("projected_score") or plan_meta.get("projectedScore"))
    finding_count = _optional_int(plan_meta.get("finding_count") or plan_meta.get("findingCount")) or len(
        plan_items
    )

    summary = str(payload.get("familyScoreSummary") or "").strip() or _summary_from_plan(
        score, grade_label or grade, plan_items
    )

    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}

    # Preserve staff-updated plan item statuses across republish.
    prev_plan = block.get("improvement_plan") if isinstance(block.get("improvement_plan"), dict) else {}
    prev_by_id = {
        str(row.get("id")): row
        for row in (prev_plan.get("items") or [])
        if isinstance(row, dict) and row.get("id")
    }
    for item in plan_items:
        prev = prev_by_id.get(str(item.get("id")))
        if not prev:
            continue
        prev_status = str(prev.get("status") or "open").strip().lower()
        if prev_status in ("open", "scheduled", "done"):
            item["status"] = prev_status
        if not item.get("estimated_cost") and prev.get("estimated_cost"):
            item["estimated_cost"] = prev.get("estimated_cost")

    # Soft cost note from plan payload
    cost_note = str(
        plan_meta.get("estimated_cost_note") or plan_meta.get("estimatedCostNote") or ""
    ).strip() or None

    history = list(block.get("score_history") or [])
    if not isinstance(history, list):
        history = []
    # Avoid duplicate consecutive entries for the same assessment id + score.
    last = history[-1] if history else None
    if not (
        isinstance(last, dict)
        and str(last.get("assessment_id") or "") == str(payload.get("id") or "")
        and _optional_int(last.get("total")) == score
    ):
        history.append(
            {
                "total": score,
                "grade": grade,
                "assessed_at": assessed_at,
                "assessment_id": str(payload.get("id") or ""),
            }
        )
    history = history[-24:]

    block["safety_score"] = {
        "total": score,
        "max_total": 100,
        "grade": grade,
        "grade_label": grade_label,
        "band_status": band_status,
        "capped_by_critical_item": bool(band.get("capped_by_critical_item")),
        "critical_findings": [
            {
                "id": str(f.get("id") or ""),
                "label": str(f.get("label") or f.get("id") or ""),
                "category": str(f.get("category") or ""),
            }
            for f in critical_findings
            if isinstance(f, dict)
        ]
        if critical_unsafe
        else [],
        "assessed_at": assessed_at,
        "summary": summary,
        "is_demo": False,
    }
    block["improvement_plan"] = {
        "assessment_id": str(payload.get("id") or ""),
        "current_score": score,
        "projected_score": projected if projected is not None else score,
        "finding_count": finding_count,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "items": plan_items,
        "estimated_cost_note": cost_note,
    }

    domains_raw = payload.get("familyDomainScores") or payload.get("family_domain_scores") or []
    if not domains_raw and isinstance(payload.get("domainScores"), dict):
        domains_raw = [
            {"id": k, "title": k, "score": v} for k, v in payload["domainScores"].items()
        ]
    domains: list[dict] = []
    if isinstance(domains_raw, list):
        for row in domains_raw:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            sid = str(row.get("id") or title).strip()
            sc = _optional_int(row.get("score"))
            if not sid or sc is None:
                continue
            domains.append(
                {
                    "id": sid,
                    "title": title or sid,
                    "score": max(0, min(100, sc)),
                    "max_points": _optional_int(row.get("max_points") or row.get("maxPoints")) or 0,
                    "earned_points": float(row.get("earned_points") or row.get("earnedPoints") or 0),
                }
            )
    block["domain_scores"] = domains

    pathway = payload.get("familyCarePathway") or payload.get("family_care_pathway") or {}
    if not isinstance(pathway, dict):
        pathway = {}
    # The frontend and the default backend rules agree (see the care-pathway
    # matrix test). When a tenant has customised the rule engine only the
    # server evaluates those rules, so its stamps win over the client pathway.
    server_wins = str(payload.get("ruleEngineSource") or "") == "tenant" and bool(
        payload.get("recommended_membership_id")
    )
    if server_wins:
        membership_id = str(payload.get("recommended_membership_id") or "").strip() or None
        ecm = payload.get("ecm_recommended")
    else:
        membership_id = str(
            pathway.get("membership_id")
            or pathway.get("membershipId")
            or payload.get("recommended_membership_id")
            or ""
        ).strip() or None
        ecm = pathway.get("ecm_recommended")
        if ecm is None:
            ecm = payload.get("ecm_recommended")
    membership_label = None
    if not server_wins:
        membership_label = str(
            pathway.get("membership_label") or pathway.get("membershipLabel") or ""
        ).strip() or None
    if not membership_label and membership_id:
        membership_label = MEMBERSHIP_LABELS.get(membership_id)
    ecm_note = str(pathway.get("ecm_note") or pathway.get("ecmNote") or "").strip() or None
    if server_wins or not ecm_note:
        ecm_note = (
            "An Elder Care Manager (ECM) is recommended for ongoing coordination."
            if ecm
            else "ECM not required based on this assessment — your team remains available."
        )
    block["care_pathway"] = {
        "membership_id": membership_id,
        "membership_label": membership_label,
        "ecm_recommended": bool(ecm),
        "ecm_note": ecm_note,
        "source": "server" if server_wins else "client",
    }

    share = str(payload.get("familyShareBrief") or payload.get("family_share_brief") or "").strip()
    if not share:
        share = summary
    block["share_brief"] = share

    block["assessment_id"] = str(payload.get("id") or "")
    if payload.get("prospectId") is not None:
        block["prospect_id"] = _optional_int(payload.get("prospectId"))
    block["score_history"] = history
    block.pop("is_demo", None)

    # Critical findings go to the family once per assessment (portal notice + email).
    aid = str(payload.get("id") or "")
    critical_labels = [
        str(f.get("label") or f.get("id") or "") for f in critical_findings if isinstance(f, dict)
    ] if critical_unsafe else []
    tell_family = bool(critical_labels) and bool(aid) and block.get("critical_notified_for") != aid
    if tell_family:
        block["critical_notified_for"] = aid

    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.flush()
    if tell_family:
        notify_family_critical(db, elder, critical_labels)
    return True


def notify_family_critical(db: Session, elder: Elder, labels: list[str]) -> None:
    """Tell the family about urgent safety fixes. Reuses notify_family (portal
    notice + email under the family's "Safety concerns" choice)."""
    from app.livewell.family_notify import notify_family

    shown = [x for x in labels if x][:5]
    more = len([x for x in labels if x]) - len(shown)
    from app.livewell.family_alert_text import finding_problem

    rows = [f"- {finding_problem(x)}" for x in shown] + ([f"- and {more} more"] if more > 0 else [])
    body = "\n".join(
        [
            "The home safety assessment found things that need fixing first:",
            *rows,
            "Your care team will call you about them. You can see them under Score & plan.",
        ]
    )
    try:
        notify_family(db, elder, "Urgent safety fixes found", body, event="safety", path="/safety")
    except Exception:  # a notice must never fail publishing the score
        import logging

        logging.getLogger(__name__).exception("critical_notice_failed elder=%s", elder.id)
