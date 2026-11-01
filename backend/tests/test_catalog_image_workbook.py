"""ImageDocumentIDs column round-trip and approve photo guard."""

from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.livewell.catalog_images import (
    format_image_document_ids_cell,
    parse_image_document_ids_cell,
)
from app.livewell.catalog_service import merge_catalog_workbook_import, normalize_catalog
from app.livewell.master_data_service import (
    _catalog_photo_preview,
    _count_products_with_photos,
)
from app.livewell.master_data_workbook import (
    build_payload_from_sheets,
    export_workbook_bytes,
    parse_workbook_bytes,
)


def test_parse_and_format_image_document_ids_cell():
    assert parse_image_document_ids_cell("") == []
    assert parse_image_document_ids_cell("101, 102") == [101, 102]
    assert parse_image_document_ids_cell("101;102") == [101, 102]
    assert format_image_document_ids_cell([101, 102]) == "101,102"


def test_workbook_import_image_document_ids_column():
    wb = Workbook()
    ws = wb.active
    ws.title = "05_Products"
    ws.append(
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
        ]
    )
    ws.append(
        [
            "prod_a",
            "",
            "Grab bars",
            "Modification",
            "",
            "",
            "",
            8500,
            "Quote",
            "",
            "",
            0,
            "101,102",
            "Yes",
        ]
    )
    buf = BytesIO()
    wb.save(buf)

    payload = build_payload_from_sheets(parse_workbook_bytes(buf.getvalue()))
    prod = payload["catalog"]["products"][0]
    assert prod["id"] == "prod_a"
    assert prod["image_ids"] == [101, 102]


def test_export_includes_image_document_ids_column():
    current = {
        "catalog": normalize_catalog(
            {
                "products": [
                    {
                        "id": "prod_a",
                        "name": "Product A",
                        "image_ids": [55, 56],
                    }
                ],
                "packages": [],
            }
        )
    }
    data = export_workbook_bytes(current)
    wb = load_workbook(BytesIO(data), read_only=True)
    ws = wb["05_Products"]
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    assert "ImageDocumentIDs" in headers
    row = next(ws.iter_rows(min_row=2, max_row=2, values_only=True))
    img_idx = headers.index("ImageDocumentIDs")
    assert row[img_idx] == "55,56"
    wb.close()


def test_catalog_photo_preview_detects_loss():
    current = {
        "catalog": normalize_catalog(
            {
                "products": [
                    {"id": "old_a", "name": "A", "image_ids": [1]},
                    {"id": "old_b", "name": "B", "image_ids": [2]},
                ],
                "packages": [],
            }
        )
    }
    staged = {
        "catalog": normalize_catalog(
            {
                "products": [{"id": "new_only", "name": "New"}],
                "packages": [],
            }
        )
    }
    preview = _catalog_photo_preview(current, staged)
    assert preview is not None
    assert preview["products_with_photos_before"] == 2
    assert preview["products_with_photos_after"] == 0
    assert preview["would_lose_photos"] is True


def test_merge_preserves_photos_when_incoming_has_explicit_empty_column():
    previous = normalize_catalog(
        {"products": [{"id": "prod_a", "name": "A", "image_ids": [101]}], "packages": []}
    )
    incoming = normalize_catalog({"products": [{"id": "prod_a", "name": "A Renamed"}], "packages": []})
    merged = merge_catalog_workbook_import(incoming, previous)
    assert merged["products"][0]["image_ids"] == [101]


def test_count_products_with_photos():
    cat = normalize_catalog(
        {
            "products": [
                {"id": "a", "name": "A", "image_ids": [1]},
                {"id": "b", "name": "B"},
            ],
            "packages": [],
        }
    )
    assert _count_products_with_photos(cat) == 1
