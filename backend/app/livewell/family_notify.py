"""Tell the family: portal alert, plus email, SMS and WhatsApp.

The portal alert is written in the request. Email / SMS / WhatsApp go out on a
background thread so a slow provider never delays the app. Each channel uses
the configured provider (NOTIFICATION_*_PROVIDER); "log" just records it, so
nothing is sent until the owner adds Zoho SMTP and MSG91 settings on the server.
"""

import logging
import threading

from sqlalchemy.orm import Session

from app.models.elder import Elder
from app.models.user import User

logger = logging.getLogger(__name__)


def _family_contacts(db: Session, elder: Elder) -> tuple[list[str], list[str]]:
    """(emails, phones) of the family: portal logins for this client + the emergency contact."""
    users = db.query(User).filter(User.role == "ELDER_PORTAL", User.status == "ACTIVE")
    ids = {u.id for u in users.filter(User.elder_id == elder.id).all()}
    try:
        from app.models.family_elder_link import FamilyElderLink

        ids |= {r[0] for r in db.query(FamilyElderLink.user_id).filter(FamilyElderLink.elder_id == elder.id).all()}
    except Exception:  # table missing on older databases
        pass
    emails = sorted({u.email for u in db.query(User).filter(User.id.in_(ids or {-1})).all() if u.email})
    phones = {p for p in [elder.emergency_contact_phone] if p}
    return emails, sorted(phones)


def _send(emails: list[str], phones: list[str], subject: str, body: str) -> None:
    from app.services.notifications import get_email_provider, get_sms_provider, get_whatsapp_provider

    for to in emails:
        try:
            get_email_provider().send(to=to, subject=subject, body=body)
        except Exception:
            logger.exception("family_notify_email_failed to=%s", to)
    text = f"{subject}: {body}"
    for to in phones:
        try:
            get_sms_provider().send(to=to, body=text)
        except Exception:
            logger.exception("family_notify_sms_failed to=%s", to)
        try:
            get_whatsapp_provider().send_text(to=to, body=text)
        except Exception:
            logger.exception("family_notify_whatsapp_failed to=%s", to)


# Texts (SMS + WhatsApp) cost money and wake people up: only for things that can't wait.
# Everything else goes to the portal and email, which follow the family's email choices.
TEXT_EVENTS = {"missed", "sos"}


def notify_family(
    db: Session,
    elder: Elder,
    title: str,
    body: str,
    *,
    event: str = "visit",
    background: bool = True,
    actor_email: str | None = None,
    path: str = "",
) -> None:
    from app.livewell.family_care_hub import FamilyCareHubService
    from app.livewell.family_contacts import render_times

    # actor_email: the family member who caused it does not see it in the portal.
    # Times (family_contacts.email_time) show in IST in the portal; emails use each reader's timezone.
    FamilyCareHubService._push_alert(
        db, elder, title=render_times(title), body=render_times(body), severity="info", actor_email=actor_email
    )
    from app.livewell.email_notifications import email_context, family_recipients, family_timezones, send

    try:
        emails = family_recipients(db, elder, event)
        _, phones = _family_contacts(db, elder)
        timezones = family_timezones(db, elder)
    except Exception:
        logger.exception("family_notify_contacts_failed elder=%s", elder.id)
        return
    try:
        # path: the family page the email's button opens (e.g. "/schedule").
        with email_context(path, (elder.first_name or "").strip(), timezones):
            send(emails, title, body, family=True, background=background)
    except Exception:  # a failed email must never fail the action
        logger.exception("family_notify_email_failed elder=%s", elder.id)
    if phones and event in TEXT_EVENTS:
        title, body = render_times(title), render_times(body)
        subject = f"KushAlaya: {title}"
        if background:
            threading.Thread(target=_send, args=([], phones, subject, body), daemon=True).start()
        else:
            _send([], phones, subject, body)


def notify_manager(
    db: Session, elder: Elder, subject: str, body: str, *, event: str = "request", path: str | None = None
) -> None:
    """Email the staff who follow this event (Settings → Email notifications)."""
    from app.livewell.email_notifications import email_staff

    email_staff(db, elder, event, subject, body, path=path)
