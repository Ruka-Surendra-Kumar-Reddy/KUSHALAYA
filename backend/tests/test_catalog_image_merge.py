from app.livewell.catalog_service import merge_catalog_workbook_import, normalize_catalog


def test_merge_catalog_workbook_import_preserves_images_and_solutions():
    previous = normalize_catalog(
        {
            "products": [
                {
                    "id": "prod_a",
                    "name": "Product A",
                    "image_ids": [101, 102],
                    "solution_ids": ["SH-001"],
                    "details": "Long details",
                    "short_description": "Short",
                }
            ],
            "packages": [
                {
                    "id": "pkg_a",
                    "name": "Package A",
                    "description": "Full description",
                    "price_inr": 2500,
                    "product_ids": ["prod_a"],
                }
            ],
        }
    )
    incoming = normalize_catalog(
        {
            "products": [
                {
                    "id": "prod_a",
                    "name": "Product A Renamed",
                    "short_description": "Product A Renamed",
                    "price_inr": 5000,
                },
            ],
            "packages": [
                {
                    "id": "pkg_a",
                    "name": "Package A",
                    "tagline": "Tag",
                    "product_ids": [],
                }
            ],
        }
    )
    merged = merge_catalog_workbook_import(incoming, previous)
    prod = merged["products"][0]
    assert prod["image_ids"] == [101, 102]
    assert prod["solution_ids"] == ["SH-001"]
    assert prod["details"] == "Long details"
    assert prod["short_description"] == "Short"
    pkg = merged["packages"][0]
    assert pkg["description"] == "Full description"
    assert pkg["price_inr"] == 2500
    assert pkg["product_ids"] == ["prod_a"]


def test_merge_catalog_product_images_preserves_existing():
    previous = normalize_catalog(
        {
            "products": [
                {
                    "id": "prod_a",
                    "name": "Product A",
                    "image_ids": [101, 102],
                }
            ],
        }
    )
    incoming = normalize_catalog(
        {
            "products": [
                {
                    "id": "prod_a",
                    "name": "Product A Renamed",
                    "price_inr": 5000,
                },
                {
                    "id": "prod_b",
                    "name": "Product B",
                },
            ],
        }
    )
    merged = merge_catalog_workbook_import(incoming, previous)
    by_id = {p["id"]: p for p in merged["products"]}
    assert by_id["prod_a"]["image_ids"] == [101, 102]
    assert by_id["prod_a"]["name"] == "Product A Renamed"
    assert by_id["prod_b"].get("image_ids") == []


def test_merge_catalog_product_images_keeps_incoming_when_provided():
    previous = normalize_catalog(
        {"products": [{"id": "prod_a", "name": "A", "image_ids": [101]}]}
    )
    incoming = normalize_catalog(
        {"products": [{"id": "prod_a", "name": "A", "image_ids": [202]}]}
    )
    merged = merge_catalog_workbook_import(incoming, previous)
    assert merged["products"][0]["image_ids"] == [202]
