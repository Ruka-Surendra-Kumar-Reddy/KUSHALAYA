from pathlib import Path

from app.core.storage import catalog_product_image_key


def test_catalog_product_image_key_sanitizes_and_keeps_name():
    key = catalog_product_image_key("BTH/001", "grab bar.png")
    assert key.startswith("catalog/products/")
    assert "BTH_001" in key
    assert key.endswith("grab_bar.png")
    assert len(Path(key).name) > 10


def test_catalog_product_image_key_strips_path_from_filename():
    key = catalog_product_image_key("prod", r"..\secret\photo.jpg")
    assert ".." not in key
    assert key.endswith("photo.jpg")
    assert key.count("/") >= 3


def test_catalog_product_image_key_truncates_long_ids():
    key = catalog_product_image_key("P" * 200, "x.png")
    product_part = key.split("/")[2]
    assert len(product_part) <= 80
