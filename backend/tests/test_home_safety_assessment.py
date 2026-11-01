"""Home safety assessment server sync."""

from pathlib import Path

from app.core.storage import get_storage
from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.document_types import HOME_SAFETY_AI_CONCEPT, HOME_SAFETY_PHOTO
from app.models.document import Document
from app.models.home_safety_ai_job import HomeSafetyAIJob


def _sample_payload(assessment_id: str = "hs-test-001") -> dict:
    return {
        "id": assessment_id,
        "createdAt": "2026-06-25T12:00:00+00:00",
        "updatedAt": "2026-06-25T12:00:00+00:00",
        "completedAt": None,
        "status": "draft",
        "clientFirstName": "Jane",
        "clientLastName": "Doe",
        "clientAddress": "123 Main St",
        "clientPhone": "",
        "clientEmail": "",
        "familyContactName": "",
        "familyContactPhone": "",
        "painPoints": "",
        "assessorName": "",
        "notes": "",
        "residentProfile": {"medicalConditions": [], "smartHomeAssessment": True},
        "ratings": {},
        "itemNotes": {},
        "prospectId": None,
        "prospectSyncedAt": None,
        "elderId": None,
        "photos": [{"id": "p1", "caption": "Bath", "roomType": "bathroom", "documentId": None, "localPreview": None, "uploadedAt": None}],
        "purchaseOrder": None,
    }


def test_upsert_and_list_assessment(db, seed_tenant):
    admin = seed_tenant["admin"]
    payload = _sample_payload()

    created = HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)
    assert created["assessment_id"] == "hs-test-001"
    assert created["status"] == "draft"
    assert created["payload"]["clientFirstName"] == "Jane"

    listed = HomeSafetyAssessmentService.list_assessments(db, admin)
    assert any(row["assessment_id"] == "hs-test-001" for row in listed)
    assert "payload" not in listed[0]
    full = HomeSafetyAssessmentService.list_assessments(db, admin, full=True)
    row = next(r for r in full if r["assessment_id"] == "hs-test-001")
    assert row["payload"]["clientFirstName"] == "Jane"

    fetched = HomeSafetyAssessmentService.get_assessment(db, admin, "hs-test-001")
    assert fetched["payload"]["photos"][0]["roomType"] == "bathroom"

    payload["status"] = "completed"
    payload["completedAt"] = "2026-06-25T13:00:00+00:00"
    payload["clientFirstName"] = "Janet"
    updated = HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)
    assert updated["status"] == "completed"
    assert updated["payload"]["clientFirstName"] == "Janet"

    HomeSafetyAssessmentService.delete_assessment(db, admin, "hs-test-001")
    listed_after = HomeSafetyAssessmentService.list_assessments(db, admin)
    assert not any(row["assessment_id"] == "hs-test-001" for row in listed_after)


def test_delete_assessment_removes_photos_and_storage(db, seed_tenant, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")

    admin = seed_tenant["admin"]
    elder = seed_tenant["elder"]
    assessment_id = "hs-photo-del-001"
    other_assessment_id = "hs-photo-keep-001"

    storage = get_storage()
    photo_key, photo_url = storage.save(
        elder.tenant_id,
        "elder",
        elder.id,
        "bath.jpg",
        b"photo-bytes",
        "image/jpeg",
    )
    concept_key, concept_url = storage.save(
        elder.tenant_id,
        "elder",
        elder.id,
        "concept.jpg",
        b"concept-bytes",
        "image/jpeg",
    )
    keep_key, keep_url = storage.save(
        elder.tenant_id,
        "elder",
        elder.id,
        "keep.jpg",
        b"keep-bytes",
        "image/jpeg",
    )

    photo = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_PHOTO,
        file_name="bath.jpg",
        storage_key=photo_key,
        storage_url=photo_url,
        mime_type="image/jpeg",
        ocr_extracted_json={"assessment_id": assessment_id, "room_type": "bathroom"},
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
    )
    concept = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_AI_CONCEPT,
        file_name="concept.jpg",
        storage_key=concept_key,
        storage_url=concept_url,
        mime_type="image/jpeg",
        ocr_extracted_json={"assessment_id": assessment_id},
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
    )
    keep = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_PHOTO,
        file_name="keep.jpg",
        storage_key=keep_key,
        storage_url=keep_url,
        mime_type="image/jpeg",
        ocr_extracted_json={"assessment_id": other_assessment_id},
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
    )
    db.add_all([photo, concept, keep])
    db.flush()

    job = HomeSafetyAIJob(
        public_id="job-photo-del-1",
        tenant_id=elder.tenant_id,
        assessment_id=assessment_id,
        room_type="bathroom",
        package_level="recommended",
        source_document_id=photo.id,
        status="succeeded",
        generated_document_id=concept.id,
    )
    db.add(job)
    db.flush()

    payload = _sample_payload(assessment_id)
    payload["elderId"] = elder.id
    payload["photos"] = [
        {
            "id": "p1",
            "caption": "Bath",
            "roomType": "bathroom",
            "documentId": photo.id,
            "localPreview": None,
            "uploadedAt": None,
        }
    ]
    HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)

    assert Path(tmp_path, photo_key).exists()
    assert Path(tmp_path, concept_key).exists()
    assert Path(tmp_path, keep_key).exists()

    HomeSafetyAssessmentService.delete_assessment(db, admin, assessment_id)

    assert db.query(Document).filter(Document.id == photo.id).first() is None
    assert db.query(Document).filter(Document.id == concept.id).first() is None
    assert db.query(Document).filter(Document.id == keep.id).first() is not None
    assert (
        db.query(HomeSafetyAIJob)
        .filter(HomeSafetyAIJob.assessment_id == assessment_id)
        .first()
        is None
    )
    assert not Path(tmp_path, photo_key).exists()
    assert not Path(tmp_path, concept_key).exists()
    assert Path(tmp_path, keep_key).exists()
