"""SafeHome 360™ master data import — validate, stage, approve, version, drift sync."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.ai_config_service import normalize_ai_config
from app.livewell.catalog_service import merge_catalog_workbook_import, normalize_catalog
from app.livewell.catalog_images import normalize_image_ids
from app.livewell.config_keys import (
    CONFIG_KEYS,
    MASTER_BASELINE_KEY,
    MASTER_STAGING_KEY,
    MASTER_VERSIONS_KEY,
)
from app.livewell.master_data_drift import compute_field_drift, config_is_effectively_empty
from app.livewell.master_data_workbook import (
    build_payload_from_sheets,
    extract_workbook_meta,
    parse_workbook_bytes,
)
from app.livewell.pricing_defaults import DEFAULT_PRICING
from app.livewell.pricing_service import normalize_pricing
from app.livewell.rubric_service import normalize_rubric
from app.livewell.seed_service import load_canonical_workbook_bytes
from app.livewell.solution_service import normalize_solutions
from app.livewell.stored_config import entity_is_empty, normalize_entity_config, read_stored_config
from app.livewell.supplier_service import normalize_supplier_directory
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import AuditService

STAGING_KEY = MASTER_STAGING_KEY
VERSIONS_KEY = MASTER_VERSIONS_KEY
BASELINE_KEY = MASTER_BASELINE_KEY
MAX_VERSIONS = 20
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
CORE_ENTITIES = ("rubric", "solutions", "catalog")


def _save_tenant_cfg(db: Session, tenant: Tenant, cfg: dict) -> None:
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_current_config(cfg: dict, db: Session | None = None) -> dict:
    current = read_stored_config(cfg)
    if db is not None:
        from app.livewell.catalog_service import normalize_catalog
        from app.livewell.global_catalog_store import load_raw_global_catalog

        global_raw = load_raw_global_catalog(db)
        if isinstance(global_raw, dict) and (
            global_raw.get("products") or global_raw.get("packages")
        ):
            current["catalog"] = normalize_catalog(global_raw)
    return current


def _get_baseline(cfg: dict) -> dict | None:
    raw = cfg.get(BASELINE_KEY)
    return raw if isinstance(raw, dict) else None


def _write_baseline(
    cfg: dict,
    *,
    upload_id: str,
    approved_at: str,
    config: dict,
    exported_at: str | None = None,
) -> None:
    cfg[BASELINE_KEY] = {
        "upload_id": upload_id,
        "approved_at": approved_at,
        "exported_at": exported_at,
        "baseline": deepcopy(normalize_entity_config(config)),
    }


def _clear_baseline(cfg: dict) -> None:
    cfg.pop(BASELINE_KEY, None)


def _config_snapshot_equals(left: dict, right: dict) -> bool:
    """True when two configs are identical (full payload, not summary counts)."""
    return json.dumps(normalize_entity_config(left), sort_keys=True) == json.dumps(
        normalize_entity_config(right), sort_keys=True
    )


def _entity_ids(entity: str, data: dict) -> set[str]:
    if entity == "rubric":
        return {c["id"] for c in data.get("categories") or []}
    if entity == "solutions":
        return {s["id"] for s in data.get("solutions") or []}
    if entity == "catalog_products":
        return {p["id"] for p in data.get("products") or []}
    if entity == "catalog_packages":
        return {p["id"] for p in data.get("packages") or []}
    if entity == "suppliers":
        return {s["id"] for s in data.get("suppliers") or []}
    return set()


def _has_core_content(cleaned: dict) -> bool:
    for entity in CORE_ENTITIES:
        if entity in cleaned and not entity_is_empty(entity, cleaned[entity]):
            return True
    return False


def _validate_upload_bytes(file_bytes: bytes, filename: str | None = None) -> None:
    if not file_bytes:
        raise_bad_request("Empty file")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise_bad_request(
            f"Workbook exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        )
    name = (filename or "").lower()
    if name and not (name.endswith(".xlsx") or name.endswith(".xlsm")):
        raise_bad_request("Upload must be an Excel workbook (.xlsx)")
    # ZIP/OOXML signature for xlsx
    if not file_bytes.startswith(b"PK"):
        raise_bad_request("File does not look like a valid .xlsx workbook")


def _validate_payload(payload: dict, errors: list[str], warnings: list[str]) -> dict:
    """Re-normalize and cross-validate; return cleaned payload."""
    cleaned: dict = {}

    if "rubric" in payload:
        rubric = normalize_rubric(payload["rubric"])
        if not rubric["categories"]:
            errors.append("Rubric sheet produced no active categories/questions.")
        else:
            item_ids = {i["id"] for c in rubric["categories"] for i in c["items"]}
            if len(item_ids) < sum(len(c["items"]) for c in rubric["categories"]):
                errors.append("Duplicate QuestionID values in rubric.")
            cleaned["rubric"] = rubric

    if "solutions" in payload:
        solutions = normalize_solutions(payload["solutions"])
        if not solutions["solutions"]:
            warnings.append("Solutions sheet is empty — existing solutions will be kept on partial import.")
        else:
            rubric_ids = {
                i["id"]
                for c in (cleaned.get("rubric") or payload.get("rubric", {})).get("categories") or []
                for i in c.get("items") or []
            }
            for sol in solutions["solutions"]:
                for qid in sol.get("rubricItemIds") or []:
                    if rubric_ids and qid not in rubric_ids:
                        warnings.append(f"Solution {sol['id']} references unknown QuestionID {qid}.")
            cleaned["solutions"] = solutions

    if "catalog" in payload:
        catalog = normalize_catalog(payload["catalog"])
        if not catalog["products"]:
            errors.append("Products sheet produced no valid products.")
        else:
            solution_ids = {s["id"] for s in (cleaned.get("solutions") or payload.get("solutions", {})).get("solutions") or []}
            for prod in catalog["products"]:
                for sid in prod.get("solution_ids") or []:
                    if solution_ids and sid not in solution_ids:
                        warnings.append(f"Product {prod['id']} references unknown SolutionID {sid}.")
            cleaned["catalog"] = catalog

    if "pricing" in payload:
        cleaned["pricing"] = normalize_pricing(payload["pricing"])

    if "suppliers" in payload:
        product_ids = {p["id"] for p in (cleaned.get("catalog") or payload.get("catalog", {})).get("products") or []}
        suppliers = normalize_supplier_directory(
            payload["suppliers"],
            valid_product_ids=product_ids or None,
        )
        for offer in suppliers.get("offers") or []:
            if product_ids and offer["product_id"] not in product_ids:
                warnings.append(
                    f"ProductSuppliers row references unknown ProductID {offer['product_id']}."
                )
        cleaned["suppliers"] = suppliers

    if "ai_config" in payload:
        ai_cfg = normalize_ai_config(payload["ai_config"])
        if not ai_cfg.get("prompt_templates"):
            warnings.append("AI config has no prompt templates — defaults will apply on normalize.")
        solution_ids = {s["id"] for s in (cleaned.get("solutions") or payload.get("solutions", {})).get("solutions") or []}
        for row in ai_cfg.get("package_solutions") or []:
            if solution_ids and row["solution_id"] not in solution_ids:
                warnings.append(
                    f"AIPackageSolutions references unknown SolutionID {row['solution_id']}."
                )
        cleaned["ai_config"] = ai_cfg

    # Rule-engine sheets (19–28) — nested under rule_engine for persistence.
    if isinstance(payload.get("rule_engine"), dict) and payload["rule_engine"]:
        cleaned["rule_engine"] = payload["rule_engine"]
    else:
        # Backward-compatible flat keys from older parsers / tests.
        re_flat = {
            k: payload[k]
            for k in (
                "membership_rules",
                "ecm_rules",
                "assessment_findings",
                "rule_master",
                "rule_conditions",
                "rule_actions",
                "risk_rules",
                "quote_rules",
                "notification_rules",
                "followup_rules",
            )
            if payload.get(k)
        }
        if re_flat:
            cleaned["rule_engine"] = re_flat

    if not cleaned:
        errors.append("Workbook contained no recognized sheets with data.")

    return cleaned


def _diff_entity(name: str, old: Any, new: Any) -> dict:
    if name == "rubric":
        old_ids = _entity_ids("rubric", old or {})
        new_ids = _entity_ids("rubric", new or {})
        return {
            "categories_added": len(new_ids - old_ids),
            "categories_removed": len(old_ids - new_ids),
            "categories_unchanged": len(old_ids & new_ids),
        }
    if name == "solutions":
        old_ids = _entity_ids("solutions", old or {})
        new_ids = _entity_ids("solutions", new or {})
        return {
            "added": len(new_ids - old_ids),
            "removed": len(old_ids - new_ids),
            "unchanged": len(old_ids & new_ids),
        }
    if name == "catalog":
        op = _entity_ids("catalog_products", old or {})
        np = _entity_ids("catalog_products", new or {})
        ok = _entity_ids("catalog_packages", old or {})
        nk = _entity_ids("catalog_packages", new or {})
        return {
            "products_added": len(np - op),
            "products_removed": len(op - np),
            "packages_added": len(nk - ok),
            "packages_removed": len(ok - nk),
        }
    if name == "suppliers":
        old_ids = _entity_ids("suppliers", old or {})
        new_ids = _entity_ids("suppliers", new or {})
        old_offers = len((old or {}).get("offers") or [])
        new_offers = len((new or {}).get("offers") or [])
        return {
            "vendors_added": len(new_ids - old_ids),
            "vendors_removed": len(old_ids - new_ids),
            "offers_before": old_offers,
            "offers_after": new_offers,
        }
    if name == "pricing":
        all_keys = set(old or {}) | set(new or {})
        changes = {
            k: {"before": (old or {}).get(k), "after": (new or {}).get(k)}
            for k in sorted(all_keys)
            if (old or {}).get(k) != (new or {}).get(k)
        }
        return {"fields_changed": len(changes), "changes": changes}
    if name == "ai_config":
        ot = {t["id"] for t in (old or {}).get("tiers") or []}
        nt = {t["id"] for t in (new or {}).get("tiers") or []}
        ops = len((old or {}).get("package_solutions") or [])
        nps = len((new or {}).get("package_solutions") or [])
        opt = len((old or {}).get("prompt_templates") or [])
        npt = len((new or {}).get("prompt_templates") or [])
        return {
            "tiers_added": len(nt - ot),
            "tiers_removed": len(ot - nt),
            "package_solution_rows_before": ops,
            "package_solution_rows_after": nps,
            "prompt_templates_before": opt,
            "prompt_templates_after": npt,
        }
    return {}


def _config_summary(config: dict) -> dict:
    """Compact counts for UI — what is live in workflow_config right now."""
    rubric = config.get("rubric") or {}
    solutions = config.get("solutions") or {}
    catalog = config.get("catalog") or {}
    suppliers = config.get("suppliers") or {}
    categories = rubric.get("categories") or []
    products = catalog.get("products") or []
    packages = catalog.get("packages") or []
    return {
        "rubric_categories": len(categories),
        "rubric_questions": sum(len(c.get("items") or []) for c in categories),
        "solutions": len(solutions.get("solutions") or []),
        "catalog_products": len(products),
        "catalog_packages": len(packages),
        "products_with_photos": sum(1 for p in products if p.get("image_ids")),
        "products_with_solution_links": sum(1 for p in products if p.get("solution_ids")),
        "pricing_keys": len(config.get("pricing") or {}),
        "suppliers": len(suppliers.get("suppliers") or []),
        "supplier_offers": len(suppliers.get("offers") or []),
        "ai_tiers": len((config.get("ai_config") or {}).get("tiers") or []),
        "ai_prompt_templates": len((config.get("ai_config") or {}).get("prompt_templates") or []),
        "membership_rules": len((config.get("rule_engine") or {}).get("membership_rules") or []),
        "ecm_rules": len((config.get("rule_engine") or {}).get("ecm_rules") or []),
        "assessment_findings": len(
            (config.get("rule_engine") or {}).get("assessment_findings") or []
        ),
        "quote_rules": len((config.get("rule_engine") or {}).get("quote_rules") or []),
    }


def _build_diff(current: dict, staged: dict) -> dict:
    diff: dict = {}
    for key in staged:
        diff[key] = _diff_entity(key, current.get(key), staged.get(key))
    return diff


def _effective_live_pricing(current: dict) -> dict:
    stored = (current.get("pricing") or {}) if current else {}
    if stored:
        return normalize_pricing(stored)
    return normalize_pricing(DEFAULT_PRICING)


def _display_staged_pricing(payload: dict, current: dict) -> tuple[dict, bool]:
    if "pricing" in payload:
        return normalize_pricing(payload["pricing"]), True
    return _effective_live_pricing(current), False


def _import_result_from_record(record: dict, current: dict) -> dict:
    payload = record.get("payload") or {}
    errors = list(record.get("errors") or [])
    staged_pricing, from_workbook = _display_staged_pricing(payload, current)
    return {
        "version_id": record.get("version_id", ""),
        "status": "rejected" if errors else record.get("status", "pending"),
        "errors": errors,
        "warnings": list(record.get("warnings") or []),
        "diff": record.get("diff") or {},
        "field_diff": record.get("field_diff") or {},
        "sheets_found": list(record.get("sheets_found") or []),
        "entities": list(payload.keys()),
        "workbook_meta": record.get("workbook_meta") or {},
        "catalog_photo_preview": record.get("catalog_photo_preview"),
        "staged_pricing": staged_pricing,
        "live_pricing": _effective_live_pricing(current),
        "pricing_from_workbook": from_workbook,
        "pricing_edited_in_staging": bool(record.get("pricing_edited_in_staging")),
    }


def _count_products_with_photos(catalog: dict | None) -> int:
    products = (catalog or {}).get("products") or []
    return sum(1 for p in products if normalize_image_ids(p))


def _preview_merged_catalog(current: dict, staged_payload: dict) -> dict | None:
    if "catalog" not in staged_payload:
        return None
    return merge_catalog_workbook_import(
        staged_payload["catalog"],
        (current.get("catalog") or {}),
    )


def _catalog_photo_preview(current: dict, staged_payload: dict) -> dict | None:
    merged = _preview_merged_catalog(current, staged_payload)
    if merged is None:
        return None
    before = _count_products_with_photos(current.get("catalog"))
    after = _count_products_with_photos(merged)
    return {
        "products_with_photos_before": before,
        "products_with_photos_after": after,
        "would_lose_photos": after < before,
    }


def _projected_after_approve(current: dict, cleaned: dict) -> dict:
    projected = deepcopy(current)
    for entity, value in cleaned.items():
        if entity == "catalog":
            projected["catalog"] = merge_catalog_workbook_import(
                value,
                current.get("catalog") or {},
            )
        else:
            projected[entity] = value
    return projected


def _sync_status_payload(cfg: dict, db: Session | None = None) -> dict:
    current = _get_current_config(cfg, db)
    baseline_rec = _get_baseline(cfg)
    is_empty = config_is_effectively_empty(current)
    upload_id = (baseline_rec or {}).get("upload_id")
    approved_at = (baseline_rec or {}).get("approved_at")
    exported_at = (baseline_rec or {}).get("exported_at")
    baseline_cfg = (baseline_rec or {}).get("baseline") if baseline_rec else None

    if baseline_cfg is None:
        drift = {
            "dirty": False,
            "change_count": 0,
            "truncated": False,
            "by_entity": {},
            "changes": [],
        }
        dirty = False
    else:
        drift = compute_field_drift(baseline_cfg, current)
        dirty = bool(drift.get("dirty"))

    return {
        "has_baseline": bool(baseline_rec and upload_id),
        "upload_id": upload_id,
        "approved_at": approved_at,
        "exported_at": exported_at,
        "is_empty": is_empty,
        "requires_upload": is_empty and not upload_id,
        "dirty": dirty,
        "drift": drift,
        "summary": _config_summary(current),
        "message": (
            "Configuration is empty. Upload Kushalaya_Configuration.xlsx and Approve to load master data."
            if is_empty and not upload_id
            else (
                f"Live config differs from spreadsheet upload {upload_id}. Export and re-upload to sync."
                if dirty
                else (
                    f"In sync with spreadsheet upload {upload_id}."
                    if upload_id
                    else "No approved spreadsheet upload yet."
                )
            )
        ),
    }


class HomeSafetyMasterDataService:

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
    def get_current(db: Session, user: User) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        return _get_current_config(tenant.workflow_config or {}, db)

    @staticmethod
    def get_current_summary(db: Session, user: User) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        config = _get_current_config(tenant.workflow_config or {}, db)
        return {"summary": _config_summary(config)}

    @staticmethod
    def get_sync_status(db: Session, user: User) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        return _sync_status_payload(tenant.workflow_config or {}, db)

    @staticmethod
    def import_workbook(
        db: Session,
        user: User,
        file_bytes: bytes,
        comments: str = "",
        *,
        filename: str | None = None,
    ) -> dict:
        _validate_upload_bytes(file_bytes, filename)
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        cfg = dict(tenant.workflow_config or {})

        try:
            sheets = parse_workbook_bytes(file_bytes)
            raw_payload = build_payload_from_sheets(sheets)
            workbook_meta = extract_workbook_meta(sheets)
        except Exception as exc:
            raise_bad_request(f"Could not parse workbook: {exc}")

        errors: list[str] = []
        warnings: list[str] = []
        cleaned = _validate_payload(raw_payload, errors, warnings)

        current = _get_current_config(cfg, db)
        baseline_rec = _get_baseline(cfg)
        current_upload_id = (baseline_rec or {}).get("upload_id") or ""

        if config_is_effectively_empty(current):
            if not errors and not _has_core_content(cleaned):
                errors.append(
                    "First upload must include at least one of: Assessment rubric, Solutions, or Products."
                )
            elif not errors:
                missing_core = [e for e in CORE_ENTITIES if e not in cleaned]
                if missing_core:
                    warnings.append(
                        "First upload is missing sheets for: "
                        + ", ".join(missing_core)
                        + ". You can upload additional sheets in a later import."
                    )

        file_upload_id = (workbook_meta.get("upload_id") or "").strip()
        if file_upload_id and current_upload_id and file_upload_id == current_upload_id:
            projected = _projected_after_approve(current, cleaned) if cleaned else current
            reupload_drift = compute_field_drift(
                (baseline_rec or {}).get("baseline") or current,
                projected,
            )
            if not reupload_drift.get("dirty"):
                warnings.append(
                    f"Workbook UploadId {file_upload_id} matches the current baseline and "
                    "projected config has no field changes — re-upload may be unnecessary."
                )
        elif file_upload_id and current_upload_id and file_upload_id != current_upload_id:
            warnings.append(
                f"Workbook UploadId is {file_upload_id}, but live baseline is {current_upload_id}. "
                "Approving will replace the baseline with a new UploadId."
            )
        elif not file_upload_id:
            warnings.append(
                "Workbook has no 00_Meta UploadId (older export or hand-built file). "
                "Approve will assign a new UploadId stamped on the next Export."
            )

        if not sheets:
            errors.append("Workbook has no readable sheets.")

        diff = _build_diff(current, cleaned)
        field_diff = compute_field_drift(current, _projected_after_approve(current, cleaned)) if cleaned else {}

        photo_preview = _catalog_photo_preview(current, cleaned)
        if photo_preview and photo_preview.get("would_lose_photos"):
            warnings.append(
                "Catalog import would reduce linked showcase photos "
                f"({photo_preview['products_with_photos_before']} → "
                f"{photo_preview['products_with_photos_after']} products with images). "
                "Export the current workbook (ImageDocumentIDs column) or confirm on approve."
            )

        version_id = f"md-{uuid.uuid4().hex[:12]}"
        staging = dict(cfg.get(STAGING_KEY) or {})
        staging[version_id] = {
            "version_id": version_id,
            "status": "pending",
            "created_at": _utc_now(),
            "created_by": user.id,
            "comments": comments.strip(),
            "payload": cleaned,
            "errors": errors,
            "warnings": warnings,
            "diff": diff,
            "field_diff": field_diff,
            "sheets_found": sorted(sheets.keys()),
            "workbook_meta": workbook_meta,
            "catalog_photo_preview": photo_preview,
        }
        cfg[STAGING_KEY] = staging
        AuditService.log(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            entity_type="tenant_master_data",
            entity_id=int(tenant.id),
            action="master_data_import_staged",
            old_value={"summary": _config_summary(current)},
            new_value={
                "version_id": version_id,
                "filename": filename,
                "comments": comments.strip(),
                "entities": sorted(cleaned.keys()),
                "sheets_found": sorted(sheets.keys()),
                "errors": errors,
                "warnings": warnings,
                "upload_id": file_upload_id,
            },
        )
        _save_tenant_cfg(db, tenant, cfg)

        return _import_result_from_record(staging[version_id], current)

    @staticmethod
    def update_staged_pricing(
        db: Session,
        user: User,
        version_id: str,
        pricing_payload: dict,
    ) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        cfg = dict(tenant.workflow_config or {})
        staging = dict(cfg.get(STAGING_KEY) or {})
        record = staging.get(version_id)
        if not record:
            raise_not_found("Import version not found")
        if record.get("errors"):
            raise_bad_request("Cannot edit pricing on a rejected import")
        if record.get("status") != "pending":
            raise_bad_request("Import version is not pending")

        normalized = normalize_pricing(pricing_payload)
        payload = dict(record.get("payload") or {})
        payload["pricing"] = normalized
        current = _get_current_config(cfg, db)
        record["payload"] = payload
        record["pricing_edited_in_staging"] = True
        record["diff"] = _build_diff(current, payload)
        record["field_diff"] = compute_field_drift(
            current, _projected_after_approve(current, payload)
        )
        staging[version_id] = record
        cfg[STAGING_KEY] = staging
        _save_tenant_cfg(db, tenant, cfg)

        return _import_result_from_record(record, current)

    @staticmethod
    def get_staged(db: Session, user: User, version_id: str) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        staging = (tenant.workflow_config or {}).get(STAGING_KEY) or {}
        record = staging.get(version_id)
        if not record:
            raise_not_found("Import version not found")
        current = _get_current_config(tenant.workflow_config or {}, db)
        return _import_result_from_record(record, current)

    @staticmethod
    def approve_import(
        db: Session,
        user: User,
        version_id: str,
        *,
        confirm_catalog_photo_loss: bool = False,
    ) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        cfg = dict(tenant.workflow_config or {})
        staging = dict(cfg.get(STAGING_KEY) or {})
        record = staging.get(version_id)
        if not record:
            raise_not_found("Import version not found")
        if record.get("errors"):
            raise_bad_request("Cannot approve import with validation errors")
        if record.get("status") != "pending":
            raise_bad_request("Import version is not pending")

        payload = record.get("payload") or {}
        if not payload:
            raise_bad_request("Import payload is empty — nothing to approve")

        snapshot = _get_current_config(cfg, db)
        if config_is_effectively_empty(snapshot) and not _has_core_content(payload):
            raise_bad_request(
                "First approve requires core content (rubric, solutions, or products)."
            )

        for entity, config_key in CONFIG_KEYS.items():
            if entity not in payload:
                continue
            value = payload[entity]
            if entity == "catalog":
                value = merge_catalog_workbook_import(
                    value,
                    snapshot.get("catalog") or {},
                )
                photo_preview = _catalog_photo_preview(snapshot, payload)
                if (
                    photo_preview
                    and photo_preview.get("would_lose_photos")
                    and not confirm_catalog_photo_loss
                ):
                    before = photo_preview["products_with_photos_before"]
                    after = photo_preview["products_with_photos_after"]
                    raise_bad_request(
                        f"Import would reduce showcase/catalog photos from {before} to {after} "
                        f"product(s) with linked images. Export the current workbook first "
                        f"(ImageDocumentIDs column), keep ProductIDs stable, or set "
                        f"confirm_catalog_photo_loss=true to approve anyway."
                    )
                from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
                from app.livewell.global_catalog_store import save_raw_global_catalog
                import logging

                # Re-attach any orphaned Documents keyed by product_id (common after
                # thin workbook imports that omit ImageDocumentIDs).
                value, relinked = HomeSafetyCatalogImageService.relink_orphaned_images(
                    db, value
                )
                if relinked:
                    logging.getLogger(__name__).info(
                        "Relinked catalog photos on %s product(s) during master-data approve",
                        relinked,
                    )

                from app.livewell.catalog_link_fixes import mark_link_fixes_current

                mark_link_fixes_current(db, f"workbook import {version_id}")
                save_raw_global_catalog(db, value, commit=False)
            if entity in ("rubric", "solutions"):
                from app.livewell.rubric_gap_fixes import mark_rubric_gap_fixes_current

                mark_rubric_gap_fixes_current(cfg, f"workbook import {version_id}")
            cfg[config_key] = value

        approved_at = _utc_now()
        versions = list(cfg.get(VERSIONS_KEY) or [])
        versions.append(
            {
                "version_id": version_id,
                "approved_at": approved_at,
                "approved_by": user.id,
                "comments": record.get("comments", ""),
                "snapshot": snapshot,
                "applied": list(payload.keys()),
                "prior_upload_id": (record.get("workbook_meta") or {}).get("upload_id") or "",
            }
        )
        cfg[VERSIONS_KEY] = versions[-MAX_VERSIONS:]
        record["status"] = "approved"
        staging[version_id] = record
        cfg[STAGING_KEY] = staging

        live = _get_current_config(cfg, db)
        _write_baseline(
            cfg,
            upload_id=version_id,
            approved_at=approved_at,
            config=live,
            exported_at=None,
        )

        AuditService.log(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            entity_type="tenant_master_data",
            entity_id=int(tenant.id),
            action="master_data_import_approved",
            old_value={"summary": _config_summary(snapshot)},
            new_value={
                "version_id": version_id,
                "approved_at": approved_at,
                "applied": list(payload.keys()),
                "comments": record.get("comments", ""),
                "confirm_catalog_photo_loss": bool(confirm_catalog_photo_loss),
                "summary": _config_summary(live),
            },
        )
        _save_tenant_cfg(db, tenant, cfg)
        db.refresh(tenant)

        return {
            "version_id": version_id,
            "status": "approved",
            "applied": list(payload.keys()),
            "upload_id": version_id,
            "config": live,
        }

    @staticmethod
    def list_versions(db: Session, user: User) -> list[dict]:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        versions = (tenant.workflow_config or {}).get(VERSIONS_KEY) or []
        current_cfg = _get_current_config(tenant.workflow_config or {}, db)
        baseline = _get_baseline(tenant.workflow_config or {})
        latest_id = versions[-1].get("version_id") if versions else None
        out = []
        for v in reversed(versions):
            snapshot = v.get("snapshot") or {}
            snap_summary = _config_summary(snapshot) if snapshot else None
            vid = v.get("version_id")
            out.append(
                {
                    "version_id": vid,
                    "approved_at": v.get("approved_at"),
                    "approved_by": v.get("approved_by"),
                    "comments": v.get("comments", ""),
                    "applied": v.get("applied", []),
                    "snapshot_summary": snap_summary,
                    "matches_current": _config_snapshot_equals(snapshot, current_cfg)
                    if snapshot
                    else False,
                    "is_latest_import": vid == latest_id,
                    "is_current_baseline": bool(baseline and baseline.get("upload_id") == vid),
                }
            )
        return out

    @staticmethod
    def rollback(db: Session, user: User, version_id: str) -> dict:
        tenant = HomeSafetyMasterDataService._tenant(db, user)
        cfg = dict(tenant.workflow_config or {})
        versions = list(cfg.get(VERSIONS_KEY) or [])
        match_idx = next(
            (i for i, v in enumerate(versions) if v.get("version_id") == version_id),
            None,
        )
        if match_idx is None:
            raise_not_found("Version snapshot not found")
        match = versions[match_idx]
        if not match.get("snapshot"):
            raise_not_found("Version snapshot not found")
        snapshot = match["snapshot"]
        for entity, config_key in CONFIG_KEYS.items():
            if entity in snapshot:
                cfg[config_key] = deepcopy(snapshot[entity])
            else:
                cfg.pop(config_key, None)

        # Drop this import and any later imports — live config no longer includes them.
        remaining = versions[:match_idx]
        cfg[VERSIONS_KEY] = remaining

        live = _get_current_config(cfg, db)
        if remaining:
            last = remaining[-1]
            _write_baseline(
                cfg,
                upload_id=str(last.get("version_id") or ""),
                approved_at=str(last.get("approved_at") or _utc_now()),
                config=live,
                exported_at=None,
            )
        else:
            _clear_baseline(cfg)

        AuditService.log(
            db,
            tenant_id=tenant.id,
            user_id=user.id,
            entity_type="tenant_master_data",
            entity_id=int(tenant.id),
            action="master_data_rollback",
            old_value={
                "summary": _config_summary(_get_current_config(dict(tenant.workflow_config or {}), db)),
                "versions": [str(v.get("version_id") or "") for v in versions],
            },
            new_value={
                "version_id": version_id,
                "versions_removed": len(versions) - match_idx,
                "restored_baseline_version": (
                    str(remaining[-1].get("version_id") or "") if remaining else None
                ),
                "summary": _config_summary(live),
            },
        )
        _save_tenant_cfg(db, tenant, cfg)
        return {
            "version_id": version_id,
            "status": "rolled_back",
            "summary": _config_summary(live),
            "versions_removed": len(versions) - match_idx,
            "sync": _sync_status_payload(cfg, db),
        }

    @staticmethod
    def seed_defaults(db: Session, user: User) -> dict:
        """Stage the factory workbook for approve — does not write live config directly."""
        try:
            raw = load_canonical_workbook_bytes()
        except FileNotFoundError as exc:
            raise_bad_request(str(exc))
        return HomeSafetyMasterDataService.import_workbook(
            db,
            user,
            raw,
            comments="Factory Kushalaya_Configuration.xlsx (staged — Approve to apply)",
            filename="Kushalaya_Configuration.xlsx",
        )

    @staticmethod
    def export_workbook(db: Session, user: User) -> bytes:
        from app.livewell.master_data_workbook import export_workbook_bytes

        tenant = HomeSafetyMasterDataService._tenant(db, user)
        cfg = dict(tenant.workflow_config or {})
        current = _get_current_config(cfg, db)
        if config_is_effectively_empty(current):
            raise_bad_request(
                "Configuration is empty. Upload and Approve a spreadsheet before exporting."
            )

        baseline = _get_baseline(cfg) or {}
        sync = _sync_status_payload(cfg, db)
        if sync.get("dirty"):
            # Still allow export (that's how you save app edits back), but stamp current upload id.
            pass

        exported_at = _utc_now()
        meta = {
            "upload_id": baseline.get("upload_id") or "",
            "uploaded_at": baseline.get("approved_at") or "",
            "exported_at": exported_at,
            "tenant_id": str(tenant.id),
        }
        raw = export_workbook_bytes(current, meta=meta)

        if baseline:
            baseline = dict(baseline)
            baseline["exported_at"] = exported_at
            cfg[BASELINE_KEY] = baseline
            _save_tenant_cfg(db, tenant, cfg)

        return raw
