# LiveWell360 configuration spreadsheet (canonical)

**File:** `Kushalaya_Configuration.xlsx`

Single Tek Matrix master workbook for LiveWell360. **Products and packages live only
here** (sheets 05–06, 10–11). Do not hand-edit `default_catalog.json` or frontend
catalog seed files — regenerate them from this workbook.

Edit, import, and export via **Master Data**. Rule tables (19–28) persist as tenant
`workflow_config.livewell_rule_engine`.

## Sheet map (engines)

| Sheets | Engine |
|--------|--------|
| 01–02 | Assessment rubric |
| 03–04 | Recommendation (Solution Library v1 `LW-CAT-SUB-nnn` + triggers) |
| 05–08 | Product / vendor (**05–06 + 10–11 = catalog SoT**) |
| 09–11 | Pricing / packages |
| 12–18 | AI prompt / vision |
| 19 | Membership (score + family + clinical) |
| 20 | ECM assignment |
| 21 | Assessment findings (platform language) |
| 22–24 | Generic rules (+ DependsOnRuleID) |
| 25 | Risk bands |
| 26 | Quote discounts |
| 27 | Notifications (ops vs customer) |
| 28 | Follow-ups (event-driven) |

Keep **Finding → Solution → Product → Vendor**. Do not link findings directly to SKUs.

## Edit workflow (catalog)

1. Edit **05_Products**, **06_ProductSolutions**, **10_Packages**, **11_PackageProducts** in the xlsx
   (or **Export workbook** from Master Data, edit, re-upload).
2. Sync JSON mirrors used by the API factory fallback and frontend offline defaults:

```bash
python backend/scripts/sync_catalog_defaults_from_workbook.py
```

3. **Upload → Approve** on the tenant so live DB matches the spreadsheet  
   (empty `ImageDocumentIDs` keep existing product photos). Or from the API host:

```bash
cd backend
python scripts/apply_workbook_catalog_preserving_images.py --dry-run
python scripts/apply_workbook_catalog_preserving_images.py
```

4. Commit the xlsx **and** the generated `default_catalog.json` /
   `frontend/lib/livewell/generated/catalog-from-workbook.json`.

Fresh tenants: **Seed from master spreadsheet** fills empty entities, including `rule_engine` and catalog.

## Rebuild non-catalog sheets from code defaults

```bash
python backend/scripts/build_master_workbook.py
python backend/scripts/validate_master_workbook.py
```

`build_master_workbook.py` **preserves products/packages from the existing xlsx** when
present. It does not invent catalog rows from hand-edited TypeScript.
