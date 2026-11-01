"""Safe Home product catalog API — global catalog (not tenant-scoped)."""

from copy import deepcopy

from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.global_catalog_store import load_raw_global_catalog
from app.models.document import Document


def test_public_catalog_returns_defaults(client, seed_tenant):
    res = client.get("/api/v1/home-safety/catalog/public")
    assert res.status_code == 200
    data = res.json()
    assert len(data["products"]) == len(DEFAULT_CATALOG["products"])
    assert len(data["packages"]) == len(DEFAULT_CATALOG["packages"])
    assert data["products"][0]["name"] == DEFAULT_CATALOG["products"][0]["name"]


def test_admin_get_and_save_catalog(client, admin_headers, seed_tenant):
    res = client.get("/api/v1/home-safety/catalog", headers=admin_headers)
    assert res.status_code == 200
    original = res.json()

    updated = deepcopy(original)
    updated["products"][0]["name"] = "Custom Assessment Name"
    updated["packages"][1]["product_ids"] = [updated["products"][0]["id"]]

    save = client.put("/api/v1/home-safety/catalog", headers=admin_headers, json=updated)
    assert save.status_code == 200
    saved = save.json()
    assert saved["products"][0]["name"] == "Custom Assessment Name"

    public = client.get("/api/v1/home-safety/catalog/public")
    assert public.status_code == 200
    assert public.json()["products"][0]["name"] == "Custom Assessment Name"


def test_admin_catalog_includes_seeded_category_types(client, admin_headers, seed_tenant):
    res = client.get("/api/v1/home-safety/catalog", headers=admin_headers)
    assert res.status_code == 200
    types = res.json()["category_types"]
    by_prefix = {row["prefix"]: row for row in types}
    assert by_prefix["SVC"]["kind"] == "service"
    assert by_prefix["NUR"]["kind"] == "service"
    assert by_prefix["BTH"]["kind"] == "product"

    updated = res.json()
    updated["category_types"] = [
        {**row, "label": "Care visits"} if row["prefix"] == "SVC" else row for row in types
    ]
    save = client.put("/api/v1/home-safety/catalog", headers=admin_headers, json=updated)
    assert save.status_code == 200
    saved_types = {row["prefix"]: row for row in save.json()["category_types"]}
    assert saved_types["SVC"]["label"] == "Care visits"


def test_catalog_image_upload_is_global(client, admin_headers, db, seed_tenant, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")

    # Ensure catalog exists with at least one product
    res = client.get("/api/v1/home-safety/catalog", headers=admin_headers)
    assert res.status_code == 200
    product_id = res.json()["products"][0]["id"]

    files = {"file": ("grab.jpg", b"fake-jpeg-bytes", "image/jpeg")}
    upload = client.post(
        f"/api/v1/home-safety/catalog/products/{product_id}/image",
        headers=admin_headers,
        files=files,
    )
    assert upload.status_code == 200, upload.text
    catalog = upload.json()
    product = next(p for p in catalog["products"] if p["id"] == product_id)
    assert product["image_ids"]
    doc_id = product["image_ids"][-1]
    assert product["image_urls"][-1] == f"/api/v1/home-safety/catalog/public/images/{doc_id}"
    assert "tenant_id=" not in product["image_urls"][-1]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.document_type == "HOME_SAFETY_CATALOG_IMAGE"
    assert doc.storage_key.startswith("catalog/products/")

    img = client.get(f"/api/v1/home-safety/catalog/public/images/{doc_id}")
    assert img.status_code == 200
    assert img.content == b"fake-jpeg-bytes"

    # Still works with legacy tenant_id query (ignored)
    img2 = client.get(
        f"/api/v1/home-safety/catalog/public/images/{doc_id}?tenant_id={seed_tenant['tenant'].id}"
    )
    assert img2.status_code == 200

    global_raw = load_raw_global_catalog(db)
    assert global_raw is not None
    assert any(p.get("id") == product_id for p in global_raw.get("products") or [])
