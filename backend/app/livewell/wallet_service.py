"""Family wallet ledger.

Rules this module enforces, in order of importance:

1. Every balance change is an append-only `WalletTransaction`. Nothing ever
   edits a balance directly — a correction is a new `adjustment` row.
2. Every write carries an `idempotency_key` unique per tenant. Retried webhooks,
   double-tapped buttons and replayed requests return the original row instead
   of moving money twice.
3. The wallet row is locked for the read-modify-write on databases that support
   it; `version` is bumped so a lost update is detectable on SQLite (dev), where
   SELECT ... FOR UPDATE is a no-op.
4. Balance may never go negative — enforced here and by a CHECK constraint.

Amounts are integer minor units (paise). Callers pass whole rupees nowhere.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.family_wallet import (
    CREDIT_KINDS,
    DEBIT_KINDS,
    FamilyWallet,
    WalletTransaction,
)
from app.models.user import User


def _new_public_id() -> str:
    return f"wtx_{uuid.uuid4().hex[:12]}"


def _supports_row_lock(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and bind.dialect.name != "sqlite")


def _lock_wallet(db: Session, wallet_id: int) -> FamilyWallet:
    # populate_existing: the wallet is usually already in the session, and without it the
    # locked SELECT would hand back the stale in-memory balance.
    query = db.query(FamilyWallet).filter(FamilyWallet.id == wallet_id).populate_existing()
    if _supports_row_lock(db):
        query = query.with_for_update()
    wallet = query.first()
    if wallet is None:
        raise_not_found("Wallet not found")
    return wallet


class WalletService:
    """All money movement for the family prepaid wallet."""

    @staticmethod
    def get_or_create(db: Session, elder: Elder, *, commit: bool = True) -> FamilyWallet:
        wallet = (
            db.query(FamilyWallet)
            .filter(
                FamilyWallet.tenant_id == elder.tenant_id,
                FamilyWallet.elder_id == elder.id,
            )
            .first()
        )
        if wallet is not None:
            return wallet

        wallet = FamilyWallet(
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            balance_minor=0,
            currency="INR",
            status="active",
            version=0,
        )
        db.add(wallet)
        try:
            db.flush()
        except IntegrityError:
            # Concurrent create — the other writer won, use their row.
            db.rollback()
            wallet = (
                db.query(FamilyWallet)
                .filter(
                    FamilyWallet.tenant_id == elder.tenant_id,
                    FamilyWallet.elder_id == elder.id,
                )
                .first()
            )
            if wallet is None:
                raise
            return wallet
        if commit:
            db.commit()
            db.refresh(wallet)
        return wallet

    @staticmethod
    def find_existing_entry(
        db: Session,
        *,
        tenant_id: int,
        idempotency_key: str,
    ) -> WalletTransaction | None:
        return (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.tenant_id == tenant_id,
                WalletTransaction.idempotency_key == idempotency_key,
            )
            .first()
        )

    @staticmethod
    def record(
        db: Session,
        wallet: FamilyWallet,
        *,
        kind: str,
        amount_minor: int,
        idempotency_key: str,
        status: str = "success",
        reference_type: str | None = None,
        reference_id: str | None = None,
        gateway: str | None = None,
        gateway_order_id: str | None = None,
        gateway_payment_id: str | None = None,
        note: str | None = None,
        user: User | None = None,
        commit: bool = True,
    ) -> WalletTransaction:
        """Write one ledger entry and move the cached balance with it.

        `amount_minor` is always passed positive; `kind` decides the direction.
        A `pending` entry (an unconfirmed recharge) does not move the balance —
        only `success` does.
        """
        if amount_minor <= 0:
            raise_bad_request("Amount must be greater than zero")
        if kind not in CREDIT_KINDS | DEBIT_KINDS and kind != "adjustment":
            raise_bad_request("Unknown wallet transaction type")

        existing = WalletService.find_existing_entry(
            db,
            tenant_id=wallet.tenant_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing

        signed = -amount_minor if kind in DEBIT_KINDS else amount_minor

        locked = _lock_wallet(db, wallet.id)
        # A refund always goes back, even into a frozen wallet; nothing else moves a frozen one.
        if locked.status != "active" and kind != "refund":
            raise_bad_request("This wallet is frozen — contact the care team")

        balance_after: int | None = None
        if status == "success":
            balance_after = locked.balance_minor + signed
            if balance_after < 0:
                raise_bad_request("Not enough wallet balance")
            locked.balance_minor = balance_after
            locked.version = (locked.version or 0) + 1

        entry = WalletTransaction(
            public_id=_new_public_id(),
            tenant_id=locked.tenant_id,
            wallet_id=locked.id,
            kind=kind,
            amount_minor=signed,
            balance_after_minor=balance_after,
            currency=locked.currency,
            status=status,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            gateway=gateway,
            gateway_order_id=gateway_order_id,
            gateway_payment_id=gateway_payment_id,
            note=note,
            created_by_user_id=user.id if user is not None else None,
        )
        db.add(entry)

        try:
            db.flush()
        except IntegrityError:
            # Another writer used this idempotency key first — discard ours.
            db.rollback()
            winner = WalletService.find_existing_entry(
                db,
                tenant_id=wallet.tenant_id,
                idempotency_key=idempotency_key,
            )
            if winner is None:
                raise
            return winner

        # GST invoice / credit note for a paid order or service request, in this same
        # transaction so the invoice number rolls back with the payment (no gaps).
        from app.livewell.gst_invoices import on_wallet_entry

        on_wallet_entry(db, entry)

        if commit:
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def settle_pending(
        db: Session,
        entry: WalletTransaction,
        *,
        status: str,
        gateway_payment_id: str | None = None,
        commit: bool = True,
    ) -> WalletTransaction:
        """Move a pending recharge to success (crediting the balance) or failed.

        Safe to call repeatedly with the same outcome — a settled entry is
        returned untouched, so duplicate gateway webhooks cannot double-credit.
        """
        if entry.status != "pending":
            return entry
        if status not in ("success", "failed"):
            raise_bad_request("Unknown settlement status")

        wallet = _lock_wallet(db, entry.wallet_id)
        # Re-read the entry after the lock: a concurrent webhook/verify may have settled it.
        db.refresh(entry)
        if entry.status != "pending":
            return entry

        if status == "success":
            balance_after = wallet.balance_minor + entry.amount_minor
            if balance_after < 0:
                raise_bad_request("Settlement would make the balance negative")
            wallet.balance_minor = balance_after
            wallet.version = (wallet.version or 0) + 1
            entry.balance_after_minor = balance_after

        entry.status = status
        if gateway_payment_id:
            entry.gateway_payment_id = gateway_payment_id

        if commit:
            db.commit()
            db.refresh(entry)
        return entry

    @staticmethod
    def history(
        db: Session,
        wallet: FamilyWallet,
        *,
        limit: int = 50,
    ) -> list[WalletTransaction]:
        return (
            db.query(WalletTransaction)
            .filter(WalletTransaction.wallet_id == wallet.id)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .limit(max(1, min(limit, 200)))
            .all()
        )

    @staticmethod
    def reconciled_balance_minor(db: Session, wallet: FamilyWallet) -> int:
        """SUM of successful ledger rows — compare against the cached balance."""
        rows = (
            db.query(WalletTransaction.amount_minor)
            .filter(
                WalletTransaction.wallet_id == wallet.id,
                WalletTransaction.status == "success",
            )
            .all()
        )
        return sum(int(r[0]) for r in rows)
