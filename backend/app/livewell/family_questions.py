"""Family "Call me" / "Ask about…" (K2 #91).

A family member asks the care team to call (in a time window) or asks about a
visit or a KushLife flag. It lands in ops "Needs attention" and in the client's
Messages thread; the client's care manager gets an email (staff event
"family_question"). Staff reply or mark it done. Household-scoped: everyone in
the family circle of that client sees the question and the reply.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.responses import WorkforceHTTPError, raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.family_contact import DEFAULT_TIMEZONE, FamilyQuestion
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

KINDS = ("call_me", "ask")
DAYS = {"today": "Today", "tomorrow": "Tomorrow"}
WINDOWS = {
    "asap": ("As soon as you can", None),
    "morning": ("Morning", "9 AM–12 PM"),
    "afternoon": ("Afternoon", "12–5 PM"),
    "evening": ("Evening", "5–8 PM"),
}
HOURS = {"morning": (9, 12), "afternoon": (12, 17), "evening": (17, 20)}
IST = timezone(timedelta(hours=5, minutes=30))
MAX_OPEN_PER_PERSON = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _name(u: User | None) -> str:
    if not u:
        return ""
    return f"{u.first_name or ''} {u.last_name or ''}".strip() or (u.email or "")


def _elder_name(e: Elder) -> str:
    return f"{e.first_name or ''} {e.last_name or ''}".strip()


def _hm(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def ist_span(window: str, day: str, tz_name: str, now: datetime | None = None) -> str | None:
    """The family's call window in IST, for the care team ("9:30 PM–12:30 AM IST")."""
    if window not in HOURS:
        return None
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    d = (now or _now()).astimezone(zone).date() + timedelta(days=1 if day == "tomorrow" else 0)
    a, b = HOURS[window]
    start = datetime.combine(d, time(a), tzinfo=zone).astimezone(IST)
    end = datetime.combine(d, time(b), tzinfo=zone).astimezone(IST)
    return f"{_hm(start)}–{_hm(end)} IST"


def window_label(window: str, day: str, tz_name: str, now: datetime | None = None) -> str:
    title, hours = WINDOWS[window]
    if hours is None:
        return title
    if tz_name in (DEFAULT_TIMEZONE, "Asia/Calcutta"):
        return f"{DAYS.get(day, 'Today')} {title.lower()}, {hours} IST"
    zone = f"{tz_name.rsplit('/', 1)[-1].replace('_', ' ')} time"
    ist = ist_span(window, day, tz_name, now)
    return f"{DAYS.get(day, 'Today')} {title.lower()}, {hours} {zone}" + (f" ({ist})" if ist else "")


def _asker_phone(db: Session, q: FamilyQuestion, cache: dict) -> str:
    """The asker's phone (My details / family card), for staff to call back."""
    from app.livewell.family_contacts import contact_prefs

    key = ("phone", q.elder_id, q.asker_user_id)
    if key not in cache:
        elder = db.get(Elder, q.elder_id)
        asker = db.get(User, q.asker_user_id) if q.asker_user_id else None
        cache[key] = contact_prefs(db, elder, user=asker)["phone"] if elder and asker else ""
    return cache[key]


def serialize(db: Session, q: FamilyQuestion, *, viewer: User | None = None, users: dict | None = None) -> dict:
    """``viewer`` is the family member reading; staff reads pass none and also get the asker's phone."""
    users = users if users is not None else {}

    def who(uid):
        if uid is None:
            return ""
        if uid not in users:
            users[uid] = db.get(User, uid)
        return _name(users[uid])

    return {
        "id": q.id,
        "elder_id": q.elder_id,
        "kind": q.kind,
        "kind_label": "Call me" if q.kind == "call_me" else "Question",
        "body": q.body or "",
        "call_window": q.call_window or "",
        "visit_ref": q.visit_ref,
        "visit_label": q.visit_label or "",
        "flag_key": q.flag_key,
        "status": q.status,
        "asker_name": who(q.asker_user_id),
        "is_mine": bool(viewer and viewer.id == q.asker_user_id),
        "reply": q.reply or "",
        "replied_by_name": q.replied_by_name or "",
        "replied_at": _iso(q.replied_at),
        "done_at": _iso(q.done_at),
        "done_by_name": who(q.done_by_user_id),
        "created_at": _iso(q.created_at),
        **({} if viewer is not None else {"asker_phone": _asker_phone(db, q, users)}),
    }


def summary_text(q: FamilyQuestion) -> str:
    """One line for the Messages thread and emails."""
    about = f" about {q.visit_label}" if q.visit_label else ""
    if q.kind == "call_me":
        text = f"Please call me — {q.call_window or 'as soon as you can'}."
        if q.body:
            text += f" {q.body}"
        return text
    return f"Question{about}: {q.body or ''}".strip()


# --- family side ---------------------------------------------------------------


def list_for_family(db: Session, user: User) -> list[dict]:
    elder = ElderPortalService.get_linked_elder(db, user)
    rows = (
        db.query(FamilyQuestion)
        .filter(FamilyQuestion.elder_id == elder.id)
        .order_by(FamilyQuestion.created_at.desc(), FamilyQuestion.id.desc())
        .limit(50)
        .all()
    )
    users: dict = {}
    return [serialize(db, q, viewer=user, users=users) for q in rows]


def ask(db: Session, user: User, data: dict) -> dict:
    from app.livewell.email_notifications import email_staff, staff_path
    from app.livewell.family_care_hub import _hub, _iso as hub_iso, _new_id, _save_hub
    from app.livewell.family_contacts import contact_prefs

    elder = ElderPortalService.get_linked_elder(db, user)
    kind = str(data.get("kind") or "").strip()
    if kind not in KINDS:
        raise_bad_request("Choose Call me or Ask about")
    body = str(data.get("body") or "").strip()[:1000]
    window = None
    if kind == "call_me":
        w = str(data.get("window") or "asap").strip()
        day = str(data.get("day") or "today").strip()
        if w not in WINDOWS or day not in DAYS:
            raise_bad_request("Choose when we should call")
        tz_name = contact_prefs(db, elder, user=user)["timezone"]
        window = window_label(w, day, tz_name)
    elif not body:
        raise_bad_request("Write your question")
    open_mine = (
        db.query(FamilyQuestion)
        .filter(
            FamilyQuestion.elder_id == elder.id,
            FamilyQuestion.asker_user_id == user.id,
            FamilyQuestion.status == "open",
        )
        .count()
    )
    if open_mine >= MAX_OPEN_PER_PERSON:
        raise WorkforceHTTPError(
            "You already have several open questions — your care team will reply soon", status_code=409
        )
    q = FamilyQuestion(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        asker_user_id=user.id,
        kind=kind,
        body=body or None,
        call_window=window,
        visit_ref=(str(data.get("visit_ref") or "").strip()[:64] or None),
        visit_label=(str(data.get("visit_label") or "").strip()[:200] or None),
        flag_key=(str(data.get("flag_key") or "").strip()[:120] or None),
        status="open",
        created_at=_now(),
    )
    db.add(q)
    db.flush()

    # The same words in the client's Messages thread, so the whole family sees it.
    hub = _hub(elder)
    hub["messages"] = [
        *hub["messages"],
        {
            "id": _new_id("fmsg"),
            "body": summary_text(q),
            "sender_role": "family",
            "sender_name": _name(user),
            "sender_user_id": user.id,
            "question_id": q.id,
            "created_at": hub_iso(),
        },
    ][-200:]
    _save_hub(db, elder, hub)  # commits
    db.refresh(q)

    name = _elder_name(elder)
    who = _name(user)
    phone = contact_prefs(db, elder, user=user)["phone"]
    lines = [f"{who} ({user.email}{', ' + phone if phone else ''}) asked about {name}:", summary_text(q)]
    lines.append("Reply or mark it done from Dashboard → Needs attention, or on the client's page.")
    email_staff(
        db, elder, "family_question",
        ("Call request" if kind == "call_me" else "Family question") + f" — {name}",
        "\n".join(lines),
        path=staff_path(elder),
    )
    return serialize(db, q, viewer=user)


# --- staff side -----------------------------------------------------------------


def list_for_elder(db: Session, elder: Elder) -> list[dict]:
    rows = (
        db.query(FamilyQuestion)
        .filter(FamilyQuestion.elder_id == elder.id)
        .order_by(FamilyQuestion.created_at.desc(), FamilyQuestion.id.desc())
        .limit(50)
        .all()
    )
    users: dict = {}
    return [serialize(db, q, users=users) for q in rows]


def open_for_elders(db: Session, elders: list[Elder]) -> list[dict]:
    """Open questions for the dashboard's Needs attention (oldest first)."""
    names = {e.id: _elder_name(e) for e in elders}
    if not names:
        return []
    rows = (
        db.query(FamilyQuestion)
        .filter(FamilyQuestion.elder_id.in_(list(names)), FamilyQuestion.status == "open")
        .order_by(FamilyQuestion.created_at.asc())
        .limit(50)
        .all()
    )
    users: dict = {}
    return [{**serialize(db, q, users=users), "elder_name": names.get(q.elder_id, "")} for q in rows]


def _get(db: Session, elder: Elder, question_id: int) -> FamilyQuestion:
    q = db.get(FamilyQuestion, question_id)
    if not q or q.elder_id != elder.id:
        raise_not_found("Question not found")
    return q


def reply(db: Session, elder: Elder, staff: User, question_id: int, text: str, *, done: bool = True) -> dict:
    from app.livewell.email_notifications import email_context, family_recipients, family_timezones, send
    from app.livewell.family_care_hub import FamilyCareHubService, _hub, _iso as hub_iso, _new_id, _save_hub

    q = _get(db, elder, question_id)
    text = (text or "").strip()
    if not text:
        raise_bad_request("Write a reply")
    if len(text) > 4000:
        raise_bad_request("Reply too long")
    now = _now()
    q.reply = text
    q.replied_by_user_id = staff.id
    q.replied_by_name = _name(staff)
    q.replied_at = now
    if done:
        q.status = "done"
        q.done_by_user_id = staff.id
        q.done_at = now
    db.flush()

    hub = _hub(elder)
    hub["messages"] = [
        *hub["messages"],
        {
            "id": _new_id("tmsg"),
            "body": text,
            "sender_role": "team",
            "sender_name": _name(staff),
            "sender_user_id": staff.id,
            "question_id": q.id,
            "created_at": hub_iso(),
        },
    ][-200:]
    _save_hub(db, elder, hub)  # commits
    db.refresh(q)

    asker = db.get(User, q.asker_user_id)
    preview = text if len(text) <= 160 else text[:157].rstrip() + "..."
    FamilyCareHubService._push_alert(db, elder, title="Reply from your care team", body=preview, severity="info")
    # The person who asked always hears back; the rest of the family follows their level.
    to = family_recipients(db, elder, "reply")
    if asker and asker.email and asker.email.lower() not in {a.lower() for a in to}:
        to = [asker.email, *to]
    asked = summary_text(q)
    body = f"{_name(asker) or 'Your family'} asked: {asked}\n\nReply from {_name(staff)}:\n{text}"
    try:
        with email_context("/messages", (elder.first_name or "").strip(), family_timezones(db, elder)):
            send(to, "Reply from your care team", body, family=True)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("family_question_reply_email_failed q=%s", q.id)
    return serialize(db, q)


def mark_done(db: Session, elder: Elder, staff: User, question_id: int) -> dict:
    q = _get(db, elder, question_id)
    if q.status != "done":
        q.status = "done"
        q.done_by_user_id = staff.id
        q.done_at = _now()
        db.commit()
        db.refresh(q)
    return serialize(db, q)
