from app.livewell.supplier_defaults import DEFAULT_SUPPLIERS
from app.livewell.supplier_service import normalize_supplier_directory


def test_normalize_supplier_directory_defaults():
    out = normalize_supplier_directory(DEFAULT_SUPPLIERS)
    assert len(out["suppliers"]) == 3
    assert len(out["offers"]) == 3
    preferred = [o for o in out["offers"] if o["preferred"]]
    assert len(preferred) == 1
    assert preferred[0]["product_id"] == "prod_bth_001"


def test_normalize_one_preferred_per_product():
    raw = {
        "suppliers": [
            {"id": "s1", "name": "A", "active": True, "sort_order": 0},
            {"id": "s2", "name": "B", "active": True, "sort_order": 1},
        ],
        "offers": [
            {
                "product_id": "p1",
                "supplier_id": "s1",
                "supplier_cost_inr": 100,
                "preferred": True,
            },
            {
                "product_id": "p1",
                "supplier_id": "s2",
                "supplier_cost_inr": 80,
                "preferred": True,
            },
        ],
    }
    out = normalize_supplier_directory(raw)
    preferred = [o for o in out["offers"] if o["preferred"]]
    assert len(preferred) == 1
    assert preferred[0]["supplier_cost_inr"] == 80


def test_suppliers_api_get_and_save(client, admin_headers, seed_tenant):
    res = client.get("/api/v1/home-safety/suppliers", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["suppliers"]) >= 1

    updated = {
        **body,
        "suppliers": [
            *body["suppliers"],
            {
                "id": "sup_test",
                "name": "Test Vendor",
                "city": "Chennai",
                "active": True,
                "sort_order": 99,
            },
        ],
    }
    save = client.put("/api/v1/home-safety/suppliers", headers=admin_headers, json=updated)
    assert save.status_code == 200
    names = [s["name"] for s in save.json()["suppliers"]]
    assert "Test Vendor" in names
