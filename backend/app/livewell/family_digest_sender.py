"""Family care digest sender — turns the digest *preferences* into deliveries.

The family portal lets a household choose a cadence (daily / weekly), a
channel (whatsapp / email / none) and a timezone, and shows a text preview
(``FamilyCareHubService.digest_preview``). Until this module nothing sent that
text. ``run_family_digest_send`` is the hourly job: for every elder whose next
send slot (08:00 local, Monday for weekly) has passed since the last send, it
renders the same preview and delivers it through the configured provider.

Delivery state lives next to the preferences in
``elder.custom_attributes.safe_home.family_hub.prefs``:

    digest_last_sent_at   ISO timestamp of the last attempt that was delivered
    digest_last_result    {"at", "status", "channel", "recipients", "detail"}

Family users carry no phone number, so WhatsApp goes to the elder record's
phones (emergency contact first, then the elder's own). With no phone on file
the digest falls back to email to every family member's sign-in address.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.rbac import ELDER_PORTAL
from app.livewell.brand import with_brand
from app.livewell.family_care_hub import FamilyCareHubService, _hub, _save_hub
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.user import User
from app.services.notifications import (
    DeliveryResult,
    DeliveryStatus,
    WhatsAppTemplateMessage,
    get_email_provider,
    get_whatsapp_provider,
    normalize_phone,
)

logger = logging.getLogger(__name__)

# Local send time. Weekly digests go out on Monday morning; daily ones every
# morning. Both are evaluated against the household's own timezone.
DIGEST_SEND_HOUR = 8
DIGEST_WEEKLY_WEEKDAY = 0  # Monday
DEFAULT_TIMEZONE = "Asia/Kolkata"
WHATSAPP_TEMPLATE_NAME = "family_care_digest"

LAST_SENT_KEY = "digest_last_sent_at"
LAST_RESULT_KEY = "digest_last_result"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _zone(name: str | None):
    try:
        return ZoneInfo((name or "").strip() or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        pass
    try:
        return ZoneInfo(DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        # No tz database at all (bare Windows without `tzdata`): IST is fixed
        # offset, so the default household timezone still works.
        return timezone(timedelta(hours=5, minutes=30), "IST")


def latest_send_slot(cadence: str, tz_name: str | None, now: datetime) -> datetime:
    """Most recent scheduled send instant (UTC) at or before `now`."""
    zone = _zone(tz_name)
    local_now = now.astimezone(zone)
    slot = local_now.replace(hour=DIGEST_SEND_HOUR, minute=0, second=0, microsecond=0)
    if slot > local_now:
        slot -= timedelta(days=1)
    if (cadence or "weekly").lower() == "weekly":
        back = (slot.weekday() - DIGEST_WEEKLY_WEEKDAY) % 7
        slot -= timedelta(days=back)
    return slot.astimezone(timezone.utc)


def digest_is_due(prefs: dict, now: datetime) -> bool:
    if not prefs.get("digest_enabled", True):
        return False
    channel = str(prefs.get("digest_channel") or "whatsapp").lower()
    if channel == "none":
        return False
    cadence = str(prefs.get("digest_cadence") or "weekly").lower()
    if cadence not in ("daily", "weekly"):
        return False
    slot = latest_send_slot(cadence, prefs.get("digest_timezone"), now)
    last_sent = _parse_dt(prefs.get(LAST_SENT_KEY))
    return last_sent is None or last_sent < slot


@dataclass
class DigestDelivery:
    elder_id: int
    tenant_id: int
    status: str
    channel: str
    recipients: list[str] = field(default_factory=list)
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "elder_id": self.elder_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "channel": self.channel,
            "recipients": list(self.recipients),
            "detail": self.detail,
        }


def family_members_for_elder(db: Session, elder: Elder) -> list[User]:
    """Family portal users linked to this elder (join table or legacy users.elder_id)."""
    linked_ids = {
        row.user_id
        for row in db.query(FamilyElderLink).filter(FamilyElderLink.elder_id == elder.id).all()
    }
    q = db.query(User).filter(User.role == ELDER_PORTAL, User.status == "ACTIVE")
    members: dict[int, User] = {}
    for user in q.filter(User.elder_id == elder.id).all():
        members[user.id] = user
    if linked_ids:
        for user in q.filter(User.id.in_(sorted(linked_ids))).all():
            members[user.id] = user
    return [members[k] for k in sorted(members)]


def whatsapp_phones_for_elder(elder: Elder) -> list[str]:
    out: list[str] = []
    for raw in (elder.emergency_contact_phone, elder.phone):
        phone = normalize_phone(raw)
        if phone and phone not in out:
            out.append(phone)
    return out


def _preview_user(elder: Elder, members: list[User]) -> User | None:
    """digest_preview renders for a family user's *active* elder, so pick one
    whose active elder is this one."""
    for m in members:
        if m.elder_id == elder.id:
            return m
    return None


def _send_whatsapp(to: str, text: str) -> DeliveryResult:
    provider = get_whatsapp_provider()
    result = provider.send_text(to, text)
    if result.status == DeliveryStatus.FAILED:
        # Providers without free-text (Meta stub, log) accept an approved template.
        result = provider.send_template(
            to,
            WhatsAppTemplateMessage(
                template_name=WHATSAPP_TEMPLATE_NAME,
                body_params=(text,),
            ),
        )
    return result


def _send_email(to: str, subject: str, text: str) -> DeliveryResult:
    return get_email_provider().send(to, subject, text)


def _record(db: Session, elder: Elder, delivery: DigestDelivery, *, sent_at: datetime) -> None:
    hub = _hub(elder)
    prefs = dict(hub.get("prefs") or {})
    if delivery.status in (DeliveryStatus.SENT.value, DeliveryStatus.LOGGED.value):
        prefs[LAST_SENT_KEY] = sent_at.isoformat()
    prefs[LAST_RESULT_KEY] = {
        "at": sent_at.isoformat(),
        "status": delivery.status,
        "channel": delivery.channel,
        "recipients": list(delivery.recipients),
        "detail": delivery.detail,
    }
    hub["prefs"] = prefs
    _save_hub(db, elder, hub)


def send_digest_for_elder(
    db: Session,
    elder: Elder,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> DigestDelivery | None:
    """Render and deliver one elder's digest if it is due. Returns None when skipped."""
    now = now or _now()
    hub = _hub(elder)
    prefs = dict(hub.get("prefs") or {})
    if not force and not digest_is_due(prefs, now):
        return None

    members = family_members_for_elder(db, elder)
    channel = str(prefs.get("digest_channel") or "whatsapp").lower()
    if not members:
        delivery = DigestDelivery(
            elder_id=elder.id,
            tenant_id=elder.tenant_id,
            status=DeliveryStatus.SKIPPED.value,
            channel=channel,
            detail="No family portal members linked to this elder",
        )
        _record(db, elder, delivery, sent_at=now)
        return delivery

    preview_user = _preview_user(elder, members)
    if preview_user is None:
        delivery = DigestDelivery(
            elder_id=elder.id,
            tenant_id=elder.tenant_id,
            status=DeliveryStatus.SKIPPED.value,
            channel=channel,
            detail="No family member has this elder as their active profile",
        )
        _record(db, elder, delivery, sent_at=now)
        return delivery

    try:
        preview = FamilyCareHubService.digest_preview(db, preview_user)
    except Exception as exc:  # render failures must not stop the batch
        logger.exception("family_digest_render_failed elder=%s", elder.id)
        delivery = DigestDelivery(
            elder_id=elder.id,
            tenant_id=elder.tenant_id,
            status=DeliveryStatus.FAILED.value,
            channel=channel,
            detail=f"Could not render digest: {exc}"[:300],
        )
        _record(db, elder, delivery, sent_at=now)
        return delivery

    text = str(preview.get("text") or "").strip()
    senior = str(preview.get("senior_name") or f"{elder.first_name} {elder.last_name}").strip()
    subject = with_brand(f"LiveWell360 care digest — {senior}")

    results: list[tuple[str, DeliveryResult]] = []
    used_channel = channel
    if channel == "whatsapp":
        phones = whatsapp_phones_for_elder(elder)
        if phones:
            for phone in phones:
                results.append((phone, _send_whatsapp(phone, text)))
        else:
            used_channel = "email"
    if used_channel == "email":
        for member in members:
            if member.email:
                results.append((member.email, _send_email(member.email, subject, text)))

    if not results:
        delivery = DigestDelivery(
            elder_id=elder.id,
            tenant_id=elder.tenant_id,
            status=DeliveryStatus.SKIPPED.value,
            channel=used_channel,
            detail="No recipient address on file",
        )
        _record(db, elder, delivery, sent_at=now)
        return delivery

    delivered = [to for to, r in results if r.success]
    statuses = {r.status for _, r in results}
    if DeliveryStatus.SENT in statuses:
        status = DeliveryStatus.SENT.value
    elif DeliveryStatus.LOGGED in statuses:
        status = DeliveryStatus.LOGGED.value
    else:
        status = DeliveryStatus.FAILED.value
    detail = "; ".join(
        f"{to}: {r.status.value}" + (f" ({r.detail})" if r.detail and not r.success else "")
        for to, r in results
    )[:500]
    delivery = DigestDelivery(
        elder_id=elder.id,
        tenant_id=elder.tenant_id,
        status=status,
        channel=used_channel,
        recipients=delivered,
        detail=detail,
    )
    _record(db, elder, delivery, sent_at=now)
    return delivery


def run_family_digest_send(
    db: Session,
    *,
    tenant_id: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Hourly job body: send every due digest. Idempotent within a send slot."""
    now = now or _now()
    q = db.query(Elder).filter(Elder.status == "ACTIVE")
    if tenant_id is not None:
        q = q.filter(Elder.tenant_id == int(tenant_id))
    deliveries: list[dict] = []
    checked = 0
    for elder in q.order_by(Elder.id).all():
        checked += 1
        try:
            delivery = send_digest_for_elder(db, elder, now=now)
        except Exception:
            logger.exception("family_digest_send_failed elder=%s", elder.id)
            db.rollback()
            continue
        if delivery is not None:
            deliveries.append(delivery.as_dict())
    counts: dict[str, int] = {}
    for d in deliveries:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    return {
        "elders_checked": checked,
        "digests_due": len(deliveries),
        "sent": counts.get(DeliveryStatus.SENT.value, 0) + counts.get(DeliveryStatus.LOGGED.value, 0),
        "failed": counts.get(DeliveryStatus.FAILED.value, 0),
        "skipped": counts.get(DeliveryStatus.SKIPPED.value, 0),
        "deliveries": deliveries,
    }
