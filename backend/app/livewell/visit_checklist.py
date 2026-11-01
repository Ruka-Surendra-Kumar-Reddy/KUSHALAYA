"""Per-client visit checklist (FIX_TODO #99).

The care manager keeps a short list of tasks for each client ("Give 9am medicines",
"Check feet", "Walk 10 min") in ``elder.custom_attributes["visit_checklist"]``; it can
be seeded from rubric questions flagged ``visitQuestion``. On each visit the caregiver
marks every item done / not done (+ reason); the result is saved on the visit as
``job.report["checklist"]`` and shown in the ops and family visit report.

Unticked items do not block closing a visit (KushLife already does); the app asks first.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request
from app.models.elder import Elder
from app.models.tenant import Tenant

KEY = "visit_checklist"
MAX_ITEMS = 30


def items_for(elder: Elder | None) -> list[dict]:
    raw = ((elder.custom_attributes or {}) if elder else {}).get(KEY) or {}
    rows = raw.get("items") if isinstance(raw, dict) else None
    return [
        {"id": str(i.get("id")), "label": str(i.get("label") or ""), "source": i.get("source") or ""}
        for i in (rows or [])
        if isinstance(i, dict) and i.get("id") and i.get("label")
    ]


def get_checklist(elder: Elder) -> dict:
    raw = (elder.custom_attributes or {}).get(KEY) or {}
    return {"items": items_for(elder), "updated_at": raw.get("updated_at") if isinstance(raw, dict) else None}


def save_checklist(db: Session, elder: Elder, items: list, user=None) -> dict:
    clean, seen = [], set()
    for i in (items or [])[:MAX_ITEMS]:
        if isinstance(i, str):
            i = {"label": i}
        if not isinstance(i, dict):
            continue
        label = str(i.get("label") or "").strip()[:200]
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        clean.append({
            "id": str(i.get("id") or "").strip()[:40] or uuid.uuid4().hex[:8],
            "label": label,
            "source": str(i.get("source") or "")[:60],
        })
    if len(items or []) > MAX_ITEMS:
        raise_bad_request(f"Keep the checklist to {MAX_ITEMS} items or fewer")
    attrs = dict(elder.custom_attributes or {})
    attrs[KEY] = {
        "items": clean,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": f"{user.first_name} {user.last_name}".strip() if user else "",
    }
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    return get_checklist(elder)


def rubric_suggestions(db: Session, elder: Elder) -> list[dict]:
    """Rubric questions the manager flagged as visit questions (Phase 3A), as checklist ideas."""
    from app.livewell.scoring import effective_rubric

    tenant = db.get(Tenant, elder.tenant_id)
    categories, _ = effective_rubric(tenant.workflow_config if tenant else None)
    have = {i["label"].lower() for i in items_for(elder)}
    out = []
    for c in categories:
        for i in c.get("items", []):
            if i.get("visitQuestion") and not i.get("hidden") and i.get("label"):
                out.append({
                    "id": f"rubric-{i['id']}",
                    "label": i["label"],
                    "source": f"rubric:{i['id']}",
                    "already_added": i["label"].lower() in have,
                })
    return out


def record_results(elder: Elder, raw) -> list[dict]:
    """The caregiver's answers against the client's current list.

    ``raw``: {item_id: {"done": bool, "reason": str}} or a list of {id, done, reason}.
    Items with no answer are saved as unticked (done = None).
    """
    if isinstance(raw, list):
        raw = {str(r.get("id")): r for r in raw if isinstance(r, dict)}
    raw = raw if isinstance(raw, dict) else {}
    out = []
    for item in items_for(elder):
        ans = raw.get(item["id"]) or {}
        if not isinstance(ans, dict):
            ans = {"done": ans}
        done = ans.get("done")
        done = None if done is None else bool(done)
        out.append({
            "id": item["id"],
            "label": item["label"],
            "done": done,
            "reason": str(ans.get("reason") or "").strip()[:300] if done is False else "",
        })
    return out


def family_lines(results: list[dict] | None) -> str:
    """Plain words for the family visit report."""
    if not results:
        return ""
    done = [r for r in results if r.get("done") is True]
    not_done = [r for r in results if r.get("done") is False]
    text = f"Visit checklist: {len(done)} of {len(results)} done."
    if not_done:
        text += " Not done: " + "; ".join(
            r["label"] + (f" ({r['reason']})" if r.get("reason") else "") for r in not_done
        ) + "."
    return text
