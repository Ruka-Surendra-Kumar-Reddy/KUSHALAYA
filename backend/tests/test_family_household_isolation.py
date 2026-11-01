"""Two unrelated families in one tenant, and a third in another tenant, must never
see or act on each other's elder data through the family API."""

from datetime import datetime, timezone

import pytest

from app.core.security import hash_password
from app.livewell.document_types import FAMILY_UPLOAD_TYPE_CODES, HOME_SAFETY_PHOTO
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.visit_service import HomeSafetyVisitService
from app.livewell.wallet_service import WalletService
from app.models.document import Document
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.iot_device import IotDevice
from app.models.tenant import Tenant
from app.models.user import User

F = "/api/v1/home-safety/family"


def _headers(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag):
    elder = Elder(tenant_id=tenant_id, first_name=f"Senior{tag}", last_name="Iso", status="ACTIVE")
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.iso@test.example",
        password_hash=hash_password("testpass123"),
        first_name=f"Fam{tag}",
        last_name="Iso",
        role="ELDER_PORTAL",
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


def _document(db, elder, doc_type, name):
    doc = Document(
        tenant_id=elder.tenant_id,
        entity_type="elder",
        entity_id=elder.id,
        document_type=doc_type,
        document_name=name,
        file_name=f"{name}.jpg",
        storage_key=f"iso/{elder.id}/{name}.jpg",
        storage_url=f"/iso/{elder.id}/{name}.jpg",
        mime_type="image/jpeg",
        uploaded_at=datetime.now(timezone.utc),
        verification_status="PENDING",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture
def households(db, client, seed_tenant):
    """Family A and B share the seed tenant; family C lives in another tenant.
    B (and C) get one of everything so A has real ids to try and reach."""
    tenant = seed_tenant["tenant"]
    other = Tenant(name="Other Org", email="otherorg@test.example", phone="1", address="x", city="y", state="z")
    db.add(other)
    db.flush()

    out = {}
    for tag, tid in (("a", tenant.id), ("b", tenant.id), ("c", other.id)):
        user, elder = _family(db, tid, tag)
        headers = _headers(client, user.email)
        data = {"user": user, "elder": elder, "headers": headers}

        # message + alert
        client.post(f"{F}/messages", headers=headers, json={"body": f"secret note {tag}"})
        alert = FamilyCareHubService._push_alert(db, elder, title=f"Alert {tag}", body="x", severity="warning")
        data["alert_id"] = alert["id"]

        # documents: a family upload and an assessment photo
        data["doc_id"] = _document(db, elder, next(iter(sorted(FAMILY_UPLOAD_TYPE_CODES))), f"upload-{tag}").id
        data["photo_id"] = _document(db, elder, HOME_SAFETY_PHOTO, f"photo-{tag}").id

        # a completed visit (staff of the elder's tenant)
        staff = seed_tenant["manager"] if tid == tenant.id else None
        if staff is not None:
            visit = HomeSafetyVisitService.create_for_elder(
                db,
                staff,
                elder.id,
                {"visit_type": "Wellness visit", "status": "completed", "summary": f"visit {tag}",
                 "baseline": {"typical_mobility": "walks unaided", "notes": f"baseline {tag}"}},
            )
            data["visit_id"] = visit["id"]

        # a quoted service request, wallet money and a receipt
        req = client.post(f"{F}/service-requests", headers=headers, json={"service_type": "home_repair"}).json()
        data["request_id"] = req["id"]
        wallet = WalletService.get_or_create(db, elder)
        entry = WalletService.record(
            db, wallet, kind="recharge", amount_minor=50_000, idempotency_key=f"iso:{tag}", user=user
        )
        data["tx_id"] = entry.public_id

        device = IotDevice(
            tenant_id=tid, elder_id=elder.id, label=f"band {tag}", mac_address=f"aa:bb:cc:dd:ff:0{ord(tag) - 96}"
        )
        db.add(device)
        db.commit()
        data["device_id"] = device.id
        out[tag] = data

    # staff quote for B so its request is payable
    out["b"]["elder"].manager_user_id = seed_tenant["manager"].id  # staff updates are team-scoped
    db.commit()
    staff_headers = _headers(client, seed_tenant["manager"].email)
    res = client.patch(
        f"/api/v1/home-safety/care/elders/{out['b']['elder'].id}/service-requests/{out['b']['request_id']}",
        headers=staff_headers,
        json={"status": "requested", "quoted_amount_minor": 10_000},
    )
    assert res.status_code == 200, res.text
    return out


def _assert_denied(res, *, path):
    assert res.status_code in (403, 404), f"{path} -> {res.status_code}: {res.text}"
    body = res.text.lower()
    assert "secret note" not in body and "seniorb" not in body and "seniorc" not in body


def test_family_a_cannot_reach_family_b_or_c_by_id(client, households):
    a, b, c = households["a"], households["b"], households["c"]
    h = a["headers"]

    for target in (b, c):
        res = client.post(f"{F}/elders/active", headers=h, json={"elder_id": target["elder"].id})
        _assert_denied(res, path="elders/active")

    # Still on their own elder afterwards.
    dash = client.get(f"{F}/dashboard", headers=h).json()
    assert dash["active_elder_id"] == a["elder"].id
    assert dash["senior_name"].startswith("Seniora")
    assert {e["id"] for e in dash["elders"]} == {a["elder"].id}

    for target in (b, c):
        checks = [
            ("get", f"{F}/documents/{target['doc_id']}/file", None),
            ("get", f"{F}/photos/{target['photo_id']}/image", None),
            ("post", f"{F}/alerts/{target['alert_id']}/read", None),
            ("post", f"{F}/service-requests/{target['request_id']}/pay", None),
            ("post", f"{F}/service-requests/{target['request_id']}/cancel", None),
            ("get", f"{F}/receipts/{target['tx_id']}", None),
            ("delete", f"{F}/circle/{target['user'].id}", None),
        ]
        if "visit_id" in target:
            checks.append(("get", f"{F}/visits/{target['visit_id']}", None))
            checks.append(
                (
                    "post",
                    f"{F}/visits/{target['visit_id']}/experience-rating",
                    {"rating": 5, "comment": "great"},
                )
            )
        for method, path, payload in checks:
            kwargs = {"headers": h}
            if payload is not None:
                kwargs["json"] = payload
            _assert_denied(getattr(client, method)(path, **kwargs), path=path)


def test_family_a_lists_contain_only_own_data(client, households):
    a, b, c = households["a"], households["b"], households["c"]
    h = a["headers"]
    foreign_alert_ids = {b["alert_id"], c["alert_id"]}
    foreign_tx = {b["tx_id"], c["tx_id"]}
    foreign_devices = {b["device_id"], c["device_id"]}
    foreign_users = {b["user"].id, c["user"].id}
    foreign_requests = {b["request_id"], c["request_id"]}

    alerts = client.get(f"{F}/alerts", headers=h).json()
    assert {x["id"] for x in alerts} & foreign_alert_ids == set()
    assert any(x["id"] == a["alert_id"] for x in alerts)

    msgs = client.get(f"{F}/messages", headers=h).json()
    assert [m["body"] for m in msgs] == ["secret note a"]

    wallet = client.get(f"{F}/wallet", headers=h).json()
    assert wallet["elder_id"] == a["elder"].id
    assert wallet["balance_minor"] == 50_000
    txs = client.get(f"{F}/wallet/transactions", headers=h).json()
    assert {t["id"] for t in txs} == {a["tx_id"]}
    receipts = client.get(f"{F}/receipts", headers=h).json()
    assert {r["id"] for r in receipts} == {a["tx_id"]}
    assert {r["id"] for r in receipts} & foreign_tx == set()

    reqs = client.get(f"{F}/service-requests", headers=h).json()
    assert {r["id"] for r in reqs} == {a["request_id"]}
    assert {r["id"] for r in reqs} & foreign_requests == set()

    circle = client.get(f"{F}/circle", headers=h).json()
    assert {m["id"] for m in circle} == {a["user"].id}
    assert {m["id"] for m in circle} & foreign_users == set()

    devices = client.get(f"{F}/devices", headers=h).json()
    assert {d["id"] for d in devices} == {a["device_id"]}
    assert {d["id"] for d in devices} & foreign_devices == set()

    docs = client.get(f"{F}/documents", headers=h).json()
    assert {d["id"] for d in docs} == {a["doc_id"]}

    visits = client.get(f"{F}/visits", headers=h).json()
    assert all("visit b" not in (v.get("summary") or "") for v in visits)
    for v in visits:
        assert v["id"] != b.get("visit_id")


def test_cross_tenant_link_row_is_ignored(db, client, households):
    """A stale/forged link into another organization's elder must not grant access."""
    a, c = households["a"], households["c"]
    db.add(FamilyElderLink(user_id=c["user"].id, elder_id=a["elder"].id))
    db.commit()
    h = c["headers"]

    elders = client.get(f"{F}/elders", headers=h).json()
    assert {e["id"] for e in elders["elders"]} == {c["elder"].id}
    res = client.post(f"{F}/elders/active", headers=h, json={"elder_id": a["elder"].id})
    _assert_denied(res, path="elders/active cross-tenant")
    dash = client.get(f"{F}/dashboard", headers=h).json()
    assert dash["active_elder_id"] == c["elder"].id
    assert "Seniora" not in dash["senior_name"]

    # Even with users.elder_id forced onto the foreign elder, resolution falls back.
    c["user"].elder_id = a["elder"].id
    db.commit()
    dash = client.get(f"{F}/dashboard", headers=h).json()
    assert dash["active_elder_id"] == c["elder"].id
    msgs = client.get(f"{F}/messages", headers=h).json()
    assert all("secret note a" != m["body"] for m in msgs)
