"""Family receipts — a read-only view over the wallet ledger.

A receipt is a successful `WalletTransaction` (top-up, service payment, refund,
adjustment) for the active elder's wallet, joined to the service request it
paid for when there is one. Nothing is stored: the ledger is the source of
truth, and the receipt number is derived from the row id so it never changes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.money import format_minor
from app.core.responses import raise_not_found
from app.livewell.wallet_service import WalletService
from app.models.elder import Elder
from app.models.family_wallet import WalletTransaction
from app.models.tenant import Tenant
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

RECEIPT_PREFIX = "KA"

_KIND_LABELS = {
    "recharge": "Wallet top-up",
    "debit": "Service payment",
    "refund": "Refunded to your KushAlaya wallet",
    "adjustment": "Adjustment",
}


def receipt_number(entry: WalletTransaction) -> str:
    when = entry.created_at or datetime.now(timezone.utc)
    return f"{RECEIPT_PREFIX}-{when.year}-{entry.id}"


def _service_requests(elder: Elder) -> dict[str, dict]:
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    sh = attrs.get("safe_home") if isinstance(attrs.get("safe_home"), dict) else {}
    rows = sh.get("service_requests") if isinstance(sh.get("service_requests"), list) else []
    return {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id")}


def _description(entry: WalletTransaction, request: dict | None) -> str:
    if entry.kind == "recharge":
        return entry.note or "Wallet top-up"
    label = None
    if request:
        from app.livewell.family_service_requests import SERVICE_LABELS

        label = SERVICE_LABELS.get(str(request.get("service_type") or ""), None)
    if entry.kind == "refund":
        return entry.note or (f"Refunded to your KushAlaya wallet — {label}" if label else "Refunded to your KushAlaya wallet")
    if entry.kind == "adjustment":
        return entry.note or "Wallet adjustment"
    return entry.note or label or "Service payment"


class FamilyReceiptService:
    @staticmethod
    def _serialize(
        entry: WalletTransaction,
        *,
        elder: Elder,
        tenant: Tenant | None,
        requests: dict[str, dict],
        payer: User | None,
    ) -> dict:
        request = None
        if entry.reference_type == "service_request" and entry.reference_id:
            request = requests.get(str(entry.reference_id))
        payment_reference = (
            entry.gateway_payment_id
            or entry.gateway_order_id
            or (entry.public_id if entry.kind == "recharge" else None)
        )
        return {
            "id": entry.public_id,
            "receipt_number": receipt_number(entry),
            "date": entry.created_at,
            "kind": entry.kind,
            "kind_label": _KIND_LABELS.get(entry.kind, entry.kind.title()),
            "description": _description(entry, request),
            "amount_minor": int(entry.amount_minor),
            "amount_display": format_minor(entry.amount_minor, entry.currency),
            "balance_after_minor": entry.balance_after_minor,
            "currency": entry.currency,
            "status": entry.status,
            "payment_method": (entry.gateway or ("wallet" if entry.kind != "recharge" else "stub")),
            "payment_reference": payment_reference,
            "service_request_id": str(request.get("id")) if request else None,
            "service_label": (
                _description(entry, request) if request and entry.kind == "debit" else None
            ),
            "service_status": str(request.get("status") or "") if request else None,
            "service_preferred_at": request.get("preferred_at") if request else None,
            "elder_id": elder.id,
            "elder_name": f"{elder.first_name} {elder.last_name}".strip(),
            "tenant_name": tenant.name if tenant else "",
            "paid_by": (
                f"{payer.first_name} {payer.last_name}".strip() or payer.email if payer else None
            ),
        }

    @staticmethod
    def _context(db: Session, user: User):
        elder = ElderPortalService.get_linked_elder(db, user)
        wallet = WalletService.get_or_create(db, elder)
        tenant = db.query(Tenant).filter(Tenant.id == elder.tenant_id).first()
        return elder, wallet, tenant, _service_requests(elder)

    @staticmethod
    def list_for_family(db: Session, user: User, *, limit: int = 100) -> list[dict]:
        elder, wallet, tenant, requests = FamilyReceiptService._context(db, user)
        rows = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet.id,
                WalletTransaction.status == "success",
            )
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        payer_ids = {r.created_by_user_id for r in rows if r.created_by_user_id}
        payers = (
            {u.id: u for u in db.query(User).filter(User.id.in_(list(payer_ids))).all()}
            if payer_ids
            else {}
        )
        return [
            FamilyReceiptService._serialize(
                r,
                elder=elder,
                tenant=tenant,
                requests=requests,
                payer=payers.get(r.created_by_user_id),
            )
            for r in rows
        ]

    @staticmethod
    def get_for_family(db: Session, user: User, receipt_id: str) -> dict:
        elder, wallet, tenant, requests = FamilyReceiptService._context(db, user)
        entry = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet.id,
                WalletTransaction.public_id == str(receipt_id),
                WalletTransaction.status == "success",
            )
            .first()
        )
        if entry is None:
            raise_not_found("Receipt not found")
        payer = (
            db.query(User).filter(User.id == entry.created_by_user_id).first()
            if entry.created_by_user_id
            else None
        )
        return FamilyReceiptService._serialize(
            entry, elder=elder, tenant=tenant, requests=requests, payer=payer
        )
