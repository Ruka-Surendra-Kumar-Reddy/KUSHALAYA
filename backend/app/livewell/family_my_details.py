"""Family "My details": the signed-in family member's own name and phone, and the
parent's emergency contact. Health details are never edited by the family directly —
they send a "details_change" request that staff check and apply.

The family member's phone, preferred channel, timezone and level (what they want
to hear about) live in family_contacts (K2 #88); the phone is mirrored to
elder.custom_attributes.safe_home.family_phones[str(user.id)] for older readers.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request
from app.models.elder import Elder
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{6,20}$")
HEALTH_FIELDS = (
    ("conditions", "Health conditions"),
    ("allergies", "Allergies"),
    ("medicines", "Medicines"),
    ("mobility", "Walking and mobility"),
)


def _clean_phone(value: str | None) -> str:
    v = (value or "").strip()
    if v and not _PHONE_RE.match(v):
        raise_bad_request("Enter a phone number with digits only, e.g. +91 98765 43210")
    return v


def _family_phones(elder: Elder) -> dict:
    sh = (elder.custom_attributes or {}).get("safe_home")
    phones = sh.get("family_phones") if isinstance(sh, dict) else None
    return dict(phones) if isinstance(phones, dict) else {}


def _set_family_phone(elder: Elder, user_id: int, phone: str) -> None:
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    phones = _family_phones(elder)
    if phone:
        phones[str(user_id)] = phone
    else:
        phones.pop(str(user_id), None)
    block["family_phones"] = phones
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")


def _payload(user: User, elder: Elder, db: Session | None = None) -> dict:
    from app.livewell.family_contacts import contact_prefs

    contact = (
        contact_prefs(db, elder, user=user)
        if db is not None
        else {"phone": _family_phones(elder).get(str(user.id), "")}
    )
    return {
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "email": user.email,
        **contact,
        "elder_id": elder.id,
        "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
        "emergency_contact_name": elder.emergency_contact_name or "",
        "emergency_contact_phone": elder.emergency_contact_phone or "",
        "health": {
            "conditions": elder.medical_conditions or "",
            "allergies": elder.allergies or "",
            "mobility": elder.mobility_status or "",
        },
    }


def get_my_details(db: Session, user: User) -> dict:
    return _payload(user, ElderPortalService.get_linked_elder(db, user), db)


def update_my_details(db: Session, user: User, data: dict) -> dict:
    from app.livewell.family_service_requests import lock_elder
    from app.services.audit_service import AuditService

    elder = lock_elder(db, ElderPortalService.get_linked_elder(db, user))
    before = _payload(user, elder, db)
    if data.get("first_name") is not None:
        first = str(data["first_name"]).strip()[:100]
        if not first:
            raise_bad_request("Please enter your first name")
        user.first_name = first
    if data.get("last_name") is not None:
        user.last_name = str(data["last_name"]).strip()[:100]
    contact = {k: data[k] for k in ("phone", "channel", "timezone", "level") if data.get(k) is not None}
    if contact:
        from app.livewell.family_contacts import save_contact

        save_contact(db, elder, contact, user=user)
    if str(data.get("timezone") or "").strip():
        # "Where you live" is the one timezone setting: the care digest follows it.
        from app.livewell.family_care_hub import FamilyCareHubService

        FamilyCareHubService.update_prefs(db, user, {"digest_timezone": str(data["timezone"]).strip()})
    if data.get("emergency_contact_name") is not None:
        elder.emergency_contact_name = str(data["emergency_contact_name"]).strip()[:200] or None
    if data.get("emergency_contact_phone") is not None:
        elder.emergency_contact_phone = _clean_phone(data["emergency_contact_phone"]) or None
    after = _payload(user, elder, db)
    changed = {k: after[k] for k in after if k != "health" and after[k] != before[k]}
    if changed:
        AuditService.log(
            db, tenant_id=elder.tenant_id, user_id=user.id, entity_type="family_details",
            entity_id=elder.id, action="family_details_updated",
            old_value={k: before[k] for k in changed}, new_value=changed,
        )
    db.commit()
    return after


def request_details_change(db: Session, user: User, data: dict) -> dict:
    """Health details change → a family service request (type details_change) that staff apply."""
    from app.livewell import family_service_requests as fsr
    from app.livewell.family_notify import notify_family, notify_manager

    elder = fsr.lock_elder(db, ElderPortalService.get_linked_elder(db, user))
    if any(
        r.get("service_type") == "details_change" and str(r.get("status") or "requested") in fsr.OPEN_REQUEST_STATUSES
        for r in fsr._requests(elder)
    ):
        from app.core.responses import WorkforceHTTPError

        db.commit()  # release the lock
        raise WorkforceHTTPError(
            "A change request is already open — your care team will update the details soon", status_code=409
        )
    parts = []
    for key, label in HEALTH_FIELDS:
        val = str(data.get(key) or "").strip()[:1000]
        if val:
            parts.append(f"{label}: {val}")
    note = str(data.get("note") or "").strip()[:1000]
    if note:
        parts.append(f"Note: {note}")
    if not parts:
        raise_bad_request("Tell us what has changed")
    row = fsr._normalize({
        "id": fsr._new_id(),
        "service_type": "details_change",
        "notes": "\n".join(parts),
        "status": "requested",
        "created_at": fsr._iso(),
        "created_by": user.email,
        "updated_at": fsr._iso(),
    })
    rows = fsr._requests(elder)
    rows.insert(0, row)
    fsr._save_requests(db, elder, rows)
    name = f"{elder.first_name} {elder.last_name}".strip()
    notify_manager(
        db, elder, f"Health details change: {name}",
        f"{user.first_name} {user.last_name} asked to update {name}'s health details.\n"
        + "\n".join(parts) + "\nCheck and apply it on the client's profile.",
    )
    notify_family(
        db, elder, "Change request received",
        "Your care team will check the health details and update them.", event="request",
    )
    return fsr._to_response(row)
