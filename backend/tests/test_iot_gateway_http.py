"""Minew HTTP gateway ingest, the Add device / assign flow, and immobility rules.

Payloads follow the Minew G1 / MG3 HTTP upload formats:
* JSON-RAW:  [{"type":"Gateway",...}, {"type":"Unknown","mac":..,"rssi":..,"rawData":..}]
* JSON-LONG: parsed rows ({"type":"iBeacon","ibeaconMajor":1,"ibeaconMinor":1,"battery":87})
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.iot_gateway_http import process_gateway_upload
from app.livewell.iot_registry_service import IotRegistryService
from app.models.elder import Elder
from app.models.incident import Incident
from app.models.iot_device import IotDevice, IotHub
from app.models.user import User
from iot_ingestor.band_watch import BandState, WatchPolicy, evaluate_watch

WATCH_MAC = "c3:00:00:98:f3:f8"
WATCH_RAW_MAC = "C3000098F3F8"
GATEWAY_RAW_MAC = "AC233FC12345"
IST = timezone(timedelta(hours=5, minutes=30))
NOON = datetime(2026, 10, 29, 12, 0, tzinfo=IST)

UUID = "FDA50693A4E24FB1AFCFC6EB07647825"


def ibeacon_raw(major: int, minor: int) -> str:
    return "0201061AFF4C000215" + UUID + f"{major:04X}{minor:04X}" + "C5"


def acc_raw(x: int, y: int, z: int, battery: int = 87) -> str:
    def h(v: int) -> str:
        return f"{v & 0xFFFF:04X}"

    return "0201060303E1FF0C16E1FFA103" + f"{battery:02X}" + h(x) + h(y) + h(z)


def batch(*ads: dict, ts: str = "2026-10-29T06:30:00.000Z") -> list[dict]:
    rows = [{"timestamp": ts, "type": "Gateway", "mac": GATEWAY_RAW_MAC, "gatewayFree": 93, "gatewayLoad": 0.04}]
    for ad in ads:
        rows.append({"timestamp": ts, "type": "Unknown", "bleName": "", **ad})
    return rows


def sos_ad(mac: str = WATCH_RAW_MAC) -> dict:
    return {"mac": mac, "rssi": -61, "rawData": ibeacon_raw(1, 1)}


def idle_ad(mac: str = WATCH_RAW_MAC) -> dict:
    return {"mac": mac, "rssi": -62, "rawData": ibeacon_raw(1, 2)}


def acc_ad(x: int, y: int, z: int, mac: str = WATCH_RAW_MAC) -> dict:
    return {"mac": mac, "rssi": -63, "rawData": acc_raw(x, y, z)}


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _elder(db, tenant_id, tag="g"):
    elder = Elder(tenant_id=tenant_id, first_name=f"Gw{tag}", last_name="Client", status="ACTIVE")
    db.add(elder)
    db.commit()
    db.refresh(elder)
    return elder


def _setup(db, seed_tenant, *, assigned=True):
    tid = seed_tenant["tenant"].id
    elder = _elder(db, tid)
    gw = IotRegistryService.add_device(db, tenant_id=tid, kind="gateway", mac_address=GATEWAY_RAW_MAC, label="Hall gateway")
    watch = IotRegistryService.add_device(
        db, tenant_id=tid, kind="watch", mac_address=WATCH_RAW_MAC, elder_id=elder.id if assigned else None
    )
    hub = db.get(IotHub, gw["id"])
    return elder, hub, db.get(IotDevice, watch["id"])


def _incidents(db, elder_id, kind):
    return db.query(Incident).filter(Incident.elder_id == elder_id, Incident.kind == kind).all()


def _token(hub: IotHub) -> str:
    return hub.http_token or ""


# ----- HTTP endpoint -----


def test_gateway_link_check_and_bad_token(db, client, seed_tenant):
    _, hub, _ = _setup(db, seed_tenant)
    res = client.get(f"/api/v1/home-safety/gateway/{_token(hub)}")
    assert res.status_code == 200 and res.json()["ok"] is True
    assert client.get("/api/v1/home-safety/gateway/not-a-real-token-at-all-xxxxxxxx").status_code == 404
    assert client.post("/api/v1/home-safety/gateway/not-a-real-token-at-all-xxxxxxxx", json=[]).status_code == 404


def test_http_sos_raises_once_per_press(db, client, seed_tenant):
    elder, hub, device = _setup(db, seed_tenant)
    url = f"/api/v1/home-safety/gateway/{_token(hub)}"
    res = client.post(url, json=batch(sos_ad(), acc_ad(7, 0, 250)))
    assert res.status_code == 200, res.text
    assert res.json()["registered"] == 1 and res.json()["events"] == 1
    assert len(_incidents(db, elder.id, "sos_button")) == 1
    # The band keeps advertising 1/1 for ~60 s: same press, no new alert.
    res = client.post(url, json=batch(sos_ad()))
    assert res.json()["events"] == 0
    assert len(_incidents(db, elder.id, "sos_button")) == 1
    db.refresh(device)
    db.refresh(hub)
    assert device.last_seen_at is not None and hub.last_seen_at is not None
    assert device.battery_level == 87 and device.last_rssi is not None
    assert hub.mac_address == "ac:23:3f:c1:23:45"


def test_http_unknown_mac_ignored(db, client, seed_tenant):
    elder, hub, _ = _setup(db, seed_tenant)
    res = client.post(f"/api/v1/home-safety/gateway/{_token(hub)}", json=batch(sos_ad("D00000000001")))
    assert res.status_code == 200
    assert res.json()["registered"] == 0 and res.json()["events"] == 0
    assert db.query(Incident).filter(Incident.device_mac == "d0:00:00:00:00:01").count() == 0


def test_http_unassigned_device_heard_but_never_alerts(db, client, seed_tenant):
    _, hub, device = _setup(db, seed_tenant, assigned=False)
    res = client.post(f"/api/v1/home-safety/gateway/{_token(hub)}", json=batch(sos_ad(), acc_ad(1, 2, 250)))
    assert res.json()["registered"] == 1 and res.json()["events"] == 0
    db.refresh(device)
    assert device.last_seen_at is not None and device.battery_level == 87
    assert db.query(Incident).filter(Incident.device_mac == WATCH_MAC).count() == 0


def test_http_json_long_wrapped_and_gzip(db, client, seed_tenant):
    elder, hub, _ = _setup(db, seed_tenant)
    body = {
        "gatewayMac": GATEWAY_RAW_MAC,
        "data": [
            {
                "type": "iBeacon",
                "mac": WATCH_RAW_MAC,
                "rssi": -58,
                "ibeaconUuid": UUID,
                "ibeaconMajor": 1,
                "ibeaconMinor": 1,
                "ibeaconTxPower": -59,
                "battery": 64,
            }
        ],
    }
    res = client.post(
        f"/api/v1/home-safety/gateway/{_token(hub)}",
        content=gzip.compress(json.dumps(body).encode()),
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["events"] == 1
    assert len(_incidents(db, elder.id, "sos_button")) == 1
    assert db.query(IotDevice).filter(IotDevice.mac_address == WATCH_MAC).one().battery_level == 64


# ----- Immobility (persisted watch state, HTTP path) -----


def _run(db, hub, ad, start, first_min, last_min, step=2):
    """Gateway uploads every ``step`` minutes; returns the events raised."""
    events = []
    m = first_min
    while m <= last_min:
        out = process_gateway_upload(db, hub, batch(ad), now=start + timedelta(minutes=m))
        events += [(m, e["event_type"]) for e in out["events"]]
        m += step
    return events


def test_immobility_once_per_episode_and_rearm(db, seed_tenant):
    elder, hub, _ = _setup(db, seed_tenant)
    t = NOON
    process_gateway_upload(db, hub, batch(idle_ad(), acc_ad(7, 0, 250)), now=t)
    # Still (tiny jitter) for 29 minutes: nothing.
    assert _run(db, hub, acc_ad(8, 0, 250), t, 1, 29, step=1) == []
    # 30 minutes still: one alert, then none while still not moving.
    assert _run(db, hub, acc_ad(7, 0, 250), t, 30, 120) == [(30, "IMMOBILITY_WARNING")]
    assert len(_incidents(db, elder.id, "immobility")) == 1
    # Staff close it; a real movement re-arms; still again for 30 min -> new alert.
    row = _incidents(db, elder.id, "immobility")[0]
    row.status = "resolved"
    db.commit()
    events = _run(db, hub, acc_ad(-64, -115, 227), t, 122, 170)
    assert events == [(152, "IMMOBILITY_WARNING")]
    assert len(_incidents(db, elder.id, "immobility")) == 2


def test_back_from_out_of_range_is_not_immobility(db, seed_tenant):
    elder, hub, _ = _setup(db, seed_tenant)
    t = NOON
    assert _run(db, hub, acc_ad(7, 0, 250), t, 0, 20) == []
    # Out of range for 25 minutes (no uploads), then back with the same XYZ:
    # the clock restarts at the return (+45), it does not count the gap.
    events = _run(db, hub, acc_ad(7, 0, 250), t, 45, 90)
    assert events == [(75, "IMMOBILITY_WARNING")]


def test_night_stillness_counts_from_window_start(db, seed_tenant):
    elder, hub, _ = _setup(db, seed_tenant)
    night = datetime(2026, 10, 29, 2, 0, tzinfo=IST)
    process_gateway_upload(db, hub, batch(acc_ad(7, 0, 250)), now=night)
    # Asleep and still from 02:00; the day window opens at 07:00 (= +300 min).
    events = _run(db, hub, acc_ad(7, 0, 250), night, 2, 340)
    assert events == [(330, "IMMOBILITY_WARNING")]  # 07:30, not 07:00


def test_sensor_never_raises_immobility(db, seed_tenant):
    tid = seed_tenant["tenant"].id
    elder = _elder(db, tid, "s")
    gw = IotRegistryService.add_device(db, tenant_id=tid, kind="gateway", mac_address="AC233FC00001")
    IotRegistryService.add_device(db, tenant_id=tid, kind="sensor", mac_address="AC233FD00002", elder_id=elder.id)
    hub = db.get(IotHub, gw["id"])
    assert _run(db, hub, acc_ad(7, 0, 250, mac="AC233FD00002"), NOON, 0, 90) == []


def test_ingest_endpoint_folds_repeat_immobility(db, client, seed_tenant, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "IOT_INGEST_API_KEY", "k")
    elder, _, _ = _setup(db, seed_tenant)
    body = {"event_type": "IMMOBILITY_WARNING", "mac_address": WATCH_RAW_MAC, "dedupe_key": f"{WATCH_MAC}:IMMOBILITY_WARNING"}
    first = client.post("/api/v1/iot/events", json=body, headers={"X-IoT-Ingest-Key": "k"}).json()
    # e.g. the MQTT ingestor restarted and lost its latch, an hour later:
    second = client.post("/api/v1/iot/events", json=body, headers={"X-IoT-Ingest-Key": "k"}).json()
    assert first["duplicate"] is False and second["duplicate"] is True
    assert len(_incidents(db, elder.id, "immobility")) == 1


def test_ingest_endpoint_ignores_unknown_and_unassigned(db, client, seed_tenant, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "IOT_INGEST_API_KEY", "k")
    _setup(db, seed_tenant, assigned=False)
    for mac in (WATCH_RAW_MAC, "D00000000009"):
        res = client.post(
            "/api/v1/iot/events",
            json={"event_type": "SOS_BUTTON", "mac_address": mac},
            headers={"X-IoT-Ingest-Key": "k"},
        )
        assert res.status_code == 200 and res.json()["accepted"] is False
    assert db.query(Incident).filter(Incident.kind == "sos_button").count() == 0


# ----- band_watch unit rules (shared with the MQTT ingestor) -----

DAY = datetime(2026, 10, 29, 12, 0, tzinfo=IST)
NIGHT = datetime(2026, 10, 29, 23, 30, tzinfo=IST)


def test_offline_once_per_episode_and_not_at_night():
    policy = WatchPolicy(offline_seconds=180)
    state = BandState(mac=WATCH_MAC)
    state.note_seen(0.0)
    assert evaluate_watch(state, 400.0, policy, wall_now=NIGHT) is None  # charging overnight
    assert evaluate_watch(state, 400.0, policy, wall_now=DAY) == "DEVICE_OFFLINE"
    assert evaluate_watch(state, 4000.0, policy, wall_now=DAY) is None  # still the same episode
    state.note_seen(4100.0, offline_seconds=180)
    assert evaluate_watch(state, 4500.0, policy, wall_now=DAY) == "DEVICE_OFFLINE"  # new episode


def test_movement_rearms_immobility():
    policy = WatchPolicy(immobility_minutes=30, offline_seconds=180)
    state = BandState(mac=WATCH_MAC)
    state.note_accelerometer((7, 0, 250), 0.0)
    for i in range(1, 32):
        state.note_accelerometer((7, 0, 250), i * 60.0)
    assert evaluate_watch(state, 31 * 60.0, policy, wall_now=DAY) == "IMMOBILITY_WARNING"
    for i in range(32, 200):
        state.note_accelerometer((7, 0, 250), i * 60.0)
        assert evaluate_watch(state, i * 60.0, policy, wall_now=DAY) is None
    assert state.note_accelerometer((-64, -115, 227), 200 * 60.0) is True
    assert state.last_immobility_alert_at is None


# ----- Add device / assign API -----


def test_add_device_api_duplicates_and_validation(db, client, seed_tenant, admin_headers):
    tid = seed_tenant["tenant"].id
    elder = _elder(db, tid, "api")
    res = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "watch", "mac_address": "c3-00-00-98-f3-f8", "label": "Amma's watch"})
    assert res.status_code == 200, res.text
    assert res.json()["mac_address"] == WATCH_MAC and res.json()["elder_id"] is None
    dupe = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "sensor", "mac_address": WATCH_RAW_MAC})
    assert dupe.status_code == 409 and "already added" in dupe.text and "Amma's watch" in dupe.text
    bad = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "watch", "mac_address": "12:34"})
    assert bad.status_code == 400
    gw = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "gateway", "mac_address": GATEWAY_RAW_MAC, "elder_id": elder.id})
    assert gw.status_code == 200, gw.text
    url = gw.json()["http_url"]
    assert url.startswith("https://") and "/api/v1/home-safety/gateway/" in url
    gw_dupe = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "watch", "mac_address": GATEWAY_RAW_MAC})
    assert gw_dupe.status_code == 409
    # New link: the old one stops working.
    old_token = url.rsplit("/", 1)[1]
    new = client.post(f"/api/v1/iot/hubs/{gw.json()['id']}/http-token", headers=admin_headers).json()
    assert new["http_url"] != url
    assert client.get(f"/api/v1/home-safety/gateway/{old_token}").status_code == 404
    assert client.get(f"/api/v1/home-safety/gateway/{new['http_url'].rsplit('/', 1)[1]}").status_code == 200


def test_assign_move_unassign_and_family_card(db, client, seed_tenant, admin_headers):
    tid = seed_tenant["tenant"].id
    a = _elder(db, tid, "a")
    b = _elder(db, tid, "b")
    fam = User(
        email="fam.gw@test.example",
        password_hash=hash_password("testpass123"),
        first_name="F",
        last_name="G",
        role="ELDER_PORTAL",
        tenant_id=tid,
        elder_id=a.id,
    )
    db.add(fam)
    db.flush()
    ensure_family_elder_link(db, fam, a)
    db.commit()
    dev = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "watch", "mac_address": WATCH_RAW_MAC}).json()
    gw = client.post("/api/v1/iot/add-device", headers=admin_headers, json={"kind": "gateway", "mac_address": GATEWAY_RAW_MAC, "label": "MG3"}).json()
    assert IotRegistryService.device_map_for_tenant(db, tid) == {}  # unassigned: not in the map

    fam_headers = _login(client, fam.email)
    assert client.get("/api/v1/home-safety/family/devices", headers=fam_headers).json() == []

    assert client.put(f"/api/v1/iot/devices/{dev['id']}/assign", headers=admin_headers, json={"elder_id": a.id}).status_code == 200
    assert client.put(f"/api/v1/iot/hubs/{gw['id']}/assign", headers=admin_headers, json={"elder_id": a.id}).status_code == 200
    rows = client.get("/api/v1/home-safety/family/devices", headers=fam_headers).json()
    assert [(r["kind"], r["label"]) for r in rows] == [("watch", "SOS watch"), ("gateway", "Home gateway")]
    assert IotRegistryService.device_map_for_tenant(db, tid) == {WATCH_MAC: a.id}

    # Move to client b: gone from a's card.
    client.put(f"/api/v1/iot/devices/{dev['id']}/assign", headers=admin_headers, json={"elder_id": b.id})
    rows = client.get("/api/v1/home-safety/family/devices", headers=fam_headers).json()
    assert [r["kind"] for r in rows] == ["gateway"]
    # Unassign.
    res = client.put(f"/api/v1/iot/devices/{dev['id']}/assign", headers=admin_headers, json={"elder_id": None})
    assert res.json()["elder_id"] is None
    heard = client.get(f"/api/v1/iot/devices/{dev['id']}/heard", headers=admin_headers).json()
    assert heard["last_seen_at"] is None and heard["online"] is False
