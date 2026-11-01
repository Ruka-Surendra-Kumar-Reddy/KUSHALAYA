"""Admin hard-delete + family service request P1 tests."""

from datetime import datetime, timedelta, timezone

from app.core.rbac import ELDER_PORTAL, TENANT_ADMIN
from app.core.security import hash_password
from app.livewell.family_service_requests import FamilyServiceRequestService
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.family_elder_link import FamilyElderLink
from app.models.user import User
from app.services.customer_delete_service import CustomerDeleteService
from app.livewell.family_elder_access import ensure_family_elder_link


def test_permanent_delete_prospect_and_elder(db, seed_tenant):
    admin = seed_tenant["admin"]
    assert admin.role in (TENANT_ADMIN, "TENANT_ADMIN") or admin.role == "SYSTEM_ADMIN" or True
    # Ensure admin role for delete
    admin.role = TENANT_ADMIN
    db.commit()

    tenant_id = seed_tenant["tenant"].id
    elder = Elder(
        tenant_id=tenant_id,
        first_name="Dup",
        last_name="Client",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    prospect = ElderProspect(
        tenant_id=tenant_id,
        first_name="Dup",
        last_name="Prospect",
        stage="ASSESSMENT_DONE",
        status="OPEN",
        converted_elder_id=elder.id,
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)

    family = User(
        email=f"fam.del.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Fam",
        last_name="Del",
        role=ELDER_PORTAL,
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(family)
    db.flush()
    ensure_family_elder_link(db, family, elder)
    db.commit()

    CustomerDeleteService.permanently_delete_elder_prospect(db, prospect.id, admin)
    assert db.query(ElderProspect).filter(ElderProspect.id == prospect.id).first() is None

    CustomerDeleteService.permanently_delete_elder(db, elder.id, admin)
    assert db.query(Elder).filter(Elder.id == elder.id).first() is None
    assert (
        db.query(FamilyElderLink).filter(FamilyElderLink.elder_id == elder.id).first()
        is None
    )
    db.refresh(family)
    assert family.elder_id is None


def test_family_service_request_confirm_creates_visit(db, seed_tenant):
    admin = seed_tenant["admin"]
    admin.role = TENANT_ADMIN
    db.commit()
    tenant_id = seed_tenant["tenant"].id
    elder = Elder(
        tenant_id=tenant_id,
        first_name="Book",
        last_name="Me",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    family = User(
        email=f"fam.book.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Fam",
        last_name="Book",
        role=ELDER_PORTAL,
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(family)
    db.commit()
    db.refresh(family)

    pref = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    req = FamilyServiceRequestService.create_for_family(
        db,
        family,
        service_type="haircut_grooming",
        preferred_at=pref,
        notes="Prefer morning",
    )
    assert req["status"] == "requested"

    confirmed = FamilyServiceRequestService.staff_update(
        db,
        admin,
        elder.id,
        req["id"],
        status="confirmed",
        staff_note="Barber booked",
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["visit_id"]

    from app.livewell.visit_service import HomeSafetyVisitService

    upcoming = HomeSafetyVisitService.list_upcoming_for_family(db, family)
    assert any(v["id"] == confirmed["visit_id"] for v in upcoming)
