#!/usr/bin/env python3
"""Validate Kushalaya_Configuration.xlsx import, export, sheets."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.livewell.master_data_service import _validate_payload  # noqa: E402
from app.livewell.master_data_workbook import (  # noqa: E402
    build_payload_from_sheets,
    export_workbook_bytes,
    parse_workbook_bytes,
)

# Core catalog/AI sheets — always required.
REQUIRED_SHEETS = [
    "01_AssessmentCategories",
    "02_AssessmentQuestions",
    "03_Solutions",
    "04_SolutionTriggers",
    "05_Products",
    "06_ProductSolutions",
    "07_Suppliers",
    "08_ProductSuppliers",
    "09_Pricing",
    "10_Packages",
    "11_PackageProducts",
    "12_AIPackageTiers",
    "13_AIPackageSolutions",
    "14_VisionFindingMap",
    "15_AIPromptTemplates",
    "16_AIPromptFragments",
    "17_AIWorkflowMap",
    "18_AISettings",
]

# Rule-engine — required on fresh exports; optional on legacy workbooks.
RULE_ENGINE_SHEETS = [
    "19_MembershipRules",
    "20_EcmRules",
    "21_AssessmentFindings",
    "22_RuleMaster",
    "23_RuleConditions",
    "24_RuleActions",
    "25_RiskRules",
    "26_QuoteRules",
    "27_NotificationRules",
    "28_FollowUpRules",
]

# Decision tables that should be present on new builds (warn if missing).
PREFERRED_RULE_SHEETS = [
    "19_MembershipRules",
    "20_EcmRules",
    "25_RiskRules",
]

EXPECTED_EXPORT_SHEETS = REQUIRED_SHEETS + RULE_ENGINE_SHEETS

CANONICAL = BACKEND / "app" / "livewell" / "data" / "Kushalaya_Configuration.xlsx"


def _counts(payload: dict) -> dict:
    rubric = payload.get("rubric") or {}
    solutions = payload.get("solutions") or {}
    catalog = payload.get("catalog") or {}
    suppliers = payload.get("suppliers") or {}
    categories = rubric.get("categories") or []
    questions = sum(len(c.get("items") or []) for c in categories)
    products = catalog.get("products") or []
    with_solutions = sum(1 for p in products if p.get("solution_ids"))
    with_details = sum(1 for p in products if str(p.get("details") or "").strip())
    packages = catalog.get("packages") or []
    pkg_with_desc = sum(1 for p in packages if str(p.get("description") or "").strip())
    return {
        "categories": len(categories),
        "questions": questions,
        "solutions": len(solutions.get("solutions") or []),
        "products": len(products),
        "products_with_solution_links": with_solutions,
        "products_with_details": with_details,
        "packages": len(packages),
        "packages_with_description": pkg_with_desc,
        "pricing_keys": len(payload.get("pricing") or {}),
        "suppliers": len(suppliers.get("suppliers") or []),
        "supplier_offers": len(suppliers.get("offers") or []),
        "membership_rules": len((payload.get("rule_engine") or {}).get("membership_rules") or []),
        "ecm_rules": len((payload.get("rule_engine") or {}).get("ecm_rules") or []),
        "assessment_findings": len(
            (payload.get("rule_engine") or {}).get("assessment_findings") or []
        ),
        "quote_rules": len((payload.get("rule_engine") or {}).get("quote_rules") or []),
        "notification_rules": len(
            (payload.get("rule_engine") or {}).get("notification_rules") or []
        ),
        "followup_rules": len((payload.get("rule_engine") or {}).get("followup_rules") or []),
    }


def _sheet_row_counts(path: Path) -> dict[str, int]:
    wb = load_workbook(path, read_only=True, data_only=True)
    out: dict[str, int] = {}
    for name in wb.sheetnames:
        ws = wb[name]
        rows = max(0, (ws.max_row or 1) - 1)
        out[name] = rows
    wb.close()
    return out


def validate(path: Path) -> int:
    if not path.is_file():
        print(f"FAIL: workbook not found: {path}")
        return 1

    raw = path.read_bytes()
    print(f"Validating {path} ({len(raw):,} bytes)\n")

    sheets = parse_workbook_bytes(raw)
    canonical_keys = sorted(sheets.keys())
    print("Parsed sheet keys:", ", ".join(canonical_keys) or "(none)")

    errors: list[str] = []
    warnings: list[str] = []
    payload = build_payload_from_sheets(sheets)
    cleaned = _validate_payload(payload, errors, warnings)

    if errors:
        print("\nValidation ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    if warnings:
        print("\nValidation warnings:")
        for w in warnings[:10]:
            print(f"  - {w}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")

    counts = _counts(cleaned)
    print("\nImport payload counts:")
    for k, v in counts.items():
        print(f"  {k}: {v}")

    file_rows = _sheet_row_counts(path)
    print("\nWorkbook tab row counts (excl. header):")
    for title in REQUIRED_SHEETS:
        rows = file_rows.get(title, 0)
        flag = "OK" if rows > 0 or title in ("07_Suppliers", "08_ProductSuppliers") else "EMPTY"
        print(f"  {title}: {rows} rows [{flag}]")

    for title in RULE_ENGINE_SHEETS:
        if title in file_rows:
            rows = file_rows[title]
            flag = "OK" if rows > 0 or title in (
                "21_AssessmentFindings",
                "22_RuleMaster",
                "23_RuleConditions",
                "24_RuleActions",
            ) else "EMPTY"
            print(f"  {title}: {rows} rows [{flag}] (rule-engine)")
        else:
            print(f"  {title}: missing [OPTIONAL]")

    missing_tabs = [t for t in REQUIRED_SHEETS if t not in file_rows]
    if missing_tabs:
        print("\nFAIL: missing required tabs:", ", ".join(missing_tabs))
        return 1

    missing_preferred = [t for t in PREFERRED_RULE_SHEETS if t not in file_rows]
    if missing_preferred:
        print(
            "\nNote: preferred rule-engine tabs missing (optional on legacy):",
            ", ".join(missing_preferred),
        )

    known = set(REQUIRED_SHEETS) | set(RULE_ENGINE_SHEETS)
    extra_tabs = [t for t in file_rows if t not in known]
    if extra_tabs:
        print("\nNote: extra tabs:", ", ".join(extra_tabs))

    # Roundtrip: export cleaned config and re-import
    exported = export_workbook_bytes(cleaned)
    wb2 = load_workbook(BytesIO(exported), read_only=True)
    if wb2.sheetnames != EXPECTED_EXPORT_SHEETS:
        print("\nFAIL: export sheet order/names mismatch")
        print("  expected:", EXPECTED_EXPORT_SHEETS)
        print("  got:     ", wb2.sheetnames)
        wb2.close()
        return 1
    wb2.close()

    sheets2 = parse_workbook_bytes(exported)
    payload2 = build_payload_from_sheets(sheets2)
    errors2: list[str] = []
    warnings2: list[str] = []
    cleaned2 = _validate_payload(payload2, errors2, warnings2)
    if errors2:
        print("\nFAIL: roundtrip export validation errors:")
        for e in errors2:
            print(f"  - {e}")
        return 1

    counts2 = _counts(cleaned2)
    print("\nRoundtrip export -> re-import counts:")
    for k, v in counts2.items():
        delta = v - counts.get(k, 0)
        mark = " OK" if delta == 0 else f" ({delta:+d})"
        print(f"  {k}: {v}{mark}")

    regressions = []
    for key in counts:
        if counts2.get(key, 0) < counts.get(key, 0):
            regressions.append(f"{key}: {counts[key]} → {counts2.get(key, 0)}")

    if regressions:
        print("\nFAIL: roundtrip lost data:")
        for r in regressions:
            print(f"  - {r}")
        return 1

    print("\nPASS: master spreadsheet validates and roundtrips cleanly.")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else CANONICAL
    raise SystemExit(validate(target))
