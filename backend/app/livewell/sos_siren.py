"""SOS siren (C1): who hears an SOS, the watch "verify first" step, acks, escalation.

An SOS can come from the family app (a relative or the elder's own login), the
caregiver app, Ops (raise emergency on a client) or the SOS watch. Each one is a
``care_incidents`` row; this module adds one ``sos_siren_alerts`` row per person
who must hear it. The browser polls ``/api/v1/sos-siren/active`` and plays the
siren for the rows that are not acknowledged yet.

Who hears it: only people with access to that client —

* staff: the client's care manager(s) (``team_elder_ids``) and the heads
  (agency admins, who see every client);
* family: the client's family logins (not the elder's own login).

Never other staff or other families.

Every SOS goes to the care team first (owner, 29 Oct: "Alert should first go
to care manager. After he confirms then only he should be able to notify
family"). Only staff rows are made, plus the presser's own row when a family
member pressed it ("Your care team has been alerted"). The steps:

1. acknowledge: "I've seen it" (stops that person's siren);
2. confirm: "it's real" (a manager or admin raising it counts as confirming);
3. notify family: adds the family rows, rings their phones and sends the
   family alert (portal + email) that was held back.

"False alarm" closes it before step 3; the family never hears, except the
family member who pressed it, who sees it was handled. While the family is held
back, every family update (``incident_service.tell_family``) goes only to the
family presser, if any.

If no staff member acknowledges within ``ESCALATE_AFTER`` the incident is
escalated (the existing ladder: email / SMS / Telegram) and every head gets the
siren again, marked escalated. Run from ``incident_service.run_escalation_scan``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import CARE_MANAGER, CAREGIVER, ELDER_PORTAL, SYSTEM_ADMIN, TENANT_ADMIN
from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.incident import OPEN_STATUSES, Incident
from app.models.sos_siren import SosSirenAlert
from app.models.tenant import Tenant
from app.models.user import User

SIREN_KINDS = frozenset({"family_sos", "staff_emergency", "sos_button"})
ESCALATE_AFTER = timedelta(minutes=2)
HEAD_ROLES = (TENANT_ADMIN,)
STAFF_ACK_ROLES = frozenset({CARE_MANAGER, TENANT_ADMIN, SYSTEM_ADMIN})
SOURCES = ("family", "elder", "caregiver", "ops", "watch")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _name(user: User | None) -> str:
    if not user:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "").split("@", 1)[0]


def siren(row: Incident) -> dict:
    details = row.details if isinstance(row.details, dict) else {}
    block = details.get("siren")
    return dict(block) if isinstance(block, dict) else {}


def _save_siren(row: Incident, block: dict) -> None:
    details = dict(row.details) if isinstance(row.details, dict) else {}
    details["siren"] = block
    row.details = details
    flag_modified(row, "details")


def family_held(row: Incident) -> bool:
    """The family has not been told yet: they must not hear of it.

    Blocks written before 29 Oct have no ``family_notified_at`` key: there a
    confirmed watch SOS had already told the family.
    """
    block = siren(row)
    if not block.get("verify") or block.get("family_notified_at"):
        return False
    if "family_notified_at" not in block and block.get("confirmed_at"):
        return False
    return True


def family_presser(db: Session, row: Incident) -> User | None:
    """The family (or elder) login that pressed this SOS, if one did."""
    uid = siren(row).get("pressed_by_user_id")
    user = db.get(User, uid) if uid else None
    return user if user is not None and user.role == ELDER_PORTAL else None


def summary(row: Incident) -> dict | None:
    """The SOS steps for the Alerts page (None when this incident has no siren)."""
    block = siren(row)
    if not block:
        return None
    held = family_held(row)
    return {
        "source": block.get("source") or "",
        "pressed_by": block.get("pressed_by") or "",
        "family_held": held,
        "confirmed_at": block.get("confirmed_at"),
        "confirmed_by": block.get("confirmed_by"),
        "family_notified_at": block.get("family_notified_at"),
        "family_notified_by": block.get("family_notified_by"),
        "can_confirm": held and not block.get("confirmed_at"),
        "can_notify_family": held and bool(block.get("confirmed_at")),
    }


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------


def staff_recipient_ids(db: Session, elder: Elder) -> set[int]:
    """The client's care manager(s) plus the heads, by the app's team-scope rules."""
    from app.core.team_scope import team_elder_ids

    out: set[int] = set()
    users = (
        db.query(User)
        .filter(
            User.tenant_id == elder.tenant_id,
            User.status == "ACTIVE",
            User.role.in_([CARE_MANAGER, *HEAD_ROLES]),
        )
        .all()
    )
    for u in users:
        if u.role in HEAD_ROLES:
            out.add(u.id)
            continue
        ids = team_elder_ids(db, u)
        if ids is not None and elder.id in ids:
            out.add(u.id)
    return out


def head_ids(db: Session, tenant_id: int) -> set[int]:
    return {
        r[0]
        for r in db.query(User.id)
        .filter(User.tenant_id == tenant_id, User.status == "ACTIVE", User.role.in_(list(HEAD_ROLES)))
        .all()
    }


def family_recipient_ids(db: Session, elder: Elder) -> set[int]:
    """The client's family logins (direct and linked), the elder's own login included:
    families often share it, and the owner expects it to ring (27 Oct). Whoever
    pressed SOS is still left out by the caller (they start acknowledged)."""
    from app.models.family_elder_link import FamilyElderLink

    linked = {r[0] for r in db.query(FamilyElderLink.user_id).filter(FamilyElderLink.elder_id == elder.id).all()}
    q = db.query(User).filter(User.role == ELDER_PORTAL, User.status == "ACTIVE")
    rows = q.filter(User.elder_id == elder.id).all()
    if linked:
        rows += q.filter(User.id.in_(list(linked))).all()
    return {u.id for u in rows}


def _add_rows(db: Session, row: Incident, user_ids: set[int], audience: str, *, acked: set[int] | None = None,
              at: datetime | None = None) -> int:
    have = {
        r[0] for r in db.query(SosSirenAlert.user_id).filter(SosSirenAlert.incident_id == row.id).all()
    }
    added = 0
    for uid in sorted(user_ids - have):
        db.add(
            SosSirenAlert(
                tenant_id=row.tenant_id,
                incident_id=row.id,
                user_id=uid,
                audience=audience,
                acknowledged_at=(at or _now()) if acked and uid in acked else None,
            )
        )
        added += 1
    return added


# ---------------------------------------------------------------------------
# Start / confirm / false alarm
# ---------------------------------------------------------------------------


def start(
    db: Session,
    row: Incident,
    *,
    source: str,
    presser: User | None = None,
    verify: bool = False,
    family_pending: dict | None = None,
    confirmed_by: User | None = None,
    now: datetime | None = None,
) -> bool:
    """Sound the siren for the care team (and a family presser). Once per incident.

    The family is always held back until staff confirm and tap "Notify family";
    ``verify`` is kept for old callers and no longer changes that.
    ``confirmed_by``: a manager or admin who raised it themselves (it is real).
    """
    if row.kind not in SIREN_KINDS or siren(row):
        return False
    elder = db.get(Elder, row.elder_id)
    if not elder:
        return False
    at = now or _now()
    src = source if source in SOURCES else "ops"
    if src == "watch":
        label = "SOS watch"
    elif src == "elder":
        label = f"{(elder.first_name or '').strip() or 'The client'} (the client)"
    elif src == "family":
        label = f"{_name(presser) or 'Family'} (family)"
    elif src == "caregiver":
        label = f"{_name(presser) or 'Caregiver'} (caregiver)"
    else:
        label = f"{_name(presser) or 'Care team'} (care team)"
    block: dict[str, Any] = {
        "source": src,
        "pressed_by": label,
        "pressed_by_user_id": presser.id if presser else None,
        "pressed_at": at.isoformat(),
        "verify": True,
        "confirmed_at": at.isoformat() if confirmed_by else None,
        "confirmed_by": _name(confirmed_by) if confirmed_by else None,
        "family_notified_at": None,
        "family_notified_by": None,
        "escalated_at": None,
    }
    if family_pending:
        block["family_pending"] = family_pending
    _save_siren(row, block)
    # Per DEVICE, not per account (owner, 27 Oct): the presser's row is NOT
    # pre-acknowledged, so their other phones and laptops ring too; only the device
    # that pressed stays quiet (it remembers locally — see pressed_by_me). A staff
    # presser still counts as handling it for escalation (_staff_acked).
    pressed: set[int] = set()
    staff = staff_recipient_ids(db, elder)
    if presser and presser.role in STAFF_ACK_ROLES and presser.tenant_id == row.tenant_id:
        staff.add(presser.id)
    _add_rows(db, row, staff, "staff", acked=pressed, at=at)
    if presser and presser.role == ELDER_PORTAL:
        # Only the presser: "Your care team has been alerted" on their other devices.
        _add_rows(db, row, {presser.id} - staff, "family", acked=pressed, at=at)
    db.commit()
    _push(db, row, _user_ids(db, row) - pressed, "start")
    return True


def _push(db: Session, row: Incident, user_ids: set[int], reason: str) -> None:
    """Ring these people's phones too (Android app, FCM). No-op when FCM is not set up."""
    from app.livewell import push

    push.notify_sos(db, row.id, user_ids, reason=reason)


def _staff_row(db: Session, row: Incident, user: User) -> None:
    from app.core.team_scope import team_elder_ids

    if user.role not in STAFF_ACK_ROLES:
        raise_not_found("SOS not found")
    if user.role != SYSTEM_ADMIN and user.tenant_id != row.tenant_id:
        raise_not_found("SOS not found")
    ids = team_elder_ids(db, user)
    if ids is not None and row.elder_id not in ids:
        raise_not_found("SOS not found")


def _incident(db: Session, incident_id: int) -> Incident:
    row = db.get(Incident, incident_id)
    if not row or not siren(row):
        raise_not_found("SOS not found")
    return row


def confirm(db: Session, incident_id: int, user: User, *, now: datetime | None = None) -> Incident:
    """Staff checked the SOS and it is real. The family is still not told: that is
    the separate "Notify family" step. The confirmer's siren card stays up to offer it."""
    from app.livewell import incident_service as inc

    row = _incident(db, incident_id)
    _staff_row(db, row, user)
    if row.status not in OPEN_STATUSES:
        raise_bad_request("This SOS is already closed")
    block = siren(row)
    if block.get("confirmed_at") or not family_held(row):
        return row
    at = now or _now()
    block["confirmed_at"] = at.isoformat()
    block["confirmed_by"] = _name(user)
    _save_siren(row, block)
    inc.record_event(
        db, row, "note", channel="portal", actor_user_id=user.id,
        detail="Confirmed the SOS is real", at=at,
    )
    db.commit()
    if row.acknowledged_at is None:
        inc.acknowledge(db, row, user, now=at, stop_siren=False)
    db.refresh(row)
    return row


def notify_family(
    db: Session, incident_id: int, user: User, *, message: str | None = None, now: datetime | None = None
) -> Incident:
    """After confirming: alert every family login of this client (siren, phone, portal, email)."""
    from app.livewell import incident_service as inc

    row = _incident(db, incident_id)
    _staff_row(db, row, user)
    if row.status not in OPEN_STATUSES:
        raise_bad_request("This SOS is already closed")
    block = siren(row)
    if not family_held(row):
        return row  # already told
    if not block.get("confirmed_at"):
        raise_bad_request("Confirm the SOS first")
    at = now or _now()
    text = " ".join((message or "").split())[:300]
    block["family_notified_at"] = at.isoformat()
    block["family_notified_by"] = _name(user)
    pending = block.pop("family_pending", None)
    _save_siren(row, block)
    elder = db.get(Elder, row.elder_id)
    new_family = family_recipient_ids(db, elder) - _user_ids(db, row)
    _add_rows(db, row, new_family, "family", at=at)
    _ack_row(db, row, user, at)  # the notifier is done with this card
    inc.record_event(
        db, row, "note", channel="portal", actor_user_id=user.id,
        detail="Notified the family" + (f": {text}" if text else ""), at=at,
    )
    db.commit()
    _publish_to_family(db, elder, row, pending or {}, message=text, sender=user)
    _push(db, row, new_family, "notify_family")
    db.refresh(row)
    return row


def _publish_to_family(
    db: Session, elder: Elder, row: Incident, pending: dict, *, message: str = "", sender: User | None = None
) -> None:
    """The family alert that was held back: hub row, portal alert, email."""
    from app.livewell import incident_service as inc
    from app.livewell.family_care_hub import FamilyCareHubService, _hub, _iso, _save_hub

    note = f"\nMessage from {_name(sender).split(' ')[0] or 'the care team'}: {message}" if message else ""
    if row.kind == "staff_emergency":
        from app.livewell.emergency_service import _mirror_open_to_family

        _mirror_open_to_family(db, elder, row, note=note)
        return
    first = (elder.first_name or "").strip() or "your family member"
    presser = family_presser(db, row)
    if row.kind == "family_sos":
        title = f"SOS for {first}"
        body = f"{siren(row).get('pressed_by') or 'Family'} pressed SOS. Our care team has confirmed it and is responding."
    else:
        title = pending.get("title") or f"SOS from {first}'s watch"
        body = pending.get("body") or "The care team checked it and is responding now."
    try:
        hub = _hub(elder)
        mine = [i for i in hub["incidents"] if isinstance(i, dict) and i.get("incident_db_id") == row.id]
        for item in mine:
            item.pop("held_for", None)  # now every family login sees it
        if mine:
            legacy = mine[0].get("id")
        else:
            item = dict(pending.get("hub_incident") or {})
            item.setdefault("id", row.legacy_id or f"inc_{row.id}")
            item.setdefault("kind", "sos")
            item.setdefault("note", body)
            item.update({"status": "open", "incident_db_id": row.id})
            item.setdefault("created_at", _iso())
            hub["incidents"] = [item, *hub["incidents"]][:50]
            legacy = item["id"]
        _save_hub(db, elder, hub)
        FamilyCareHubService._push_alert(
            db, elder, title=title, body=body + note, severity="critical", incident_id=legacy,
            actor_email=presser.email if presser else None, self_notice=bool(presser),
        )
        from app.livewell.email_notifications import email_context, family_recipients, send

        skip = (presser.email or "").lower() if presser else ""
        to = [e for e in family_recipients(db, elder, "sos") if e.lower() != skip]
        with email_context("/alerts", (elder.first_name or "").strip()):
            send(to, title, body + note, family=True)
    except Exception:  # noqa: BLE001
        inc.logger.exception("sos_siren_family_publish_failed incident=%s", row.id)


def false_alarm(db: Session, incident_id: int, user: User, *, note: str | None = None) -> Incident:
    """Staff checked it and it was nothing: close it before the family is told.
    The family never hears, except a family member who pressed it: they are told it was checked."""
    from app.livewell import incident_service as inc

    row = _incident(db, incident_id)
    _staff_row(db, row, user)
    if row.status not in OPEN_STATUSES:
        return row
    if not family_held(row):
        raise_bad_request("The family has been told already. Close it from Alerts instead.")
    at = _now()
    what = "Watch SOS" if siren(row).get("source") == "watch" else "SOS"
    text = (note or "").strip() or f"{what} checked by {_name(user)} — false alarm"
    if row.kind == "staff_emergency":
        from app.livewell import emergency_service

        emergency_service.close(db, row, user, outcome="false_alarm", note=text)
    else:
        inc.resolve(db, row, outcome="false_alarm", note=text, user=user, notify_family=False, now=at)
    if family_presser(db, row) is not None:
        who = _name(user).split(" ")[0] or "Your care team"
        # Still held back, so this reaches only the family member who pressed it.
        inc.tell_family(db, row, "SOS checked — all clear", f"{who} from your care team checked it. No emergency.")
    for r in db.query(SosSirenAlert).filter(SosSirenAlert.incident_id == row.id, SosSirenAlert.acknowledged_at.is_(None)):
        r.acknowledged_at = at
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Acknowledge
# ---------------------------------------------------------------------------


def _user_ids(db: Session, row: Incident) -> set[int]:
    return {r[0] for r in db.query(SosSirenAlert.user_id).filter(SosSirenAlert.incident_id == row.id).all()}


def _ack_row(db: Session, row: Incident, user: User, at: datetime) -> bool:
    mine = (
        db.query(SosSirenAlert)
        .filter(SosSirenAlert.incident_id == row.id, SosSirenAlert.user_id == user.id)
        .first()
    )
    if mine and mine.acknowledged_at is None:
        mine.acknowledged_at = at
        return True
    return False


def mark_acknowledged(db: Session, row: Incident, user: User, at: datetime | None = None) -> None:
    """Called by ``incident_service.acknowledge``: acking on the Alerts page stops the siren too. No commit."""
    _ack_row(db, row, user, at or _now())


def acknowledge(db: Session, alert_id: int, user: User, *, now: datetime | None = None) -> dict:
    from app.livewell import incident_service as inc

    alert = db.get(SosSirenAlert, alert_id)
    if not alert or alert.user_id != user.id:
        raise_not_found("SOS alert not found")
    at = now or _now()
    if alert.acknowledged_at is not None:
        return {"ok": True, "id": alert.id}
    row = db.get(Incident, alert.incident_id)
    alert.acknowledged_at = at
    db.commit()
    if row is not None and row.status in OPEN_STATUSES:
        if alert.audience == "staff" and user.role in STAFF_ACK_ROLES and row.acknowledged_at is None:
            inc.acknowledge(db, row, user, now=at)
        else:
            inc.record_event(
                db, row, "note", channel="portal", actor_user_id=user.id,
                detail=f"SOS alert acknowledged by {inc.person_label(user)}", at=at, commit=True,
            )
    return {"ok": True, "id": alert.id}


# ---------------------------------------------------------------------------
# Read: the polling endpoint
# ---------------------------------------------------------------------------


def _call_for(db: Session, row: Incident, elder: Elder, audience: str, block: dict) -> dict:
    """The number the notice's Call button dials."""
    if audience == "family":
        tenant = db.get(Tenant, row.tenant_id)
        return {"label": "Call the care team", "phone": (tenant.phone or "").strip() if tenant else ""}
    first = (elder.first_name or "the client").strip()
    presser = db.get(User, block["pressed_by_user_id"]) if block.get("pressed_by_user_id") else None
    if presser and presser.role == ELDER_PORTAL and (presser.portal_relationship or "").lower() != "self":
        from app.livewell.family_contacts import _legacy_phone, _row

        contact = _row(db, elder, user_id=presser.id)
        phone = ((getattr(contact, "phone", None) or "") if contact else "") or _legacy_phone(elder, presser.id)
        if phone:
            return {"label": f"Call {_name(presser).split(' ')[0] or 'family'}", "phone": phone}
    if presser and presser.role == CAREGIVER and presser.caregiver_id:
        from app.models.caregiver import Caregiver

        cg = db.get(Caregiver, presser.caregiver_id)
        if cg and (cg.phone or "").strip():
            return {"label": f"Call {cg.first_name or 'caregiver'}", "phone": cg.phone.strip()}
    phone = (elder.phone or "").strip() or (elder.emergency_contact_phone or "").strip()
    return {"label": f"Call {first}", "phone": phone}


def serialize(db: Session, alert: SosSirenAlert, row: Incident, elder: Elder) -> dict:
    block = siren(row)
    name = f"{elder.first_name or ''} {elder.last_name or ''}".strip() or "Client"
    staff = alert.audience == "staff"
    held = family_held(row)
    confirmed = bool(block.get("confirmed_at"))
    verify = held and not confirmed
    if verify and staff and block.get("source") == "watch":
        title = "Watch SOS — verify"
    elif row.kind == "staff_emergency":
        title = "Emergency"
    else:
        title = "SOS"
    presser_id = block.get("pressed_by_user_id")
    acked = (
        db.query(SosSirenAlert.user_id, SosSirenAlert.acknowledged_at)
        .filter(SosSirenAlert.incident_id == row.id, SosSirenAlert.acknowledged_at.isnot(None))
        .order_by(SosSirenAlert.acknowledged_at)
        .all()
    )
    ack_ids = [uid for uid, _ in acked if uid != presser_id]
    users = {u.id: u for u in db.query(User).filter(User.id.in_(ack_ids or [-1])).all()}
    from app.livewell.incident_service import person_label

    return {
        "id": alert.id,
        "incident_id": row.id,
        "elder_id": elder.id,
        "elder_name": name if staff else (elder.first_name or name),
        "kind": row.kind,
        "title": title,
        "audience": alert.audience,
        "pressed_by": block.get("pressed_by") or "",
        # The device that pressed it stays quiet; this account's other devices ring.
        "pressed_by_me": bool(block.get("pressed_by_user_id")) and block.get("pressed_by_user_id") == alert.user_id,
        "source": block.get("source") or "",
        "pressed_at": block.get("pressed_at") or (_aware(row.opened_at).isoformat() if row.opened_at else None),
        "verify": verify and staff,
        # Confirmed, family not told yet: the staff card offers "Notify family".
        "notify_family": held and confirmed and staff,
        "family_told": not held,
        "escalated": bool(block.get("escalated_at")),
        "confirmed_by": block.get("confirmed_by"),
        "acknowledged_by": [person_label(users[uid]) for uid in ack_ids if uid in users],
        "call": _call_for(db, row, elder, alert.audience, block),
    }


def active_for(db: Session, user: User) -> list[dict]:
    rows = (
        db.query(SosSirenAlert, Incident)
        .join(Incident, Incident.id == SosSirenAlert.incident_id)
        .filter(
            SosSirenAlert.user_id == user.id,
            SosSirenAlert.acknowledged_at.is_(None),
            Incident.status.in_(list(OPEN_STATUSES)),
        )
        .order_by(SosSirenAlert.id.desc())
        .limit(20)
        .all()
    )
    out = []
    for alert, row in rows:
        elder = db.get(Elder, row.elder_id)
        if elder:
            out.append(serialize(db, alert, row, elder))
    return out


# ---------------------------------------------------------------------------
# Escalation (from incident_service.run_escalation_scan, every 2 minutes)
# ---------------------------------------------------------------------------


def _staff_acked(db: Session, row: Incident) -> bool:
    if siren(row).get("confirmed_at"):
        return True  # a staff member confirmed it: someone has it
    # A staff member who pressed it is already handling it.
    presser_id = siren(row).get("pressed_by_user_id")
    if presser_id:
        presser = db.get(User, presser_id)
        if presser and presser.role in STAFF_ACK_ROLES and presser.tenant_id == row.tenant_id:
            return True
    return (
        db.query(SosSirenAlert.id)
        .filter(
            SosSirenAlert.incident_id == row.id,
            SosSirenAlert.audience == "staff",
            SosSirenAlert.acknowledged_at.isnot(None),
        )
        .first()
        is not None
    )


def run_escalation(db: Session, *, now: datetime | None = None, tenant_id: int | None = None) -> list[dict]:
    """No staff acknowledgement within 2 minutes: escalate and sound it again for the heads."""
    from app.livewell import incident_service as inc

    at = now or _now()
    q = db.query(Incident).filter(Incident.kind.in_(list(SIREN_KINDS)), Incident.status.in_(list(OPEN_STATUSES)))
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    out: list[dict] = []
    for row in q.all():
        block = siren(row)
        if not block or block.get("escalated_at"):
            continue
        try:
            pressed = datetime.fromisoformat(block.get("pressed_at") or "")
        except ValueError:
            pressed = _aware(row.opened_at) or at
        pressed = _aware(pressed) or at
        if at - pressed < ESCALATE_AFTER or _staff_acked(db, row):
            continue
        block["escalated_at"] = at.isoformat()
        _save_siren(row, block)
        heads = head_ids(db, row.tenant_id)
        _add_rows(db, row, heads, "staff", at=at)
        db.commit()
        _push(db, row, heads, "escalation")
        inc.escalate(
            db, row, now=at, mark_escalated=True,
            reason="SOS not acknowledged within 2 minutes — escalated to the heads",
        )
        out.append({"incident_id": row.id, "level": int(row.escalation_level or 0), "sos_siren": True})
    return out
