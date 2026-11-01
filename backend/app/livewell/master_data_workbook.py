"""Parse LiveWell360 Master Data Workbook (.xlsx) into normalized config payloads.

Export sheet order (01–28):
  01–11 Rubric / solutions / catalog / pricing / suppliers / packages
  12–18 AI (prompt / vision / workflow) — AI Prompt Engine
  19 MembershipRules — Membership Engine
  20 EcmRules — ECM Engine
  21 AssessmentFindings — Finding Engine language
  22–24 RuleMaster / Conditions / Actions — generic rules (+ DependsOn)
  25 RiskRules — Risk Engine bands
  26 QuoteRules — Quote Engine discounts
  27 NotificationRules — Notification Engine
  28 FollowUpRules — Follow-up Engine

Rule sheets nest under payload key ``rule_engine`` (workflow_config livewell_rule_engine).
Finding→Solution→Product stays on sheets 03–08 (not flattened to Finding→Product).

Import accepts any numeric prefix via SHEET_ALIASES.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook

from app.livewell.catalog_images import (
    format_image_document_ids_cell,
    parse_image_document_ids_cell,
)
from app.livewell.ai_config_service import normalize_ai_config
from app.livewell.catalog_service import normalize_catalog
from app.livewell.pricing_service import normalize_pricing
from app.livewell.rubric_service import normalize_rubric
from app.livewell.rule_engine_defaults import (
    DEFAULT_ASSESSMENT_FINDINGS,
    DEFAULT_ECM_RULES,
    DEFAULT_FOLLOWUP_RULES,
    DEFAULT_MEMBERSHIP_RULES,
    DEFAULT_NOTIFICATION_RULES,
    DEFAULT_QUOTE_RULES,
    DEFAULT_RISK_RULES,
    default_rule_engine_payload,
)
from app.livewell.solution_service import normalize_solutions
from app.livewell.supplier_service import normalize_supplier_directory
from app.livewell.workbook_format import (
    normalize_category_prefix,
    normalize_id_token,
    parse_money_inr,
    parse_percent,
)

SHEET_ALIASES: dict[str, tuple[str, ...]] = {
    "meta": ("meta", "workbookmeta", "uploadmeta"),
    "assessmentcategories": ("assessmentcategories", "categories"),
    "assessmentquestions": ("assessmentquestions", "questions"),
    "solutions": ("solutions",),
    "solutiontriggers": ("solutiontriggers", "solutionmappings", "solutionmapping"),
    "products": ("products",),
    "productsolutions": ("productsolutions", "productsolution"),
    "packages": ("packages",),
    "packageproducts": ("packageproducts", "productpackages"),
    "pricing": ("pricing", "pricingrules", "configuration"),
    "suppliers": ("suppliers",),
    "productsuppliers": ("productsuppliers",),
    "aipackagetiers": ("aipackagetiers", "aipackagestiers"),
    "aipackagesolutions": ("aipackagesolutions",),
    "visionfindingmap": ("visionfindingmap", "visionfindings"),
    "aiprompttemplates": ("aiprompttemplates", "prompttemplates"),
    "aipromptfragments": ("aipromptfragments", "promptfragments"),
    "aiworkflowmap": ("aiworkflowmap", "workflowmap"),
    "aisettings": ("aisettings", "aisetting"),
    "membershiprules": ("membershiprules",),
    "ecmrules": ("ecmrules",),
    "assessmentfindings": ("assessmentfindings", "findings"),
    "rulemaster": ("rulemaster",),
    "ruleconditions": ("ruleconditions",),
    "ruleactions": ("ruleactions",),
    "riskrules": ("riskrules", "riskbands"),
    "quoterules": ("quoterules", "discountrules"),
    "notificationrules": ("notificationrules", "notifications"),
    "followuprules": ("followuprules", "followups"),
}

# Tabs named only "05", "06", … map here when the suffix is stripped away.
SHEET_NUMBER_MAP: dict[str, str] = {
    "00": "meta",
    "01": "assessmentcategories",
    "02": "assessmentquestions",
    "03": "solutions",
    "04": "solutiontriggers",
    "05": "products",
    "06": "productsolutions",
    "07": "suppliers",
    "08": "productsuppliers",
    "09": "pricing",
    "10": "packages",
    "11": "packageproducts",
    "12": "aipackagetiers",
    "13": "aipackagesolutions",
    "14": "visionfindingmap",
    "15": "aiprompttemplates",
    "16": "aipromptfragments",
    "17": "aiworkflowmap",
    "18": "aisettings",
    "19": "membershiprules",
    "20": "ecmrules",
    "21": "assessmentfindings",
    "22": "rulemaster",
    "23": "ruleconditions",
    "24": "ruleactions",
    "25": "riskrules",
    "26": "quoterules",
    "27": "notificationrules",
    "28": "followuprules",
}


def _canonical_sheet_name(name: str) -> str:
    raw = name.strip().lower()
    suffix = re.sub(r"^\d+[_\-.]?", "", raw)
    suffix = re.sub(r"[^a-z0-9]", "", suffix)
    if suffix:
        text = suffix
    else:
        num_match = re.match(r"^(\d+)", raw)
        if num_match:
            num = num_match.group(1).zfill(2)
            return SHEET_NUMBER_MAP.get(num, "")
        return ""
    for canonical, aliases in SHEET_ALIASES.items():
        if text in aliases or text == canonical:
            return canonical
    return text


def _noneish(text: str) -> bool:
    return text.strip().lower() in ("", "none", "null", "n/a", "na")


def _cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float)):
        return str(value).strip()
    # Text from Excel may still carry trailing .0 / scientific form
    return normalize_id_token(str(value).strip()) if str(value).strip() else ""


def _sheet_rows(ws) -> list[dict[str, str]]:
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []
    headers = [_cell_value(h) for h in header_row]
    headers = [h or f"col_{i}" for i, h in enumerate(headers)]
    out: list[dict[str, str]] = []
    for row in rows_iter:
        if not row or not any(cell is not None and str(cell).strip() for cell in row):
            continue
        record = {
            headers[i]: _cell_value(row[i]) if i < len(row) else ""
            for i in range(len(headers))
        }
        if any(v for v in record.values()):
            out.append(record)
    return out


def _header(row: dict[str, str], *names: str) -> str:
    lowered = {k.strip().lower(): v for k, v in row.items()}
    for name in names:
        key = name.lower()
        if key in lowered:
            return lowered[key]
        compact = re.sub(r"[^a-z0-9]", "", key)
        for k, v in lowered.items():
            if re.sub(r"[^a-z0-9]", "", k) == compact:
                return v
    return ""


def _active(row: dict[str, str]) -> bool:
    val = _header(row, "Active", "active").lower()
    return val not in ("no", "n", "false", "0")


def _yes(row: dict[str, str], *names: str) -> bool:
    val = _header(row, *names).lower()
    return val in ("yes", "y", "true", "1")


def _optional_bool(text: str) -> bool | None:
    val = (text or "").strip().lower()
    if val in ("", "null", "n/a", "na", "-"):
        return None
    if val in ("yes", "y", "true", "1"):
        return True
    if val in ("no", "n", "false", "0"):
        return False
    return None


def _optional_risk_level(text: str) -> str | None:
    """Blank = ignore; none/no; yes; or mild|moderate|high|severe|low|critical."""
    val = (text or "").strip().lower()
    if val in ("", "null", "n/a", "na", "-"):
        return None
    if val in ("no", "n", "false", "0", "none"):
        return "none"
    if val in ("yes", "y", "true", "1"):
        return "yes"
    return val


def _risk_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _int_val(text: str, default: int = 0) -> int:
    try:
        return int(float(text)) if text else default
    except (TypeError, ValueError):
        return default


def _float_val(text: str, default: float = 0) -> float:
    try:
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def parse_workbook_bytes(data: bytes) -> dict[str, list[dict[str, str]]]:
    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    sheets: dict[str, list[dict[str, str]]] = {}
    for name in wb.sheetnames:
        canonical = _canonical_sheet_name(name)
        rows = _sheet_rows(wb[name])
        if canonical in sheets:
            sheets[canonical].extend(rows)
        else:
            sheets[canonical] = rows
    wb.close()
    return sheets


def extract_workbook_meta(sheets: dict[str, list[dict[str, str]]]) -> dict:
    """Parse 00_Meta (Key/Value) for upload provenance."""
    rows = sheets.get("meta") or []
    raw: dict[str, str] = {}
    for row in rows:
        key = _header(row, "Key", "Name", "Field", "key", "Setting")
        value = _header(row, "Value", "value", "SettingValue")
        if key:
            raw[key.strip()] = value.strip()
    lowered = {k.lower().replace(" ", "").replace("_", ""): v for k, v in raw.items()}

    def pick(*aliases: str) -> str:
        for a in aliases:
            hit = lowered.get(a.lower().replace(" ", "").replace("_", ""))
            if hit:
                return hit
        return ""

    return {
        "upload_id": pick("UploadId", "ConfigurationVersionId", "VersionId", "uploadid"),
        "uploaded_at": pick("UploadedAt", "ApprovedAt"),
        "exported_at": pick("ExportedAt"),
        "tenant_id": pick("TenantId"),
        "raw": raw,
    }


def build_payload_from_sheets(sheets: dict[str, list[dict[str, str]]]) -> dict:
    """Convert workbook rows into workflow_config-shaped payloads."""
    payload: dict = {}

    cat_rows = sheets.get("assessmentcategories") or []
    q_rows = [r for r in (sheets.get("assessmentquestions") or []) if _active(r)]
    if cat_rows or q_rows:
        categories_by_id: dict[str, dict] = {}
        for row in cat_rows:
            if not _active(row):
                continue
            cat_id = normalize_id_token(_header(row, "CategoryID", "categoryid", "id"))
            name = _header(row, "Category Name", "CategoryName", "name", "title")
            if not cat_id or not name:
                continue
            categories_by_id[cat_id] = {
                "id": cat_id,
                "title": name,
                "maxPoints": _int_val(_header(row, "Weight", "maxpoints"), 0),
                "sectionNumber": _int_val(_header(row, "Display Order", "SectionNumber", "sectionnumber"), 0) or None,
                "items": [],
            }
        for row in q_rows:
            qid = normalize_id_token(_header(row, "QuestionID", "questionid", "id"))
            cat_id = normalize_id_token(_header(row, "CategoryID", "categoryid"))
            label = _header(row, "Question", "Label", "label")
            if not qid or not cat_id or not label:
                continue
            cat = categories_by_id.get(cat_id)
            if not cat:
                # Orphan question (inactive/missing category) — do not invent stub categories.
                continue
            critical = _yes(row, "Critical", "critical")
            rule = _header(row, "Conditional Rule", "ConditionalRule", "skipWhen")
            item: dict = {
                "id": qid,
                "label": label,
                "maxPoints": max(1, _int_val(_header(row, "Weight", "maxpoints"), 1)),
                "scoringScale": "critical" if critical else "standard",
                "source": _header(row, "Source", "source") or "safehome360",
            }
            group = _header(row, "Group", "group")
            if group:
                item["group"] = group
            if rule:
                item["skipWhen"] = {"when": rule}
            cat["items"].append(item)
        if categories_by_id:
            payload["rubric"] = normalize_rubric({"categories": list(categories_by_id.values())})

    sol_rows = [r for r in (sheets.get("solutions") or []) if _active(r)]
    trigger_rows = sheets.get("solutiontriggers") or []
    if sol_rows:
        solutions_by_id: dict[str, dict] = {}
        for i, row in enumerate(sol_rows):
            sid = normalize_id_token(_header(row, "SolutionID", "solutionid", "id"))
            finding = _header(row, "Finding Name", "Finding", "finding")
            if not sid:
                continue
            priority = _header(row, "Priority", "priority").lower() or "medium"
            name = _header(row, "SolutionName", "Name", "name")
            desc = _header(row, "Description", "riskDescription", "riskdescription")
            actions_cell = _header(row, "RecommendedActions", "recommendedSolutions", "Actions")
            products_cell = _header(row, "RecommendedProducts", "productCategories", "Products")
            evidence = _header(row, "EvidenceLevel", "evidenceLevel", "Evidence") or "B"
            ai_cell = _header(row, "AIVisualization", "aiVisualization", "AI")
            solutions_by_id[sid] = {
                "id": sid,
                "section": _header(row, "Section", "Category", "section") or "General",
                "subcategory": _header(row, "Subcategory", "subcategory"),
                "name": name or finding or sid,
                "finding": finding or name or sid,
                "riskDescription": desc,
                "priority": priority,
                "recommendedSolutions": [
                    s.strip()
                    for s in (actions_cell or desc).split("\n")
                    if s.strip()
                ]
                or ([name] if name else []),
                "contractorType": _header(
                    row, "RequiredProfessional", "ContractorType", "contractortype"
                ),
                "productCategories": [
                    s.strip() for s in products_cell.replace(";", ",").split(",") if s.strip()
                ],
                "estimatedCost": _header(row, "EstCost", "EstimatedCost", "estimatedcost"),
                "installationTime": _header(
                    row, "InstallTime", "EstimatedCompletion", "installationtime"
                ),
                "scoreImprovement": _int_val(_header(row, "ScoreGain", "scoreImprovement"), 0),
                "rubricItemIds": [],
                "sort_order": i + 1,
                "legacyIds": [
                    s.strip()
                    for s in _header(row, "LegacyIDs", "legacyIds").replace(";", ",").split(",")
                    if s.strip()
                ],
                "evidenceLevel": evidence,
                "membershipImpact": _header(
                    row, "MembershipImpact", "membershipImpact", "Membership"
                ),
                "aiVisualization": ai_cell.lower() in ("yes", "y", "true", "1") if ai_cell else False,
                "followUpDays": _int_val(_header(row, "FollowUpDays", "followUpDays", "FollowUp"), 30),
            }
        for row in trigger_rows:
            qid = normalize_id_token(_header(row, "QuestionID", "questionid", "FindingID", "findingid"))
            sid = normalize_id_token(_header(row, "SolutionID", "solutionid"))
            if not qid or not sid:
                continue
            sol = solutions_by_id.get(sid)
            if not sol:
                # Orphan trigger — do not invent stub solutions from junction-only rows.
                continue
            if qid not in sol["rubricItemIds"]:
                sol["rubricItemIds"].append(qid)
        payload["solutions"] = normalize_solutions({"solutions": list(solutions_by_id.values())})

    prod_rows = [r for r in (sheets.get("products") or []) if _active(r)]
    ps_rows = sheets.get("productsolutions") or []
    pkg_rows = [r for r in (sheets.get("packages") or []) if _active(r)]
    pp_rows = sheets.get("packageproducts") or []
    if prod_rows or pkg_rows:
        products_by_id: dict[str, dict] = {}
        for i, row in enumerate(prod_rows):
            pid = normalize_id_token(_header(row, "ProductID", "productid", "id"))
            name = _header(row, "Product Name", "ProductName", "name")
            if not pid or not name:
                continue
            price_text = _header(row, "BasePriceINR", "Base Cost", "price_inr", "priceinr")
            price_inr = parse_money_inr(price_text) if price_text else None
            product_code = normalize_id_token(_header(row, "ProductCode", "productcode"))
            image_ids_raw = _header(
                row,
                "ImageDocumentIDs",
                "ImageIDs",
                "image_ids",
                "imagedocumentids",
            )
            product_row: dict = {
                "id": pid,
                "product_code": None if _noneish(product_code) else product_code,
                "name": name,
                "short_description": _header(row, "ShortDescription", "short_description") or name,
                "details": _header(row, "Details", "details"),
                "category": _header(row, "Category", "category") or "General",
                "price_inr": price_inr,
                "price_label": _header(row, "Unit", "PriceLabel", "price_label") or "Quote",
                "sort_order": i + 1,
                "solution_ids": [],
                "safety_improvement": _int_val(_header(row, "SafetyGain", "safety_improvement"), 0),
                "contractor_type": _header(row, "ContractorType", "contractortype"),
                "install_time": _header(row, "InstallTime", "installtime"),
                "category_prefix": normalize_category_prefix(
                    _header(row, "CategoryPrefix", "categoryprefix")
                ),
            }
            if image_ids_raw:
                product_row["image_ids"] = parse_image_document_ids_cell(image_ids_raw)
            products_by_id[pid] = product_row
        for row in ps_rows:
            pid = normalize_id_token(_header(row, "ProductID", "productid"))
            sid = normalize_id_token(_header(row, "SolutionID", "solutionid"))
            if not pid or not sid:
                continue
            prod = products_by_id.get(pid)
            if not prod:
                # Orphan ProductSolutions row — do not invent stub products.
                continue
            if sid not in prod["solution_ids"]:
                prod["solution_ids"].append(sid)
        packages_by_id: dict[str, dict] = {}
        for row in pkg_rows:
            pkg_id = normalize_id_token(_header(row, "PackageID", "packageid", "id"))
            name = _header(row, "Package Name", "PackageName", "name")
            if not pkg_id or not name:
                continue
            price_text = _header(row, "PriceINR", "price_inr", "Price")
            packages_by_id[pkg_id] = {
                "id": pkg_id,
                "name": name,
                "tagline": _header(row, "Tagline", "tagline"),
                "description": _header(row, "Description", "description"),
                "price_inr": parse_money_inr(price_text) if price_text else None,
                "price_label": _header(row, "PriceLabel", "price_label") or "From",
                "highlight": _yes(row, "Highlight", "highlight"),
                "product_ids": [],
                "sort_order": _int_val(_header(row, "Display Order", "sort_order", "DisplayOrder"), 0),
            }
        for row in pp_rows:
            pkg_id = normalize_id_token(_header(row, "PackageID", "packageid"))
            pid = normalize_id_token(_header(row, "ProductID", "productid"))
            if not pkg_id or not pid:
                continue
            pkg = packages_by_id.get(pkg_id)
            if not pkg:
                # Orphan PackageProducts row — do not invent stub packages.
                continue
            qty = max(1, _int_val(_header(row, "Qty", "Quantity"), 1))
            for _ in range(qty):
                pkg["product_ids"].append(pid)
        payload["catalog"] = normalize_catalog(
            {
                "products": list(products_by_id.values()),
                "packages": list(packages_by_id.values()),
            }
        )

    pricing_rows = sheets.get("pricing") or []
    if pricing_rows:
        pricing_raw: dict[str, Any] = {}
        for row in pricing_rows:
            key = _header(row, "Key", "RuleID", "ruleid", "Setting")
            val = _header(row, "Value", "value")
            if not key:
                continue
            key_norm = re.sub(r"[^a-z0-9_]", "_", key.strip().lower())
            mapping = {
                "default": "default_margin_percent",
                "default_margin": "default_margin_percent",
                "default_margin_percent": "default_margin_percent",
                "margin_percent": "default_margin_percent",
                "min_margin": "min_margin_percent",
                "min_margin_percent": "min_margin_percent",
                "max_margin": "max_margin_percent",
                "max_margin_percent": "max_margin_percent",
                "travel_cost_km": "travel_rate_per_km_inr",
                "travel_rate_per_km": "travel_rate_per_km_inr",
                "travel_rate_per_km_inr": "travel_rate_per_km_inr",
                "misc_charge": "default_miscellaneous_inr",
                "minimum_service_charge": "minimum_service_charge_inr",
                "labor_rate_per_hour": "labor_rate_per_hour_inr",
                "gst": "gst_percent",
                "gst_percent": "gst_percent",
                "default_gst": "gst_percent",
                "round_off": "round_off_rule",
                "round_off_rule": "round_off_rule",
                "use_vendor_cost_for_margin": "use_vendor_cost_for_margin",
            }
            field = mapping.get(key_norm, key_norm)
            if field == "use_vendor_cost_for_margin":
                pricing_raw[field] = _yes(row, "Value", "value") or val.lower() in ("true", "1", "yes")
            elif field == "round_off_rule":
                pricing_raw[field] = val or "nearest_100"
            elif field.endswith("_percent"):
                pct = parse_percent(val)
                pricing_raw[field] = pct if pct is not None else _float_val(val)
            elif field in ("default_travel_km",):
                pricing_raw[field] = _float_val(val)
            elif field.endswith("_inr"):
                money = parse_money_inr(val)
                pricing_raw[field] = money if money is not None else _int_val(val)
            else:
                money = parse_money_inr(val)
                pricing_raw[field] = money if money is not None else _int_val(val)
        payload["pricing"] = normalize_pricing(pricing_raw)

    sup_rows = [r for r in (sheets.get("suppliers") or []) if _active(r)]
    offer_rows = [r for r in (sheets.get("productsuppliers") or []) if _active(r)]
    if sup_rows or offer_rows:
        suppliers = []
        for i, row in enumerate(sup_rows):
            sid = normalize_id_token(_header(row, "SupplierID", "supplierid", "id"))
            name = _header(row, "Name", "name")
            if not sid or not name:
                continue
            rating_text = _header(row, "Rating", "rating")
            suppliers.append(
                {
                    "id": sid,
                    "name": name,
                    "contact": _header(row, "Contact", "contact"),
                    "phone": _header(row, "Phone", "phone"),
                    "email": _header(row, "Email", "email"),
                    "city": _header(row, "City", "city"),
                    "rating": float(rating_text) if rating_text else None,
                    "active": True,
                    "sort_order": _int_val(_header(row, "SortOrder", "sort_order"), i + 1),
                }
            )
        product_ids = {p["id"] for p in payload.get("catalog", {}).get("products") or []}
        offers = []
        for row in offer_rows:
            pid = normalize_id_token(_header(row, "ProductID", "productid"))
            sid = normalize_id_token(_header(row, "SupplierID", "supplierid"))
            if not pid or not sid:
                continue
            cost_raw = _header(row, "SupplierCostINR", "suppliercostinr")
            cost = parse_money_inr(cost_raw)
            offers.append(
                {
                    "product_id": pid,
                    "supplier_id": sid,
                    "supplier_cost_inr": cost if cost is not None else 0,
                    "preferred": _yes(row, "Preferred", "preferred"),
                    "moq": max(1, _int_val(_header(row, "MOQ", "moq"), 1)),
                    "lead_time_days": _int_val(_header(row, "LeadTimeDays", "leadtimedays", "Lead Time"), 0),
                    "vendor_sku": _header(row, "VendorSKU", "vendorsku"),
                    "active": True,
                }
            )
        payload["suppliers"] = normalize_supplier_directory(
            {"suppliers": suppliers, "offers": offers},
            valid_product_ids=product_ids or None,
        )

    ai_tier_rows = [r for r in (sheets.get("aipackagetiers") or []) if _active(r)]
    ai_ps_rows = sheets.get("aipackagesolutions") or []
    ai_vision_rows = [r for r in (sheets.get("visionfindingmap") or []) if _active(r)]
    ai_prompt_rows = [r for r in (sheets.get("aiprompttemplates") or []) if _active(r)]
    ai_frag_rows = sheets.get("aipromptfragments") or []
    ai_wf_rows = [r for r in (sheets.get("aiworkflowmap") or []) if _active(r)]
    ai_settings_rows = sheets.get("aisettings") or []
    if (
        ai_tier_rows
        or ai_ps_rows
        or ai_prompt_rows
        or ai_wf_rows
        or ai_settings_rows
    ):
        ai_raw: dict[str, Any] = {}
        if ai_tier_rows:
            ai_raw["tiers"] = [
                {
                    "id": _header(row, "TierID", "tierid", "id"),
                    "name": _header(row, "DisplayName", "Name", "name"),
                    "description": _header(row, "Description", "description"),
                    "sort_order": _int_val(_header(row, "SortOrder", "sort_order"), i + 1),
                    "active": True,
                }
                for i, row in enumerate(ai_tier_rows)
                if _header(row, "TierID", "tierid", "id")
            ]
        if ai_ps_rows:
            ai_raw["package_solutions"] = [
                {
                    "tier_id": _header(row, "TierID", "tierid", "PackageLevel", "packagelevel"),
                    "room_type": _header(row, "RoomType", "roomtype"),
                    "solution_id": _header(row, "SolutionID", "solutionid"),
                    "priority": _int_val(_header(row, "Priority", "priority"), 0),
                    "active": _active(row),
                }
                for row in ai_ps_rows
                if _header(row, "SolutionID", "solutionid")
            ]
        if ai_vision_rows:
            ai_raw["vision_finding_map"] = [
                {
                    "finding_code": _header(row, "FindingCode", "findingcode"),
                    "room_type": _header(row, "RoomType", "roomtype"),
                    "solution_id": _header(row, "SolutionID", "solutionid"),
                    "min_confidence": _int_val(_header(row, "MinConfidence", "minconfidence"), 60),
                    "auto_apply_above": _int_val(
                        _header(row, "AutoApplyAbove", "autoapplyabove"), 85
                    ),
                    "active": _active(row),
                }
                for row in ai_vision_rows
                if _header(row, "FindingCode", "findingcode")
            ]
        if ai_prompt_rows:
            ai_raw["prompt_templates"] = [
                {
                    "id": _header(row, "TemplateID", "templateid", "id"),
                    "room_type": _header(row, "RoomType", "roomtype"),
                    "package_level": _header(row, "PackageLevel", "packagelevel"),
                    "prompt_text": _header(row, "PromptText", "prompttext", "Prompt"),
                    "negative_prompt": _header(row, "NegativePrompt", "negativeprompt"),
                    "version": _int_val(_header(row, "Version", "version"), 1),
                    "active": True,
                }
                for row in ai_prompt_rows
                if _header(row, "RoomType", "roomtype")
            ]
        if ai_frag_rows:
            ai_raw["prompt_fragments"] = [
                {
                    "solution_id": _header(row, "SolutionID", "solutionid"),
                    "prompt_fragment": _header(
                        row, "PromptFragment", "promptfragment", "Fragment"
                    ),
                }
                for row in ai_frag_rows
                if _header(row, "SolutionID", "solutionid")
            ]
        if ai_wf_rows:
            ai_raw["workflow_map"] = [
                {
                    "room_type": _header(row, "RoomType", "roomtype"),
                    "package_level": _header(row, "PackageLevel", "packagelevel"),
                    "workflow_name": _header(row, "WorkflowName", "workflowname"),
                    "model_name": _header(row, "ModelName", "modelname"),
                    "draft_width": _int_val(_header(row, "DraftWidth", "draftwidth"), 1024),
                    "draft_height": _int_val(_header(row, "DraftHeight", "draftheight"), 1024),
                    "active": _active(row),
                }
                for row in ai_wf_rows
                if _header(row, "WorkflowName", "workflowname")
            ]
        if ai_settings_rows:
            settings: dict[str, Any] = {}
            for row in ai_settings_rows:
                key = _header(row, "Key", "Setting")
                val = _header(row, "Value", "value")
                if not key:
                    continue
                key_norm = re.sub(r"[^a-z0-9_]", "_", key.strip().lower())
                if val.lower() in ("true", "yes", "1"):
                    settings[key_norm] = True
                elif val.lower() in ("false", "no", "0"):
                    settings[key_norm] = False
                elif val.isdigit():
                    settings[key_norm] = int(val)
                else:
                    try:
                        settings[key_norm] = float(val)
                    except ValueError:
                        settings[key_norm] = val
            ai_raw["settings"] = settings
        payload["ai_config"] = normalize_ai_config(ai_raw)

    mbr_rows = sheets.get("membershiprules") or []
    if mbr_rows:
        membership_rules: list[dict] = []
        for row in mbr_rows:
            rid = _header(row, "RuleID", "ID", "id")
            membership_id = _header(
                row,
                "RecommendedMembershipID",
                "recommended_membership_id",
                "MembershipID",
            )
            if not rid and not membership_id:
                continue
            membership_rules.append(
                {
                    "id": rid or membership_id,
                    "min_independence_score": _int_val(
                        _header(row, "MinIndependenceScore", "min_independence_score", "MinScore"),
                        0,
                    ),
                    "max_independence_score": _int_val(
                        _header(row, "MaxIndependenceScore", "max_independence_score", "MaxScore"),
                        100,
                    ),
                    "lives_alone": _optional_bool(_header(row, "LivesAlone", "lives_alone")),
                    "family_abroad": _optional_bool(_header(row, "FamilyAbroad", "family_abroad")),
                    "mobility_risk": _optional_risk_level(
                        _header(row, "MobilityRisk", "mobility_risk")
                    ),
                    "cognitive_risk": _optional_risk_level(
                        _header(row, "CognitiveRisk", "cognitive_risk")
                    ),
                    "health_complexity": _optional_risk_level(
                        _header(row, "HealthComplexity", "health_complexity")
                    ),
                    "recommended_membership_id": membership_id or rid,
                    "priority": _int_val(_header(row, "Priority", "priority"), 100),
                    "notes": _header(row, "Notes", "notes", "PrimaryTrigger"),
                }
            )
        if membership_rules:
            payload["membership_rules"] = membership_rules

    ecm_rows = sheets.get("ecmrules") or []
    if ecm_rows:
        ecm_rules: list[dict] = []
        for row in ecm_rows:
            rid = _header(row, "RuleID", "ID", "id")
            condition = _header(row, "Condition", "condition")
            if not rid and not condition:
                continue
            assign_raw = _optional_bool(_header(row, "AssignmentRequired", "assignment_required"))
            ecm_rules.append(
                {
                    "id": rid or condition,
                    "condition": condition,
                    "assignment_required": True if assign_raw is None else assign_raw,
                    "visit_frequency": _header(row, "VisitFrequency", "visit_frequency"),
                    "escalation_level": _header(row, "EscalationLevel", "escalation_level"),
                    "action": _header(row, "Action", "action", "ActionType"),
                }
            )
        if ecm_rules:
            payload["ecm_rules"] = ecm_rules

    finding_rows = sheets.get("assessmentfindings") or []
    if finding_rows:
        findings: list[dict] = []
        for row in finding_rows:
            fid = _header(row, "FindingID", "findingid", "id")
            if not fid:
                continue
            findings.append(
                {
                    "id": fid,
                    "domain": _header(row, "Domain", "domain", "Area"),
                    "question_id": _header(row, "QuestionID", "questionid"),
                    "answer": _header(row, "Answer", "answer", "Rating"),
                    "severity": _header(row, "Severity", "severity"),
                    "label": _header(row, "Label", "Finding", "label"),
                }
            )
        if findings:
            payload["assessment_findings"] = findings

    rule_master_rows = sheets.get("rulemaster") or []
    if rule_master_rows:
        rules: list[dict] = []
        for row in rule_master_rows:
            rid = _header(row, "RuleID", "ruleid", "id")
            if not rid:
                continue
            rules.append(
                {
                    "id": rid,
                    "category": _header(row, "Category", "category"),
                    "priority": _int_val(_header(row, "Priority", "priority"), 100),
                    "enabled": _active(row),
                    "version": _header(row, "Version", "version"),
                    "effective_from": _header(row, "EffectiveFrom", "effective_from"),
                    "effective_to": _header(row, "EffectiveTo", "effective_to"),
                    "depends_on_rule_id": _header(
                        row, "DependsOnRuleID", "depends_on_rule_id", "DependsOn"
                    ),
                }
            )
        if rules:
            payload["rule_master"] = rules

    cond_rows = sheets.get("ruleconditions") or []
    if cond_rows:
        conditions: list[dict] = []
        for row in cond_rows:
            rid = _header(row, "RuleID", "ruleid")
            field = _header(row, "Field", "field")
            if not rid and not field:
                continue
            conditions.append(
                {
                    "rule_id": rid,
                    "field": field,
                    "operator": _header(row, "Operator", "operator"),
                    "value": _header(row, "Value", "value"),
                    "join": _header(row, "Join", "LogicalJoin", "join"),
                }
            )
        if conditions:
            payload["rule_conditions"] = conditions

    action_rows = sheets.get("ruleactions") or []
    if action_rows:
        actions: list[dict] = []
        for row in action_rows:
            rid = _header(row, "RuleID", "ruleid")
            action_type = _header(row, "ActionType", "action_type", "Type")
            if not rid and not action_type:
                continue
            actions.append(
                {
                    "rule_id": rid,
                    "action_type": action_type,
                    "value": _header(row, "Value", "value"),
                    "sequence": _int_val(_header(row, "Sequence", "sequence"), 0),
                }
            )
        if actions:
            payload["rule_actions"] = actions

    risk_rows = sheets.get("riskrules") or []
    if risk_rows:
        risk_rules: list[dict] = []
        for row in risk_rows:
            rid = _header(row, "RuleID", "RiskBandID", "id")
            if not rid:
                continue
            risk_rules.append(
                {
                    "id": rid,
                    "min_independence_score": _int_val(
                        _header(row, "MinIndependenceScore", "MinScore"), 0
                    ),
                    "max_independence_score": _int_val(
                        _header(row, "MaxIndependenceScore", "MaxScore"), 100
                    ),
                    "band": _header(row, "Band", "RiskBand", "band"),
                    "label": _header(row, "Label", "Meaning", "label"),
                    "escalation_level": _header(row, "EscalationLevel", "escalation_level"),
                }
            )
        if risk_rules:
            payload["risk_rules"] = risk_rules

    quote_rows = sheets.get("quoterules") or []
    if quote_rows:
        quote_rules: list[dict] = []
        for row in quote_rows:
            rid = _header(row, "RuleID", "id")
            if not rid:
                continue
            enabled = _optional_bool(_header(row, "Enabled", "Active"))
            quote_rules.append(
                {
                    "id": rid,
                    "discount_type": _header(row, "DiscountType", "discount_type", "Type"),
                    "condition": _header(row, "Condition", "condition"),
                    "percent": _float_val(_header(row, "Percent", "DiscountPercent"), 0),
                    "priority": _int_val(_header(row, "Priority", "priority"), 100),
                    "enabled": True if enabled is None else enabled,
                    "campaign_code": _header(row, "CampaignCode", "campaign_code"),
                }
            )
        if quote_rules:
            payload["quote_rules"] = quote_rules

    ntf_rows = sheets.get("notificationrules") or []
    if ntf_rows:
        notification_rules: list[dict] = []
        for row in ntf_rows:
            rid = _header(row, "RuleID", "id")
            if not rid:
                continue
            enabled = _optional_bool(_header(row, "Enabled", "Active"))
            notification_rules.append(
                {
                    "id": rid,
                    "audience": _header(row, "Audience", "audience"),
                    "channel": _header(row, "Channel", "channel"),
                    "event": _header(row, "Event", "TriggerEvent", "event"),
                    "template_id": _header(row, "TemplateID", "template_id"),
                    "enabled": True if enabled is None else enabled,
                }
            )
        if notification_rules:
            payload["notification_rules"] = notification_rules

    fu_rows = sheets.get("followuprules") or []
    if fu_rows:
        followup_rules: list[dict] = []
        for row in fu_rows:
            rid = _header(row, "RuleID", "id")
            if not rid:
                continue
            enabled = _optional_bool(_header(row, "Enabled", "Active"))
            followup_rules.append(
                {
                    "id": rid,
                    "trigger_event": _header(row, "TriggerEvent", "Event", "trigger_event"),
                    "delay_days": _int_val(_header(row, "DelayDays", "delay_days"), 0),
                    "action_type": _header(row, "ActionType", "Action", "action_type"),
                    "template_id": _header(row, "TemplateID", "template_id"),
                    "repeat": _header(row, "Repeat", "repeat"),
                    "enabled": True if enabled is None else enabled,
                }
            )
        if followup_rules:
            payload["followup_rules"] = followup_rules

    # Nest decision tables under rule_engine for tenant persistence.
    re_keys = (
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
    rule_engine: dict[str, Any] = {}
    for key in re_keys:
        if key in payload and payload[key]:
            rule_engine[key] = payload.pop(key)
    if rule_engine:
        payload["rule_engine"] = rule_engine

    return payload


def export_workbook_bytes(current: dict, *, meta: dict | None = None) -> bytes:
    """Build Kushalaya_Configuration.xlsx from current tenant config payloads."""
    wb = Workbook()
    default_ws = wb.active
    wb.remove(default_ws)

    def add_sheet(title: str, headers: list[str], rows: list[list[Any]]):
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in rows:
            ws.append(row)

    meta = meta or {}
    add_sheet(
        "00_Meta",
        ["Key", "Value"],
        [
            ["UploadId", meta.get("upload_id") or ""],
            ["UploadedAt", meta.get("uploaded_at") or ""],
            ["ExportedAt", meta.get("exported_at") or ""],
            ["TenantId", meta.get("tenant_id") or ""],
            ["Product", "LiveWell360"],
            ["FormatVersion", "2"],
        ],
    )

    rubric = current.get("rubric") or {}
    add_sheet(
        "01_AssessmentCategories",
        ["CategoryID", "Category Name", "Weight", "Display Order", "Active"],
        [
            [
                c["id"],
                c["title"],
                c.get("maxPoints", 0),
                c.get("sectionNumber", ""),
                "Yes",
            ]
            for c in rubric.get("categories") or []
        ],
    )
    q_rows: list[list[Any]] = []
    for cat in rubric.get("categories") or []:
        for item in cat.get("items") or []:
            skip = ""
            if isinstance(item.get("skipWhen"), dict):
                skip = item["skipWhen"].get("when") or item["skipWhen"].get("field") or ""
            q_rows.append(
                [
                    item["id"],
                    cat["id"],
                    item["label"],
                    item.get("group", ""),
                    item.get("maxPoints", 1),
                    "Yes" if item.get("scoringScale") == "critical" else "No",
                    skip,
                    item.get("source", "safehome360"),
                    "Yes",
                ]
            )
    add_sheet(
        "02_AssessmentQuestions",
        ["QuestionID", "CategoryID", "Question", "Group", "Weight", "Critical", "ConditionalRule", "Source", "Active"],
        q_rows,
    )

    solutions = current.get("solutions") or {}
    sol_list = solutions.get("solutions") or []
    add_sheet(
        "03_Solutions",
        [
            "SolutionID",
            "Section",
            "Subcategory",
            "SolutionName",
            "Finding",
            "Priority",
            "Description",
            "RecommendedActions",
            "RecommendedProducts",
            "RequiredProfessional",
            "EstCost",
            "InstallTime",
            "ScoreGain",
            "EvidenceLevel",
            "MembershipImpact",
            "AIVisualization",
            "FollowUpDays",
            "LegacyIDs",
            "Active",
        ],
        [
            [
                s["id"],
                s.get("section", ""),
                s.get("subcategory", ""),
                s.get("name") or s.get("finding", ""),
                s.get("finding", ""),
                s.get("priority", ""),
                s.get("riskDescription", ""),
                "\n".join(s.get("recommendedSolutions") or []),
                ", ".join(s.get("productCategories") or []),
                s.get("contractorType", ""),
                s.get("estimatedCost", ""),
                s.get("installationTime", ""),
                s.get("scoreImprovement", 0),
                s.get("evidenceLevel", "B"),
                s.get("membershipImpact", ""),
                "Yes" if s.get("aiVisualization") else "No",
                s.get("followUpDays", 30),
                ", ".join(s.get("legacyIds") or []),
                "Yes",
            ]
            for s in sol_list
        ],
    )
    trigger_rows = []
    for s in sol_list:
        for qid in s.get("rubricItemIds") or []:
            trigger_rows.append([qid, "unsafe,acceptable", s["id"], 1])
    add_sheet(
        "04_SolutionTriggers",
        ["QuestionID", "TriggerRatings", "SolutionID", "Priority"],
        trigger_rows,
    )

    catalog = current.get("catalog") or {}
    products = catalog.get("products") or []
    add_sheet(
        "05_Products",
        [
            "ProductID",
            "ProductCode",
            "Product Name",
            "Category",
            "CategoryPrefix",
            "ShortDescription",
            "Details",
            "BasePriceINR",
            "Unit",
            "ContractorType",
            "InstallTime",
            "SafetyGain",
            "ImageDocumentIDs",
            "Active",
        ],
        [
            [
                p["id"],
                "" if _noneish(str(p.get("product_code") or "")) else (p.get("product_code") or ""),
                p.get("name", ""),
                p.get("category", ""),
                p.get("category_prefix") or "",
                p.get("short_description", ""),
                p.get("details", ""),
                "" if p.get("price_inr") is None else p.get("price_inr"),
                p.get("price_label", "Quote"),
                p.get("contractor_type", ""),
                p.get("install_time", ""),
                p.get("safety_improvement", 0),
                format_image_document_ids_cell(p.get("image_ids")),
                "Yes",
            ]
            for p in products
        ],
    )
    ps_rows = []
    for p in products:
        for sid in p.get("solution_ids") or []:
            ps_rows.append([p["id"], sid])
    add_sheet("06_ProductSolutions", ["ProductID", "SolutionID"], ps_rows)

    suppliers = current.get("suppliers") or {}
    add_sheet(
        "07_Suppliers",
        ["SupplierID", "Name", "Contact", "Phone", "Email", "City", "Rating", "Active"],
        [
            [
                s["id"],
                s.get("name", ""),
                s.get("contact", ""),
                s.get("phone", ""),
                s.get("email", ""),
                s.get("city", ""),
                s.get("rating", ""),
                "Yes" if s.get("active", True) else "No",
            ]
            for s in suppliers.get("suppliers") or []
        ],
    )
    add_sheet(
        "08_ProductSuppliers",
        ["ProductID", "SupplierID", "SupplierCostINR", "Preferred", "MOQ", "LeadTimeDays", "VendorSKU", "Active"],
        [
            [
                o["product_id"],
                o["supplier_id"],
                o.get("supplier_cost_inr", 0),
                "Yes" if o.get("preferred") else "No",
                o.get("moq", 1),
                o.get("lead_time_days", 0),
                o.get("vendor_sku", ""),
                "Yes" if o.get("active", True) else "No",
            ]
            for o in suppliers.get("offers") or []
        ],
    )

    pricing = current.get("pricing") or {}
    add_sheet(
        "09_Pricing",
        ["Key", "Value"],
        [[k, pricing[k]] for k in sorted(pricing.keys())],
    )

    packages = catalog.get("packages") or []
    add_sheet(
        "10_Packages",
        [
            "PackageID",
            "Package Name",
            "Tagline",
            "Description",
            "PriceINR",
            "PriceLabel",
            "Display Order",
            "Highlight",
            "Active",
        ],
        [
            [
                p["id"],
                p.get("name", ""),
                p.get("tagline", ""),
                p.get("description", ""),
                "" if p.get("price_inr") is None else p.get("price_inr"),
                p.get("price_label", "From"),
                p.get("sort_order", 0),
                "Yes" if p.get("highlight") else "No",
                "Yes",
            ]
            for p in packages
        ],
    )
    pp_rows = []
    for p in packages:
        for pid in p.get("product_ids") or []:
            pp_rows.append([p["id"], pid, 1])
    add_sheet("11_PackageProducts", ["PackageID", "ProductID", "Qty"], pp_rows)

    ai = normalize_ai_config(current.get("ai_config") or {})
    add_sheet(
        "12_AIPackageTiers",
        ["TierID", "DisplayName", "Description", "SortOrder", "Active"],
        [
            [
                t["id"],
                t.get("name", ""),
                t.get("description", ""),
                t.get("sort_order", 0),
                "Yes" if t.get("active", True) else "No",
            ]
            for t in ai.get("tiers") or []
        ],
    )
    add_sheet(
        "13_AIPackageSolutions",
        ["TierID", "RoomType", "SolutionID", "Priority", "Active"],
        [
            [
                r["tier_id"],
                r["room_type"],
                r["solution_id"],
                r.get("priority", 0),
                "Yes" if r.get("active", True) else "No",
            ]
            for r in ai.get("package_solutions") or []
        ],
    )
    add_sheet(
        "14_VisionFindingMap",
        ["FindingCode", "RoomType", "SolutionID", "MinConfidence", "AutoApplyAbove", "Active"],
        [
            [
                r["finding_code"],
                r.get("room_type") or "",
                r["solution_id"],
                r.get("min_confidence", 60),
                r.get("auto_apply_above", 85),
                "Yes" if r.get("active", True) else "No",
            ]
            for r in ai.get("vision_finding_map") or []
        ],
    )
    add_sheet(
        "15_AIPromptTemplates",
        ["TemplateID", "RoomType", "PackageLevel", "PromptText", "NegativePrompt", "Version", "Active"],
        [
            [
                t.get("id", ""),
                t["room_type"],
                t["package_level"],
                t.get("prompt_text", ""),
                t.get("negative_prompt", ""),
                t.get("version", 1),
                "Yes" if t.get("active", True) else "No",
            ]
            for t in ai.get("prompt_templates") or []
        ],
    )
    add_sheet(
        "16_AIPromptFragments",
        ["SolutionID", "PromptFragment"],
        [
            [r["solution_id"], r.get("prompt_fragment", "")]
            for r in ai.get("prompt_fragments") or []
        ],
    )
    add_sheet(
        "17_AIWorkflowMap",
        [
            "RoomType",
            "PackageLevel",
            "WorkflowName",
            "ModelName",
            "DraftWidth",
            "DraftHeight",
            "Active",
        ],
        [
            [
                r["room_type"],
                r["package_level"],
                r["workflow_name"],
                r.get("model_name", ""),
                r.get("draft_width", 1024),
                r.get("draft_height", 1024),
                "Yes" if r.get("active", True) else "No",
            ]
            for r in ai.get("workflow_map") or []
        ],
    )
    settings = ai.get("settings") or {}
    add_sheet(
        "18_AISettings",
        ["Key", "Value"],
        [[k, settings[k]] for k in sorted(settings.keys())],
    )

    re_cfg = current.get("rule_engine") if isinstance(current.get("rule_engine"), dict) else {}
    if not re_cfg:
        # Flat keys (seed/build scripts) still supported.
        re_cfg = {
            k: current[k]
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
            if current.get(k)
        }
    if not re_cfg:
        re_cfg = default_rule_engine_payload()

    membership_rules = re_cfg.get("membership_rules") or DEFAULT_MEMBERSHIP_RULES
    add_sheet(
        "19_MembershipRules",
        [
            "RuleID",
            "MinIndependenceScore",
            "MaxIndependenceScore",
            "LivesAlone",
            "FamilyAbroad",
            "MobilityRisk",
            "CognitiveRisk",
            "HealthComplexity",
            "RecommendedMembershipID",
            "Priority",
            "Notes",
        ],
        [
            [
                r.get("id", ""),
                r.get("min_independence_score", ""),
                r.get("max_independence_score", ""),
                "" if r.get("lives_alone") is None else ("Yes" if r.get("lives_alone") else "No"),
                "" if r.get("family_abroad") is None else ("Yes" if r.get("family_abroad") else "No"),
                _risk_cell(r.get("mobility_risk")),
                _risk_cell(r.get("cognitive_risk")),
                _risk_cell(r.get("health_complexity")),
                r.get("recommended_membership_id", ""),
                r.get("priority", ""),
                r.get("notes", ""),
            ]
            for r in membership_rules
        ],
    )

    ecm_rules = re_cfg.get("ecm_rules") or DEFAULT_ECM_RULES
    add_sheet(
        "20_EcmRules",
        [
            "RuleID",
            "Condition",
            "AssignmentRequired",
            "VisitFrequency",
            "EscalationLevel",
            "Action",
        ],
        [
            [
                r.get("id", ""),
                r.get("condition", ""),
                "Yes" if r.get("assignment_required", True) else "No",
                r.get("visit_frequency", ""),
                r.get("escalation_level", ""),
                r.get("action", ""),
            ]
            for r in ecm_rules
        ],
    )

    findings = re_cfg.get("assessment_findings") or DEFAULT_ASSESSMENT_FINDINGS
    add_sheet(
        "21_AssessmentFindings",
        ["FindingID", "Domain", "QuestionID", "Answer", "Severity", "Label"],
        [
            [
                f.get("id", ""),
                f.get("domain", ""),
                f.get("question_id", ""),
                f.get("answer", ""),
                f.get("severity", ""),
                f.get("label", ""),
            ]
            for f in findings
        ],
    )

    rule_master = re_cfg.get("rule_master") or []
    add_sheet(
        "22_RuleMaster",
        [
            "RuleID",
            "Category",
            "Priority",
            "Enabled",
            "Version",
            "EffectiveFrom",
            "EffectiveTo",
            "DependsOnRuleID",
        ],
        [
            [
                r.get("id", ""),
                r.get("category", ""),
                r.get("priority", ""),
                "Yes" if r.get("enabled", True) else "No",
                r.get("version", ""),
                r.get("effective_from", ""),
                r.get("effective_to", ""),
                r.get("depends_on_rule_id", ""),
            ]
            for r in rule_master
        ],
    )

    rule_conditions = re_cfg.get("rule_conditions") or []
    add_sheet(
        "23_RuleConditions",
        ["RuleID", "Field", "Operator", "Value", "Join"],
        [
            [
                r.get("rule_id", ""),
                r.get("field", ""),
                r.get("operator", ""),
                r.get("value", ""),
                r.get("join", ""),
            ]
            for r in rule_conditions
        ],
    )

    rule_actions = re_cfg.get("rule_actions") or []
    add_sheet(
        "24_RuleActions",
        ["RuleID", "ActionType", "Value", "Sequence"],
        [
            [
                r.get("rule_id", ""),
                r.get("action_type", ""),
                r.get("value", ""),
                r.get("sequence", ""),
            ]
            for r in rule_actions
        ],
    )

    risk_rules = re_cfg.get("risk_rules") or DEFAULT_RISK_RULES
    add_sheet(
        "25_RiskRules",
        [
            "RuleID",
            "MinIndependenceScore",
            "MaxIndependenceScore",
            "Band",
            "Label",
            "EscalationLevel",
        ],
        [
            [
                r.get("id", ""),
                r.get("min_independence_score", ""),
                r.get("max_independence_score", ""),
                r.get("band", ""),
                r.get("label", ""),
                r.get("escalation_level", ""),
            ]
            for r in risk_rules
        ],
    )

    quote_rules = re_cfg.get("quote_rules") or DEFAULT_QUOTE_RULES
    add_sheet(
        "26_QuoteRules",
        [
            "RuleID",
            "DiscountType",
            "Condition",
            "Percent",
            "Priority",
            "Enabled",
            "CampaignCode",
        ],
        [
            [
                r.get("id", ""),
                r.get("discount_type", ""),
                r.get("condition", ""),
                r.get("percent", ""),
                r.get("priority", ""),
                "Yes" if r.get("enabled", True) else "No",
                r.get("campaign_code", ""),
            ]
            for r in quote_rules
        ],
    )

    notification_rules = re_cfg.get("notification_rules") or DEFAULT_NOTIFICATION_RULES
    add_sheet(
        "27_NotificationRules",
        ["RuleID", "Audience", "Channel", "Event", "TemplateID", "Enabled"],
        [
            [
                r.get("id", ""),
                r.get("audience", ""),
                r.get("channel", ""),
                r.get("event", ""),
                r.get("template_id", ""),
                "Yes" if r.get("enabled", True) else "No",
            ]
            for r in notification_rules
        ],
    )

    followup_rules = re_cfg.get("followup_rules") or DEFAULT_FOLLOWUP_RULES
    add_sheet(
        "28_FollowUpRules",
        [
            "RuleID",
            "TriggerEvent",
            "DelayDays",
            "ActionType",
            "TemplateID",
            "Repeat",
            "Enabled",
        ],
        [
            [
                r.get("id", ""),
                r.get("trigger_event", ""),
                r.get("delay_days", ""),
                r.get("action_type", ""),
                r.get("template_id", ""),
                r.get("repeat", ""),
                "Yes" if r.get("enabled", True) else "No",
            ]
            for r in followup_rules
        ],
    )

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
