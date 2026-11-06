"""Self-service password setup for new logins (owner decision 2026-11-01).

Nobody types a password for someone else any more. A new staff member, family
member, caregiver or website customer gets a link by email and WhatsApp (SMS as
fallback) and chooses their own password. The link is the existing reset-token
flow with a longer life and a welcome screen.
"""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from app.core.rbac import ELDER_PORTAL
from app.models.user import User

logger = logging.getLogger(__name__)

SETUP_LINK_HOURS = 72


def random_password() -> str:
    """Unknown to everyone; the person sets their own via the link."""
    return secrets.token_urlsafe(24)


def portal_base(user: User) -> str:
    from app.livewell.email_notifications import FAMILY_URL, OPS_URL

    return FAMILY_URL if user.role == ELDER_PORTAL else OPS_URL


def setup_path(user: User) -> str:
    from app.services.auth_service import create_password_reset_token

    token = create_password_reset_token(user, minutes=SETUP_LINK_HOURS * 60)
    return f"/reset-password?token={token}&welcome=1"


def setup_link(user: User) -> str:
    return portal_base(user) + setup_path(user)


def send_account_setup(
    db: Session,
    user: User,
    *,
    phone: str | None = None,
    intro: str | None = None,
    subject: str = "Set up your KushAlaya login",
) -> dict:
    """Email + WhatsApp (+ SMS fallback) with the set-password link. Never raises:
    a failed message must not undo the account that was just created."""
    from app.livewell import email_notifications
    from app.services.notifications.factory import get_sms_provider, get_whatsapp_provider
    from app.services.notifications.types import normalize_phone

    name = (user.first_name or "").strip() or "there"
    path = setup_path(user)
    link = portal_base(user) + path
    intro = intro or "Your KushAlaya login is ready."
    family = user.role == ELDER_PORTAL
    results: dict[str, str] = {}

    if user.email and "@" in user.email:
        body = (
            f"Hello {name},\n\n{intro}\n\n"
            f"Set your password with this link (valid for {SETUP_LINK_HOURS} hours):\n{link}\n\n"
            "After that you can sign in with this email or your mobile number."
        )
        try:
            with email_notifications.email_context(path=path):
                delivered = email_notifications.send([user.email], subject, body, family=family, background=False)
            results["email"] = "failed" if delivered is False else "sent"
        except Exception:  # noqa: BLE001
            logger.exception("account_setup_email_failed user=%s", user.id)
            results["email"] = "failed"

    to = normalize_phone(phone or user.phone)
    if to:
        short = f"Hi {name}, {intro} Set your password here (valid {SETUP_LINK_HOURS} h): {link}"
        try:
            wa = get_whatsapp_provider().send_text(to, short)
            results["whatsapp"] = wa.status.value.lower()
        except Exception:  # noqa: BLE001
            logger.exception("account_setup_whatsapp_failed user=%s", user.id)
            results["whatsapp"] = "failed"
        if results.get("whatsapp") != "sent":
            try:
                sms = get_sms_provider().send(to, short)
                results["sms"] = sms.status.value.lower()
            except Exception:  # noqa: BLE001
                logger.exception("account_setup_sms_failed user=%s", user.id)
                results["sms"] = "failed"
    return results


def ensure_family_login(
    db: Session,
    elder,
    *,
    email: str | None,
    phone: str | None,
    first_name: str | None,
    last_name: str | None,
    relationship: str = "family",
) -> tuple[User | None, bool]:
    """A family-portal login for this client's contact (website purchase). Returns
    (user, created). Existing logins are linked, not duplicated. Does not commit."""
    from sqlalchemy import func

    from app.core.security import hash_password
    from app.livewell.family_elder_access import ensure_family_elder_link, primary_link_for_elder

    ident = (email or "").strip().lower()
    if not ident or "@" not in ident:
        return None, False
    user = db.query(User).filter(func.lower(User.email) == ident).first()
    created = False
    if user is None:
        user = User(
            email=ident,
            password_hash=hash_password(random_password()),
            first_name=(first_name or "").strip() or "Family",
            last_name=(last_name or "").strip() or "Member",
            role=ELDER_PORTAL,
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            phone=(phone or None),
            portal_relationship=relationship,
        )
        db.add(user)
        db.flush()
        created = True
    if user.role != ELDER_PORTAL or user.tenant_id != elder.tenant_id:
        # A staff address was used as the customer's contact — do not turn staff into family.
        return user, False
    link = ensure_family_elder_link(db, user, elder)
    if primary_link_for_elder(db, elder.id) is None or link.is_primary is None:
        link.is_primary = True
    return user, created
