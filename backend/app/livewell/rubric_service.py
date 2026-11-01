"""SafeHome 360™ assessment rubric — per-tenant workflow_config storage."""

from __future__ import annotations

import logging

from copy import deepcopy

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request
from app.livewell.stored_config import read_stored_config
from app.models.tenant import Tenant
from app.models.user import User

from app.livewell.config_keys import RUBRIC_KEY

VALID_SOURCES = frozenset({"safehome360", "aarp", "cdc_steadi", "cdc"})
VALID_SCALES = frozenset({"standard", "critical"})
VALID_INPUT_TYPES = frozenset({"rating", "yesno", "text"})
# Answer options an admin sets per question; each still saves one of these ratings,
# so scoring is unchanged (several options may share a rating).
VALID_OPTION_RATINGS = ("excellent", "acceptable", "unsafe", "na")
MAX_OPTIONS = 8
MAX_OPTION_LABEL = 100
MAX_ASK = 200


def _parse_options(raw) -> list[dict]:
    """Trimmed {label, rating} options: empty or unknown ones dropped, at most 8."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for opt in raw:
        if not isinstance(opt, dict):
            continue
        label = str(opt.get("label") or "").strip()[:MAX_OPTION_LABEL].strip()
        rating = str(opt.get("rating") or "").strip().lower()
        if label and rating in VALID_OPTION_RATINGS:
            out.append({"label": label, "rating": rating})
        if len(out) >= MAX_OPTIONS:
            break
    return out


def _parse_skip_rule(raw: str | dict | None) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw if raw.get("when") or raw.get("field") else None
    text = str(raw).strip()
    if not text:
        return None
    return {"when": text}


def _normalize_item(raw: dict, index: int) -> dict | None:
    item_id = str(raw.get("id", "")).strip()
    label = str(raw.get("label", "")).strip()
    if not item_id or not label:
        return None
    scale = str(raw.get("scoringScale", "standard")).lower()
    if scale not in VALID_SCALES:
        scale = "critical" if raw.get("critical") else "standard"
    source = str(raw.get("source", "safehome360")).lower()
    if source not in VALID_SOURCES:
        source = "safehome360"
    item = {
        "id": item_id,
        "label": label,
        "maxPoints": max(1, int(raw.get("maxPoints") or raw.get("max_points") or 1)),
        "scoringScale": scale,
        "source": source,
    }
    input_type = str(raw.get("inputType") or raw.get("input_type") or "rating").lower()
    if input_type not in VALID_INPUT_TYPES:
        input_type = "rating"
    if input_type != "rating":
        item["inputType"] = input_type
    ask = str(raw.get("ask") or "").strip()[:MAX_ASK].strip()
    if ask:
        item["ask"] = ask
    options = _parse_options(raw.get("options"))
    if options:
        item["options"] = options
    help_text = str(raw.get("help") or "").strip()
    if help_text:
        item["help"] = help_text
    group = str(raw.get("group", "")).strip()
    if group:
        item["group"] = group
    # Soft hide: kept in the bank (old reports still render it), not asked on new assessments.
    if raw.get("hidden") is True:
        item["hidden"] = True
    if raw.get("visitQuestion") is True:
        item["visitQuestion"] = True
    added_on = str(raw.get("addedOn") or "").strip()[:10]
    if added_on:
        item["addedOn"] = added_on  # see scoring.categories_for_payload
    skip = _parse_skip_rule(raw.get("skipWhen") or raw.get("conditional_rule"))
    if skip:
        item["skipWhen"] = skip
    return item


def _normalize_category(raw: dict, index: int) -> dict | None:
    cat_id = str(raw.get("id", "")).strip()
    title = str(raw.get("title", "")).strip()
    if not cat_id or not title:
        return None
    items = [
        i
        for j, item in enumerate(raw.get("items") or [])
        if (i := _normalize_item(item, j))
    ]
    if not items:
        return None
    max_points = int(raw.get("maxPoints") or raw.get("max_points") or 0)
    if max_points <= 0:
        max_points = sum(i["maxPoints"] for i in items)
    cat = {
        "id": cat_id,
        "title": title,
        "maxPoints": max_points,
        "items": items,
    }
    section = raw.get("sectionNumber") or raw.get("section_number")
    if section is not None and section != "":
        cat["sectionNumber"] = int(section)
    skip = _parse_skip_rule(raw.get("skipWhen"))
    if skip:
        cat["skipWhen"] = skip
    return cat


def normalize_rubric(raw: dict | list) -> dict:
    if isinstance(raw, list):
        categories_in = raw
    else:
        categories_in = raw.get("categories") or []
    categories = [
        c
        for i, cat in enumerate(categories_in)
        if (c := _normalize_category(cat, i))
    ]
    sort_key = lambda c: (c.get("sectionNumber") or 999, c["title"])
    categories.sort(key=sort_key)
    for cat in categories:
        cat["maxPoints"] = sum(i["maxPoints"] for i in cat["items"])
    return {"categories": categories}


def _apply_gap_fixes(db: Session, tenant: Tenant) -> None:
    """Add the 2026-10-11 assessment questions / links once per tenant (rubric_gap_fixes)."""
    from app.livewell.rubric_gap_fixes import apply_rubric_gap_fixes_once

    try:
        apply_rubric_gap_fixes_once(db, tenant)
    except Exception:  # never block reading config
        db.rollback()
        logging.getLogger(__name__).exception("rubric gap fixes failed for tenant %s", tenant.id)


class HomeSafetyRubricService:

    @staticmethod
    def _tenant(db: Session, user: User) -> Tenant:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_bad_request("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def get_rubric(db: Session, user: User) -> dict:
        tenant = HomeSafetyRubricService._tenant(db, user)
        _apply_gap_fixes(db, tenant)
        stored = read_stored_config(tenant.workflow_config or {})["rubric"]
        return normalize_rubric(stored)

    @staticmethod
    def save_rubric(db: Session, user: User, payload: dict) -> dict:
        tenant = HomeSafetyRubricService._tenant(db, user)
        normalized = normalize_rubric(payload)
        if not normalized["categories"]:
            raise_bad_request("At least one category with items is required")
        cfg = dict(tenant.workflow_config or {})
        cfg[RUBRIC_KEY] = normalized
        from app.livewell.rubric_gap_fixes import mark_rubric_gap_fixes_current

        mark_rubric_gap_fixes_current(cfg, "admin rubric save")
        tenant.workflow_config = cfg
        flag_modified(tenant, "workflow_config")
        db.commit()
        db.refresh(tenant)
        return normalized
