"""The care journey: Assess → choose fixes → install → KushLife visits → reassess.

One small read for the family home page and the ops client page. Each step is
``done``, ``current`` or ``upcoming``; the first unfinished step carries "what's next"
and who does it. Money is integer paise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.care_job import CareJob
from app.models.commerce import Order
from app.models.elder import Elder
from app.livewell.brand import safety_score_name

OPEN_ORDER = ("pending_approval", "approved", "scheduled")


def _sh(elder: Elder) -> dict:
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    sh = attrs.get("safe_home")
    return sh if isinstance(sh, dict) else {}


def journey_for_elder(db: Session, elder: Elder) -> dict:
    from app.livewell.kushlife import kushlife_view
    from app.livewell.reassessment import due_info

    sh = _sh(elder)
    score = (sh.get("safety_score") or {}) if isinstance(sh.get("safety_score"), dict) else {}
    plan = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
    plan_items = [i for i in (plan.get("items") or []) if isinstance(i, dict)]
    critical = [c for c in (score.get("critical_findings") or []) if isinstance(c, dict)]
    if plan_items:
        # Same items as /plan: every critical finding has a plan item there.
        from app.livewell.family_service import _critical_findings, align_plan_urgency

        plan_items = align_plan_urgency(plan_items, _critical_findings(score))
    to_fix = max(len(plan_items), len(critical))
    re = due_info(db, elder)
    orders = db.query(Order).filter(Order.elder_id == elder.id, Order.status != "cancelled").all()
    done_orders = [o for o in orders if o.status == "completed"]
    since = datetime.now(timezone.utc) - timedelta(days=30)
    visits_30 = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder.id, CareJob.kind == "visit", CareJob.status == "completed",
                CareJob.completed_at >= since)
        .count()
    )
    kl = kushlife_view(db, elder, limit=3, staff=True)

    assessed = bool(re["last_assessed_at"]) and score.get("total") is not None
    steps = [
        {
            "key": "assess",
            "label": "Home assessment",
            "state": "done" if assessed else "current",
            "detail": f"{safety_score_name()} {score.get('total')}/100" if assessed else
                      ("Booked" if re["booked_job_id"] else "Not done yet"),
            "owner": "Care manager",
            "cta": None if assessed else ("Start assessment" if re["booked_job_id"] else "Book assessment"),
            "date": re["last_assessed_at"] if assessed else re["booked_at"],
        },
        {
            "key": "fixes",
            "label": "Fixes chosen",
            "state": "upcoming" if not assessed else ("done" if orders or not to_fix else "current"),
            "detail": (f"{len(orders)} of {to_fix} chosen" if to_fix and orders else
                       (f"{to_fix} fix{'es' if to_fix != 1 else ''} to choose"
                        + (f" ({len(critical)} critical)" if critical else "") if to_fix else
                        (f"{len(orders)} chosen" if orders else "Nothing to fix"))),
            "owner": "Family",
            "cta": "Approve fixes" if assessed and to_fix and not orders else None,
            "date": None,
        },
        {
            "key": "installed",
            "label": "Installed",
            "state": "upcoming" if not orders else ("done" if len(done_orders) == len(orders) else "current"),
            "detail": f"{len(done_orders)} of {len(orders)} installed" if orders else "After fixes are chosen",
            "owner": "Installer",
            "cta": None,
            "date": None,
        },
        {
            "key": "kushlife",
            "label": "KushLife visits",
            "state": "done" if visits_30 else "upcoming",
            "detail": (f"{visits_30} visit{'s' if visits_30 != 1 else ''} in 30 days · {kl['status']}" if visits_30
                       else "First KushLife visit to be booked"),
            "owner": "Care team",
            "cta": None if visits_30 else "Book a visit",
            "date": kl["visits"][0]["date"] if kl["visits"] else None,
        },
        {
            "key": "reassess",
            "label": "Reassessment",
            "state": "upcoming" if not assessed else ("current" if re["overdue"] else "upcoming"),
            "detail": ("Booked" if re["booked_job_id"] else ("Overdue" if re["overdue"] else "Due")) if assessed
                      else "Every 6 months",
            "owner": "Care manager",
            "cta": "Book reassessment" if assessed and re["overdue"] and not re["booked_job_id"] else None,
            "date": re["booked_at"] or re["due_at"],
        },
    ]
    current = next((s for s in steps if s["state"] == "current"), None)
    return {
        "steps": steps,
        "current": current["key"] if current else None,
        "next": (
            {"label": current["label"], "owner": current["owner"], "cta": current["cta"]} if current else None
        ),
        "score": score.get("total"),
        "target_score": plan.get("projected_score"),
        "spent_paise": sum(o.total_paise for o in done_orders),
        "remaining_paise": sum(o.total_paise for o in orders if o.status in OPEN_ORDER),
    }
