"""Wearable status for families: ingest updates last_seen/battery, family endpoint scopes by elder."""

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.iot_registry_service import IotRegistryService
from app.models.elder import Elder
from app.models.iot_device import IotDevice, IotHub
from app.models.user import User

KEY = "test-ingest-key"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag):
    elder = Elder(tenant_id=tenant_id, first_name=f"Elder{tag}", last_name="Band", status="ACTIVE")
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.band@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Band",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


def _kit(db, tenant_id, elder_id, mac, *, hub_key="mg7-a"):
    hub = IotHub(
        tenant_id=tenant_id,
        home_key="home1",
        hub_key=hub_key,
        label=f"Hub {hub_key}",
        mqtt_username=f"mg7_{hub_key}_{elder_id}",
        mqtt_password="x",
        mqtt_topic="t",
    )
    db.add(hub)
    db.flush()
    device = IotDevice(
        tenant_id=tenant_id,
        hub_id=hub.id,
        elder_id=elder_id,
        label="Amma's band",
        mac_address=mac,
        status="active",
    )
    db.add(device)
    db.commit()
    return hub, device


def test_ingest_updates_last_seen_and_battery(db, client, seed_tenant, monkeypatch):
    monkeypatch.setattr(settings, "IOT_INGEST_API_KEY", KEY)
    fam, elder = _family(db, seed_tenant["tenant"].id, "a")
    hub, device = _kit(db, seed_tenant["tenant"].id, elder.id, "aa:bb:cc:dd:ee:01")
    headers = _login(client, fam.email)

    before = client.get("/api/v1/home-safety/family/devices", headers=headers).json()
    assert len(before) == 1
    assert before[0]["online"] is False and before[0]["last_seen_at"] is None

    # A heartbeat the API otherwise ignores still proves the band is alive.
    res = client.post(
        "/api/v1/iot/events",
        headers={"X-IoT-Ingest-Key": KEY},
        json={"event_type": "BAND_SEEN", "mac_address": "AA:BB:CC:DD:EE:01", "hub_id": "mg7-a", "battery_level": 77},
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    device = db.query(IotDevice).filter(IotDevice.id == device.id).one()
    hub = db.query(IotHub).filter(IotHub.id == hub.id).one()
    assert device.last_seen_at is not None
    assert device.battery_level == 77
    assert hub.last_seen_at is not None

    rows = client.get("/api/v1/home-safety/family/devices", headers=headers).json()
    assert rows[0]["online"] is True
    assert rows[0]["battery_level"] == 77
    assert rows[0]["label"] == "Amma's band"
    assert rows[0]["hub_label"] == "Hub mg7-a"
    assert rows[0]["hub_online"] is True

    # An SOS also counts as "seen"; an OFFLINE event must not.
    seen_at = device.last_seen_at
    res = client.post(
        "/api/v1/iot/events",
        headers={"X-IoT-Ingest-Key": KEY},
        json={"event_type": "SOS_BUTTON", "mac_address": "aa:bb:cc:dd:ee:01", "battery_level": 60},
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    device = db.query(IotDevice).filter(IotDevice.id == device.id).one()
    assert device.battery_level == 60
    assert device.last_seen_at >= seen_at

    device.last_seen_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db.commit()
    res = client.post(
        "/api/v1/iot/events",
        headers={"X-IoT-Ingest-Key": KEY},
        json={"event_type": "DEVICE_OFFLINE", "mac_address": "aa:bb:cc:dd:ee:01"},
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    device = db.query(IotDevice).filter(IotDevice.id == device.id).one()
    stale = device.last_seen_at.replace(tzinfo=timezone.utc) if device.last_seen_at.tzinfo is None else device.last_seen_at
    assert datetime.now(timezone.utc) - stale > timedelta(hours=2)
    rows = client.get("/api/v1/home-safety/family/devices", headers=headers).json()
    assert rows[0]["online"] is False


def test_touch_clamps_battery_and_ignores_unknown_mac(db, seed_tenant):
    _fam, elder = _family(db, seed_tenant["tenant"].id, "b")
    _hub, device = _kit(db, seed_tenant["tenant"].id, elder.id, "aa:bb:cc:dd:ee:02", hub_key="mg7-b")
    assert IotRegistryService.touch_device_seen(db, mac_address="00:00:00:00:00:00") is None
    IotRegistryService.touch_device_seen(db, mac_address="aa:bb:cc:dd:ee:02", battery_level=140)
    db.refresh(device)
    assert device.battery_level == 100


def test_family_devices_scoped_to_active_elder(db, client, seed_tenant):
    fam_a, elder_a = _family(db, seed_tenant["tenant"].id, "c")
    fam_b, elder_b = _family(db, seed_tenant["tenant"].id, "d")
    _kit(db, seed_tenant["tenant"].id, elder_a.id, "aa:bb:cc:dd:ee:03", hub_key="mg7-c")
    _kit(db, seed_tenant["tenant"].id, elder_b.id, "aa:bb:cc:dd:ee:04", hub_key="mg7-d")
    rows_a = client.get("/api/v1/home-safety/family/devices", headers=_login(client, fam_a.email)).json()
    rows_b = client.get("/api/v1/home-safety/family/devices", headers=_login(client, fam_b.email)).json()
    assert len(rows_a) == 1 and len(rows_b) == 1
    assert rows_a[0]["id"] != rows_b[0]["id"]
    assert "mac_address" not in rows_a[0]
