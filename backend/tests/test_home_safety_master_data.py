from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.livewell.master_data_workbook import (
    build_payload_from_sheets,
    export_workbook_bytes,
    parse_workbook_bytes,
)

EXPECTED_EXPORT_SHEETS = [
    "00_Meta",
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


def _minimal_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "03_Solutions"
    ws.append(["SolutionID", "Section", "Finding", "Priority", "Description", "ContractorType", "EstCost", "InstallTime", "ScoreGain", "Active"])
    ws.append(["SH-TEST-001", "Bathroom", "Test finding", "high", "Fix it", "Installer", "1000", "2 hours", 5, "Yes"])
    ws2 = wb.create_sheet("04_SolutionTriggers")
    ws2.append(["QuestionID", "TriggerRatings", "SolutionID", "Priority"])
    ws2.append(["q_test", "unsafe,acceptable", "SH-TEST-001", 1])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_workbook_solutions():
    sheets = parse_workbook_bytes(_minimal_workbook_bytes())
    assert "solutions" in sheets
    payload = build_payload_from_sheets(sheets)
    assert "solutions" in payload
    assert payload["solutions"]["solutions"][0]["id"] == "SH-TEST-001"
    assert "q_test" in payload["solutions"]["solutions"][0]["rubricItemIds"]


def test_validate_payload_empty_errors():
    from app.livewell.master_data_service import _validate_payload

    errors: list[str] = []
    warnings: list[str] = []
    out = _validate_payload({}, errors, warnings)
    assert not out
    assert errors


def test_export_workbook_contiguous_sheet_order():
    data = export_workbook_bytes({})
    wb = load_workbook(BytesIO(data), read_only=True)
    assert wb.sheetnames == EXPECTED_EXPORT_SHEETS
    wb.close()


def test_parse_workbook_numeric_only_sheet_tab():
    """Tabs named only '05' must still map to products."""
    wb = Workbook()
    ws = wb.active
    ws.title = "05"
    ws.append(
        [
            "ProductID",
            "Product Name",
            "Category",
            "BasePriceINR",
            "Active",
        ]
    )
    ws.append(["prod_test", "Test Product", "General", 1000, "Yes"])
    buf = BytesIO()
    wb.save(buf)
    sheets = parse_workbook_bytes(buf.getvalue())
    assert "products" in sheets
    assert len(sheets["products"]) == 1
    payload = build_payload_from_sheets(sheets)
    assert payload["catalog"]["products"][0]["id"] == "prod_test"


def test_import_formats_money_prefix_and_skips_orphan_links():
    """Formatted prices, uppercase CategoryPrefix, no stub rows from orphan junctions."""
    wb = Workbook()
    ws = wb.active
    ws.title = "05_Products"
    ws.append(
        [
            "ProductID",
            "Product Name",
            "Category",
            "CategoryPrefix",
            "BasePriceINR",
            "Active",
        ]
    )
    ws.append(["prod_bar", "Grab bar", "Bathroom", "bth", "₹3,500", "Yes"])
    ws.append(["prod_zero", "Free sample", "General", "GEN", 0, "Yes"])

    ws_ps = wb.create_sheet("06_ProductSolutions")
    ws_ps.append(["ProductID", "SolutionID"])
    ws_ps.append(["prod_bar", "SOL-1"])
    ws_ps.append(["missing_prod", "SOL-ORPHAN"])  # orphan product stub must not appear

    ws_pkg = wb.create_sheet("10_Packages")
    ws_pkg.append(
        ["PackageID", "Package Name", "PriceINR", "PriceLabel", "Display Order", "Highlight", "Active"]
    )
    ws_pkg.append(["pkg_a", "Starter", "12,000", "From", 1, "No", "Yes"])

    ws_pp = wb.create_sheet("11_PackageProducts")
    ws_pp.append(["PackageID", "ProductID", "Qty"])
    ws_pp.append(["pkg_a", "prod_bar", 1])
    ws_pp.append(["pkg_missing", "prod_bar", 1])  # orphan package stub must not appear

    ws_cat = wb.create_sheet("01_AssessmentCategories")
    ws_cat.append(["CategoryID", "Category Name", "Weight", "Display Order", "Active"])
    ws_cat.append(["cat_bath", "Bathroom", 10, 1, "Yes"])

    ws_q = wb.create_sheet("02_AssessmentQuestions")
    ws_q.append(["QuestionID", "CategoryID", "Question", "Weight", "Critical", "Active"])
    ws_q.append(["q_bath_1", "cat_bath", "Grab bars present?", 1, "No", "Yes"])
    ws_q.append(["q_orphan", "cat_missing", "Orphan question?", 1, "No", "Yes"])

    ws_sol = wb.create_sheet("03_Solutions")
    ws_sol.append(
        [
            "SolutionID",
            "Section",
            "Finding",
            "Priority",
            "Description",
            "Active",
        ]
    )
    ws_sol.append(["SOL-1", "Bathroom", "Missing grab bars", "high", "Install grab bars", "Yes"])

    ws_tr = wb.create_sheet("04_SolutionTriggers")
    ws_tr.append(["QuestionID", "TriggerRatings", "SolutionID", "Priority"])
    ws_tr.append(["q_bath_1", "unsafe", "SOL-1", 1])
    ws_tr.append(["q_bath_1", "unsafe", "SOL-MISSING", 1])  # orphan solution stub must not appear

    buf = BytesIO()
    wb.save(buf)
    payload = build_payload_from_sheets(parse_workbook_bytes(buf.getvalue()))

    products = {p["id"]: p for p in payload["catalog"]["products"]}
    assert set(products) == {"prod_bar", "prod_zero"}
    assert products["prod_bar"]["price_inr"] == 3500
    assert products["prod_bar"]["category_prefix"] == "BTH"
    assert products["prod_bar"]["solution_ids"] == ["SOL-1"]
    assert products["prod_zero"]["price_inr"] == 0

    packages = {p["id"]: p for p in payload["catalog"]["packages"]}
    assert set(packages) == {"pkg_a"}
    assert packages["pkg_a"]["price_inr"] == 12000
    assert packages["pkg_a"]["product_ids"] == ["prod_bar"]

    cats = {c["id"]: c for c in payload["rubric"]["categories"]}
    assert set(cats) == {"cat_bath"}
    assert [i["id"] for i in cats["cat_bath"]["items"]] == ["q_bath_1"]

    sols = {s["id"]: s for s in payload["solutions"]["solutions"]}
    assert set(sols) == {"SOL-1"}
    assert sols["SOL-1"]["rubricItemIds"] == ["q_bath_1"]


def test_export_preserves_zero_price_inr():
    data = export_workbook_bytes(
        {
            "catalog": {
                "products": [
                    {
                        "id": "p0",
                        "name": "Free",
                        "short_description": "Free",
                        "category": "General",
                        "price_inr": 0,
                        "price_label": "Quote",
                    }
                ],
                "packages": [
                    {
                        "id": "pkg0",
                        "name": "Zero pack",
                        "price_inr": 0,
                        "price_label": "From",
                        "product_ids": [],
                        "sort_order": 1,
                    }
                ],
            }
        }
    )
    sheets = parse_workbook_bytes(data)
    assert sheets["products"][0]["BasePriceINR"] == "0"
    assert sheets["packages"][0]["PriceINR"] == "0"
    payload = build_payload_from_sheets(sheets)
    assert payload["catalog"]["products"][0]["price_inr"] == 0
    assert payload["catalog"]["packages"][0]["price_inr"] == 0


def test_catalog_roundtrip_preserves_solution_links_and_package_fields():
    current = {
        "catalog": {
            "products": [
                {
                    "id": "prod_a",
                    "name": "Grab bars",
                    "category": "Modification",
                    "short_description": "Short",
                    "details": "Long details",
                    "price_inr": 8500,
                    "solution_ids": ["LW-HS-007"],
                }
            ],
            "packages": [
                {
                    "id": "pkg_basic",
                    "name": "Basic",
                    "tagline": "Essentials",
                    "description": "Package description",
                    "price_inr": 18500,
                    "price_label": "From",
                    "highlight": True,
                    "product_ids": ["prod_a"],
                    "sort_order": 2,
                }
            ],
        }
    }
    data = export_workbook_bytes(current)
    sheets = parse_workbook_bytes(data)
    assert sheets.get("productsolutions")
    assert sheets["productsolutions"][0]["SolutionID"] == "LW-HS-007"
    payload = build_payload_from_sheets(sheets)
    cat = payload["catalog"]
    # Legacy solution ids from the workbook resolve to the current id (LW-HS-007 -> LW-HS-BTH-001).
    assert cat["products"][0]["solution_ids"] == ["LW-HS-BTH-001"]
    assert cat["products"][0]["details"] == "Long details"
    pkg = cat["packages"][0]
    assert pkg["description"] == "Package description"
    assert pkg["price_inr"] == 18500
    assert pkg["product_ids"] == ["prod_a"]


def test_product_code_none_imported_as_null():
    wb = Workbook()
    ws = wb.active
    ws.title = "05_Products"
    ws.append(["ProductID", "ProductCode", "Product Name", "Category", "Active"])
    ws.append(["prod_x", "None", "Widget", "General", "Yes"])
    buf = BytesIO()
    wb.save(buf)
    payload = build_payload_from_sheets(parse_workbook_bytes(buf.getvalue()))
    assert payload["catalog"]["products"][0]["product_code"] is None


def test_parse_workbook_legacy_sheet_numbers():
    """Older exports used non-contiguous numbers (05_Solutions, etc.)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "05_Solutions"
    ws.append(
        [
            "SolutionID",
            "Section",
            "Finding",
            "Priority",
            "Description",
            "ContractorType",
            "EstCost",
            "InstallTime",
            "ScoreGain",
            "Active",
        ]
    )
    ws.append(["SH-LEG-001", "General", "Legacy", "low", "Desc", "", "", "", 0, "Yes"])
    buf = BytesIO()
    wb.save(buf)
    sheets = parse_workbook_bytes(buf.getvalue())
    assert "solutions" in sheets
    payload = build_payload_from_sheets(sheets)
    assert payload["solutions"]["solutions"][0]["id"] == "SH-LEG-001"


def test_config_snapshot_equals_uses_full_config_not_summary_counts():
    from app.livewell.config_keys import (
        AI_CONFIG_KEY,
        CATALOG_KEY,
        PRICING_KEY,
        RUBRIC_KEY,
        SOLUTIONS_KEY,
        SUPPLIERS_KEY,
    )
    from app.livewell.master_data_service import _config_snapshot_equals
    from app.livewell.stored_config import normalize_entity_config

    base_snapshot = {
        "rubric": {"categories": [{"id": "c1", "items": []}]},
        "solutions": {"solutions": []},
        "catalog": {"products": [{"id": "p1", "name": "A"}], "packages": []},
        "pricing": {},
        "suppliers": {"suppliers": [], "offers": []},
        "ai_config": {},
    }
    live_cfg = {
        RUBRIC_KEY: base_snapshot["rubric"],
        SOLUTIONS_KEY: base_snapshot["solutions"],
        CATALOG_KEY: base_snapshot["catalog"],
        PRICING_KEY: base_snapshot["pricing"],
        SUPPLIERS_KEY: base_snapshot["suppliers"],
        AI_CONFIG_KEY: {"tiers": [{"id": "essential", "label": "Essential"}]},
    }
    assert not _config_snapshot_equals(base_snapshot, live_cfg)
    assert normalize_entity_config(base_snapshot) != normalize_entity_config(live_cfg)


def test_list_versions_matches_current_only_when_snapshot_equals_live(db, seed_tenant):
    from app.livewell.config_keys import CATALOG_KEY, RUBRIC_KEY
    from app.livewell.master_data_service import HomeSafetyMasterDataService, VERSIONS_KEY

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    rubric = {"categories": [{"id": "c1", "name": "Cat", "items": []}]}
    catalog_v1 = {"products": [{"id": "p1", "name": "One"}], "packages": []}
    catalog_v2 = {"products": [{"id": "p1", "name": "Two"}], "packages": []}

    tenant.workflow_config = {
        RUBRIC_KEY: rubric,
        CATALOG_KEY: catalog_v2,
        VERSIONS_KEY: [
            {
                "version_id": "md-old",
                "approved_at": "2026-06-25T18:00:00+00:00",
                "applied": ["catalog"],
                "snapshot": {"rubric": rubric, "catalog": catalog_v1},
            },
            {
                "version_id": "md-new",
                "approved_at": "2026-06-28T20:00:00+00:00",
                "applied": ["catalog"],
                "snapshot": {"rubric": rubric, "catalog": catalog_v1},
            },
        ],
    }
    db.commit()

    versions = HomeSafetyMasterDataService.list_versions(db, admin)
    assert len(versions) == 2
    assert versions[0]["version_id"] == "md-new"
    assert versions[0]["is_latest_import"] is True
    assert versions[0]["matches_current"] is False
    assert versions[1]["matches_current"] is False


def test_update_staged_pricing(db, seed_tenant):
    from app.livewell.master_data_service import (
        HomeSafetyMasterDataService,
        STAGING_KEY,
    )
    from app.livewell.pricing_defaults import DEFAULT_PRICING

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    version_id = "md-pricing-test"
    imported = {**DEFAULT_PRICING, "labor_rate_per_hour_inr": 800}
    tenant.workflow_config = {
        **(tenant.workflow_config or {}),
        STAGING_KEY: {
            version_id: {
                "version_id": version_id,
                "status": "pending",
                "errors": [],
                "warnings": [],
                "payload": {"pricing": imported},
                "diff": {"pricing": {"fields_changed": 1, "changes": {}}},
                "sheets_found": ["pricing"],
            }
        },
    }
    db.commit()

    result = HomeSafetyMasterDataService.update_staged_pricing(
        db,
        admin,
        version_id,
        {**imported, "gst_percent": 12, "labor_rate_per_hour_inr": 950},
    )
    assert result["pricing_edited_in_staging"] is True
    assert result["staged_pricing"]["gst_percent"] == 12
    assert result["staged_pricing"]["labor_rate_per_hour_inr"] == 950
    assert "pricing" in result["entities"]
    pricing_diff = result["diff"].get("pricing") or {}
    assert pricing_diff.get("fields_changed", 0) >= 1
    assert "gst_percent" in (pricing_diff.get("changes") or {})


def test_export_includes_meta_upload_id():
    from app.livewell.master_data_workbook import export_workbook_bytes, extract_workbook_meta, parse_workbook_bytes

    data = export_workbook_bytes(
        {"catalog": {"products": [], "packages": []}},
        meta={
            "upload_id": "md-test123",
            "uploaded_at": "2026-01-01T00:00:00Z",
            "exported_at": "2026-01-02T00:00:00Z",
            "tenant_id": "9",
        },
    )
    sheets = parse_workbook_bytes(data)
    assert "meta" in sheets
    meta = extract_workbook_meta(sheets)
    assert meta["upload_id"] == "md-test123"
    assert meta["tenant_id"] == "9"


def test_field_drift_detects_price_change():
    from app.livewell.master_data_drift import compute_field_drift

    baseline = {
        "catalog": {
            "products": [{"id": "p1", "name": "Bar", "price_inr": 1000}],
            "packages": [],
        }
    }
    current = {
        "catalog": {
            "products": [{"id": "p1", "name": "Bar", "price_inr": 1500}],
            "packages": [],
        }
    }
    drift = compute_field_drift(baseline, current)
    assert drift["dirty"] is True
    assert any(c["field"] == "price_inr" for c in drift["changes"])


def test_validate_upload_rejects_non_xlsx():
    from app.livewell.master_data_service import _validate_upload_bytes
    import pytest

    with pytest.raises(Exception):
        _validate_upload_bytes(b"not-a-zip", "notes.txt")


def test_export_blocked_when_empty(db, seed_tenant):
    from sqlalchemy.orm.attributes import flag_modified

    from app.livewell.master_data_service import HomeSafetyMasterDataService
    import pytest

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    tenant.workflow_config = {}
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)

    with pytest.raises(Exception):
        HomeSafetyMasterDataService.export_workbook(db, admin)


def test_approve_sets_baseline_and_sync_clean(db, seed_tenant):
    from sqlalchemy.orm.attributes import flag_modified

    from app.livewell.catalog_defaults import DEFAULT_CATALOG
    from app.livewell.config_keys import MASTER_BASELINE_KEY
    from app.livewell.master_data_service import (
        HomeSafetyMasterDataService,
        STAGING_KEY,
        _validate_payload,
    )
    from app.livewell.master_data_workbook import (
        build_payload_from_sheets,
        export_workbook_bytes,
        parse_workbook_bytes,
    )

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    tenant.workflow_config = {}
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)

    sync = HomeSafetyMasterDataService.get_sync_status(db, admin)
    assert sync["requires_upload"] is True
    assert sync["is_empty"] is True

    version_id = "md-sync-1"
    raw = export_workbook_bytes({"catalog": DEFAULT_CATALOG})
    sheets = parse_workbook_bytes(raw)
    errors: list[str] = []
    warnings: list[str] = []
    cleaned = _validate_payload(build_payload_from_sheets(sheets), errors, warnings)
    assert not errors
    tenant.workflow_config = {
        STAGING_KEY: {
            version_id: {
                "version_id": version_id,
                "status": "pending",
                "errors": [],
                "warnings": warnings,
                "payload": cleaned,
                "diff": {},
                "sheets_found": sorted(sheets.keys()),
                "workbook_meta": {},
            }
        }
    }
    flag_modified(tenant, "workflow_config")
    db.commit()

    result = HomeSafetyMasterDataService.approve_import(db, admin, version_id)
    assert result["upload_id"] == version_id
    db.refresh(tenant)
    baseline = (tenant.workflow_config or {}).get(MASTER_BASELINE_KEY) or {}
    assert baseline.get("upload_id") == version_id

    sync2 = HomeSafetyMasterDataService.get_sync_status(db, admin)
    assert sync2["has_baseline"] is True
    assert sync2["dirty"] is False
    assert sync2["requires_upload"] is False


def test_rollback_restores_snapshot_and_truncates_history(db, seed_tenant):
    from app.livewell.config_keys import CATALOG_KEY, RUBRIC_KEY
    from app.livewell.master_data_service import HomeSafetyMasterDataService, VERSIONS_KEY

    tenant = seed_tenant["tenant"]
    admin = seed_tenant["admin"]
    rubric = {"categories": []}
    snap_a = {"rubric": rubric, "catalog": {"products": [{"id": "a", "name": "A"}], "packages": []}}
    snap_b = {"rubric": rubric, "catalog": {"products": [{"id": "b", "name": "B"}], "packages": []}}

    tenant.workflow_config = {
        RUBRIC_KEY: snap_b["rubric"],
        CATALOG_KEY: {"products": [{"id": "live", "name": "Live"}], "packages": []},
        VERSIONS_KEY: [
            {"version_id": "md-1", "snapshot": snap_a, "applied": ["catalog"]},
            {"version_id": "md-2", "snapshot": snap_b, "applied": ["catalog"]},
            {"version_id": "md-3", "snapshot": snap_b, "applied": ["catalog"]},
        ],
    }
    db.commit()

    result = HomeSafetyMasterDataService.rollback(db, admin, "md-2")
    db.refresh(tenant)

    assert result["status"] == "rolled_back"
    assert result["versions_removed"] == 2
    remaining = (tenant.workflow_config or {}).get(VERSIONS_KEY) or []
    assert len(remaining) == 1
    assert remaining[0]["version_id"] == "md-1"
    assert tenant.workflow_config[CATALOG_KEY]["products"][0]["id"] == "b"


def test_legacy_solution_ids_resolve_regardless_of_what_was_loaded_before():
    """A small library loaded earlier (another import/test) must not drop the factory
    legacy -> current map; unknown ids are kept as given."""
    from app.livewell.solution_id_aliases import reload_aliases_from_solutions, remap_solution_ids

    reload_aliases_from_solutions([{"id": "LW-X-001", "legacyIds": ["OLD-X"]}])
    assert remap_solution_ids(["LW-HS-007", "OLD-X", "LW-CUSTOM-9"]) == ["LW-HS-BTH-001", "LW-X-001", "LW-CUSTOM-9"]
    reload_aliases_from_solutions([])
    assert remap_solution_ids(["LW-HS-007", "OLD-X"]) == ["LW-HS-BTH-001", "OLD-X"]
