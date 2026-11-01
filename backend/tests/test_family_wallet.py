"""Family wallet ledger — the invariants that protect real money."""

import pytest
from workforceos_core.exceptions import WorkforceHTTPError

from app.core.money import format_minor, rupees_to_minor
from app.livewell.wallet_service import WalletService
from app.models.elder import Elder as ElderModel


@pytest.fixture
def elder(db, seed_tenant):
    row = ElderModel(
        first_name="Lakshmi",
        last_name="Reddy",
        tenant_id=seed_tenant["tenant"].id,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def wallet(db, elder):
    return WalletService.get_or_create(db, elder, commit=False)


def test_new_wallet_starts_empty(wallet):
    assert wallet.balance_minor == 0
    assert wallet.currency == "INR"
    assert wallet.status == "active"


def test_get_or_create_is_stable(db, elder, wallet):
    again = WalletService.get_or_create(db, elder, commit=False)
    assert again.id == wallet.id


def test_recharge_credits_balance(db, wallet):
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    assert wallet.balance_minor == 50_000


def test_debit_reduces_balance(db, wallet):
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    entry = WalletService.record(
        db,
        wallet,
        kind="debit",
        amount_minor=20_000,
        idempotency_key="debit:service_request:fsr_1",
        commit=False,
    )
    assert entry.amount_minor == -20_000, "debits are stored signed negative"
    assert wallet.balance_minor == 30_000


def test_debit_beyond_balance_is_refused(db, wallet):
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=10_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    with pytest.raises(WorkforceHTTPError) as exc:
        WalletService.record(
            db,
            wallet,
            kind="debit",
            amount_minor=25_000,
            idempotency_key="debit:service_request:fsr_1",
            commit=False,
        )
    assert exc.value.status_code == 400
    assert wallet.balance_minor == 10_000, "a refused debit must not move money"


def test_same_idempotency_key_does_not_move_money_twice(db, wallet):
    first = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    second = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    assert first.id == second.id
    assert wallet.balance_minor == 50_000


def test_pending_recharge_does_not_credit_until_settled(db, wallet):
    entry = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        status="pending",
        commit=False,
    )
    assert wallet.balance_minor == 0, "unpaid top-up must not show as money"

    WalletService.settle_pending(db, entry, status="success", commit=False)
    assert wallet.balance_minor == 50_000


def test_settling_twice_does_not_double_credit(db, wallet):
    entry = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        status="pending",
        commit=False,
    )
    WalletService.settle_pending(db, entry, status="success", commit=False)
    WalletService.settle_pending(db, entry, status="success", commit=False)
    assert wallet.balance_minor == 50_000, "a replayed webhook must be a no-op"


def test_failed_recharge_leaves_balance_alone(db, wallet):
    entry = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        status="pending",
        commit=False,
    )
    WalletService.settle_pending(db, entry, status="failed", commit=False)
    assert wallet.balance_minor == 0


def test_refund_returns_money(db, wallet):
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=50_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    WalletService.record(
        db,
        wallet,
        kind="debit",
        amount_minor=20_000,
        idempotency_key="debit:service_request:fsr_1",
        commit=False,
    )
    WalletService.record(
        db,
        wallet,
        kind="refund",
        amount_minor=20_000,
        idempotency_key="refund:service_request:fsr_1",
        commit=False,
    )
    assert wallet.balance_minor == 50_000


def test_zero_or_negative_amounts_are_refused(db, wallet):
    for bad in (0, -100):
        with pytest.raises(WorkforceHTTPError):
            WalletService.record(
                db,
                wallet,
                kind="recharge",
                amount_minor=bad,
                idempotency_key=f"recharge:bad{bad}",
                commit=False,
            )


def test_frozen_wallet_refuses_movement(db, wallet):
    wallet.status = "frozen"
    db.flush()
    with pytest.raises(WorkforceHTTPError):
        WalletService.record(
            db,
            wallet,
            kind="recharge",
            amount_minor=10_000,
            idempotency_key="recharge:order_1",
            commit=False,
        )


def test_ledger_sum_reconciles_with_cached_balance(db, wallet):
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=100_000,
        idempotency_key="recharge:order_1",
        commit=False,
    )
    WalletService.record(
        db,
        wallet,
        kind="debit",
        amount_minor=35_000,
        idempotency_key="debit:service_request:fsr_1",
        commit=False,
    )
    WalletService.record(
        db,
        wallet,
        kind="refund",
        amount_minor=5_000,
        idempotency_key="refund:service_request:fsr_1",
        commit=False,
    )
    db.flush()
    assert WalletService.reconciled_balance_minor(db, wallet) == wallet.balance_minor


def test_history_is_newest_first(db, wallet):
    for i in range(3):
        WalletService.record(
            db,
            wallet,
            kind="recharge",
            amount_minor=1_000,
            idempotency_key=f"recharge:order_{i}",
            commit=False,
        )
    db.flush()
    rows = WalletService.history(db, wallet)
    assert len(rows) == 3
    assert rows[0].id > rows[-1].id


class TestMoneyFormatting:
    def test_rupees_to_paise_has_no_float_drift(self):
        assert rupees_to_minor("1250.55") == 125_055
        assert rupees_to_minor(0.1 + 0.2) == 30
        assert rupees_to_minor(1999.999) == 200_000

    def test_display_strings(self):
        assert format_minor(125_055) == "₹1,250.55"
        assert format_minor(-20_000) == "-₹200.00"
        assert format_minor(0) == "₹0.00"


class TestRazorpayWebhookSignature:
    """The signature check is the only thing standing between a stranger's
    HTTP request and a credited wallet, so it gets its own tests."""

    @staticmethod
    def _provider(monkeypatch):
        from app.core.config import settings
        from app.services.payments.razorpay_provider import RazorpayProvider

        monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_key", raising=False)
        monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret_abc", raising=False)
        monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_abc", raising=False)
        return RazorpayProvider()

    def test_forged_signature_is_rejected(self, monkeypatch):
        provider = self._provider(monkeypatch)
        with pytest.raises(WorkforceHTTPError):
            provider.verify_webhook(payload=b'{"event":"payment.captured"}', signature="forged")

    def test_empty_signature_is_rejected(self, monkeypatch):
        provider = self._provider(monkeypatch)
        with pytest.raises(WorkforceHTTPError):
            provider.verify_webhook(payload=b'{"event":"payment.captured"}', signature="")

    def test_valid_signature_is_accepted_and_parsed(self, monkeypatch):
        import hashlib
        import hmac
        import json

        provider = self._provider(monkeypatch)
        body = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {
                        "entity": {"id": "pay_123", "order_id": "order_123", "amount": 150000}
                    }
                },
            }
        ).encode("utf-8")
        signature = hmac.new(b"whsec_abc", body, hashlib.sha256).hexdigest()

        event = provider.verify_webhook(payload=body, signature=signature)
        assert event.event == "payment.captured"
        assert event.order_id == "order_123"
        assert event.payment_id == "pay_123"
        assert event.amount_minor == 150000

    def test_signature_of_a_different_body_is_rejected(self, monkeypatch):
        """Guards against replaying a valid signature onto a larger amount."""
        import hashlib
        import hmac

        provider = self._provider(monkeypatch)
        original = b'{"event":"payment.captured","amount":100}'
        signature = hmac.new(b"whsec_abc", original, hashlib.sha256).hexdigest()
        tampered = b'{"event":"payment.captured","amount":9999999}'

        with pytest.raises(WorkforceHTTPError):
            provider.verify_webhook(payload=tampered, signature=signature)

    def test_checkout_signature_roundtrip(self, monkeypatch):
        import hashlib
        import hmac

        provider = self._provider(monkeypatch)
        good = hmac.new(b"secret_abc", b"order_1|pay_1", hashlib.sha256).hexdigest()
        assert provider.verify_checkout_signature(
            order_id="order_1", payment_id="pay_1", signature=good
        )
        assert not provider.verify_checkout_signature(
            order_id="order_1", payment_id="pay_1", signature="nope"
        )
