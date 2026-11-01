"""IoT device delete / unbind."""

from app.livewell.iot_registry_service import IotRegistryService
from app.models.elder import Elder
from app.models.iot_device import IotDevice


def test_delete_device_removes_mac_binding(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="Band",
        last_name="Owner",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    created = IotRegistryService.register_device(
        db,
        tenant_id=tenant.id,
        elder_id=elder.id,
        mac_address="c3:00:00:98:f3:f8",
        label="B7 test",
    )
    assert created["id"]
    assert IotRegistryService.resolve_elder_id(db, "C3000098F3F8") == elder.id

    removed = IotRegistryService.delete_device(
        db, tenant_id=tenant.id, device_id=int(created["id"])
    )
    assert removed["mac_address"] == "c3:00:00:98:f3:f8"
    assert IotRegistryService.resolve_elder_id(db, "c3:00:00:98:f3:f8") is None
    assert db.query(IotDevice).filter(IotDevice.id == created["id"]).first() is None


def test_delete_hub_unlinks_devices(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="Hub",
        last_name="Owner",
        status="ACTIVE",
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)

    hub = IotRegistryService.register_hub(
        db,
        tenant_id=tenant.id,
        label="Test hub",
        provision_mqtt=False,
    )
    device = IotRegistryService.register_device(
        db,
        tenant_id=tenant.id,
        elder_id=elder.id,
        mac_address="aa:bb:cc:dd:ee:11",
        hub_id=hub["id"],
    )
    assert device["hub_id"] == hub["id"]

    IotRegistryService.delete_hub(db, tenant_id=tenant.id, hub_id=int(hub["id"]))
    row = db.query(IotDevice).filter(IotDevice.id == device["id"]).first()
    assert row is not None
    assert row.hub_id is None
    assert IotRegistryService.resolve_elder_id(db, "aa:bb:cc:dd:ee:11") == elder.id
