"""'Why this score?' for the Independence Score™, in plain words.

Built from the client's latest completed assessment with the same arithmetic as
scoring.score_assessment: Safe = full points, Needs attention = half, Risk = 0,
Doesn't apply = left out. Each question's lost points are turned into score points
(out of 100) so a family sees what pulls the number down.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.livewell import scoring
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.tenant import Tenant


PLAIN_AREAS = {
    "Activities of Daily Living (ADL)": "Daily self-care",
    "Instrumental ADLs (IADL)": "Household tasks",
}


def _area(title) -> str:
    """'1. Home Safety' → 'Home Safety'; jargon areas get plain names."""
    t = str(title or "").lstrip("0123456789. ").strip() or str(title or "")
    return PLAIN_AREAS.get(t, t)

RATING_WORDS = {"excellent": "Safe", "acceptable": "Needs attention", "unsafe": "Risk", "na": "Doesn't apply"}
SOURCES = "AARP HomeFit (home safety), CDC STEADI (falls) and WHO ICOPE (healthy ageing)"


def _latest(db: Session, elder_id: int) -> HomeSafetyAssessmentRecord | None:
    return (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder_id, HomeSafetyAssessmentRecord.status == "completed")
        .order_by(HomeSafetyAssessmentRecord.completed_at.desc().nullslast(), HomeSafetyAssessmentRecord.id.desc())
        .first()
    )


def _history_with_real_dates(db: Session, elder: Elder, raw: list) -> list[dict]:
    """Score history dated by when each assessment was actually done.

    The stored ``assessed_at`` fell back to the publish time; the assessment
    record's ``completed_at`` is the real date. One point per assessment.
    """
    rows = [h for h in raw if isinstance(h, dict) and h.get("total") is not None]
    ids = {str(h.get("assessment_id")) for h in rows if h.get("assessment_id")}
    done: dict[str, str] = {}
    if ids:
        for rec in (
            db.query(HomeSafetyAssessmentRecord)
            .filter(HomeSafetyAssessmentRecord.elder_id == elder.id, HomeSafetyAssessmentRecord.assessment_id.in_(ids))
            .all()
        ):
            p = rec.payload if isinstance(rec.payload, dict) else {}
            at = rec.completed_at.isoformat() if rec.completed_at else (p.get("completedAt") or p.get("completed_at"))
            if at:
                done[str(rec.assessment_id)] = str(at)
    out: list[dict] = []
    index: dict[str, int] = {}
    for h in rows:
        aid = str(h.get("assessment_id") or "")
        point = {"total": h.get("total"), "at": done.get(aid) or h.get("assessed_at") or h.get("at")}
        if aid and aid in index:
            out[index[aid]] = point  # re-published: keep the latest score, one row
            continue
        if aid:
            index[aid] = len(out)
        out.append(point)
    return out


def explain(db: Session, elder: Elder, *, staff: bool = False) -> dict:
    rec = _latest(db, elder.id)
    if not rec or not isinstance(rec.payload, dict):
        return {"has_score": False, "how": _how(0, 0)}
    payload = rec.payload
    tenant = db.get(Tenant, elder.tenant_id)
    categories, _source = scoring.effective_rubric(tenant.workflow_config if tenant else None)
    categories = scoring.categories_for_payload(categories, payload)
    result = scoring.score_assessment(payload, categories)
    ratings = payload.get("ratings") if isinstance(payload.get("ratings"), dict) else {}
    profile = scoring.profile_from_payload(payload)
    max_total = float(result["max"] or 0)
    per_point = 100.0 / max_total if max_total else 0.0

    questions = 0
    na = 0
    drags: list[dict] = []
    answers: list[dict] = []
    for cat in scoring.applicable_categories(categories, profile):
        for item in cat["items"]:
            if scoring.is_hidden_unanswered(item, ratings):
                continue
            questions += 1
            r = scoring.normalize_rating(ratings.get(item["id"]))
            if r == "na":
                na += 1
            mp = float(item.get("maxPoints") or 0)
            earned = 0.0 if r == "na" else scoring.item_points(ratings.get(item["id"]), mp, str(item.get("scoringScale") or "standard"))
            lost = 0.0 if r == "na" else (mp - earned) * per_point
            row = {
                "label": item.get("label") or item["id"],
                "area": _area(cat.get("title") or cat["id"]),
                "rating": RATING_WORDS.get(r or "", "Not answered"),
                "lost": round(lost, 1),
                "critical": str(item.get("scoringScale") or "") == "critical",
            }
            if lost > 0:
                drags.append(row)
            if staff:
                answers.append(row)
    drags.sort(key=lambda d: -d["lost"])

    sh = (elder.custom_attributes or {}).get("safe_home") if isinstance(elder.custom_attributes, dict) else {}
    history = _history_with_real_dates(db, elder, (sh or {}).get("score_history") or [])
    raw_hist = [h for h in ((sh or {}).get("score_history") or []) if isinstance(h, dict)]
    idx = next((i for i, h in enumerate(raw_hist) if str(h.get("assessment_id") or "") == str(payload.get("id") or "")), None)
    if idx is None:
        previous = raw_hist[-1]["total"] if raw_hist and raw_hist[-1].get("total") != result["independence_score"] else None
    else:
        previous = raw_hist[idx - 1].get("total") if idx > 0 else None
    published = (sh or {}).get("safety_score") if isinstance((sh or {}).get("safety_score"), dict) else {}
    critical = [{"label": c["label"], "area": _area(c["category"])} for c in result["critical_unsafe"]]
    when = rec.completed_at or rec.updated_at
    return {
        "has_score": True,
        "score": result["independence_score"],
        "assessed_at": when.isoformat() if when else None,
        "assessor": str(payload.get("assessorName") or "").strip() or None,
        "questions_total": questions,
        "na_count": na,
        "areas": [{"title": _area(d["title"]), "score": d["score"]} for d in sorted(result["domain_scores"], key=lambda d: d["score"])],
        "top_drags": drags[:5],
        "critical": critical,
        # The band shown everywhere else: a critical item marked Risk caps it at High Risk.
        "grade": published.get("grade"),
        "grade_label": published.get("grade_label"),
        "capped": bool(critical) and (published.get("grade") in ("High Risk", "Critical")),
        "previous": previous,
        "history": history[-8:],
        "how": _how(questions, len(result["domain_scores"])),
        "answers": answers if staff else None,
    }


def _how(questions: int, areas: int) -> dict:
    return {
        "steps": [
            f"Our assessor answered {questions or 'about 80'} questions about the home and daily life, in {areas or 12} areas.",
            "Safe = full points · Needs attention = half · Risk = 0 · Doesn't apply = left out.",
            "Bathroom and fall safety count the most.",
            "Some items are critical (for example no grab bar by the toilet). If one is marked Risk, the band stays "
            "at High Risk until it's fixed, whatever the number.",
        ],
        "bands": [
            # Same words as LWA_INDEPENDENCE_BANDS (frontend/lib/livewell/assessment.ts).
            {"min": 90, "grade": "Excellent", "label": "Fully independent"},
            {"min": 75, "grade": "Good", "label": "Minor improvements recommended"},
            {"min": 60, "grade": "Moderate Risk", "label": "Several improvements recommended"},
            {"min": 40, "grade": "High Risk", "label": "Comprehensive intervention recommended"},
            {"min": 0, "grade": "Critical", "label": "Immediate safety and care coordination required"},
        ],
        "sources": f"Based on {SOURCES}. Guidance for safety at home, not a medical test.",
        "scale": "Out of 100. Higher is safer.",
    }
