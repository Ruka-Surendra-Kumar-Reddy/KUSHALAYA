"""Family care hub P0 smoke tests."""

from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.visit_service import HomeSafetyVisitService
from app.models.elder import Elder
from app.models.user import User
from app.core.rbac import ELDER_PORTAL
from app.core.security import hash_password


def _family_user(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="Lakshmi",
        last_name="P0",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    user = User(
        email=f"family.p0.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Family",
        last_name="P0",
        role=ELDER_PORTAL,
        tenant_id=tenant.id,
        elder_id=elder.id,
        portal_relationship="self",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, elder


def test_family_p0_message_sos_digest_circle(db, seed_tenant):
    user, elder = _family_user(db, seed_tenant)

    msg = FamilyCareHubService.send_message(db, user, "Please check the bathroom grab bar.")
    assert msg["body"].startswith("Please check")
    alerts = FamilyCareHubService.list_alerts(db, user)
    assert not any("Message sent" in a["title"] for a in alerts)  # Phase 2E #64

    sos = FamilyCareHubService.raise_sos(db, user, "Possible fall")
    assert sos["kind"] == "sos"
    assert sos["status"] == "open"
    # Care team first (29 Oct): no family alert until staff confirm and notify.
    assert FamilyCareHubService.unread_alert_count(elder) == 0

    resolved = FamilyCareHubService.resolve_incident(db, user, sos["id"], status="resolved")
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None
    open_rows = [
        i
        for i in FamilyCareHubService.list_incidents(db, user)
        if i["id"] == sos["id"]
    ]
    assert open_rows[0]["status"] == "resolved"
    # Linked SOS alert should be marked read when incident is resolved.
    # The sender no longer sees the "SOS sent" echo (Phase 2E); check the stored rows.
    from app.livewell.family_care_hub import _hub

    db.refresh(elder)
    sos_alerts = [a for a in _hub(elder)["alerts"] if a.get("severity") == "critical"]
    assert all(a.get("read_at") for a in sos_alerts)  # none while the care team had it (29 Oct)

    prefs = FamilyCareHubService.update_prefs(
        db, user, {"digest_timezone": "America/New_York", "digest_cadence": "daily"}
    )
    assert prefs["digest_timezone"] == "America/New_York"
    digest = FamilyCareHubService.digest_preview(db, user)
    assert "Safety Score" in digest["text"] or "Next visit" in digest["text"]

    invited = FamilyCareHubService.invite_member(
        db,
        user,
        email=f"nri.p0.{elder.id}@example.com",
        password="demo1234",
        first_name="Arjun",
        last_name="P0",
        portal_relationship="nri",
    )
    circle = FamilyCareHubService.list_circle(db, user)
    assert len(circle) == 2
    assert any(m["email"] == invited["email"] for m in circle)

    feed = FamilyCareHubService.care_feed(db, user)
    assert any(i["kind"] == "message" for i in feed)


def test_acknowledge_alert_resolves_linked_sos(db, seed_tenant):
    """Reading the alert no longer resolves the SOS — staff own that decision.

    (Name kept so history stays greppable; the behaviour is now the opposite.)
    """
    from app.livewell import incident_service

    user, elder = _family_user(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, user, "Need a callback")
    from app.livewell import sos_siren

    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    sos_siren.confirm(db, row.id, seed_tenant["admin"])
    sos_siren.notify_family(db, row.id, seed_tenant["admin"])  # care team first (29 Oct)
    # The sender no longer sees the "SOS sent" echo (Phase 2E); a sibling would.
    from app.livewell.family_care_hub import _hub

    db.refresh(elder)
    sos_alert = next(a for a in _hub(elder)["alerts"] if a.get("severity") == "critical")
    FamilyCareHubService.mark_alert_read(db, user, sos_alert["id"])
    rows = FamilyCareHubService.list_incidents(db, user)
    match = next(i for i in rows if i["id"] == sos["id"])
    assert match["status"] == "open"
    assert FamilyCareHubService.unread_alert_count(elder) == 0
    # The DB incident stays open and records the family read as a note.
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    assert row is not None and row.status == "acknowledged" and row.kind == "family_sos"
    events = incident_service.list_events(db, row.id)
    assert any(e.event == "note" and "family acknowledged alert" in (e.detail or "") for e in events)

    from datetime import datetime, timezone

    from app.livewell.document_types import LW_HOME_ASSESSMENT_CONSENT
    from app.models.document import Document

    user, elder = _family_user(db, seed_tenant)
    doc = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=LW_HOME_ASSESSMENT_CONSENT,
        file_name="consent.jpg",
        storage_key="test/consent.jpg",
        storage_url="/test/consent.jpg",
        mime_type="image/jpeg",
        uploaded_at=datetime.now(timezone.utc),
        verification_status="PENDING",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    rows = FamilyCareHubService.list_documents(db, user)
    assert len(rows) == 1
    assert rows[0]["id"] == doc.id
    assert rows[0]["title"] == "consent.jpg"
    assert rows[0]["created_at"] is not None
    assert rows[0]["url"].endswith(f"/documents/{doc.id}/file")
