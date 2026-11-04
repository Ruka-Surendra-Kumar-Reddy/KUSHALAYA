"""Sales -> Vendors: create / list / update / deactivate, validation, roles, tenant isolation."""

from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User

BASE = {
    "company_name": "Sri Sai Plumbing",
    "phone1": "9876543210",
    "owner_name": "Ramesh",
    "gstin": "36abcde1234f1z5",
    "services": ["plumbing", "grab_bars"],
    "fee_paise": 50000,
    "fee_basis": "per_visit",
    "last_payment_date": "2026-10-01",
}


def _create(client, headers, **over):
    return client.post("/api/v1/vendors", headers=headers, json={**BASE, **over})


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_create_and_list(client, seed_tenant, auth_headers):
    res = _create(client, auth_headers)
    assert res.status_code == 201, res.text
    v = res.json()
    assert v["gstin"] == "36ABCDE1234F1Z5"
    assert v["fee_paise"] == 50000 and isinstance(v["fee_paise"], int)
    assert v["services"] == ["grab_bars", "plumbing"]  # list order
    assert v["status"] == "active" and v["created_at"]
    assert v["created_by_user_id"] == seed_tenant["manager"].id

    _create(client, auth_headers, company_name="Care Physio", owner_name="Lakshmi", services=["physiotherapy"], gstin=None)
    rows = client.get("/api/v1/vendors", headers=auth_headers).json()
    assert [r["company_name"] for r in rows] == ["Care Physio", "Sri Sai Plumbing"]
    assert [r["company_name"] for r in client.get("/api/v1/vendors?service=physiotherapy", headers=auth_headers).json()] == ["Care Physio"]
    assert [r["company_name"] for r in client.get("/api/v1/vendors?q=ramesh", headers=auth_headers).json()] == ["Sri Sai Plumbing"]


def test_options_list(client, seed_tenant, auth_headers):
    opts = client.get("/api/v1/vendors/options", headers=auth_headers).json()
    assert opts["services"][0]["label"] == "Grab bar & safety installation"
    assert opts["services"][-1]["code"] == "other"
    assert [b["code"] for b in opts["fee_bases"]] == ["per_visit", "monthly", "one_time", "per_job"]


def test_validation(client, seed_tenant, auth_headers):
    assert _create(client, auth_headers, company_name="  ").status_code == 422
    assert _create(client, auth_headers, phone1="").status_code == 422
    assert _create(client, auth_headers, gstin="36ABCDE1234").status_code == 422
    assert _create(client, auth_headers, services=["massage"]).status_code == 422
    assert _create(client, auth_headers, fee_basis="weekly").status_code == 422
    assert _create(client, auth_headers, fee_paise=-1).status_code == 422
    assert _create(client, auth_headers, fee_paise=500.5).status_code == 422  # paise are whole numbers


def test_update_and_deactivate(client, seed_tenant, auth_headers):
    v = _create(client, auth_headers, services=["other"], services_other="Tiling").json()
    assert v["services_other"] == "Tiling"
    res = client.put(f"/api/v1/vendors/{v['id']}", headers=auth_headers, json={**BASE, "fee_paise": 120000, "fee_basis": "monthly"})
    assert res.status_code == 200, res.text
    assert res.json()["fee_paise"] == 120000 and res.json()["fee_basis"] == "monthly"
    assert res.json()["services_other"] is None  # "other" no longer ticked
    off = client.post(f"/api/v1/vendors/{v['id']}/deactivate", headers=auth_headers).json()
    assert off["status"] == "inactive"
    assert client.get("/api/v1/vendors?status=active", headers=auth_headers).json() == []


def test_viewer_reads_only(client, seed_tenant, auth_headers):
    _create(client, auth_headers)
    viewer = _login(client, "viewer@test.example")
    assert len(client.get("/api/v1/vendors", headers=viewer).json()) == 1
    assert _create(client, viewer).status_code == 403


def test_tenant_isolation(db, client, seed_tenant, auth_headers):
    v = _create(client, auth_headers).json()
    other = Tenant(name="Other Agency", email="other@test.example", phone="+91-40-0000", address="2 Road", city="Hyderabad", state="TS")
    db.add(other)
    db.flush()
    db.add(User(email="mgr2@test.example", password_hash=hash_password("testpass123"), first_name="Other",
                last_name="Manager", role="CARE_MANAGER", tenant_id=other.id))
    db.commit()
    h2 = _login(client, "mgr2@test.example")
    assert client.get("/api/v1/vendors", headers=h2).json() == []
    assert client.get(f"/api/v1/vendors/{v['id']}", headers=h2).status_code == 404
    assert client.put(f"/api/v1/vendors/{v['id']}", headers=h2, json=BASE).status_code == 404


PDF = b"%PDF-1.4 signed on paper"


def _upload(client, headers, vendor_id, content=PDF, name="signed.pdf", mime="application/pdf"):
    return client.post(
        f"/api/v1/vendors/{vendor_id}/signed-agreement", headers=headers, files={"file": (name, content, mime)}
    )


def test_signed_copy_marks_vendor_signed(client, seed_tenant, auth_headers):
    vid = _create(client, auth_headers).json()["id"]
    url = "/api/v1/vendors"
    assert client.get(f"{url}/{vid}", headers=auth_headers).json()["agreement_status"] == "pending"
    assert [v["id"] for v in client.get(f"{url}?agreement=open", headers=auth_headers).json()] == [vid]

    res = _upload(client, auth_headers, vid)
    assert res.status_code == 200, res.text
    assert res.json()["agreement_status"] == "signed" and res.json()["signed_agreement_name"] == "signed.pdf"
    assert client.get(f"{url}?agreement=open", headers=auth_headers).json() == []
    assert [v["id"] for v in client.get(f"{url}?agreement=signed", headers=auth_headers).json()] == [vid]

    copy = client.get(f"{url}/{vid}/signed-agreement", headers=auth_headers)
    assert copy.status_code == 200 and copy.content == PDF

    # Saving the vendor form keeps the copy.
    assert client.put(f"{url}/{vid}", headers=auth_headers, json=BASE).json()["agreement_status"] == "signed"

    assert client.delete(f"{url}/{vid}/signed-agreement", headers=auth_headers).json()["agreement_status"] == "pending"
    assert client.get(f"{url}/{vid}/signed-agreement", headers=auth_headers).status_code == 404


def test_signed_copy_rejects_other_files(client, seed_tenant, auth_headers):
    vid = _create(client, auth_headers).json()["id"]
    assert _upload(client, auth_headers, vid, b"not a pdf").status_code == 422
    assert _upload(client, auth_headers, vid, b"MZ", "a.exe", "application/octet-stream").status_code == 422
    assert _upload(client, auth_headers, vid, b"").status_code == 422
    assert _upload(client, auth_headers, vid, PDF + b"x" * (10 * 1024 * 1024)).status_code == 422
