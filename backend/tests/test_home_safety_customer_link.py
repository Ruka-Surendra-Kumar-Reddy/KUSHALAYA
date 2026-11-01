"""Prospect/customer linkage for SafeHome assessments and artifacts."""

from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.models.elder_prospect import ElderProspect


def _sample_payload(assessment_id: str = "hs-cust-001", prospect_id: int | None = None) -> dict:
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
        "prospectId": prospect_id,
        "prospectSyncedAt": None,
        "elderId": None,
        "photos": [],
        "purchaseOrder": None,
    }


def test_upsert_stores_prospect_columns(db, seed_tenant):
    admin = seed_tenant["admin"]
    tenant_id = seed_tenant["tenant"].id

    prospect = ElderProspect(
        tenant_id=tenant_id,
        first_name="Jane",
        last_name="Doe",
        stage="NEW",
        status="OPEN",
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)

    payload = _sample_payload(prospect_id=prospect.id)
    created = HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)

    assert created["prospect_id"] == prospect.id
    assert created["payload"]["prospectId"] == prospect.id


def test_resolve_customer_requires_prospect_or_elder(db, seed_tenant):
    admin = seed_tenant["admin"]

    from app.core.rbac import resolve_tenant_id

    tid = resolve_tenant_id(admin)
    assert tid is not None

    try:
        HomeSafetyCustomerLink.resolve_customer(
            db,
            tid,
            assessment_id="missing-assessment",
            require=True,
        )
        assert False, "expected bad request"
    except Exception as exc:
        assert "prospect" in str(exc).lower() or "client" in str(exc).lower()
