"""Send a GST invoice to the customer the moment it is issued (owner decision
2026-11-01): email with a download link, WhatsApp ``invoice_ready`` with the PDF as
the document header, and ``payment_received`` for the payment itself.

The PDF link is a signed, expiring URL (no login), because WhatsApp fetches the
document itself and families should not have to sign in to open a bill.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.tax_invoice import TaxInvoice

logger = logging.getLogger(__name__)

SHARE_DAYS = 30

# Variable order of the approved Meta templates (MSG91 account, 2026-10-29).
# invoice_ready : {{1}} invoice no · {{2}} date · {{3}} billed to · {{4}} amount · {{5}} status/due
# payment_received : {{1}} invoice no · {{2}} amount · {{3}} date · {{4}} payment reference
INVOICE_READY_TEMPLATE = "invoice_ready"
PAYMENT_RECEIVED_TEMPLATE = "payment_received"


def _rupees(paise: int) -> str:
    whole, frac = divmod(int(paise), 100)
    return f"₹{whole:,}" + (f".{frac:02d}" if frac else "")


def share_token(inv: TaxInvoice, *, days: int = SHARE_DAYS) -> str:
    from jose import jwt

    from app.core.security import ALGORITHM, SECRET_KEY

    payload = {
        "sub": str(inv.id),
        "type": "invoice",
        "exp": datetime.now(timezone.utc) + timedelta(days=days),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def invoice_from_share_token(db: Session, token: str) -> TaxInvoice | None:
    from jose import JWTError, jwt

    from app.core.security import ALGORITHM, SECRET_KEY

    try:
        payload = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "invoice":
        return None
    try:
        inv_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    return db.get(TaxInvoice, inv_id)


def shared_pdf_path(inv: TaxInvoice) -> str:
    return f"/api/v1/business/invoices/shared/{share_token(inv)}"


def shared_pdf_url(inv: TaxInvoice) -> str:
    from app.livewell.email_notifications import OPS_URL

    return OPS_URL + shared_pdf_path(inv)


def _file_name(inv: TaxInvoice) -> str:
    return f"{(inv.number or 'invoice').replace('/', '-')}.pdf"


def _date(inv: TaxInvoice) -> str:
    when = inv.issued_at or datetime.now(timezone.utc)
    return when.strftime("%d %b %Y")


def send_invoice(
    db: Session,
    inv: TaxInvoice,
    *,
    to_email: str | None,
    to_phone: str | None,
    name: str,
    payment_ref: str | None = None,
    background: bool = True,
) -> None:
    """Email + WhatsApp. Never raises."""
    if background:
        threading.Thread(
            target=_send_invoice_now,
            args=(inv.id, to_email, to_phone, name, payment_ref),
            daemon=True,
        ).start()
        return
    _send_invoice_now(inv.id, to_email, to_phone, name, payment_ref, db=db)


def _send_invoice_now(inv_id: int, to_email, to_phone, name, payment_ref, db: Session | None = None) -> dict:
    from app.core.database import SessionLocal

    own = db is None
    session = db or SessionLocal()
    results: dict[str, str] = {}
    try:
        inv = session.get(TaxInvoice, inv_id)
        # Wallet payments issue the invoice inside the payment transaction; the
        # background thread may run before that commit lands. Wait a little.
        for _ in range(10):
            if inv is not None or not own:
                break
            import time

            time.sleep(1)
            session.expire_all()
            inv = session.get(TaxInvoice, inv_id)
        if inv is None:
            return results
        amount = _rupees(inv.total_paise)
        date = _date(inv)
        number = inv.number or f"#{inv.id}"
        link = shared_pdf_url(inv)
        if to_email and "@" in to_email:
            try:
                from app.livewell import email_notifications

                title = "Tax invoice" if inv.doc_type == "tax_invoice" else "Invoice"
                body = (
                    f"Dear {name or 'Customer'},\n\n"
                    f"Thank you for your payment of {amount} on {date}.\n"
                    f"{title} {number} is attached as a link below (valid {SHARE_DAYS} days):\n{link}\n\n"
                    "Your invoices are always available in the family portal under Receipts."
                )
                with email_notifications.email_context(path=shared_pdf_path(inv)):
                    email_notifications.send([to_email], f"{title} {number} — KushAlaya", body, family=True)
                results["email"] = "sent"
            except Exception:  # noqa: BLE001
                logger.exception("invoice_email_failed invoice=%s", inv_id)
                results["email"] = "failed"
        if to_phone:
            try:
                from app.services.notifications.factory import get_whatsapp_provider
                from app.services.notifications.types import (
                    WhatsAppDocumentTemplate,
                    WhatsAppTemplateMessage,
                    normalize_phone,
                )

                to = normalize_phone(to_phone)
                if to:
                    wa = get_whatsapp_provider()
                    paid = wa.send_template(
                        to,
                        WhatsAppTemplateMessage(
                            template_name=PAYMENT_RECEIVED_TEMPLATE,
                            body_params=(number, amount, date, payment_ref or number),
                        ),
                    )
                    results["whatsapp_payment"] = paid.status.value.lower()
                    doc = wa.send_template(
                        to,
                        WhatsAppDocumentTemplate(
                            template_name=INVOICE_READY_TEMPLATE,
                            body_params=(number, date, name or "Customer", amount, "Paid"),
                            header_document_url=link,
                            header_filename=_file_name(inv),
                        ),
                    )
                    results["whatsapp_invoice"] = doc.status.value.lower()
                    if not doc.success:
                        # Template or document rejected: at least hand over the link.
                        wa.send_text(to, f"Your KushAlaya invoice {number} ({amount}, {date}): {link}")
            except Exception:  # noqa: BLE001
                logger.exception("invoice_whatsapp_failed invoice=%s", inv_id)
                results["whatsapp_invoice"] = "failed"
        return results
    finally:
        if own:
            session.close()


def send_invoice_to_family(db: Session, inv: TaxInvoice, *, payment_ref: str | None = None) -> None:
    """Every family login linked to the client gets it (wallet payments, service requests)."""
    from app.core.rbac import ELDER_PORTAL
    from app.livewell.family_elder_access import links_for_elder
    from app.models.elder import Elder
    from app.models.user import User

    elder = db.get(Elder, inv.elder_id)
    name = f"{getattr(elder, 'first_name', '') or ''} {getattr(elder, 'last_name', '') or ''}".strip() or "Customer"
    ids = [row.user_id for row in links_for_elder(db, inv.elder_id)]
    users = (
        db.query(User).filter(User.id.in_(ids), User.role == ELDER_PORTAL, User.status == "ACTIVE").all()
        if ids
        else []
    )
    for u in users:
        send_invoice(db, inv, to_email=u.email, to_phone=u.phone, name=name, payment_ref=payment_ref)
