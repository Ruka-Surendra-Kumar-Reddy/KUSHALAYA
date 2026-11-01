"""Phase 3 fixes: staff decline/cancel of a paid service request refunds the wallet;
closed requests can't change; staff updates are limited to the manager's team."""

import pytest


from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.family_service_requests import FamilyServiceRequestService as S
from app.livewell.wallet_service import WalletService
from app.core.security import hash_password
from app.models.elder import Elder
from app.models.user import User


@pytest.fixture
def family(db, seed_tenant):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    u = User(email="fam.fix@test.example", password_hash=hash_password("testpass123"), first_name="Fam",
             last_name="Fix", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(u)
    db.flush()
    ensure_family_elder_link(db, u, elder)
    db.commit()
    return u


def _paid_request(db, seed_tenant, family, amount=50000):
    elder = seed_tenant["elder"]
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(db, wallet, kind="recharge", amount_minor=amount, idempotency_key=f"recharge:fix:{amount}")
    req = S.create_for_family(db, family, service_type="care_visit", preferred_at=None, notes="")
    S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="requested", quoted_amount_minor=amount)
    paid = S.pay_from_wallet(db, family, req["id"])
    assert paid["payment_status"] == "paid"
    assert WalletService.get_or_create(db, elder).balance_minor == 0
    return req


@pytest.mark.parametrize("status", ["declined", "cancelled"])
def test_staff_decline_or_cancel_refunds_paid_request(db, seed_tenant, family, monkeypatch, status):
    told = []
    monkeypatch.setattr("app.livewell.family_notify.notify_family",
                        lambda db_, elder, title, body, **kw: told.append((title, body)))
    elder = seed_tenant["elder"]
    req = _paid_request(db, seed_tenant, family)
    out = S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status=status)
    db.commit()
    assert out["status"] == status and out["payment_status"] == "refunded"
    assert WalletService.get_or_create(db, elder).balance_minor == 50000
    assert told and "refunded" in told[-1][1] and "500" in told[-1][1]
    # Closed: no more changes, and the refund can't happen twice.
    with pytest.raises(Exception):
        S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="confirmed")
    assert WalletService.get_or_create(db, elder).balance_minor == 50000


def test_done_request_cannot_be_reopened(db, seed_tenant, family):
    elder = seed_tenant["elder"]
    req = S.create_for_family(db, family, service_type="care_visit", preferred_at=None, notes="")
    S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="done")
    with pytest.raises(Exception):
        S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="requested")
    # Same status with a note is fine.
    out = S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="done", staff_note="Went well")
    assert out["staff_note"] == "Went well"


def test_staff_update_limited_to_team(db, seed_tenant, family):
    req = S.create_for_family(db, family, service_type="care_visit", preferred_at=None, notes="")
    outsider = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Not", last_name="Mine", status="ACTIVE")
    db.add(outsider)
    db.commit()
    manager = seed_tenant["manager"]
    # Own client: fine. Client outside the manager's team: 404.
    assert S.list_for_staff(db, manager, seed_tenant["elder"].id) is not None
    with pytest.raises(Exception) as e:
        S.list_for_staff(db, manager, outsider.id)
    assert e.value.status_code == 404
    with pytest.raises(Exception):
        S.staff_update(db, manager, outsider.id, req["id"], status="confirmed")
