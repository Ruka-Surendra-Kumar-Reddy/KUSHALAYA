"""Product suggestions from an assessment.

Every question rated Risk ("unsafe") or Needs attention ("acceptable") is
matched to the products that fix it: the admin's list on the Products page
(`Product.fixes`), or — until that is set — keywords in the question text.
Suggestions show inside the assessment, on the client's Orders tab and in the
family portal; there is no separate suggestions page.
"""

from sqlalchemy.orm import Session

from app.livewell.commerce import GST_BP, ensure_default_products, price_paise
from app.livewell.scoring import effective_rubric
from app.models.commerce import Product
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.tenant import Tenant

# Keyword fallback: product-name fragment -> words in a question that it fixes.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("grab bar", ("grab bar", "grab-bar", "grab rail")),
    ("toilet rail", ("toilet",)),
    ("shower chair", ("shower chair", "shower seat", "bath seat", "bathing", "sit to shower")),
    ("bath mat", ("anti-slip", "non-slip", "slip", "wet floor", "bath mat")),
    ("floor treatment", ("anti-slip", "non-slip", "slip", "flooring", "slippery")),
    ("pull cord", ("emergency", "alarm", "call bell", "pull cord")),
    ("bed rail", ("bed",)),
    ("sos wearable", ("emergency", "fall alert", "alarm", "alone", "help button", "sos")),
]

SEVERITY = {"unsafe": "risk", "acceptable": "attention"}


def _questions(db: Session, tenant_id: int) -> dict[str, str]:
    tenant = db.get(Tenant, tenant_id)
    categories, _ = effective_rubric(tenant.workflow_config if tenant else None)
    return {i["id"]: str(i.get("label") or i["id"]) for c in categories for i in c.get("items", []) if i.get("id")}


def default_fixes(product_name: str, questions: dict[str, str]) -> list[str]:
    name = product_name.lower()
    words: tuple[str, ...] = ()
    for frag, kw in KEYWORDS:
        if frag in name:
            words = kw
            break
    if not words:
        return []
    return [qid for qid, label in questions.items() if any(w in label.lower() for w in words)]


def fixes_for(product: Product, questions: dict[str, str]) -> list[str]:
    return list(product.fixes or []) or default_fixes(product.name, questions)


def latest_assessment(db: Session, elder_id: int) -> HomeSafetyAssessmentRecord | None:
    rows = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder_id)
        .order_by(HomeSafetyAssessmentRecord.updated_at.desc())
        .all()
    )
    done = [r for r in rows if r.status == "completed"]
    return (done or rows or [None])[0]


def suggestions_for_ratings(db: Session, tenant_id: int, ratings: dict) -> list[dict]:
    ensure_default_products(db, tenant_id)
    questions = _questions(db, tenant_id)
    flagged = {qid: SEVERITY[r] for qid, r in (ratings or {}).items() if r in SEVERITY}
    if not flagged:
        return []
    out = []
    for p in db.query(Product).filter(Product.tenant_id == tenant_id, Product.active.is_(True)).all():
        hits = [q for q in fixes_for(p, questions) if q in flagged]
        if not hits:
            continue
        reasons = sorted(
            ({"question_id": q, "label": questions.get(q, q), "severity": flagged[q]} for q in hits),
            key=lambda r: r["severity"] != "risk",
        )
        risk = sum(1 for r in reasons if r["severity"] == "risk")
        price = price_paise(p.cost_paise, p.margin_bp)
        out.append(
            {
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "price_paise": price,
                "price_with_gst_paise": price + price * GST_BP // 10000,
                "priced": p.cost_paise > 0,
                "reasons": reasons,
                "priority": "high" if risk else "medium",
                "_rank": risk * 2 + (len(reasons) - risk),
            }
        )
    out.sort(key=lambda s: -s["_rank"])
    for s in out:
        s.pop("_rank")
    return out


def suggestions_for_elder(db: Session, tenant_id: int, elder_id: int) -> dict:
    row = latest_assessment(db, elder_id)
    payload = (row.payload if row else None) or {}
    photos = [
        {
            "document_id": p.get("documentId"),
            "room_type": p.get("roomType") or "",
            "caption": p.get("caption") or "",
        }
        for p in payload.get("photos") or []
        if isinstance(p, dict) and p.get("documentId")
    ]
    return {
        "assessment_id": row.assessment_id if row else None,
        "assessment_status": row.status if row else None,
        "score": payload.get("independenceScore"),
        "items": suggestions_for_ratings(db, tenant_id, payload.get("ratings") or {}) if row else [],
        "photos": photos,
    }


def family_view(data: dict) -> dict:
    """What the family sees: products, why, and the price with GST — never cost or margin."""
    return {
        "score": data["score"],
        "items": [
            {
                "product_id": s["product_id"],
                "name": s["name"],
                "priority": s["priority"],
                "price_with_gst_paise": s["price_with_gst_paise"] if s["priced"] else None,
                "reasons": [r["label"] for r in s["reasons"]],
            }
            for s in data["items"]
        ],
    }
