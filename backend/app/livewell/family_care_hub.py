"""Family care hub P0 — schedule-adjacent data stored on elder.custom_attributes.safe_home.family_hub."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.livewell.family_alert_text import sanitize_family_alert
from app.core.rbac import ELDER_PORTAL
from app.core.responses import WorkforceHTTPError, raise_bad_request, raise_conflict, raise_not_found
from app.core.security import hash_password
from app.livewell.brand import safety_score_name, with_brand
from app.models.elder import Elder
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService
from app.services.notifications import get_email_provider


# Allowlist for family uploads. These files are served back from our own origin,
# so script-bearing types (text/html, image/svg+xml) must never be accepted —
# they would be stored XSS against staff viewing the client record.
FAMILY_UPLOAD_ALLOWED_MIME = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/heic",
        "image/heif",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/webp": ".webp",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def _safe_file_name(raw: str, mime: str) -> str:
    """Strip any path and odd characters, and force the extension to match the
    MIME we validated — an uploader must not get to name a file `x.html`."""
    import re
    from pathlib import PurePosixPath, PureWindowsPath

    name = PurePosixPath(PureWindowsPath(raw or "").name).name or "document"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name).lstrip(".")
    stem = (stem.rsplit(".", 1)[0] or "document")[:80]
    return f"{stem}{_MIME_EXTENSIONS.get(mime, '.bin')}"


# Alert titles the system raises alongside a richer feed entry. The timeline
# skips them so one action does not read as two events.
FEED_ECHO_ALERT_TITLES = frozenset(
    {
        "Service request received",
        "Visit / service confirmed",
        "Document shared by family",
        # The reply itself is in the feed as a message from the named sender.
        "Reply from your care team",
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _job_photo_ids(db: Session, visit_id) -> list:
    """photo_ids on a care job's report, from its family visit id ("job-<n>")."""
    from app.livewell.visit_feedback import job_id_from_visit_id
    from app.models.care_job import CareJob

    jid = job_id_from_visit_id(str(visit_id or ""))
    job = db.get(CareJob, jid) if jid else None
    return list(((job.report if job else None) or {}).get("photo_ids") or [])


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _safe_home(elder: Elder) -> dict:
    attrs = elder.custom_attributes or {}
    block = attrs.get("safe_home")
    return dict(block) if isinstance(block, dict) else {}


def _hub(elder: Elder) -> dict:
    sh = _safe_home(elder)
    hub = sh.get("family_hub")
    if not isinstance(hub, dict):
        hub = {}
    return {
        "alerts": list(hub.get("alerts") or []) if isinstance(hub.get("alerts"), list) else [],
        "messages": list(hub.get("messages") or []) if isinstance(hub.get("messages"), list) else [],
        "incidents": list(hub.get("incidents") or []) if isinstance(hub.get("incidents"), list) else [],
        "prefs": dict(hub.get("prefs") or {}) if isinstance(hub.get("prefs"), dict) else {},
        # When the care team last opened this family's thread (staff inbox).
        "staff_read_at": hub.get("staff_read_at"),
    }


def open_sos_incident_count(incidents: list) -> int:
    """Open wearable/family SOS only — warnings (offline, immobility) do not count as SOS."""
    return sum(
        1
        for i in incidents
        if isinstance(i, dict)
        and str(i.get("status") or "open").lower() not in ("closed", "resolved")
        and str(i.get("kind") or "sos").lower() == "sos"
    )


def _save_hub(db: Session, elder: Elder, hub: dict) -> None:
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    block["family_hub"] = hub
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    db.refresh(elder)


def _default_prefs() -> dict:
    return {
        "digest_enabled": True,
        "digest_channel": "whatsapp",  # whatsapp | email | none
        "digest_cadence": "weekly",  # daily | weekly
        "digest_timezone": "Asia/Kolkata",
    }


# Notices the family used to get about their own actions (Phase 2E #64).
# Older rows (no actor stored) may still exist; they are hidden for everyone.
SELF_NOTICE_TITLES = frozenset({"Message sent to your care team", "Document shared by family"})

# Only these reach the Alerts page and the badge; "info" rows are updates and
# appear in the Updates timeline instead.
ALERT_SEVERITIES = frozenset({"warning", "high", "critical", "urgent"})


def _family_alert(row, user: User | None = None) -> bool:
    """Visible to this family member? Hides notices about their own actions.

    A row with ``actor_email`` is hidden only for that member. Critical rows are
    never hidden, except the "SOS sent" echo for the person who sent it (the
    SOS card on the Alerts page already shows it).
    """
    if not isinstance(row, dict):
        return False
    only = str(row.get("only_email") or "").lower()
    if only and (user is None or only != str(user.email or "").lower()):
        return False
    if str(row.get("title") or "") in SELF_NOTICE_TITLES and not row.get("actor_email"):
        return False
    actor = str(row.get("actor_email") or "").lower()
    if user is not None and actor and actor == str(user.email or "").lower():
        if str(row.get("severity") or "") != "critical" or row.get("self_notice"):
            return False
    return True


def _zone_words(tz: str | None) -> str:
    """Plain zone label: "IST" (as everywhere else in the portal), "New York time" (never "Asia/Kolkata")."""
    z = str(tz or "").strip()
    if not z or z in ("Asia/Kolkata", "Asia/Calcutta"):
        return "IST"
    return f"{z.rsplit('/', 1)[-1].replace('_', ' ')} time"


def _is_alert(row: dict) -> bool:
    return str(row.get("severity") or "info").lower() in ALERT_SEVERITIES


class FamilyCareHubService:
    """P0 family care: alerts, messages, SOS, digests, circle, care feed, documents."""

    @staticmethod
    def unread_alert_count(elder: Elder, user: User | None = None) -> int:
        """Badge count: unread real alerts (not info updates) this member can see."""
        return sum(
            1
            for a in _hub(elder)["alerts"]
            if _family_alert(a, user) and _is_alert(a) and not a.get("read_at")
        )

    @staticmethod
    def list_alerts(db: Session, user: User, *, include_info: bool = False) -> list[dict]:
        """Alerts, read ones included (the page shows them as "Past alerts").

        Info rows are left out unless ``include_info`` (the Updates timeline).
        """
        elder = ElderPortalService.get_linked_elder(db, user)
        rows = [
            a
            for a in _hub(elder)["alerts"]
            if _family_alert(a, user) and (include_info or _is_alert(a))
        ]
        rows.sort(key=lambda a: str(a.get("created_at") or ""), reverse=True)
        out: list[dict] = []
        for a in rows:
            created = _parse_dt(a.get("created_at")) or _now()
            # Old device rows carried device/hub/MAC codes: rewrite on the way out.
            title, body = sanitize_family_alert(
                str(a.get("title") or "Alert"),
                str(a.get("body") or ""),
                elder_name=getattr(elder, "first_name", None),
                created_at=created,
            )
            out.append(
                {
                    "id": str(a.get("id") or ""),
                    "title": title,
                    "body": body,
                    "severity": str(a.get("severity") or "info"),
                    "read_at": _parse_dt(a.get("read_at")),
                    "created_at": created,
                }
            )
        return out

    @staticmethod
    def mark_alert_read(db: Session, user: User, alert_id: str) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        hub = _hub(elder)
        found = None
        for row in hub["alerts"]:
            if isinstance(row, dict) and str(row.get("id")) == str(alert_id):
                row["read_at"] = _iso()
                found = row
                break
        if not found:
            raise_not_found("Alert not found")
        _save_hub(db, elder, hub)
        # Reading an alert is not resolving the incident: staff own that
        # decision. It used to silently close the linked SOS (Sept 2026), so
        # nobody on the ops side ever saw it. Now it only leaves a note.
        incident_id = found.get("incident_id")
        if incident_id:
            from app.livewell import incident_service

            row = incident_service.find_by_legacy_id(db, elder.id, str(incident_id))
            if row is not None and row.is_open:
                incident_service.record_event(
                    db,
                    row,
                    "note",
                    channel="portal",
                    actor_user_id=user.id,
                    detail=f"family acknowledged alert ({user.email or 'family'})",
                    commit=True,
                )
        return {
            "id": str(found.get("id")),
            "title": str(found.get("title") or "Alert"),
            "body": str(found.get("body") or ""),
            "severity": str(found.get("severity") or "info"),
            "read_at": _parse_dt(found.get("read_at")),
            "created_at": _parse_dt(found.get("created_at")) or _now(),
        }

    @staticmethod
    def _push_alert(
        db: Session,
        elder: Elder,
        *,
        title: str,
        body: str,
        severity: str = "info",
        incident_id: str | None = None,
        actor_email: str | None = None,
        self_notice: bool = False,
        only_email: str | None = None,
    ) -> dict:
        hub = _hub(elder)
        alert = {
            "id": _new_id("fal"),
            "title": title,
            "body": body,
            "severity": severity,
            "read_at": None,
            "created_at": _iso(),
        }
        if incident_id:
            alert["incident_id"] = str(incident_id)
        if actor_email:
            # The family member who caused it does not get told about it.
            alert["actor_email"] = str(actor_email)
            if self_notice:
                alert["self_notice"] = True
        if only_email:
            # Shown to this one family member only (an SOS they pressed, family not told yet).
            alert["only_email"] = str(only_email)
        hub["alerts"] = [alert, *hub["alerts"]][:100]
        _save_hub(db, elder, hub)
        return alert

    @staticmethod
    def list_messages(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        rows = [m for m in _hub(elder)["messages"] if isinstance(m, dict)]
        rows.sort(key=lambda m: str(m.get("created_at") or ""))
        return [
            {
                "id": str(m.get("id") or ""),
                "body": str(m.get("body") or ""),
                "sender_role": str(m.get("sender_role") or "family"),
                "sender_name": str(m.get("sender_name") or ""),
                "created_at": _parse_dt(m.get("created_at")) or _now(),
            }
            for m in rows
        ]

    @staticmethod
    def send_message(db: Session, user: User, body: str) -> dict:
        text = (body or "").strip()
        if not text:
            raise_bad_request("Message required")
        if len(text) > 4000:
            raise_bad_request("Message too long")
        elder = ElderPortalService.get_linked_elder(db, user)
        hub = _hub(elder)
        msg = {
            "id": _new_id("fmsg"),
            "body": text,
            "sender_role": "family",
            "sender_name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "sender_user_id": user.id,
            "created_at": _iso(),
        }
        hub["messages"] = [*hub["messages"], msg][-200:]
        _save_hub(db, elder, hub)
        FamilyCareHubService._notify_staff_new_message(db, elder, msg)
        # No alert to the family about their own message (Phase 2E #64): the
        # Messages page confirms it inline.
        return {
            "id": msg["id"],
            "body": msg["body"],
            "sender_role": msg["sender_role"],
            "sender_name": msg["sender_name"],
            "created_at": _parse_dt(msg["created_at"]) or _now(),
        }

    @staticmethod
    def _serialize_incident(row: dict, elder_name: str | None = None) -> dict:
        # Family-facing: old device rows carried device/hub/MAC codes in the note.
        note = sanitize_family_alert(
            "",
            str(row.get("note") or ""),
            elder_name=elder_name,
            created_at=_parse_dt(row.get("created_at")),
        )[1]
        return {
            "id": str(row.get("id") or ""),
            "kind": str(row.get("kind") or "sos"),
            "note": note,
            "status": str(row.get("status") or "open"),
            "created_at": _parse_dt(row.get("created_at")) or _now(),
            "resolved_at": _parse_dt(row.get("resolved_at")),
            "resolved_by": str(row["resolved_by"]) if row.get("resolved_by") else None,
        }

    @staticmethod
    def _resolve_incident_in_hub(
        hub: dict,
        incident_id: str,
        *,
        status: str = "resolved",
        resolved_by: str = "family",
    ) -> dict | None:
        status_n = str(status or "resolved").strip().lower()
        if status_n not in ("resolved", "closed"):
            raise_bad_request("status must be resolved or closed")
        for row in hub.get("incidents") or []:
            if not isinstance(row, dict) or str(row.get("id")) != str(incident_id):
                continue
            current = str(row.get("status") or "open").lower()
            if current in ("closed", "resolved"):
                return row
            row["status"] = status_n
            row["resolved_at"] = _iso()
            row["resolved_by"] = resolved_by
            return row
        return None

    @staticmethod
    def list_incidents(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        me = str(user.email or "").lower()
        # An SOS the care team has not passed on yet: only the member who pressed it sees it.
        rows = [
            i for i in _hub(elder)["incidents"]
            if isinstance(i, dict) and (not i.get("held_for") or str(i["held_for"]).lower() == me)
        ]
        rows.sort(key=lambda i: str(i.get("created_at") or ""), reverse=True)
        name = getattr(elder, "first_name", None)
        return [FamilyCareHubService._serialize_incident(i, name) for i in rows]

    @staticmethod
    def resolve_incident(
        db: Session,
        user: User,
        incident_id: str,
        *,
        status: str = "resolved",
    ) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        from app.livewell import incident_service
        from app.models.incident import FAMILY_OUTCOME

        # The DB row is the source of truth; resolving it mirrors back into the
        # hub JSON (legacy rows without a DB twin fall through to the JSON path).
        row = incident_service.find_by_legacy_id(db, elder.id, incident_id)
        if row is not None:
            incident_service.resolve(
                db,
                row,
                outcome=FAMILY_OUTCOME,
                user=user,
                by_family=True,
                status=status,
                resolved_by_label=user.email or "family",
            )
            db.refresh(elder)
        hub = _hub(elder)
        found = FamilyCareHubService._resolve_incident_in_hub(
            hub,
            incident_id,
            status=status,
            resolved_by=user.email or "family",
        )
        if not found:
            raise_not_found("Incident not found")
        for alert in hub.get("alerts") or []:
            if (
                isinstance(alert, dict)
                and str(alert.get("incident_id") or "") == str(incident_id)
                and not alert.get("read_at")
            ):
                alert["read_at"] = _iso()
        _save_hub(db, elder, hub)
        return FamilyCareHubService._serialize_incident(found)

    @staticmethod
    def raise_sos(db: Session, user: User, note: str | None = None) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        from app.livewell import incident_service

        legacy_id = _new_id("fsos")
        text = (note or "").strip() or "Family requested urgent help"
        row, _created = incident_service.open_incident(
            db,
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            kind="family_sos",
            severity="critical",
            source="family",
            note=f"{text} (raised by {user.email})",
            legacy_id=legacy_id,
        )
        FamilyCareHubService._alert_staff_now(db, elder, user, text, row)
        from app.livewell import sos_siren

        is_elder = (user.portal_relationship or "").strip().lower() == "self"
        sos_siren.start(db, row, source="elder" if is_elder else "family", presser=user)
        # Care team first (owner, 29 Oct): the rest of the family hears only when staff
        # confirm it and tap "Notify family" (sos_siren.notify_family).
        held = sos_siren.family_held(row)
        db.refresh(elder)
        hub = _hub(elder)
        incident = {
            "id": legacy_id,
            "kind": "sos",
            "note": text,
            "status": "open",
            "created_at": _iso(),
            "created_by": user.email,
            "incident_db_id": row.id,
        }
        if held:
            incident["held_for"] = user.email
        hub["incidents"] = [incident, *hub["incidents"]][:50]
        _save_hub(db, elder, hub)
        if held:
            return FamilyCareHubService._serialize_incident(incident)
        FamilyCareHubService._push_alert(
            db,
            elder,
            title=with_brand("SOS sent to LiveWell360 team"),
            body=incident["note"],
            severity="critical",
            incident_id=incident["id"],
            actor_email=user.email,
            self_notice=True,
        )
        return FamilyCareHubService._serialize_incident(incident)

    @staticmethod
    def _alert_staff_now(db: Session, elder: Elder, user: User, text: str, row) -> None:
        """A family SOS reaches the care team at once (email + SMS), not after the 5-minute escalation."""
        import logging

        from app.livewell import incident_service
        from app.livewell.email_notifications import email_staff
        from app.services.notifications.alert_email import format_alert_time, render_iot_alert_sms

        try:
            name = f"{elder.first_name} {elder.last_name}".strip()
            who = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
            phone = elder.emergency_contact_phone or elder.phone or ""
            email_staff(
                db, elder, "alert",
                f"SOS from {name}'s family",
                f"{who} pressed SOS at {format_alert_time()}: {text}\n"
                + (f"Call the family now: {phone}\n" if phone else "")
                + "Acknowledge in KushAlaya Ops → Alerts so the family knows someone has it.",
                path=f"/kushalaya/alerts?open={row.id}",
            )
            tree = incident_service.escalation_contacts(db, elder.tenant_id)
            phones = incident_service._merge(incident_service.phone_alert_recipients(), tree["level1_phones"])
            if phones:
                import threading

                body = render_iot_alert_sms(title="Family SOS", client_name=name)
                # Texts go out off the request thread so a slow SMS provider never delays the family's SOS.
                threading.Thread(
                    target=incident_service.deliver_phone, args=(phones,), kwargs={"body": body}, daemon=True
                ).start()
        except Exception:
            db.rollback()
            logging.getLogger(__name__).exception("family_sos_staff_alert_failed elder=%s", elder.id)

    @staticmethod
    def get_prefs(db: Session, user: User) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        prefs = {**_default_prefs(), **_hub(elder)["prefs"]}
        return {
            "digest_enabled": bool(prefs.get("digest_enabled", True)),
            "digest_channel": str(prefs.get("digest_channel") or "whatsapp"),
            "digest_cadence": str(prefs.get("digest_cadence") or "weekly"),
            "digest_timezone": str(prefs.get("digest_timezone") or "Asia/Kolkata"),
        }

    @staticmethod
    def update_prefs(db: Session, user: User, payload: dict) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        hub = _hub(elder)
        prefs = {**_default_prefs(), **hub["prefs"]}
        if "digest_enabled" in payload:
            prefs["digest_enabled"] = bool(payload.get("digest_enabled"))
        channel = payload.get("digest_channel")
        if channel is not None:
            ch = str(channel).strip().lower()
            if ch not in ("whatsapp", "email", "none"):
                raise_bad_request("digest_channel must be whatsapp, email, or none")
            prefs["digest_channel"] = ch
        cadence = payload.get("digest_cadence")
        if cadence is not None:
            cd = str(cadence).strip().lower()
            if cd not in ("daily", "weekly"):
                raise_bad_request("digest_cadence must be daily or weekly")
            prefs["digest_cadence"] = cd
        tz = payload.get("digest_timezone")
        if tz is not None:
            prefs["digest_timezone"] = str(tz).strip() or "Asia/Kolkata"
        hub["prefs"] = prefs
        _save_hub(db, elder, hub)
        return FamilyCareHubService.get_prefs(db, user)

    @staticmethod
    def digest_preview(db: Session, user: User) -> dict:
        from app.livewell.visit_service import HomeSafetyVisitService

        elder = ElderPortalService.get_linked_elder(db, user)
        prefs = FamilyCareHubService.get_prefs(db, user)
        sh = _safe_home(elder)
        score = sh.get("safety_score") if isinstance(sh.get("safety_score"), dict) else {}
        total = score.get("total")
        next_visits = HomeSafetyVisitService.list_upcoming_for_family(db, user, limit=3)
        open_alerts = FamilyCareHubService.unread_alert_count(elder)
        lines = [
            with_brand(f"LiveWell360 care digest for {elder.first_name} {elder.last_name}"),
            f"Times: {_zone_words(prefs['digest_timezone'])} · {prefs['digest_cadence']}",
        ]
        care_status = HomeSafetyVisitService.care_status_for_elder(db, elder)
        # The same status as Home (app/livewell/family_status.py), so the digest
        # never says "no change" while Home lists what the carer noted.
        from app.livewell.family_status import family_status

        status = family_status(db, elder)
        lines.append(f"Status: {elder.first_name} · {status['status_text']}")
        if status["checks_text"]:
            lines.append(f"Last visit: {status['checks_text']}")
        elif status["changes"]:
            lines.append(status["changes_text"])
        elif care_status.get("change_summary"):
            lines.append(care_status["change_summary"])
        snap = care_status.get("snapshot") or {}
        if status["mobility"]:
            lines.append(f"Mobility: {status['mobility']}")
        if snap.get("medication") and snap.get("medication") != "none":
            lines.append(f"Medication: {snap['medication']}")
        if snap.get("open_request"):
            lines.append(f"Open request: {snap['open_request']}")
        if total is not None:
            lines.append(f"{safety_score_name()}: {total}/100")
        if next_visits:
            v = next_visits[0]
            when = v["visited_at"]
            when_s = when.strftime("%d %b %Y") if hasattr(when, "strftime") else str(when)[:10]
            lines.append(f"Next visit: {v['visit_type']} on {when_s}" + (f" ({v['staff_name']})" if v.get("staff_name") else ""))
        else:
            lines.append("Next visit: none scheduled")
        lines.append(f"Unread alerts: {open_alerts}")
        plan = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
        items = plan.get("items") if isinstance(plan.get("items"), list) else []
        open_n = sum(1 for i in items if isinstance(i, dict) and str(i.get("status") or "open") != "done")
        lines.append(f"Open plan items: {open_n}")
        lines.append(care_status.get("disclaimer") or with_brand("Care coordination update — not a medical diagnosis."))
        lines.append(with_brand("— LiveWell360 Family"))
        return {
            "text": "\n".join(lines),
            "prefs": prefs,
            "senior_name": f"{elder.first_name} {elder.last_name}".strip(),
            "care_status": care_status,
        }

    @staticmethod
    def care_feed(db: Session, user: User, *, limit: int = 40) -> list[dict]:
        from app.livewell.visit_service import HomeSafetyVisitService

        elder = ElderPortalService.get_linked_elder(db, user)
        feed: list[dict] = []
        visit_ids: set[str] = set()
        # "<Visit> completed" notices echo a care visit already listed below.
        job_done: set[tuple[str, str]] = set()

        def _day(value) -> str:
            dt = _parse_dt(value)
            return dt.date().isoformat() if dt else ""

        from app.livewell.visit_reports import family_photo_items

        def _photos(ids) -> dict:
            # Same access checks as the visit page; at most 4 per visit keeps the feed small.
            try:
                items = family_photo_items(db, elder, ids) if ids else []
            except Exception:  # pragma: no cover - photos never break the feed
                items = []
            return {"photos": items[:4], "photo_count": len(items)}

        for v in HomeSafetyVisitService.list_for_family(db, user, days=120):
            visit_ids.add(str(v["id"]))
            feed.append(
                {
                    "id": f"visit-{v['id']}",
                    "kind": "visit",
                    "title": v.get("visit_type") or "Visit",
                    "body": v.get("summary") or v.get("wellness_notes") or "",
                    "created_at": v.get("visited_at"),
                    "href": f"/kushalaya/family/visits/{v['id']}",
                    **_photos(v.get("photo_ids")),
                }
            )

        # KushLife / care visits (care jobs): each opens its own report.
        try:
            from app.livewell.care_jobs import family_jobs

            _upcoming, recent_jobs = family_jobs(db, user)
        except Exception:  # pragma: no cover - the feed never fails on this
            recent_jobs = []
        for j in recent_jobs:
            if str(j.get("status")) != "completed":
                continue
            title = str(j.get("visit_type") or "Care visit")
            job_done.add((f"{title} completed".lower(), _day(j.get("visited_at"))))
            feed.append(
                {
                    "id": f"visit-{j['id']}",
                    "kind": "visit",
                    "title": title,
                    "body": j.get("family_message") or j.get("summary") or "",
                    "created_at": _parse_dt(j.get("visited_at")) or _now(),
                    "href": f"/kushalaya/family/visits/{j['id']}",
                    **_photos(_job_photo_ids(db, j.get("id"))),
                }
            )

        sh = _safe_home(elder)
        for row in sh.get("wellness_reports") or []:
            if not isinstance(row, dict):
                continue
            # A wellness report made from a visit ("wr_<visit id>") is the same event.
            rid = str(row.get("id") or "")
            if rid.startswith("wr_") and rid[3:] in visit_ids:
                continue
            feed.append(
                {
                    "id": f"wellness-{row.get('id')}",
                    "kind": "wellness",
                    "title": row.get("visit_type") or "Wellness update",
                    "body": row.get("summary") or "",
                    "created_at": _parse_dt(row.get("date")) or _now(),
                    "href": "/kushalaya/family/wellness",
                }
            )

        for a in FamilyCareHubService.list_alerts(db, user, include_info=True)[:20]:
            # These alerts are system echoes of something already in the feed as
            # a richer entry (the request itself, the visit itself). Showing both
            # made every request appear twice in the timeline.
            if a["title"] in FEED_ECHO_ALERT_TITLES:
                continue
            if (a["title"].lower(), _day(a["created_at"])) in job_done:
                continue
            feed.append(
                {
                    "id": f"alert-{a['id']}",
                    # Info rows are updates, not alerts (Phase 2E).
                    "kind": "alert" if _is_alert(a) else "update",
                    "title": a["title"],
                    "body": a["body"],
                    "created_at": a["created_at"],
                    "href": "/kushalaya/family/alerts" if _is_alert(a) else None,
                }
            )

        me = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        for m in FamilyCareHubService.list_messages(db, user)[-15:]:
            sender = (m.get("sender_name") or "").strip()
            if m.get("sender_role") == "family" and sender in (me, user.email):
                who = "you"
            else:
                who = sender or ("your care team" if m.get("sender_role") == "team" else "your family")
            feed.append(
                {
                    "id": f"msg-{m['id']}",
                    "kind": "message",
                    "title": f"Message from {who}",
                    "body": m["body"],
                    "created_at": m["created_at"],
                    "href": "/kushalaya/family/messages",
                }
            )

        from app.livewell.family_service_requests import FamilyServiceRequestService

        for req in FamilyServiceRequestService.list_for_family(db, user)[:15]:
            feed.append(
                {
                    "id": f"req-{req['id']}",
                    "kind": "request",
                    "title": f"{req['service_label']} · {req['status']}",
                    "body": req.get("notes") or "Family service request",
                    "created_at": req.get("created_at") or req.get("preferred_at"),
                    "href": "/kushalaya/family/schedule",
                }
            )

        feed.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return feed[:limit]

    @staticmethod
    def _circle_members(db: Session, elder: Elder) -> tuple[list[User], int | None]:
        """Family logins for this elder (link rows plus legacy users.elder_id) and
        the primary member's user id."""
        from app.livewell.family_elder_access import links_for_elder, primary_link_for_elder

        primary = primary_link_for_elder(db, elder.id)
        linked_ids = [row.user_id for row in links_for_elder(db, elder.id)]
        query = db.query(User).filter(
            User.role == ELDER_PORTAL,
            User.tenant_id == elder.tenant_id,
            User.status == "ACTIVE",
        )
        if linked_ids:
            query = query.filter((User.id.in_(linked_ids)) | (User.elder_id == elder.id))
        else:
            query = query.filter(User.elder_id == elder.id)
        members = query.order_by(User.id).all()
        primary_id = primary.user_id if primary else (members[0].id if members else None)
        return members, primary_id

    @staticmethod
    def list_circle(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        members, primary_id = FamilyCareHubService._circle_members(db, elder)
        return [
            {
                "id": m.id,
                "email": m.email,
                "first_name": m.first_name,
                "last_name": m.last_name,
                "portal_relationship": m.portal_relationship or "family",
                "is_you": m.id == user.id,
                "is_primary": m.id == primary_id,
            }
            for m in members
        ]

    @staticmethod
    def remove_member(db: Session, user: User, member_id: int) -> dict:
        """Primary member takes someone out of the circle for the active elder."""
        from app.livewell.family_elder_access import is_primary_member, unlink_family_user

        elder = ElderPortalService.get_linked_elder(db, user)
        if not is_primary_member(db, user, elder):
            raise WorkforceHTTPError(
                "Only the primary family member can remove people", status_code=403
            )
        if int(member_id) == user.id:
            raise_bad_request(
                "You cannot remove yourself - ask the care team to change the primary member"
            )
        members, _primary_id = FamilyCareHubService._circle_members(db, elder)
        member = next((m for m in members if m.id == int(member_id)), None)
        if member is None:
            raise_not_found("Family member not found")
        unlink_family_user(db, member, elder)
        FamilyCareHubService._push_alert(
            db,
            elder,
            title="Family member removed",
            body=f"{member.first_name} ({member.email}) no longer has access to the family app.",
            severity="info",
        )
        return {"id": member.id, "email": member.email, "removed": True}

    @staticmethod
    def invite_member(
        db: Session,
        user: User,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        portal_relationship: str = "family",
        elder_id: int | None = None,
    ) -> dict:
        from app.livewell.family_elder_access import is_primary_member, list_linked_elders

        # The invite is for one senior only: the one selected in the app.
        if elder_id is not None:
            elder = next((e for e in list_linked_elders(db, user) if e.id == int(elder_id)), None)
            if elder is None:
                raise WorkforceHTTPError("Access denied for this senior", status_code=403)
        else:
            elder = ElderPortalService.get_linked_elder(db, user)
        if not is_primary_member(db, user, elder):
            raise WorkforceHTTPError(
                "Only the primary family member can invite people", status_code=403
            )
        email_n = (email or "").strip().lower()
        if not email_n or "@" not in email_n:
            raise_bad_request("Valid email required")
        if len(password or "") < 8:
            raise_bad_request("Password must be at least 8 characters")
        if db.query(User).filter(User.email == email_n).first():
            raise_conflict("Email already registered")

        rel = (portal_relationship or "family").strip() or "family"
        member = User(
            email=email_n,
            password_hash=hash_password(password),
            first_name=(first_name or "").strip() or "Family",
            last_name=(last_name or "").strip() or "Member",
            role=ELDER_PORTAL,
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            portal_relationship=rel,
        )
        db.add(member)
        db.flush()
        from app.livewell.family_elder_access import ensure_family_elder_link

        # Only the selected senior — never the inviter's other seniors.
        link = ensure_family_elder_link(db, member, elder)
        link.invited_by_user_id = user.id
        link.is_primary = False
        db.commit()
        db.refresh(member)
        FamilyCareHubService._push_alert(
            db,
            elder,
            title="Family member added",
            body=f"{member.first_name} ({member.email}) can now use the family app.",
            severity="info",
        )
        return {
            "id": member.id,
            "email": member.email,
            "first_name": member.first_name,
            "last_name": member.last_name,
            "portal_relationship": member.portal_relationship,
            "is_you": False,
        }

    @staticmethod
    def list_documents(db: Session, user: User) -> list[dict]:
        from app.livewell.document_types import (
            FAMILY_UPLOAD_TYPE_CODES,
            HOME_SAFETY_SIGNED_DOC,
            SIGNED_DOC_FORM_CODES,
        )
        from app.models.document import Document

        elder = ElderPortalService.get_linked_elder(db, user)
        allowed = (
            set(SIGNED_DOC_FORM_CODES)
            | {HOME_SAFETY_SIGNED_DOC}
            | set(FAMILY_UPLOAD_TYPE_CODES)
        )
        rows = (
            db.query(Document)
            .filter(
                Document.tenant_id == elder.tenant_id,
                Document.entity_type == "elder",
                Document.entity_id == elder.id,
                Document.document_type.in_(list(allowed)),
            )
            .order_by(Document.uploaded_at.desc())
            .limit(80)
            .all()
        )
        # Staff can file papers under the family categories too (client vault),
        # so "shared by you" is decided by who uploaded, not by the type.
        uploader_ids = {d.uploaded_by_user_id for d in rows if d.uploaded_by_user_id}
        family_uploaders = {
            uid
            for (uid,) in db.query(User.id).filter(User.id.in_(uploader_ids or {-1}), User.role == "ELDER_PORTAL")
        }
        out = []
        for d in rows:
            out.append(
                {
                    "id": d.id,
                    "title": d.document_name or d.file_name or d.document_type,
                    "document_type": d.document_type,
                    "created_at": d.uploaded_at,
                    "url": f"/api/v1/home-safety/family/documents/{d.id}/file",
                    "uploaded_by_family": d.uploaded_by_user_id in family_uploaders
                    if d.uploaded_by_user_id
                    else d.document_type in FAMILY_UPLOAD_TYPE_CODES,
                }
            )
        return out

    @staticmethod
    def upload_document(
        db: Session,
        user: User,
        *,
        file_name: str,
        content: bytes,
        content_type: str,
        document_type: str,
        note: str | None = None,
    ) -> dict:
        """Family uploads a document (medical record, insurance, ID…).

        Saved against the elder with entity_type="elder", so it shows up in the
        ops documents view for that client without any extra wiring.
        """
        from app.core.config import settings
        from app.core.storage import get_storage
        from app.livewell.document_types import (
            FAMILY_UPLOAD_TYPE_CODES,
            FAMILY_UPLOAD_TYPE_LABELS,
        )
        from app.models.document import Document

        doc_type = (document_type or "").strip().upper()
        if doc_type not in FAMILY_UPLOAD_TYPE_CODES:
            raise_bad_request("Pick a document type")

        if not content:
            raise_bad_request("The file is empty")

        max_bytes = int(settings.MAX_UPLOAD_MB) * 1024 * 1024
        if len(content) > max_bytes:
            raise_bad_request(f"File is too large (limit {settings.MAX_UPLOAD_MB} MB)")

        mime = (content_type or "").split(";")[0].strip().lower()
        if mime not in FAMILY_UPLOAD_ALLOWED_MIME:
            # Deliberately an allowlist: these files are served back from our own
            # origin, so anything script-bearing (HTML, SVG) would be stored XSS.
            raise_bad_request("Upload a PDF, photo, or Word document")

        elder = ElderPortalService.get_linked_elder(db, user)
        safe_name = _safe_file_name(file_name, mime)

        storage = get_storage()
        storage_key, storage_url = storage.save(
            elder.tenant_id,
            "elder",
            elder.id,
            safe_name,
            content,
            mime,
        )

        label = FAMILY_UPLOAD_TYPE_LABELS.get(doc_type, "Document")
        doc = Document(
            tenant_id=elder.tenant_id,
            entity_type="elder",
            entity_id=elder.id,
            document_type=doc_type,
            document_name=(note or "").strip()[:255] or label,
            file_name=safe_name,
            storage_key=storage_key,
            storage_url=storage_url,
            mime_type=mime,
            file_size_bytes=len(content),
            uploaded_by_user_id=user.id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # No alert to the family about their own upload (Phase 2E #64).

        return {
            "id": doc.id,
            "title": doc.document_name or doc.file_name,
            "document_type": doc.document_type,
            "created_at": doc.uploaded_at,
            "url": f"/api/v1/home-safety/family/documents/{doc.id}/file",
            "uploaded_by_family": True,
        }

    @staticmethod
    def read_document_file(db: Session, user: User, document_id: int) -> tuple[bytes, str, str]:
        from app.livewell.document_types import (
            FAMILY_UPLOAD_TYPE_CODES,
            HOME_SAFETY_SIGNED_DOC,
            SIGNED_DOC_FORM_CODES,
        )
        from app.core.storage import get_storage
        from app.models.document import Document

        elder = ElderPortalService.get_linked_elder(db, user)
        allowed = (
            set(SIGNED_DOC_FORM_CODES)
            | {HOME_SAFETY_SIGNED_DOC}
            | set(FAMILY_UPLOAD_TYPE_CODES)
        )
        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.tenant_id == elder.tenant_id,
                Document.entity_type == "elder",
                Document.entity_id == elder.id,
                Document.document_type.in_(list(allowed)),
            )
            .first()
        )
        if not doc:
            raise_not_found("Document not found")
        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return content, mime or "application/octet-stream", doc.file_name or "document"

    # ----- Staff inbox (care team side of family messages) -----

    @staticmethod
    def _staff_display_name(user: User) -> str:
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email

    @staticmethod
    def _elder_for_staff(db: Session, user: User, elder_id: int) -> Elder:
        from app.core.rbac import assert_tenant_access, resolve_tenant_id

        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Client not found")
        assert_tenant_access(user, elder.tenant_id)
        tid = resolve_tenant_id(user)
        if tid is not None and elder.tenant_id != tid:
            raise_not_found("Client not found")
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder.id)
        return elder

    @staticmethod
    def _serialize_message(m: dict) -> dict:
        return {
            "id": str(m.get("id") or ""),
            "body": str(m.get("body") or ""),
            "sender_role": str(m.get("sender_role") or "family"),
            "sender_name": str(m.get("sender_name") or ""),
            "created_at": _parse_dt(m.get("created_at")) or _now(),
        }

    @staticmethod
    def list_messages_for_staff(elder: Elder) -> list[dict]:
        rows = [m for m in _hub(elder)["messages"] if isinstance(m, dict)]
        rows.sort(key=lambda m: str(m.get("created_at") or ""))
        return [FamilyCareHubService._serialize_message(m) for m in rows]

    @staticmethod
    def _unread_by_staff(hub: dict) -> int:
        seen = _parse_dt(hub.get("staff_read_at"))
        count = 0
        for m in hub["messages"]:
            if not isinstance(m, dict) or str(m.get("sender_role") or "family") != "family":
                continue
            if m.get("question_id"):
                continue  # "Call me" / "Ask about…" has its own row in Needs attention
            created = _parse_dt(m.get("created_at"))
            if created is not None and seen is not None and (created.tzinfo is None) != (seen.tzinfo is None):
                created, seen = (d if d.tzinfo else d.replace(tzinfo=timezone.utc) for d in (created, seen))
            if seen is None or created is None or created > seen:
                count += 1
        return count

    @staticmethod
    def staff_inbox(db: Session, tenant_id: int | None, elders: list[Elder] | None = None) -> list[dict]:
        """One row per elder that has a family thread: unread first, then newest activity.

        Pass ``elders`` when the caller already loaded them (the dashboard) to skip the query."""
        if elders is None:
            query = db.query(Elder)
            if tenant_id is not None:
                query = query.filter(Elder.tenant_id == tenant_id)
            elders = query.all()
        rows: list[dict] = []
        for elder in elders:
            hub = _hub(elder)
            messages = [m for m in hub["messages"] if isinstance(m, dict)]
            if not messages:
                continue
            messages.sort(key=lambda m: str(m.get("created_at") or ""))
            last = FamilyCareHubService._serialize_message(messages[-1])
            rows.append(
                {
                    "elder_id": elder.id,
                    "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
                    "message_count": len(messages),
                    "unread_count": FamilyCareHubService._unread_by_staff(hub),
                    "staff_read_at": _parse_dt(hub.get("staff_read_at")),
                    "last_message": last,
                }
            )
        rows.sort(key=lambda r: r["last_message"]["created_at"], reverse=True)
        rows.sort(key=lambda r: r["unread_count"] == 0)  # stable: keeps newest-first in each group
        return rows

    @staticmethod
    def staff_thread(db: Session, staff_user: User, elder_id: int) -> dict:
        elder = FamilyCareHubService._elder_for_staff(db, staff_user, elder_id)
        hub = _hub(elder)
        return {
            "elder_id": elder.id,
            "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
            "staff_read_at": _parse_dt(hub.get("staff_read_at")),
            "unread_count": FamilyCareHubService._unread_by_staff(hub),
            "messages": FamilyCareHubService.list_messages_for_staff(elder),
        }

    @staticmethod
    def mark_staff_read(db: Session, staff_user: User, elder_id: int) -> dict:
        elder = FamilyCareHubService._elder_for_staff(db, staff_user, elder_id)
        hub = _hub(elder)
        hub["staff_read_at"] = _iso()
        _save_hub(db, elder, hub)
        return {
            "elder_id": elder.id,
            "staff_read_at": _parse_dt(hub["staff_read_at"]),
            "unread_count": 0,
        }

    @staticmethod
    def mark_staff_unread(db: Session, staff_user: User, elder_id: int) -> dict:
        """Put the thread back to unread from the latest family message."""
        from datetime import timedelta

        elder = FamilyCareHubService._elder_for_staff(db, staff_user, elder_id)
        hub = _hub(elder)
        family = [
            _parse_dt(m.get("created_at"))
            for m in hub["messages"]
            if isinstance(m, dict) and str(m.get("sender_role") or "family") == "family"
        ]
        # Old rows may be naive (UTC); mixing them with aware ones breaks max().
        family = [d if d.tzinfo else d.replace(tzinfo=timezone.utc) for d in family if d is not None]
        hub["staff_read_at"] = (max(family) - timedelta(microseconds=1)).isoformat() if family else None
        _save_hub(db, elder, hub)
        return {
            "elder_id": elder.id,
            "staff_read_at": _parse_dt(hub["staff_read_at"]),
            "unread_count": FamilyCareHubService._unread_by_staff(hub),
        }

    @staticmethod
    def reply_message(db: Session, elder: Elder, staff_user: User, body: str) -> dict:
        text = (body or "").strip()
        if not text:
            raise_bad_request("Message required")
        if len(text) > 4000:
            raise_bad_request("Message too long")
        hub = _hub(elder)
        msg = {
            "id": _new_id("tmsg"),
            "body": text,
            "sender_role": "team",
            "sender_name": FamilyCareHubService._staff_display_name(staff_user),
            "sender_user_id": staff_user.id,
            "created_at": _iso(),
        }
        hub["messages"] = [*hub["messages"], msg][-200:]
        # Replying means the team has read everything above it.
        hub["staff_read_at"] = msg["created_at"]
        _save_hub(db, elder, hub)
        preview = text if len(text) <= 160 else text[:157].rstrip() + "..."
        FamilyCareHubService._push_alert(
            db,
            elder,
            title="Reply from your care team",
            body=preview,
            severity="info",
        )
        from app.livewell.email_notifications import email_family

        # The family member who wrote last always hears back, whatever their level.
        author = next(
            (m.get("sender_user_id") for m in reversed(hub["messages"]) if m.get("sender_role") == "family"),
            None,
        )
        author_user = db.get(User, author) if author else None
        email_family(
            db, elder, "reply", "Reply from your care team", preview, path="/messages",
            always=[author_user.email] if author_user and author_user.email else None,
        )
        return FamilyCareHubService._serialize_message(msg)

    @staticmethod
    def _staff_notification_recipients(db: Session, elder: Elder) -> list[str]:
        from app.core.rbac import CARE_MANAGER, TENANT_ADMIN

        staff = (
            db.query(User)
            .filter(
                User.tenant_id == elder.tenant_id,
                User.role.in_([CARE_MANAGER, TENANT_ADMIN]),
                User.status == "ACTIVE",
            )
            .order_by(User.id)
            .all()
        )
        seen: set[str] = set()
        out: list[str] = []
        for u in staff:
            addr = (u.email or "").strip()
            if addr and "@" in addr and addr.lower() not in seen:
                seen.add(addr.lower())
                out.append(addr)
        return out

    @staticmethod
    def _notify_staff_new_message(db: Session, elder: Elder, msg: dict) -> None:
        """Email the care managers / tenant admins. Never raises - a mail
        failure must not turn into a failed send for the family."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from app.livewell.email_notifications import email_staff

            name = f"{elder.first_name} {elder.last_name}".strip() or f"client #{elder.id}"
            body = (
                f"{msg.get('sender_name') or 'A family member'} wrote about {name}:\n"
                f"{msg.get('body') or ''}\n"
                "Reply from KushAlaya Ops → Messages."
            )
            email_staff(db, elder, "family_message", f"New message about {name}", body, path="/kushalaya/messages")
        except Exception:
            logger.exception("family_message_notify_failed elder=%s", elder.id)
