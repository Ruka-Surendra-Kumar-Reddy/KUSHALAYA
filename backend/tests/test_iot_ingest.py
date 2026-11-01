"""IoT wearable SOS ingest."""

from app.livewell.iot_ingest_service import IotIngestService
from app.models.elder import Elder


def test_raise_device_sos_creates_incident_and_alert(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="IoT",
        last_name="Senior",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    result = IotIngestService.raise_device_sos(
        db,
        elder_id=elder.id,
        device_id="b7-demo",
        hub_id="mg7-1",
        mac_address="aa:bb:cc:dd:ee:ff",
        source="mqtt",
    )
    assert result["id"].startswith("dsos_")
    assert result["status"] == "open"

    # A watch SOS is verified first (C1): nothing reaches the family until staff confirm.
    from app.livewell import sos_siren

    sos_siren.confirm(db, result["incident_db_id"], seed_tenant["admin"])
    sos_siren.notify_family(db, result["incident_db_id"], seed_tenant["admin"])
    db.refresh(elder)
    hub = (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})
    incidents = hub.get("incidents") or []
    alerts = hub.get("alerts") or []
    assert any(i.get("kind") == "sos" for i in incidents if isinstance(i, dict))
    assert any(a.get("severity") == "critical" for a in alerts if isinstance(a, dict))


def test_raise_immobility_and_offline_are_warnings(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="Watch",
        last_name="Senior",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    imm = IotIngestService.raise_device_event(
        db,
        event_type="IMMOBILITY_WARNING",
        elder_id=elder.id,
        mac_address="aa:bb:cc:dd:ee:ff",
        source="mqtt",
    )
    assert imm["id"].startswith("dimm_")
    off = IotIngestService.raise_device_event(
        db,
        event_type="DEVICE_OFFLINE",
        elder_id=elder.id,
        mac_address="aa:bb:cc:dd:ee:ff",
        source="mqtt",
    )
    assert off["id"].startswith("doff_")

    db.refresh(elder)
    hub = (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})
    incidents = hub.get("incidents") or []
    alerts = hub.get("alerts") or []
    kinds = {i.get("kind") for i in incidents if isinstance(i, dict)}
    assert "immobility" in kinds
    assert "device_offline" in kinds
    assert any(a.get("severity") == "warning" for a in alerts if isinstance(a, dict))
    sos = IotIngestService.raise_device_sos(db, elder_id=elder.id, source="mqtt")
    assert sos["id"].startswith("dsos_")
