"""Wet-signed customer document uploads."""

from app.livewell.document_types import LW_HOME_ASSESSMENT_CONSENT
from app.models.document import Document
from app.models.elder_prospect import ElderProspect


def test_upload_and_list_signed_doc(client, auth_headers, db, seed_tenant):
    tenant = seed_tenant["tenant"]
    prospect = ElderProspect(
        tenant_id=tenant.id,
        first_name="Jane",
        last_name="Doe",
        phone="+91-9000000001",
        address="12 Sample Road",
        status="OPEN",
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)

    assessment_id = "hs-signed-doc-001"
    files = {"file": ("consent.jpg", b"fake-signed-bytes", "image/jpeg")}
    data = {
        "form_code": LW_HOME_ASSESSMENT_CONSENT,
        "assessment_id": assessment_id,
        "prospect_id": str(prospect.id),
        "notes": "page 1",
    }
    res = client.post(
        "/api/v1/home-safety/signed-docs",
        headers=auth_headers,
        files=files,
        data=data,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["document_type"] == LW_HOME_ASSESSMENT_CONSENT
    doc_id = body["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    assert doc is not None
    assert doc.ocr_extracted_json["assessment_id"] == assessment_id
    assert doc.ocr_extracted_json["signature_method"] == "paper_scan"

    listed = client.get(
        f"/api/v1/home-safety/signed-docs/by-assessment/{assessment_id}",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["form_code"] == LW_HOME_ASSESSMENT_CONSENT

    file_res = client.get(
        f"/api/v1/home-safety/signed-docs/{doc_id}/file",
        headers=auth_headers,
    )
    assert file_res.status_code == 200
    assert file_res.content == b"fake-signed-bytes"
