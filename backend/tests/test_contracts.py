"""Contracts signed in the app: templates, company countersign, signing link, PDF, access."""

import base64
import io
import struct
import zipfile
import zlib
from datetime import timedelta

from app.core.security import hash_password
from app.livewell import contracts as svc
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.contract import Contract
from app.models.document import Document
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User


def _png(w: int = 40, h: int = 12) -> str:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _template(client, headers, kind="client"):
    rows = client.get(f"/api/v1/contracts/templates?kind={kind}", headers=headers).json()
    rows = [r for r in rows if r["is_placeholder"]]  # the short starter, not the full vendor agreement
    assert rows
    return rows[0]


def _setup_signature(client, admin_headers):
    res = client.put("/api/v1/contracts/signatory", headers=admin_headers,
                     json={"name": "Krishna Posa", "designation": "Director", "signature_png": _png()})
    assert res.status_code == 200, res.text
    return res.json()


def _new(client, headers, elder_id, action="draft", **over):
    t = _template(client, headers)
    body = {"template_id": t["id"], "elder_id": elder_id, "signer_name": "Ravi Kumar",
            "signer_email": "ravi@example.com", "signer_mobile": "+91 98765 43210", "signer_relation": "Son",
            "action": action, **over}
    return client.post("/api/v1/contracts", headers=headers, json=body)


def _signed_ready(client, admin_headers, seed_tenant):
    _setup_signature(client, admin_headers)
    res = _new(client, admin_headers, seed_tenant["elder"].id, action="sign_and_send")
    assert res.status_code == 201, res.text
    c = res.json()
    assert c["status"] == "sent" and c["sign_path"].startswith("/sign/")
    return c, c["sign_path"].split("/sign/")[1]


def test_render_placeholders():
    out = svc.render("Hi {client_name}, plan {plan_name}. {unknown} {date}", {"client_name": "Lakshmi", "date": "1 Nov"})
    assert out == f"Hi Lakshmi, plan {svc.BLANK}. {{unknown}} 1 Nov"


def test_default_templates_and_versioning(client, seed_tenant, admin_headers, auth_headers):
    t = _template(client, admin_headers, "vendor")
    # Starter text: no "[PLACEHOLDER" note any more, but still flagged as the example.
    assert "[PLACEHOLDER" not in t["body"] and t["is_placeholder"] and t["version"] == 1
    res = client.put(f"/api/v1/contracts/templates/{t['id']}", headers=admin_headers,
                     json={"title": "Vendor agreement", "body": "Our own wording for {vendor_company}, dated {date}."})
    assert res.status_code == 200, res.text
    v2 = res.json()
    assert v2["version"] == 2 and v2["id"] != t["id"] and not v2["is_placeholder"]
    versions = client.get(f"/api/v1/contracts/templates/{v2['id']}/versions", headers=admin_headers).json()
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[1]["body"].startswith("# Parties")  # old version kept unchanged
    # a care manager can't change templates
    assert client.put(f"/api/v1/contracts/templates/{v2['id']}", headers=auth_headers,
                      json={"title": "x", "body": "y" * 30}).status_code == 403


def test_docx_import():
    buf = io.BytesIO()
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    xml = (f'<w:document {ns}><w:body>'
           '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Terms</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Pay on time, </w:t></w:r><w:r><w:t>{client_name}.</w:t></w:r></w:p>'
           '</w:body></w:document>')
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    assert svc.docx_to_text(buf.getvalue()) == "# Terms\n\nPay on time, {client_name}."


def test_preview_fills_fields(client, seed_tenant, auth_headers):
    t = _template(client, auth_headers)
    res = client.post("/api/v1/contracts/preview", headers=auth_headers,
                      json={"template_id": t["id"], "elder_id": seed_tenant["elder"].id, "fields": {"plan_name": "Care Plus"}})
    assert res.status_code == 200, res.text
    p = res.json()
    assert "Elder One" in p["body"] and "Care Plus" in p["body"]
    assert "{client_name}" not in p["body"]


def test_countersign_required_and_manager_cannot_company_sign(client, seed_tenant, admin_headers, auth_headers):
    elder_id = seed_tenant["elder"].id
    # care manager: Sign & send is refused
    res = _new(client, auth_headers, elder_id, action="sign_and_send")
    assert res.status_code == 403
    # care manager prepares it -> waits for KushAlaya's signature, no link yet
    c = _new(client, auth_headers, elder_id, action="submit").json()
    assert c["status"] == "awaiting_company" and c["sign_path"] is None and not c["locked"]
    assert client.post(f"/api/v1/contracts/{c['id']}/sign-and-send", headers=auth_headers).status_code == 403
    assert client.put("/api/v1/contracts/signatory", headers=auth_headers,
                      json={"designation": "Manager", "signature_text": "M"}).status_code == 403
    # admin without a saved signature can't sign yet
    assert client.post(f"/api/v1/contracts/{c['id']}/sign-and-send", headers=admin_headers).status_code == 409
    _setup_signature(client, admin_headers)
    res = client.post(f"/api/v1/contracts/{c['id']}/sign-and-send", headers=admin_headers)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "sent" and out["locked"] and out["company_signer_designation"] == "Director"
    # text is locked once the company signed
    assert client.put(f"/api/v1/contracts/{c['id']}", headers=admin_headers, json={"body": "changed " * 10}).status_code == 409


def test_saved_signature_is_reused(client, seed_tenant, admin_headers, db):
    _setup_signature(client, admin_headers)
    a = _new(client, admin_headers, seed_tenant["elder"].id, action="sign_and_send").json()
    b = _new(client, admin_headers, seed_tenant["elder"].id, action="sign_and_send").json()
    ca, cb = db.get(Contract, a["id"]), db.get(Contract, b["id"])
    assert ca.company_signature_png == cb.company_signature_png == _png()
    assert ca.company_signer_name == "Krishna Posa" and ca.company_text_sha256 == svc.text_sha256(ca.title, ca.body)
    me = client.get("/api/v1/contracts/meta", headers=admin_headers).json()
    assert me["can_sign"] and me["signatory"]["designation"] == "Director"


def test_token_valid_expired_tampered(client, seed_tenant, admin_headers, db):
    c, token = _signed_ready(client, admin_headers, seed_tenant)
    view = client.get(f"/api/v1/home-safety/sign/{token}")
    assert view.status_code == 200
    v = view.json()
    assert v["status"] == "viewed" and v["company"]["name"] == "Krishna Posa" and v["company"]["signature_png"]
    assert "company_ip" not in str(v)
    cid, nonce, sig = token.split("-")
    assert client.get(f"/api/v1/home-safety/sign/{cid}-{nonce}-{'0' * 32}").status_code == 404
    assert client.get(f"/api/v1/home-safety/sign/{int(cid) + 1}-{nonce}-{sig}").status_code == 404
    row = db.get(Contract, c["id"])
    row.expires_at = svc._now() - timedelta(minutes=1)
    db.commit()
    assert client.get(f"/api/v1/home-safety/sign/{token}").status_code == 410
    assert client.get(f"/api/v1/contracts/{c['id']}", headers=admin_headers).json()["status"] == "expired"
    # resend: new link, old one dead
    new = client.post(f"/api/v1/contracts/{c['id']}/resend", headers=admin_headers).json()
    new_token = new["sign_path"].split("/sign/")[1]
    assert new_token != token
    assert client.get(f"/api/v1/home-safety/sign/{token}").status_code == 404
    assert client.get(f"/api/v1/home-safety/sign/{new_token}").status_code == 200


def test_sign_once_hash_immutability_and_pdf(client, seed_tenant, admin_headers, db):
    c, token = _signed_ready(client, admin_headers, seed_tenant)
    url = f"/api/v1/home-safety/sign/{token}"
    assert client.post(url, json={"name": "Ravi Kumar", "signature_png": _png(), "agree": False}).status_code == 422
    assert client.post(url, json={"name": "Ravi Kumar", "agree": True}).status_code == 422  # no signature
    res = client.post(url, json={"name": "Ravi Kumar", "signature_text": "Ravi Kumar", "agree": True},
                      headers={"User-Agent": "pytest-phone"})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "signed" and out["signer"]["name"] == "Ravi Kumar" and out["company"]["designation"] == "Director"
    again = client.post(url, json={"name": "Someone", "signature_text": "X Y", "agree": True})
    assert again.status_code == 409
    row = db.get(Contract, c["id"])
    db.refresh(row)
    assert row.signed_text_sha256 == row.company_text_sha256 == svc.text_sha256(row.title, row.body)
    assert row.signer_user_agent == "pytest-phone" and row.signed_name == "Ravi Kumar"
    # signed: no edit, no cancel
    assert client.put(f"/api/v1/contracts/{c['id']}", headers=admin_headers, json={"title": "New"}).status_code == 409
    assert client.post(f"/api/v1/contracts/{c['id']}/cancel", headers=admin_headers).status_code == 409
    # PDF stored with both signature blocks + audit page
    assert row.document_id and db.get(Document, row.document_id).document_type == "SIGNED_CONTRACT"
    pdf = client.get(f"/api/v1/contracts/{c['id']}/pdf", headers=admin_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{url}/pdf").content.startswith(b"%PDF")
    text = svc.render_pdf(db, row)
    assert text.startswith(b"%PDF")


def test_pdf_has_both_blocks(client, seed_tenant, admin_headers, db):
    c, token = _signed_ready(client, admin_headers, seed_tenant)
    client.post(f"/api/v1/home-safety/sign/{token}", json={"name": "Ravi Kumar", "signature_png": _png(), "agree": True})
    row = db.get(Contract, c["id"])
    db.refresh(row)
    from reportlab.platypus import SimpleDocTemplate

    seen: list[str] = []
    orig = SimpleDocTemplate.build

    def spy(self, story, *a, **k):
        def walk(x):
            if hasattr(x, "getPlainText"):
                seen.append(x.getPlainText())
            for row_ in getattr(x, "_cellvalues", []) or []:
                for cell in row_:
                    walk(cell)
        for f in story:
            walk(f)
        return orig(self, story, *a, **k)

    SimpleDocTemplate.build = spy
    try:
        svc.render_pdf(db, row)
    finally:
        SimpleDocTemplate.build = orig
    joined = "\n".join(seen)
    assert "For Test Care Agency" in joined and "Client" in joined
    assert "Krishna Posa" in joined and "Director" in joined and "Ravi Kumar" in joined
    assert "Audit trail" in joined and row.signed_text_sha256 in joined and "IST" in joined and "UTC" in joined


def test_cancel_kills_link(client, seed_tenant, admin_headers):
    c, token = _signed_ready(client, admin_headers, seed_tenant)
    assert client.post(f"/api/v1/contracts/{c['id']}/cancel", headers=admin_headers).json()["status"] == "cancelled"
    assert client.get(f"/api/v1/home-safety/sign/{token}").status_code == 404


def test_access_control(client, seed_tenant, admin_headers, db):
    c, token = _signed_ready(client, admin_headers, seed_tenant)
    client.post(f"/api/v1/home-safety/sign/{token}", json={"name": "Ravi", "signature_text": "Ravi", "agree": True})
    elder = seed_tenant["elder"]
    # family of this client sees it; family of another client does not
    fam = User(email="fam.ct@test.example", password_hash=hash_password("testpass123"), first_name="Fam",
               last_name="Ct", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    other_elder = Elder(tenant_id=elder.tenant_id, first_name="Other", last_name="Client", status="ACTIVE")
    db.add_all([fam, other_elder])
    db.flush()
    other = User(email="fam.other@test.example", password_hash=hash_password("testpass123"), first_name="O",
                 last_name="F", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=other_elder.id)
    db.add(other)
    db.flush()
    ensure_family_elder_link(db, fam, elder)
    ensure_family_elder_link(db, other, other_elder)
    db.commit()
    fh, oh = _login(client, "fam.ct@test.example"), _login(client, "fam.other@test.example")
    assert [r["id"] for r in client.get("/api/v1/home-safety/family/contracts", headers=fh).json()] == [c["id"]]
    assert client.get(f"/api/v1/home-safety/family/contracts/{c['id']}/pdf", headers=fh).status_code == 200
    assert client.get("/api/v1/home-safety/family/contracts", headers=oh).json() == []
    assert client.get(f"/api/v1/home-safety/family/contracts/{c['id']}/pdf", headers=oh).status_code == 404
    # family can't use staff endpoints
    assert client.get("/api/v1/contracts", headers=fh).status_code == 403
    # another tenant's admin can't see it
    t2 = Tenant(name="Other Agency", email="other.ct@test.example", phone="1", address="x", city="c", state="s", theme="classic", portal_title="O")
    db.add(t2)
    db.flush()
    db.add(User(email="admin2.ct@test.example", password_hash=hash_password("testpass123"), first_name="A",
                last_name="Two", role="TENANT_ADMIN", tenant_id=t2.id))
    db.commit()
    h2 = _login(client, "admin2.ct@test.example")
    assert client.get(f"/api/v1/contracts/{c['id']}", headers=h2).status_code in (403, 404)
    assert client.get(f"/api/v1/contracts/{c['id']}/pdf", headers=h2).status_code in (403, 404)
    assert client.get("/api/v1/contracts", headers=h2).json() == []


def test_vendor_agreement(client, seed_tenant, admin_headers):
    _setup_signature(client, admin_headers)
    v = client.post("/api/v1/vendors", headers=admin_headers,
                    json={"company_name": "Sri Sai Plumbing", "phone1": "9876543210", "owner_name": "Ramesh",
                          "services": ["plumbing"], "fee_paise": 150000, "fee_basis": "per_visit"}).json()
    t = _template(client, admin_headers, "vendor")
    res = client.post("/api/v1/contracts", headers=admin_headers,
                      json={"template_id": t["id"], "vendor_id": v["id"], "signer_name": "Ramesh",
                            "signer_mobile": "9876543210", "action": "sign_and_send"})
    assert res.status_code == 201, res.text
    c = res.json()
    full = client.get(f"/api/v1/contracts/{c['id']}", headers=admin_headers).json()
    assert "Sri Sai Plumbing" in full["body"] and "₹1,500 per visit" in full["body"]
    assert [r["id"] for r in client.get(f"/api/v1/contracts?vendor_id={v['id']}", headers=admin_headers).json()] == [c["id"]]


def test_placeholder_note_is_stripped_and_cannot_be_sent(db, client, seed_tenant, admin_headers):
    from app.models.contract import ContractTemplate

    t = _template(client, admin_headers, "vendor")
    row = db.get(ContractTemplate, t["id"])
    row.body = "[PLACEHOLDER — Replace with KushAlaya's own wording before sending to a real vendor.]" + chr(10) * 2 + "# Parties" + chr(10) + "Text."
    db.commit()
    rows = client.get("/api/v1/contracts/templates?kind=vendor", headers=admin_headers).json()
    assert next(r for r in rows if r["id"] == t["id"])["body"].startswith("# Parties")
    assert svc.is_starter("[PLACEHOLDER x] body") and not svc.is_starter("Our own words")


def test_full_vendor_agreement_needs_its_blanks_settled(client, seed_tenant, admin_headers):
    rows = client.get("/api/v1/contracts/templates?kind=vendor", headers=admin_headers).json()
    t = next(r for r in rows if r["title"] == svc.VENDOR_AGREEMENT_TITLE)
    assert not t["is_placeholder"] and "{vendor_company}" in t["body"] and "Annexure E" in t["body"]
    v = client.post("/api/v1/vendors", headers=admin_headers,
                    json={"company_name": "Sri Sai Plumbing", "phone1": "9876543210"}).json()
    send = {"template_id": t["id"], "vendor_id": v["id"], "signer_name": "Ramesh", "signer_mobile": "9876543210"}
    res = client.post("/api/v1/contracts", headers=admin_headers, json=send)
    assert res.status_code == 422 and "Agreement templates" in res.text

    settled = svc._UNFILLED.sub("agreed", t["body"])
    assert client.put(f"/api/v1/contracts/templates/{t['id']}", headers=admin_headers,
                      json={"title": t["title"], "body": settled}).status_code == 200
    rows = client.get("/api/v1/contracts/templates?kind=vendor", headers=admin_headers).json()
    send["template_id"] = next(r for r in rows if r["title"] == svc.VENDOR_AGREEMENT_TITLE)["id"]
    assert client.post("/api/v1/contracts", headers=admin_headers, json=send).status_code == 201
    assert len([r for r in rows if r["title"] == svc.VENDOR_AGREEMENT_TITLE]) == 1
