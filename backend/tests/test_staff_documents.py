"""Team → Documents: owners only, per person, tenant-isolated, PDF/JPG/PNG only."""

from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User

A = "/api/v1/staff-documents"
PDF = b"%PDF-1.4 signed offer letter"


def _upload(client, headers, person, content=PDF, doc_type="offer_letter", mime="application/pdf"):
    return client.post(
        f"{A}/{person}", headers=headers, data={"doc_type": doc_type}, files={"file": ("offer.pdf", content, mime)}
    )


def _me(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).json()["id"]


def test_owner_uploads_reads_and_removes(client, seed_tenant, admin_headers):
    person = f"staff/{_me(client, admin_headers)}"
    res = _upload(client, admin_headers, person)
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["doc_type"] == "offer_letter" and doc["file_name"] == "offer.pdf" and doc["uploaded_by"]
    assert [d["id"] for d in client.get(f"{A}/{person}", headers=admin_headers).json()] == [doc["id"]]
    assert client.get(f"{A}/file/{doc['id']}", headers=admin_headers).content == PDF
    assert client.delete(f"{A}/file/{doc['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{A}/{person}", headers=admin_headers).json() == []


def test_other_staff_cannot_see_them(client, seed_tenant, admin_headers, auth_headers):
    person = f"staff/{_me(client, admin_headers)}"
    doc = _upload(client, admin_headers, person).json()
    assert client.get(f"{A}/{person}", headers=auth_headers).status_code == 403
    assert client.get(f"{A}/file/{doc['id']}", headers=auth_headers).status_code == 403
    assert _upload(client, auth_headers, person).status_code == 403
    assert client.delete(f"{A}/file/{doc['id']}", headers=auth_headers).status_code == 403


def test_rejects_bad_uploads(client, seed_tenant, admin_headers):
    person = f"staff/{_me(client, admin_headers)}"
    assert _upload(client, admin_headers, person, b"not a pdf").status_code == 422
    assert _upload(client, admin_headers, person, b"").status_code == 422
    assert _upload(client, admin_headers, person, doc_type="salary").status_code == 422
    assert _upload(client, admin_headers, person, PDF + b"x" * (10 * 1024 * 1024)).status_code == 422
    assert _upload(client, admin_headers, "robot/1").status_code == 404
    assert _upload(client, admin_headers, "staff/999999").status_code == 404


def test_other_tenant_is_invisible(client, db, seed_tenant, admin_headers):
    other = Tenant(name="Other Agency", email="other@test.example", phone="+91-40-0000", address="2 Road", city="Hyderabad", state="TS")
    db.add(other)
    db.flush()
    stranger = User(
        tenant_id=other.id, email="s@other.example", first_name="S", last_name="T",
        password_hash=hash_password("testpass123"), role="CARE_MANAGER",
    )
    db.add(stranger)
    db.commit()
    assert client.get(f"{A}/staff/{stranger.id}", headers=admin_headers).status_code == 404
    assert _upload(client, admin_headers, f"staff/{stranger.id}").status_code == 404
