"""SafeHome 360™ demo clients, family portal users, and assessor.

Run after migrations:
  python -m app.seed_safehome_admin && python -m app.seed_safehome_demo

Or all-in-one:
  python -m app.seed_safehome

Creates (idempotent), password demo1234:
  - Manager: manager@sunrise-care.example
  - Clients: Lakshmi Reddy, Padmaja Posa
  - Family: lakshmi.family / arjun.family / clairview.family @sunrise-care.example
  - Assessor: anita.caregiver@sunrise-care.example
  - Master spreadsheet defaults into empty workflow_config (+ baseline UploadId)
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.livewell.seed_service import seed_tenant_defaults
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_admin import ensure_safehome_tenant, ensure_tenant_admin
from app.seed_safehome_constants import (
    ASSESSOR_EMAIL,
    DEMO_PASSWORD,
    FAMILY_EMAILS,
    MANAGER_EMAIL,
)


def _ensure_user(
    db: Session,
    *,
    email: str,
    tenant_id: int,
    role: str,
    first_name: str,
    last_name: str,
    elder_id: int | None = None,
    caregiver_id: int | None = None,
    portal_relationship: str | None = None,
) -> User:
    row = db.query(User).filter(User.email == email).first()
    pwd = hash_password(DEMO_PASSWORD)
    if row:
        row.role = role
        row.tenant_id = tenant_id
        row.first_name = first_name
        row.last_name = last_name
        row.status = "ACTIVE"
        row.elder_id = elder_id
        row.caregiver_id = caregiver_id
        row.portal_relationship = portal_relationship
        try:
            if not verify_password(DEMO_PASSWORD, row.password_hash):
                row.password_hash = pwd
        except Exception:
            row.password_hash = pwd
        return row

    row = User(
        email=email,
        password_hash=pwd,
        first_name=first_name,
        last_name=last_name,
        role=role,
        tenant_id=tenant_id,
        status="ACTIVE",
        elder_id=elder_id,
        caregiver_id=caregiver_id,
        portal_relationship=portal_relationship,
    )
    db.add(row)
    db.flush()
    return row


def _link_family_elder(db: Session, user: User, elder: Elder) -> None:
    from app.livewell.family_elder_access import ensure_family_elder_link

    ensure_family_elder_link(db, user, elder)


def _ensure_client(
    db: Session,
    tenant: Tenant,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    address: str,
    date_of_birth: date,
    emergency_name: str,
    emergency_phone: str,
) -> Elder:
    row = (
        db.query(Elder)
        .filter(
            Elder.tenant_id == tenant.id,
            Elder.first_name == first_name,
            Elder.last_name == last_name,
        )
        .first()
    )
    if row:
        row.phone = row.phone or phone
        row.address = row.address or address
        row.status = "ACTIVE"
        if not row.emergency_contact_name:
            row.emergency_contact_name = emergency_name
            row.emergency_contact_phone = emergency_phone
        return row

    row = Elder(
        tenant_id=tenant.id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        gender="Female",
        phone=phone,
        address=address,
        emergency_contact_name=emergency_name,
        emergency_contact_phone=emergency_phone,
        mobility_status="Assisted",
        care_level="Moderate",
        status="ACTIVE",
        custom_attributes={
            "safe_home": {
                "score": None,
                "grade": None,
            }
        },
    )
    db.add(row)
    db.flush()
    return row


def _ensure_assessor(db: Session, tenant: Tenant) -> Caregiver:
    row = (
        db.query(Caregiver)
        .filter(Caregiver.tenant_id == tenant.id, Caregiver.email == ASSESSOR_EMAIL)
        .first()
    )
    if not row:
        row = (
            db.query(Caregiver)
            .filter(
                Caregiver.tenant_id == tenant.id,
                Caregiver.first_name == "Anita",
                Caregiver.last_name == "Devi",
            )
            .first()
        )
    if row:
        row.email = ASSESSOR_EMAIL
        row.phone = row.phone or "+91-9000000101"
        row.status = "ACTIVE"
        row.background_check_status = row.background_check_status or "VERIFIED"
        return row

    row = Caregiver(
        tenant_id=tenant.id,
        first_name="Anita",
        last_name="Devi",
        email=ASSESSOR_EMAIL,
        phone="+91-9000000101",
        years_experience=8,
        background_check_status="VERIFIED",
        police_verification_status="VERIFIED",
        status="ACTIVE",
        custom_attributes={"role_label": "SafeHome assessor"},
    )
    db.add(row)
    db.flush()
    return row


def ensure_safehome_demo_data() -> dict:
    # Ensure admin + tenant exist (opens/closes its own session).
    ensure_tenant_admin()

    db = SessionLocal()
    try:
        tenant = ensure_safehome_tenant(db)

        manager = _ensure_user(
            db,
            email=MANAGER_EMAIL,
            tenant_id=tenant.id,
            role="CARE_MANAGER",
            first_name="Ravi",
            last_name="Nair",
        )

        lakshmi = _ensure_client(
            db,
            tenant,
            first_name="Lakshmi",
            last_name="Reddy",
            phone="+91-9000000001",
            address="45 Banjara Hills, Hyderabad",
            date_of_birth=date(1945, 3, 15),
            emergency_name="Arjun Reddy",
            emergency_phone="+91-9000000002",
        )
        padmaja = _ensure_client(
            db,
            tenant,
            first_name="Padmaja",
            last_name="Posa",
            phone="+1-404-555-0199",
            address="2450 Clairview St, Alpharetta, GA 30009",
            date_of_birth=date(1948, 7, 22),
            emergency_name="Family Clairview",
            emergency_phone="+1-404-555-0110",
        )

        family_self = _ensure_user(
            db,
            email=FAMILY_EMAILS[0],
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name="Lakshmi",
            last_name="Reddy",
            elder_id=lakshmi.id,
            portal_relationship="self",
        )
        _link_family_elder(db, family_self, lakshmi)

        arjun = _ensure_user(
            db,
            email=FAMILY_EMAILS[1],
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name="Arjun",
            last_name="Reddy",
            elder_id=lakshmi.id,
            portal_relationship="son",
        )
        # Multi-elder household demo: son linked to mother + Clairview senior
        _link_family_elder(db, arjun, lakshmi)
        _link_family_elder(db, arjun, padmaja)

        clairview_family = _ensure_user(
            db,
            email=FAMILY_EMAILS[2],
            tenant_id=tenant.id,
            role="ELDER_PORTAL",
            first_name="Padmaja",
            last_name="Posa",
            elder_id=padmaja.id,
            portal_relationship="self",
        )
        _link_family_elder(db, clairview_family, padmaja)

        assessor = _ensure_assessor(db, tenant)
        _ensure_user(
            db,
            email=ASSESSOR_EMAIL,
            tenant_id=tenant.id,
            role="CAREGIVER",
            first_name="Anita",
            last_name="Devi",
            caregiver_id=assessor.id,
        )

        db.commit()

        seeded_config = seed_tenant_defaults(db, tenant)

        summary = {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "manager": manager.email,
            "clients": [lakshmi.id, padmaja.id],
            "family_portal": family_self.email,
            "assessor": ASSESSOR_EMAIL,
            "master_data_seeded": seeded_config,
        }
        print("SafeHome demo seed complete.")
        print(f"  Tenant: {tenant.name} (id={tenant.id}, vertical={tenant.vertical})")
        print(f"  Admin: admin@sunrise-care.example / {DEMO_PASSWORD}")
        print(f"  Manager: {MANAGER_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Family (self): {FAMILY_EMAILS[0]} / {DEMO_PASSWORD}")
        print(f"  Family (son, multi-elder): {FAMILY_EMAILS[1]} / {DEMO_PASSWORD}")
        print("    -> switch between Lakshmi Reddy and Padmaja Posa in the family app")
        print(f"  Family (Clairview): {FAMILY_EMAILS[2]} / {DEMO_PASSWORD}")
        print(f"  Assessor: {ASSESSOR_EMAIL} / {DEMO_PASSWORD}")
        if seeded_config:
            print(f"  Master data seeded: {', '.join(seeded_config)}")
        else:
            print("  Master data: already present (nothing empty to seed)")
        return summary
    finally:
        db.close()


if __name__ == "__main__":
    ensure_safehome_demo_data()
