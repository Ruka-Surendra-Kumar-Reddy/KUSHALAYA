"""Family contact preferences: phone, preferred channel, timezone and level (K2 #88).

Each family member of a client — a portal login or a circle contact without a
login (an extra email on the client) — can say how to reach them and how much
they want to hear:

- everything   — every notice
- important    — safety, missed visits, orders, KushLife red flags (+ emergencies)
- emergencies  — SOS / emergencies only

The family member edits their own row on My details; staff edit any row on the
client's family card. SMS / WhatsApp are not connected yet: the channel is
stored for when they are; email goes out now and follows the level.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request
from app.models.elder import Elder
from app.models.family_contact import CONTACT_CHANNELS, CONTACT_LEVELS, DEFAULT_TIMEZONE, FamilyContact
from app.models.user import User

IST = timezone(timedelta(hours=5, minutes=30))
_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{6,20}$")

EMERGENCY_EVENTS = frozenset({"sos", "emergency"})
# What "important only" gets on top of emergencies.
IMPORTANT_EVENTS = EMERGENCY_EVENTS | frozenset({"safety", "missed", "order", "kushlife_red"})

LEVEL_LABELS = {
    "everything": "Everything",
    "important": "Important only (safety, missed visits, orders, KushLife red flags)",
    "emergencies": "Emergencies only",
}
CHANNEL_LABELS = {"whatsapp": "WhatsApp", "sms": "SMS", "call": "Phone call", "email": "Email"}


def level_allows(level: str | None, event: str) -> bool:
    level = level if level in CONTACT_LEVELS else "everything"
    if level == "emergencies":
        return event in EMERGENCY_EVENTS
    if level == "important":
        return event in IMPORTANT_EVENTS
    return True


def clean_phone(value) -> str:
    v = str(value or "").strip()
    if v and not _PHONE_RE.match(v):
        raise_bad_request("Enter a phone number with digits only, e.g. +91 98765 43210")
    return v


def clean_timezone(value) -> str:
    v = str(value or "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError):
        raise_bad_request("Choose a timezone from the list")
    return v


def _clean_choice(value, allowed: tuple[str, ...], label: str) -> str:
    v = str(value or "").strip().lower()
    if v not in allowed:
        raise_bad_request(f"Choose a {label}")
    return v


# --- rows -----------------------------------------------------------------


def _row(db: Session, elder: Elder, *, user_id: int | None = None, email: str | None = None) -> FamilyContact | None:
    # Oldest row first: if a duplicate ever slipped in, everyone reads and edits the same one.
    q = db.query(FamilyContact).filter(FamilyContact.elder_id == elder.id).order_by(FamilyContact.id)
    if user_id is not None:
        return q.filter(FamilyContact.user_id == user_id).first()
    if email:
        return q.filter(FamilyContact.user_id.is_(None), FamilyContact.email == email.strip().lower()).first()
    return None


def _legacy_phone(elder: Elder, user_id: int) -> str:
    sh = (elder.custom_attributes or {}).get("safe_home")
    phones = sh.get("family_phones") if isinstance(sh, dict) else None
    return str((phones or {}).get(str(user_id)) or "") if isinstance(phones, dict) else ""


def _sync_legacy_phone(elder: Elder, user_id: int, phone: str) -> None:
    """Keep safe_home.family_phones in step: older readers (incident calls) use it."""
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    phones = dict(block.get("family_phones") or {}) if isinstance(block.get("family_phones"), dict) else {}
    if phone:
        phones[str(user_id)] = phone
    else:
        phones.pop(str(user_id), None)
    block["family_phones"] = phones
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")


def contact_prefs(db: Session, elder: Elder, *, user: User | None = None, email: str | None = None) -> dict:
    row = _row(db, elder, user_id=user.id if user else None, email=None if user else email)
    phone = (row.phone if row else None) or (_legacy_phone(elder, user.id) if user else "")
    return {
        "phone": phone or "",
        "channel": row.channel if row and row.channel in CONTACT_CHANNELS else "whatsapp",
        "timezone": row.timezone if row and row.timezone else DEFAULT_TIMEZONE,
        "level": row.level if row and row.level in CONTACT_LEVELS else "everything",
    }


def save_contact(
    db: Session, elder: Elder, data: dict, *, user: User | None = None, email: str | None = None
) -> dict:
    """Update the given fields (phone, channel, timezone, level). No commit."""
    if user is None and not email:
        raise_bad_request("Choose a family member")
    row = _row(db, elder, user_id=user.id if user else None, email=None if user else email)
    if row is None:
        row = FamilyContact(
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            user_id=user.id if user else None,
            email=(user.email if user else email).strip().lower(),
            phone=_legacy_phone(elder, user.id) if user else None,
            channel="whatsapp",
            timezone=DEFAULT_TIMEZONE,
            level="everything",
        )
        try:
            with db.begin_nested():  # unique index: two first saves racing
                db.add(row)
                db.flush()
        except IntegrityError:
            row = _row(db, elder, user_id=user.id if user else None, email=None if user else email)
            if row is None:
                raise
    if user is not None and data.get("name") is None:
        row.name = f"{user.first_name or ''} {user.last_name or ''}".strip() or None
    if data.get("name") is not None and user is None:
        row.name = str(data["name"]).strip()[:200] or None
    if data.get("phone") is not None:
        row.phone = clean_phone(data["phone"]) or None
        if user is not None:
            _sync_legacy_phone(elder, user.id, row.phone or "")
    if data.get("channel") is not None:
        row.channel = _clean_choice(data["channel"], CONTACT_CHANNELS, "way to reach you")
    if data.get("timezone") is not None:
        row.timezone = clean_timezone(data["timezone"])
    if data.get("level") is not None:
        row.level = _clean_choice(data["level"], CONTACT_LEVELS, "what you want to hear about")
    db.flush()
    return contact_prefs(db, elder, user=user, email=email)


def prefs_by_email(db: Session, elder: Elder) -> dict[str, dict]:
    """email (lower) → {level, timezone} for everyone on this client with a row."""
    rows = db.query(FamilyContact).filter(FamilyContact.elder_id == elder.id).order_by(FamilyContact.id).all()
    user_ids = [r.user_id for r in rows if r.user_id]
    emails = {u.id: (u.email or "").lower() for u in db.query(User).filter(User.id.in_(user_ids or [-1])).all()}
    out: dict[str, dict] = {}
    from_login: set[str] = set()
    for r in rows:
        addr = emails.get(r.user_id) if r.user_id else (r.email or "").lower()
        if not addr:
            continue
        # A login's own row wins over an email-only row for the same address; among
        # rows of one kind the oldest wins (the one _row reads and edits).
        if r.user_id:
            if addr in from_login:
                continue
            from_login.add(addr)
        elif addr in out:
            continue
        out[addr] = {"level": r.level or "everything", "timezone": r.timezone or DEFAULT_TIMEZONE}
    return out


# --- staff view ---------------------------------------------------------------


def list_contacts(db: Session, elder: Elder) -> list[dict]:
    """Everyone the family emails go to: portal logins + extra (circle) emails."""
    from app.livewell.email_notifications import get_family_prefs
    from app.livewell.family_care_hub import FamilyCareHubService

    members, primary_id = FamilyCareHubService._circle_members(db, elder)
    out = []
    seen = set()
    for m in members:
        seen.add((m.email or "").lower())
        out.append({
            "key": f"user:{m.id}",
            "user_id": m.id,
            "name": f"{m.first_name or ''} {m.last_name or ''}".strip() or m.email,
            "email": m.email,
            "relationship": m.portal_relationship,
            "is_primary": m.id == primary_id,
            "has_login": True,
            **contact_prefs(db, elder, user=m),
        })
    for addr in get_family_prefs(elder)["extra"]:
        if addr.lower() in seen:
            continue
        row = _row(db, elder, email=addr)
        out.append({
            "key": f"email:{addr.lower()}",
            "user_id": None,
            "name": (row.name if row else None) or addr,
            "email": addr,
            "relationship": None,
            "is_primary": False,
            "has_login": False,
            **contact_prefs(db, elder, email=addr),
        })
    return out


def staff_save_contact(db: Session, elder: Elder, key: str, data: dict, staff: User) -> dict:
    from app.services.audit_service import AuditService

    target = next((c for c in list_contacts(db, elder) if c["key"] == key), None)
    if target is None:
        raise_bad_request("That person is not on this client's family list")
    user = db.get(User, target["user_id"]) if target["user_id"] else None
    before = {k: target[k] for k in ("phone", "channel", "timezone", "level")}
    after = save_contact(db, elder, data, user=user, email=None if user else target["email"])
    changed = {k: after[k] for k in after if after[k] != before.get(k)}
    if changed:
        AuditService.log(
            db, tenant_id=elder.tenant_id, user_id=staff.id, entity_type="family_contact",
            entity_id=elder.id, action="family_contact_updated",
            old_value={"key": key, **{k: before[k] for k in changed}}, new_value={"key": key, **changed},
        )
    db.commit()
    return next(c for c in list_contacts(db, elder) if c["key"] == key)


# --- times in the reader's timezone ------------------------------------------------

_TIME_MARK = re.compile(r"\[\[t:([^\]]+)\]\]( IST)?")


def email_time(dt: datetime | None) -> str:
    """A time for a family notice. Rendered per reader: IST as before, or their own
    timezone with IST in brackets ("Tue 6 Oct, 11:00 AM London time (3:30 PM IST)")."""
    if dt is None:
        return "a time to be confirmed"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f"[[t:{dt.astimezone(timezone.utc).isoformat()}]]"


def _fmt(dt: datetime) -> str:
    return dt.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def render_times(text: str, tz_name: str | None = None) -> str:
    tz_name = tz_name or DEFAULT_TIMEZONE

    def sub(m: re.Match) -> str:
        try:
            at = datetime.fromisoformat(m.group(1))
        except ValueError:
            return m.group(0)
        ist = at.astimezone(IST)
        if tz_name in (DEFAULT_TIMEZONE, "Asia/Calcutta"):
            return _fmt(ist) + (m.group(2) or "")
        try:
            zone = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            return _fmt(ist) + (m.group(2) or "")
        local = at.astimezone(zone)
        city = tz_name.rsplit("/", 1)[-1].replace("_", " ")
        ist_part = ist.strftime("%I:%M %p").lstrip("0")
        if local.date() != ist.date():
            ist_part = _fmt(ist)
        return f"{_fmt(local)} {city} time ({ist_part} IST)"

    return _TIME_MARK.sub(sub, text or "")
