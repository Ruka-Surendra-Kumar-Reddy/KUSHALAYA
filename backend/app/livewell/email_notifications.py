"""Email notifications: one place that decides who gets which email.

Staff rules live on the agency (``tenant.workflow_config["email_notifications"]``):
for each event, on/off, whether the client's manager and/or all admins get it,
and extra addresses. Family choices live on the client
(``elder.custom_attributes["email_prefs"]``): which kinds of email the family
gets and extra addresses (a sibling abroad without a portal login).

Every email is sent on a background thread with a plain-text and a branded
HTML part. The provider is NOTIFICATION_EMAIL_PROVIDER; with "log" nothing
leaves the server until SMTP settings are added.
"""

import contextvars
import html
import logging
import re
import threading
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

KEY = "email_notifications"
PREFS_KEY = "email_prefs"
OPS_URL = settings.PUBLIC_OPS_URL.rstrip("/")
FAMILY_URL = settings.PUBLIC_FAMILY_URL.rstrip("/")

STAFF_EVENTS = [
    {"key": "family_message", "label": "A family sends a message"},
    {"key": "family_question", "label": "A family asks for a call or asks about a visit"},
    {"key": "request", "label": "A family asks for a visit, service, product or assessment"},
    {"key": "request_cancelled", "label": "A family cancels a request"},
    {"key": "approval", "label": "A discount needs an admin's approval"},
    {"key": "alert", "label": "SOS and safety alerts"},
    {"key": "device", "label": "A wearable band is offline or its battery is low"},
    {"key": "visit_done", "label": "A visit or assessment is completed"},
    {"key": "visit_location", "label": "A visit is logged away from the client's home"},
    {"key": "hazard", "label": "A hazard is spotted at a home"},
    {"key": "incident_serious", "label": "A serious incident is reported (fall with injury, medication error)"},
    {"key": "visit_missed", "label": "A visit is missed (not started 3 hours after its time)"},
    {"key": "kushlife_flag", "label": "KushLife flag (something changed on a visit)"},
    {"key": "enquiry", "label": "A new enquiry from the website"},
    {"key": "reassessment", "label": "Daily list of assessments to book (6-monthly)"},
    {"key": "contract", "label": "A contract needs a KushAlaya signature, or is signed"},
    {"key": "lead_new", "label": "A new lead is added"},
    {"key": "assessment_booked", "label": "An assessment is booked"},
    {"key": "assessment_done", "label": "An assessment is completed"},
    {"key": "vendor_new", "label": "A new vendor is added"},
    {"key": "lead_stuck", "label": "A lead stays too long in one phase"},
]
FAMILY_EVENTS = [
    {"key": "visit", "label": "Visits booked, changed or cancelled"},
    {"key": "visit_live", "label": "Care team on the way / arrived"},
    {"key": "report", "label": "Visit and assessment reports"},
    {"key": "weekly_summary", "label": "KushLife weekly summary (Mondays, once the care manager approves it)"},
    {"key": "monthly_letter", "label": "Monthly KushLife letter (once the care manager approves it)"},
    {"key": "request", "label": "Requests received"},
    {"key": "reply", "label": "Replies from the care team"},
    {"key": "safety", "label": "Safety concerns found at home"},
    {"key": "order", "label": "Orders booked, done or cancelled"},
]
# Events whose sensible default differs from "manager + admins": only an admin can
# approve a discount, so the manager who asked does not need the email.
# Band offline / battery is the client's manager's job; admins can opt in.
# "Call me" / "Ask about…" goes to the client's care manager (admins if there is none).
_BUSINESS_ALERT = {"manager": False, "whatsapp": True}
#: Open board phases; Won and Lost are never chased.
STUCK_PHASES = ("NEW", "ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE", "FOLLOW_UP_1", "FOLLOW_UP_2")
STUCK_DEFAULT_DAYS = 3
STUCK_DEFAULT_REPEAT_DAYS = 2
_STAFF_DEFAULTS = {
    "lead_new": _BUSINESS_ALERT, "assessment_booked": _BUSINESS_ALERT, "assessment_done": _BUSINESS_ALERT,
    "vendor_new": _BUSINESS_ALERT, "lead_stuck": _BUSINESS_ALERT,
    "approval": {"manager": False}, "device": {"admins": False}, "family_question": {"admins": False}}
_STAFF_KEYS = {e["key"] for e in STAFF_EVENTS}
_FAMILY_KEYS = {e["key"] for e in FAMILY_EVENTS}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_emails(values) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        addr = str(raw or "").strip()
        if _EMAIL.match(addr) and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    return out[:20]


# --- agency (staff) rules -------------------------------------------------


def _default_staff_rule() -> dict:
    return {"enabled": True, "manager": True, "admins": True, "whatsapp": False, "extra": []}


def _days(value, default: int) -> int:
    try:
        return min(max(int(value), 1), 365)
    except (TypeError, ValueError):
        return default


def _lead_stuck(raw: dict) -> dict:
    days = raw.get("days") or {}
    return {
        "repeat_days": _days(raw.get("repeat_days"), STUCK_DEFAULT_REPEAT_DAYS),
        "days": {s: _days(days.get(s), STUCK_DEFAULT_DAYS) for s in STUCK_PHASES},
    }


def get_rules(tenant: Tenant | None) -> dict:
    raw = ((tenant.workflow_config or {}) if tenant else {}).get(KEY) or {}
    staff_raw = raw.get("staff") or {}
    family_raw = raw.get("family") or {}
    staff = {}
    for e in STAFF_EVENTS:
        r = {**_default_staff_rule(), **_STAFF_DEFAULTS.get(e["key"], {}), **(staff_raw.get(e["key"]) or {})}
        staff[e["key"]] = {
            "enabled": bool(r["enabled"]),
            "manager": bool(r["manager"]),
            "admins": bool(r["admins"]),
            "whatsapp": bool(r["whatsapp"]),
            "extra": _clean_emails(r["extra"]),
        }
    family = {e["key"]: bool(family_raw.get(e["key"], True)) for e in FAMILY_EVENTS}
    return {"staff": staff, "family": family, "lead_stuck": _lead_stuck(raw.get("lead_stuck") or {})}


def save_rules(db: Session, tenant: Tenant, body: dict) -> dict:
    current = get_rules(tenant)
    for key, r in (body.get("staff") or {}).items():
        if key in _STAFF_KEYS and isinstance(r, dict):
            merged = {**current["staff"][key], **r}
            current["staff"][key] = {
                "enabled": bool(merged["enabled"]),
                "manager": bool(merged["manager"]),
                "admins": bool(merged["admins"]),
                "whatsapp": bool(merged["whatsapp"]),
                "extra": _clean_emails(merged["extra"]),
            }
    for key, on in (body.get("family") or {}).items():
        if key in _FAMILY_KEYS:
            current["family"][key] = bool(on)
    stuck = body.get("lead_stuck")
    if isinstance(stuck, dict):
        current["lead_stuck"] = _lead_stuck({
            "repeat_days": stuck.get("repeat_days", current["lead_stuck"]["repeat_days"]),
            "days": {**current["lead_stuck"]["days"], **(stuck.get("days") or {})},
        })
    cfg = dict(tenant.workflow_config or {})
    cfg[KEY] = current
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    return current


def provider_status() -> dict:
    from app.services.notifications import channel_config

    saved = channel_config.active("email")
    if saved:
        return {"provider": "smtp (settings)", "connected": True, "from_email": saved.get("from_email") or saved["username"]}
    name = (settings.NOTIFICATION_EMAIL_PROVIDER or "log").lower()
    ready = name not in {"", "log"}
    if name == "smtp":
        ready = bool(settings.SMTP_USERNAME and settings.SMTP_PASSWORD)
    return {
        "provider": name,
        "connected": ready,
        "from_email": settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME or "",
    }


# --- client (family) choices ----------------------------------------------


def get_family_prefs(elder: Elder) -> dict:
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    raw = attrs.get(PREFS_KEY) or {}
    off = [k for k in raw.get("off") or [] if k in _FAMILY_KEYS]
    return {"extra": _clean_emails(raw.get("extra")), "off": off}


def save_family_prefs(db: Session, elder: Elder, body: dict) -> dict:
    prefs = get_family_prefs(elder)
    if "extra" in body:
        prefs["extra"] = _clean_emails(body.get("extra"))
    if "off" in body:
        prefs["off"] = [k for k in body.get("off") or [] if k in _FAMILY_KEYS]
    attrs = dict(elder.custom_attributes or {})
    attrs[PREFS_KEY] = prefs
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    return prefs


def family_logins(db: Session, elder: Elder) -> list[str]:
    ids = {u.id for u in db.query(User).filter(User.role == "ELDER_PORTAL", User.elder_id == elder.id).all()}
    try:
        from app.models.family_elder_link import FamilyElderLink

        ids |= {r[0] for r in db.query(FamilyElderLink.user_id).filter(FamilyElderLink.elder_id == elder.id).all()}
    except Exception:  # table missing on older databases
        pass
    rows = db.query(User).filter(User.id.in_(ids or {-1}), User.status == "ACTIVE").all()
    return _clean_emails(sorted(u.email for u in rows if u.email))


# --- who gets it ------------------------------------------------------------


def staff_recipients(db: Session, elder: Elder, event: str) -> list[str]:
    tenant = db.get(Tenant, elder.tenant_id)
    rule = get_rules(tenant)["staff"].get(event)
    if event == "alert" and rule:
        # Safety alerts always reach the client's manager and the admins (Settings can only add people).
        rule = {**rule, "enabled": True, "manager": True, "admins": True}
    if not rule or not rule["enabled"]:
        return []
    q = db.query(User).filter(User.tenant_id == elder.tenant_id, User.status == "ACTIVE")
    out: list[str] = []
    if rule["manager"] and elder.manager_user_id:
        out += [u.email for u in q.filter(User.id == elder.manager_user_id).all()]
    # No manager on the client: admins hear about it so nothing is missed.
    if rule["admins"] or (rule["manager"] and not elder.manager_user_id):
        out += [u.email for u in q.filter(User.role == "TENANT_ADMIN").all()]
    return _clean_emails(out + rule["extra"])


def agency_recipients(db: Session, tenant_id: int, event: str) -> list[str]:
    """For events with no client yet (website enquiries): every active admin and care manager
    the rule asks for, plus the extra addresses. "Client's manager" means all managers here."""
    rule = get_rules(db.get(Tenant, tenant_id))["staff"].get(event)
    if not rule or not rule["enabled"]:
        return []
    roles = []
    if rule["admins"]:
        roles.append("TENANT_ADMIN")
    if rule["manager"]:
        roles.append("CARE_MANAGER")
    rows = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.status == "ACTIVE", User.role.in_(roles or ["-"]))
        .all()
    )
    return _clean_emails([u.email for u in rows] + rule["extra"])


def family_recipients(db: Session, elder: Elder, event: str) -> list[str]:
    tenant = db.get(Tenant, elder.tenant_id)
    if event in _FAMILY_KEYS and not get_rules(tenant)["family"].get(event, True):
        return []
    prefs = get_family_prefs(elder)
    if event in prefs["off"]:
        return []
    everyone = _clean_emails(family_logins(db, elder) + prefs["extra"])
    # Each person's level (everything / important / emergencies) — K2 #88.
    from app.livewell.family_contacts import EMERGENCY_EVENTS, level_allows

    if event in EMERGENCY_EVENTS:
        return everyone  # an emergency reaches everyone, whatever their level
    levels = _safe_contact_prefs(db, elder)
    if levels is None:
        return everyone  # can't read levels: treat everyone as "everything"
    return [a for a in everyone if level_allows((levels.get(a.lower()) or {}).get("level"), event)]


def _safe_contact_prefs(db: Session, elder: Elder) -> dict[str, dict] | None:
    """prefs_by_email inside a SAVEPOINT, so a failed query can't abort the caller's
    (Postgres) transaction. None on error."""
    from app.livewell.family_contacts import prefs_by_email

    try:
        with db.begin_nested():
            return prefs_by_email(db, elder)
    except Exception:
        logger.exception("family_contact_prefs_failed elder=%s", elder.id)
        return None


def family_timezones(db: Session, elder: Elder) -> dict[str, str]:
    """email (lower) → timezone, for family members who set one."""
    prefs = _safe_contact_prefs(db, elder) or {}
    return {k: v["timezone"] for k, v in prefs.items()}


# --- sending ----------------------------------------------------------------


def render_html(title: str, body: str, *, link: str, link_label: str) -> str:
    paras = "".join(
        f'<p style="margin:0 0 12px;line-height:1.55">{html.escape(p)}</p>' for p in body.split("\n") if p.strip()
    )
    return f"""<!doctype html><html><body style="margin:0;background:#f3f6fa;font-family:Arial,Helvetica,sans-serif;color:#24364d">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:16px;overflow:hidden">
<tr><td style="background:#0e2a4f;padding:18px 24px;color:#fff;font-size:18px;font-weight:bold">KushAlaya</td></tr>
<tr><td style="padding:24px">
<h1 style="margin:0 0 14px;font-size:20px;color:#0e2a4f">{html.escape(title)}</h1>
{paras}
<p style="margin:20px 0 0"><a href="{html.escape(link)}" style="display:inline-block;background:#2f6fd6;color:#fff;text-decoration:none;font-weight:bold;padding:11px 20px;border-radius:10px">{html.escape(link_label)}</a></p>
</td></tr>
<tr><td style="padding:14px 24px;background:#f8fafc;color:#64748b;font-size:12px">You get this email because you are on the KushAlaya notification list. Change what you get in the portal settings.</td></tr>
</table></td></tr></table></body></html>"""


def _deliver(recipients: list[str], subject: str, text: str, page: str) -> None:
    from app.services.notifications import get_email_provider

    provider = get_email_provider()
    for to in recipients:
        try:
            result = provider.send(to=to, subject=subject, body=text, html=page)
            if not getattr(result, "success", True):
                logger.warning("email_notify_failed to=%s detail=%s", to, getattr(result, "detail", ""))
        except Exception:
            logger.exception("email_notify_failed to=%s", to)


# The page an email's button opens and who it is about. Set by email_staff /
# email_family / notify_family around send(), so send() keeps its simple signature.
_CONTEXT: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar("email_context", default=("", ""))


# email (lower) → timezone of family readers; times written with
# family_contacts.email_time() are shown in each reader's own timezone.
_TZ: contextvars.ContextVar[dict] = contextvars.ContextVar("email_timezones", default={})


@contextmanager
def email_context(path: str = "", who: str = "", timezones: dict[str, str] | None = None):
    token = _CONTEXT.set((path or "", who or ""))
    tz_token = _TZ.set(dict(timezones or {}))
    try:
        yield
    finally:
        _TZ.reset(tz_token)
        _CONTEXT.reset(token)


def staff_path(elder: Elder | None, tab: str = "") -> str:
    """The client's page in ops (optionally on a tab: timeline, orders, alerts, devices…)."""
    if not elder:
        return ""
    return f"/kushalaya/customers/{elder.id}" + (f"?tab={tab}" if tab else "")


def _subject(title: str, who: str) -> str:
    """Subjects say what happened and for whom: "Visit completed — Lakshmi"."""
    if who and who.lower() not in title.lower():
        title = f"{title} — {who}"
    return f"KushAlaya: {title}"


def send(recipients: list[str], title: str, body: str, *, family: bool, background: bool = True) -> None:
    if not recipients:
        return
    path, who = _CONTEXT.get()
    base, label = (FAMILY_URL, "Open the family portal") if family else (OPS_URL, "Open KushAlaya Ops")
    link = base + (path if path.startswith("/") else "")
    if family and path.startswith("/track/"):
        label = "Track live"  # the caregiver / care manager on the way: live map, no login
    if family and path.startswith("/sign/"):
        label = "Open the contract"  # no-login signing link (contracts.py)
    from app.livewell.family_contacts import render_times

    tz_map = _TZ.get() if family else {}
    groups: dict[str, list[str]] = {}
    for to in recipients:
        groups.setdefault(tz_map.get(to.lower()) or "Asia/Kolkata", []).append(to)
    for tz_name, group in groups.items():
        t_title, t_body = render_times(title, tz_name), render_times(body, tz_name)
        subject = _subject(t_title, who)
        text = f"{t_body}\n\n{label}: {link}"
        page = render_html(t_title, t_body, link=link, link_label=label)
        if background:
            threading.Thread(target=_deliver, args=(group, subject, text, page), daemon=True).start()
        else:
            _deliver(group, subject, text, page)


def _full_name(elder: Elder) -> str:
    return f"{elder.first_name or ''} {elder.last_name or ''}".strip()


def email_staff(db: Session, elder: Elder, event: str, title: str, body: str, *, path: str | None = None) -> None:
    """Email the staff who follow ``event``. The button opens ``path`` in ops
    (default: the client's page); the subject names the client."""
    try:
        with email_context(staff_path(elder) if path is None else path, _full_name(elder)):
            send(staff_recipients(db, elder, event), title, body, family=False)
    except Exception:
        logger.exception("email_staff_failed elder=%s event=%s", elder.id, event)


def email_family(
    db: Session, elder: Elder, event: str, title: str, body: str, *, path: str = "", always: list[str] | None = None
) -> None:
    """``always``: addresses that get it whatever their level (e.g. the person being replied to)."""
    try:
        to = family_recipients(db, elder, event)
        have = {a.lower() for a in to}
        to = [a for a in _clean_emails(always or []) if a.lower() not in have] + to
        with email_context(path, (elder.first_name or "").strip(), family_timezones(db, elder)):
            send(to, title, body, family=True)
    except Exception:
        logger.exception("email_family_failed elder=%s event=%s", elder.id, event)
