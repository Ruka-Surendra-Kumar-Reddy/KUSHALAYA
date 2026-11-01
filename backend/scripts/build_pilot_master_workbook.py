#!/usr/bin/env python3
"""Build Kushalaya_Configuration_Pilot.xlsx from the canonical workbook.

Keeps assessment rubric, solutions, suppliers, pricing keys, AI, and rule-engine
sheets intact (with membership rules retargeted to pilot packages).

Replaces commercial catalog with launch offers:
  - Safety Assessment
  - Safety Installation (SKU set)
  - Family Peace-of-Mind Support
"""

from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import load_workbook

BACKEND = Path(__file__).resolve().parents[1]
SRC = BACKEND / "app" / "livewell" / "data" / "Kushalaya_Configuration.xlsx"
OUT = BACKEND / "app" / "livewell" / "data" / "Kushalaya_Configuration_Pilot.xlsx"


def _clear_data_rows(ws) -> None:
    if ws.max_row and ws.max_row > 1:
        ws.delete_rows(2, ws.max_row - 1)


def _write_rows(ws, rows: list[list]) -> None:
    _clear_data_rows(ws)
    for r_i, row in enumerate(rows, start=2):
        for c_i, val in enumerate(row, start=1):
            ws.cell(r_i, c_i, val)


# Existing IDs + canonical ProductCodes (SVC-001, BTH-001, …) so catalog photos
# stay linked on import/merge and product-type photo seed scripts keep matching.
PILOT_PRODUCTS: list[list] = [
    # ProductID, ProductCode, Name, Category, Prefix, Short, Details, Price, Unit, Contractor, InstallTime, SafetyGain, Images, Active
    [
        "prod_svc_001",
        "SVC-001",
        "Safety Assessment",
        "Pilot — Assessment",
        "SVC",
        "Home visit with fall-risk review, consent photos, written action plan, product recommendations, and emergency information sheet.",
        (
            "Pilot Safety Assessment includes:\n"
            "- Home visit\n"
            "- Fall-risk and accessibility review\n"
            "- Photographs with consent\n"
            "- Written action plan\n"
            "- Product recommendations\n"
            "- Emergency information sheet\n"
            "Delivered by LiveWell360 assessors in Hyderabad."
        ),
        3750,
        "One-time",
        "LiveWell360 (own)",
        "2–3 hours",
        5,
        None,
        "Yes",
    ],
    [
        "prod_emg_001",
        "EMG-001",
        "Emergency Information Sheet",
        "Pilot — Assessment",
        "EMG",
        "Printed/posted emergency contacts and medical notes for the home.",
        "Included with Safety Assessment; also available as a standalone refresh.",
        500,
        "One-time",
        "LiveWell360 (own)",
        "30 minutes",
        1,
        None,
        "Yes",
    ],
    [
        "prod_bth_001",
        "BTH-001",
        "Grab bars",
        "Pilot — Safety Installation",
        "BTH",
        "Professionally installed bathroom / transfer grab bars.",
        "Installed grab bars near toilet, shower, or other transfer points. Quoted as product + labor.",
        2500,
        "Installed (product + labor)",
        "Partner installer",
        "1–2 hours",
        8,
        None,
        "Yes",
    ],
    [
        "prod_bth_008",
        "BTH-008",
        "Non-slip treatment",
        "Pilot — Safety Installation",
        "BTH",
        "Anti-slip floor coating or treatment for wet areas.",
        "Non-slip bathroom / wet-area treatment to reduce fall risk. Quoted as installed job.",
        4500,
        "Installed (product + labor)",
        "Partner installer",
        "2–4 hours",
        7,
        None,
        "Yes",
    ],
    [
        "prod_bed_004",
        "BED-004",
        "Night lighting",
        "Pilot — Safety Installation",
        "BED",
        "Motion or pathway night lighting for bed-to-bath routes.",
        "Night / motion lighting to improve visibility on common night paths.",
        1500,
        "Installed (product + labor)",
        "Partner installer",
        "1 hour",
        4,
        None,
        "Yes",
    ],
    [
        "prod_hal_001",
        "HAL-001",
        "Motion night / pathway light",
        "Pilot — Safety Installation",
        "HAL",
        "Additional motion sensor lighting for halls and transitions.",
        "Optional second lighting point for hallways or stair approaches.",
        1800,
        "Installed (product + labor)",
        "Partner installer",
        "1 hour",
        4,
        None,
        "Yes",
    ],
    [
        "prod_bth_005",
        "BTH-005",
        "Shower chair",
        "Pilot — Safety Installation",
        "BTH",
        "Stable shower chair or bath bench for seated bathing.",
        "Shower chair / bath bench supply and placement guidance; install as needed.",
        3500,
        "Installed (product + labor)",
        "Partner installer",
        "30–60 minutes",
        6,
        None,
        "Yes",
    ],
    [
        "prod_bth_006",
        "BTH-006",
        "Toilet support — raised seat",
        "Pilot — Safety Installation",
        "BTH",
        "Raised toilet seat for safer sit-to-stand.",
        "Raised toilet seat as part of toilet support options.",
        2200,
        "Installed (product + labor)",
        "Partner installer",
        "30–60 minutes",
        5,
        None,
        "Yes",
    ],
    [
        "prod_bth_007",
        "BTH-007",
        "Toilet support — safety frame",
        "Pilot — Safety Installation",
        "BTH",
        "Toilet safety frame / arm supports.",
        "Toilet safety frame for lateral support during transfers.",
        2800,
        "Installed (product + labor)",
        "Partner installer",
        "30–60 minutes",
        5,
        None,
        "Yes",
    ],
    [
        "prod_ext_001",
        "EXT-001",
        "Railings — entrance / stair",
        "Pilot — Safety Installation",
        "EXT",
        "Secure handrail at entrance or stairs.",
        "Entrance or stair handrail installation for safer access.",
        5500,
        "Installed (product + labor)",
        "Partner installer",
        "2–4 hours",
        8,
        None,
        "Yes",
    ],
    [
        "prod_hal_003",
        "HAL-003",
        "Railings — indoor / hallway",
        "Pilot — Safety Installation",
        "HAL",
        "Indoor hallway or corridor handrail.",
        "Minor indoor accessibility railing where space allows.",
        4500,
        "Installed (product + labor)",
        "Partner installer",
        "2–3 hours",
        6,
        None,
        "Yes",
    ],
    [
        "prod_wel_001",
        "WEL-001",
        "Scheduled wellness visit or call",
        "Pilot — Peace of Mind",
        "WEL",
        "Planned wellness check-in by visit or call, with a family update after each visit.",
        (
            "Scheduled wellness visit or phone/video check-in with notes for the family. "
            "Includes a family update after each visit under Peace-of-Mind support."
        ),
        1500,
        "Per visit",
        "LiveWell360 (own)",
        "30–60 minutes",
        2,
        None,
        "Yes",
    ],
    [
        "prod_trn_002",
        "TRN-002",
        "Appointment accompaniment coordination",
        "Pilot — Peace of Mind",
        "TRN",
        "Coordinate accompaniment for doctor or hospital appointments.",
        "Scheduling and coordination for appointment accompaniment (and related logistics).",
        2000,
        "Per appointment",
        "LiveWell360 (own)",
        "Varies",
        2,
        None,
        "Yes",
    ],
    [
        "prod_wel_010",
        "WEL-010",
        "Emergency escalation",
        "Pilot — Peace of Mind",
        "WEL",
        "Escalation path and family notification when something is wrong.",
        "Care coordination for emergency escalation and family notification under Peace-of-Mind support.",
        0,
        "Included in membership",
        "LiveWell360 (own)",
        "As needed",
        3,
        None,
        "Yes",
    ],
    [
        "prod_hm_004",
        "HM-004",
        "Home repair coordination",
        "Pilot — Peace of Mind",
        "HM",
        "Arrange and follow up on home repairs for the senior.",
        "Coordination of plumbing, electrical, or other home repairs with vetted workers; family updates on status.",
        750,
        "Per coordination",
        "LiveWell360 (own)",
        "Varies",
        1,
        None,
        "Yes",
    ],
]

PILOT_PRODUCT_IDS = {row[0] for row in PILOT_PRODUCTS}

PILOT_PACKAGES: list[list] = [
    [
        "pkg_safety_assessment",
        "Safety Assessment",
        "One-time home visit — fall risk, plan, and recommendations",
        (
            "Home visit with fall-risk and accessibility review, photographs with consent, "
            "written action plan, product recommendations, and an emergency information sheet. "
            "Hyderabad pilot entry offer."
        ),
        3750,
        "One-time (from)",
        1,
        "Yes",
        "Yes",
    ],
    [
        "pkg_safety_installation",
        "Safety Installation",
        "Grab bars, non-slip, lighting, shower/toilet support, railings",
        (
            "Installed safety improvements quoted after assessment: grab bars, non-slip treatment, "
            "night lighting, shower chair, toilet support products, and railings / minor accessibility "
            "changes. Prices are installed (product + labor)."
        ),
        0,
        "Quoted after assessment",
        2,
        "No",
        "Yes",
    ],
    [
        "pkg_peace_of_mind",
        "Family Peace-of-Mind Support",
        "Visits, accompaniment, escalation, repairs, family updates",
        (
            "Ongoing support for families: scheduled wellness visit or call, appointment accompaniment "
            "coordination, emergency escalation, home repair coordination, and a family update after "
            "each visit. Hyderabad pilot membership."
        ),
        36000,
        "From / year",
        3,
        "Yes",
        "Yes",
    ],
]

PILOT_PACKAGE_PRODUCTS: list[list] = [
    # Assessment package
    ["pkg_safety_assessment", "prod_svc_001", 1],
    ["pkg_safety_assessment", "prod_emg_001", 1],
    # Installation package — catalog of installables
    ["pkg_safety_installation", "prod_bth_001", 1],
    ["pkg_safety_installation", "prod_bth_008", 1],
    ["pkg_safety_installation", "prod_bed_004", 1],
    ["pkg_safety_installation", "prod_hal_001", 1],
    ["pkg_safety_installation", "prod_bth_005", 1],
    ["pkg_safety_installation", "prod_bth_006", 1],
    ["pkg_safety_installation", "prod_bth_007", 1],
    ["pkg_safety_installation", "prod_ext_001", 1],
    ["pkg_safety_installation", "prod_hal_003", 1],
    # Peace of mind (family update is included in wellness visit details)
    ["pkg_peace_of_mind", "prod_wel_001", 1],
    ["pkg_peace_of_mind", "prod_trn_002", 1],
    ["pkg_peace_of_mind", "prod_wel_010", 1],
    ["pkg_peace_of_mind", "prod_hm_004", 1],
    ["pkg_peace_of_mind", "prod_svc_001", 1],
]


def _load_live_image_ids() -> dict[str, str]:
    """Map product_id → comma-separated ImageDocumentIDs from the live global catalog.

    Best-effort: if DB is unavailable, returns {}.
    """
    try:
        from app.core.database import SessionLocal
        from app.livewell.catalog_images import format_image_document_ids_cell, normalize_image_ids
        from app.livewell.catalog_service import normalize_catalog
        from app.livewell.global_catalog_store import ensure_global_catalog_dict
    except Exception:
        return {}

    db = SessionLocal()
    try:
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        out: dict[str, str] = {}
        for product in catalog.get("products") or []:
            pid = str(product.get("id") or "")
            ids = normalize_image_ids(product)
            if pid and ids:
                out[pid] = format_image_document_ids_cell(ids)
        return out
    except Exception as exc:
        print(f"Note: could not load live image_ids ({exc}); workbook ImageDocumentIDs left blank.")
        return {}
    finally:
        db.close()


def _apply_image_ids(products: list[list], image_map: dict[str, str]) -> tuple[list[list], int]:
    """Fill ImageDocumentIDs column (index 12) from live catalog when present."""
    filled = 0
    updated: list[list] = []
    for row in products:
        row = list(row)
        pid = str(row[0])
        if image_map.get(pid):
            row[12] = image_map[pid]
            filled += 1
        updated.append(row)
    return updated, filled


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing canonical workbook: {SRC}")

    shutil.copy2(SRC, OUT)
    wb = load_workbook(OUT)

    image_map = _load_live_image_ids()
    products, images_filled = _apply_image_ids(PILOT_PRODUCTS, image_map)

    # Meta
    if "00_Meta" in wb.sheetnames:
        meta = wb["00_Meta"]
        keys = {meta.cell(r, 1).value: r for r in range(2, (meta.max_row or 1) + 1)}
        updates = {
            "WorkbookVariant": "Pilot launch catalog",
            "PilotNotes": (
                "Commercial catalog limited to Safety Assessment, Safety Installation SKUs, "
                "and Family Peace-of-Mind Support. ProductIDs/ProductCodes kept stable so "
                "existing catalog photos merge/relink on import. Rubric, solutions, suppliers, "
                "pricing keys, AI, and rule-engine sheets retained; membership rules retargeted."
            ),
            "UploadId": None,
            "UploadedAt": None,
        }
        for key, val in updates.items():
            if key in keys:
                meta.cell(keys[key], 2, val)
            else:
                meta.append([key, val])

    # Products
    ws = wb["05_Products"]
    _write_rows(ws, products)

    # ProductSolutions — keep links only for retained product IDs
    ws = wb["06_ProductSolutions"]
    header = [c.value for c in ws[1]]
    kept = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        if str(row[0]) in PILOT_PRODUCT_IDS:
            kept.append(list(row))
    _write_rows(ws, kept)
    assert header[0] == "ProductID"

    # ProductSuppliers — only offers for pilot products
    offers: list[list] = []
    if "08_ProductSuppliers" in wb.sheetnames:
        ws = wb["08_ProductSuppliers"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            if str(row[0]) in PILOT_PRODUCT_IDS:
                offers.append(list(row))
        _write_rows(ws, offers)

    # Packages
    _write_rows(wb["10_Packages"], PILOT_PACKAGES)
    _write_rows(wb["11_PackageProducts"], PILOT_PACKAGE_PRODUCTS)

    # Membership rules → pilot packages
    if "19_MembershipRules" in wb.sheetnames:
        ws = wb["19_MembershipRules"]
        header = [c.value for c in ws[1]]
        try:
            mbr_col = header.index("RecommendedMembershipID") + 1
        except ValueError:
            mbr_col = 9
        mapping = {
            "mbr_independent": "pkg_safety_assessment",
            "mbr_assisted": "pkg_peace_of_mind",
            "mbr_premium": "pkg_peace_of_mind",
            "mbr_nri": "pkg_peace_of_mind",
        }
        for r in range(2, (ws.max_row or 1) + 1):
            cur = ws.cell(r, mbr_col).value
            if cur in mapping:
                ws.cell(r, mbr_col, mapping[cur])

    if "12_AIPackageTiers" in wb.sheetnames:
        ws = wb["12_AIPackageTiers"]
        _write_rows(
            ws,
            [
                [
                    "pkg_safety_assessment",
                    "Safety Assessment",
                    "One-time assessment visit and written plan",
                    1,
                    "Yes",
                ],
                [
                    "pkg_safety_installation",
                    "Safety Installation",
                    "Installed grab bars, lighting, non-slip, toilet/shower support, railings",
                    2,
                    "Yes",
                ],
                [
                    "pkg_peace_of_mind",
                    "Family Peace-of-Mind Support",
                    "Ongoing wellness, accompaniment, escalation, repairs, family updates",
                    3,
                    "Yes",
                ],
            ],
        )

    if "13_AIPackageSolutions" in wb.sheetnames:
        ws = wb["13_AIPackageSolutions"]
        header = [c.value for c in ws[1]]
        tier_idx = 0
        for i, h in enumerate(header):
            if h and "tier" in str(h).lower():
                tier_idx = i
                break
        pilot_tiers = {
            "pkg_safety_assessment",
            "pkg_safety_installation",
            "pkg_peace_of_mind",
        }
        kept_ai = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row:
                continue
            tier = row[tier_idx]
            if tier in pilot_tiers:
                kept_ai.append(list(row))
        _write_rows(ws, kept_ai)

    wb.save(OUT)
    wb.close()
    print(f"Wrote {OUT}")
    print(f"Products: {len(products)}")
    print(f"Packages: {len(PILOT_PACKAGES)}")
    print(f"Package-product links: {len(PILOT_PACKAGE_PRODUCTS)}")
    print(f"ProductSolutions kept: {len(kept)}")
    print(f"Supplier offers kept: {len(offers)}")
    print(f"Products with ImageDocumentIDs from live catalog: {images_filled}")


if __name__ == "__main__":
    main()
