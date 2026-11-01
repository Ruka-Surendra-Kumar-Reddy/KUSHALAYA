"""Publish completed assessments into elder safe_home for family portal."""

from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.family_publish import publish_assessment_to_family


def _completed_payload(assessment_id: str, elder_id: int) -> dict:
    return {
        "id": assessment_id,
        "createdAt": "2026-07-18T12:00:00+00:00",
        "updatedAt": "2026-07-18T13:00:00+00:00",
        "completedAt": "2026-07-18T13:00:00+00:00",
        "status": "completed",
        "clientFirstName": "Lakshmi",
        "clientLastName": "Rao",
        "clientAddress": "Hyderabad",
        "clientPhone": "",
        "clientEmail": "",
        "familyContactName": "",
        "familyContactPhone": "",
        "painPoints": "",
        "assessorName": "Anita",
        "notes": "",
        "residentProfile": {},
        "ratings": {},
        "itemNotes": {},
        "prospectId": None,
        "prospectSyncedAt": None,
        "elderId": elder_id,
        "photos": [],
        "purchaseOrder": None,
        "independenceScore": 72,
        "familyScoreSummary": "LiveWell360 Independence Score™ 72/100.",
        "familyImprovementPlan": {
            "current_score": 72,
            "projected_score": 88,
            "finding_count": 2,
            "items": [
                {
                    "id": "SH-BATH-001",
                    "title": "Install bathroom grab bars",
                    "priority": "high",
                    "why": "Fall risk near toilet",
                    "actions": ["Grab bar at toilet", "Grab bar in shower"],
                    "score_gain": 8,
                    "status": "open",
                    "domain": "Bathroom",
                },
                {
                    "id": "SH-LIGHT-001",
                    "title": "Add night lighting",
                    "priority": "medium",
                    "why": "Dark hallway",
                    "actions": ["Motion night light"],
                    "score_gain": 4,
                    "status": "open",
                    "domain": "Lighting",
                },
            ],
        },
    }


def test_publish_assessment_to_family_writes_score_and_plan(db, seed_tenant):
    elder = seed_tenant["elder"]
    assert publish_assessment_to_family(
        db,
        elder_id=elder.id,
        tenant_id=elder.tenant_id,
        payload=_completed_payload("hs-fam-pub-1", elder.id),
    )
    db.commit()
    db.refresh(elder)

    sh = elder.custom_attributes["safe_home"]
    assert sh["safety_score"]["total"] == 72
    assert sh["safety_score"]["grade"] == "Moderate Risk"
    assert sh["safety_score"]["is_demo"] is False
    assert sh["improvement_plan"]["projected_score"] == 88
    assert len(sh["improvement_plan"]["items"]) == 2
    assert sh["improvement_plan"]["items"][0]["id"] == "SH-BATH-001"


def test_upsert_completed_publishes_to_linked_elder(db, seed_tenant):
    admin = seed_tenant["admin"]
    elder = seed_tenant["elder"]
    payload = _completed_payload("hs-fam-upsert-1", elder.id)

    HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)
    db.refresh(elder)

    sh = (elder.custom_attributes or {}).get("safe_home") or {}
    assert sh.get("safety_score", {}).get("total") == 72


def test_family_dashboard_uses_published_plan(db, client, seed_tenant):
    from app.core.security import hash_password
    from app.models.user import User

    elder = seed_tenant["elder"]
    publish_assessment_to_family(
        db,
        elder_id=elder.id,
        tenant_id=elder.tenant_id,
        payload=_completed_payload("hs-fam-dash-1", elder.id),
    )
    db.commit()

    user = User(
        email="family.plan@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Family",
        last_name="Member",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    dash = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["has_published_score"] is True
    assert body["safety"]["total"] == 72
    assert body["safety"]["grade"] == "Moderate Risk"
    assert body["plan_item_count"] == 2
    assert len(body["top_priorities"]) == 2
    assert body["top_priorities"][0]["title"] == "Install bathroom grab bars"

    plan = client.get("/api/v1/home-safety/family/improvement-plan", headers=headers)
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["has_plan"] is True
    assert plan_body["projected_score"] == 88
    assert len(plan_body["items"]) == 2


def test_family_dashboard_without_published_score(db, client, seed_tenant):
    from app.core.security import hash_password
    from app.models.user import User

    elder = seed_tenant["elder"]
    # Clear any prior safe_home from other tests in same DB session patterns
    attrs = dict(elder.custom_attributes or {})
    attrs["safe_home"] = {"visits": []}
    elder.custom_attributes = attrs
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(elder, "custom_attributes")
    db.commit()

    user = User(
        email="family.empty@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Empty",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    dash = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["has_published_score"] is False
    assert body["safety"]["total"] == 0
    assert body["top_priorities"] == []
    # Must not invent a demo 78 score
    assert body["safety"]["grade"] == "—"


def test_score_history_and_plan_status_flow(db, client, seed_tenant):
    from app.core.security import hash_password
    from app.models.user import User

    admin = seed_tenant["admin"]
    elder = seed_tenant["elder"]

    first = _completed_payload("hs-hist-1", elder.id)
    first["independenceScore"] = 65
    publish_assessment_to_family(
        db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=first
    )
    second = _completed_payload("hs-hist-2", elder.id)
    second["independenceScore"] = 72
    publish_assessment_to_family(
        db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=second
    )
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    patch = client.patch(
        f"/api/v1/home-safety/care/elders/{elder.id}/plan-items/SH-BATH-001",
        headers=staff_headers,
        json={"status": "done"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["status"] == "done"

    # Republish should preserve done status
    third = _completed_payload("hs-hist-3", elder.id)
    third["independenceScore"] = 75
    publish_assessment_to_family(
        db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=third
    )
    db.commit()
    db.refresh(elder)
    items = elder.custom_attributes["safe_home"]["improvement_plan"]["items"]
    bath = next(i for i in items if i["id"] == "SH-BATH-001")
    assert bath["status"] == "done"

    user = User(
        email="family.hist@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Hist",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()
    fam_login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    fam_headers = {"Authorization": f"Bearer {fam_login.json()['access_token']}"}

    dash = client.get("/api/v1/home-safety/family/dashboard", headers=fam_headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["plan_item_count"] == 1
    assert all(p["id"] != "SH-BATH-001" for p in body["top_priorities"])
    # Assessment Independence Score remains on safety card; trend graph is visit stability.
    assert "score_history" not in body or body.get("score_history") in (None, [])
    assert isinstance(body.get("stability_score_history"), list)


def test_family_approved_visualizations(db, client, seed_tenant, tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from app.core.config import settings
    from app.core.security import hash_password
    from app.core.storage import get_storage
    from app.livewell.document_types import HOME_SAFETY_AI_CONCEPT, HOME_SAFETY_PHOTO
    from app.models.document import Document
    from app.models.home_safety_ai_job import HomeSafetyAIJob
    from app.models.user import User

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")

    elder = seed_tenant["elder"]
    admin = seed_tenant["admin"]
    storage = get_storage()
    before_key, before_url = storage.save(
        elder.tenant_id, "elder", elder.id, "before.png", b"before", "image/png"
    )
    after_key, after_url = storage.save(
        elder.tenant_id, "elder", elder.id, "after.png", b"after", "image/png"
    )

    before = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_PHOTO,
        document_name="Before",
        file_name="before.png",
        mime_type="image/png",
        storage_key=before_key,
        storage_url=before_url,
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
    )
    after = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_AI_CONCEPT,
        document_name="After",
        file_name="after.png",
        mime_type="image/png",
        storage_key=after_key,
        storage_url=after_url,
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
        ocr_extracted_json={"is_stub": False, "role": "ai_concept"},
    )
    stub = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=HOME_SAFETY_AI_CONCEPT,
        document_name="Stub",
        file_name="stub.png",
        mime_type="image/png",
        storage_key=after_key,
        storage_url=after_url,
        verification_status="APPROVED",
        uploaded_by_user_id=admin.id,
        ocr_extracted_json={"is_stub": True},
    )
    db.add_all([before, after, stub])
    db.flush()

    job = HomeSafetyAIJob(
        public_id="fam-viz-ok",
        tenant_id=elder.tenant_id,
        assessment_id="hs-viz-1",
        elder_id=elder.id,
        room_type="bathroom",
        package_level="recommended",
        source_document_id=before.id,
        generated_document_id=after.id,
        status="completed",
        review_status="approved",
        provider="manual_upload",
        reviewed_at=datetime.now(timezone.utc),
        review_notes="Internal staff note for the audit trail",
    )
    stub_job = HomeSafetyAIJob(
        public_id="fam-viz-stub",
        tenant_id=elder.tenant_id,
        assessment_id="hs-viz-1",
        elder_id=elder.id,
        room_type="bedroom",
        package_level="essential",
        source_document_id=before.id,
        generated_document_id=stub.id,
        status="completed",
        review_status="approved",
        provider="local_stub",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add_all([job, stub_job])
    db.commit()

    user = User(
        email="family.viz@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Viz",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    res = client.get("/api/v1/home-safety/family/visualizations", headers=headers)
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["id"] == "fam-viz-ok"
    assert "bathroom" in rows[0]["label"].lower()
    assert "review_notes" not in rows[0]

    after_img = client.get(
        f"/api/v1/home-safety/family/photos/{after.id}/image", headers=headers
    )
    assert after_img.status_code == 200
    assert after_img.content == b"after"

    stub_img = client.get(
        f"/api/v1/home-safety/family/photos/{stub.id}/image", headers=headers
    )
    assert stub_img.status_code == 404


def test_complete_assessment_auto_converts_prospect_and_publishes(db, seed_tenant):
    from app.models.elder_prospect import ElderProspect

    admin = seed_tenant["admin"]
    tenant_id = seed_tenant["tenant"].id
    prospect = ElderProspect(
        tenant_id=tenant_id,
        first_name="Auto",
        last_name="Convert",
        stage="ASSESSMENT_DONE",
        status="OPEN",
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)

    payload = _completed_payload("hs-auto-convert-1", elder_id=0)
    payload["elderId"] = None
    payload["prospectId"] = prospect.id
    payload["independenceScore"] = 81
    payload["familyDomainScores"] = [
        {"id": "home_safety", "title": "Home Safety", "score": 70, "max_points": 20, "earned_points": 14},
        {"id": "mobility", "title": "Mobility", "score": 90, "max_points": 10, "earned_points": 9},
    ]
    payload["familyCarePathway"] = {
        "membership_id": "mbr_independent",
        "membership_label": "Independent Living",
        "ecm_recommended": False,
        "ecm_note": "ECM not required",
    }
    payload["familyShareBrief"] = "Share me"

    result = HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)
    assert result["elder_id"] is not None
    assert result["prospect_id"] is None

    from app.models.elder_prospect import ElderProspect as EP

    assert db.query(EP).filter(EP.id == prospect.id).first() is None

    from app.models.elder import Elder

    elder = db.query(Elder).filter(Elder.id == result["elder_id"]).first()
    sh = (elder.custom_attributes or {}).get("safe_home") or {}
    assert sh.get("safety_score", {}).get("total") == 81
    assert len(sh.get("domain_scores") or []) == 2
    assert sh.get("care_pathway", {}).get("membership_id") == "mbr_independent"
    assert sh.get("share_brief") == "Share me"


def test_complete_assessment_links_existing_elder_not_duplicate(db, seed_tenant):
    from app.models.elder import Elder
    from app.models.elder_prospect import ElderProspect

    admin = seed_tenant["admin"]
    tenant_id = seed_tenant["tenant"].id
    existing = Elder(
        tenant_id=tenant_id,
        first_name="Lakshmi",
        last_name="Reddy",
        status="ACTIVE",
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    prospect = ElderProspect(
        tenant_id=tenant_id,
        first_name="Lakshmi",
        last_name="Reddy",
        stage="ASSESSMENT_DONE",
        status="OPEN",
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)

    payload = _completed_payload("hs-link-existing-1", elder_id=existing.id)
    payload["prospectId"] = prospect.id
    payload["elderId"] = existing.id
    payload["independenceScore"] = 88

    result = HomeSafetyAssessmentService.upsert_assessment(db, admin, payload)
    assert result["elder_id"] == existing.id
    db.refresh(existing)
    sh = (existing.custom_attributes or {}).get("safe_home") or {}
    assert sh.get("safety_score", {}).get("total") == 88
    # Must not have created a second Lakshmi
    count = (
        db.query(Elder)
        .filter(
            Elder.tenant_id == tenant_id,
            Elder.first_name == "Lakshmi",
            Elder.last_name == "Reddy",
        )
        .count()
    )
    assert count == 1
