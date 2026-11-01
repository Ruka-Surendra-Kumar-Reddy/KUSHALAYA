"""IoT events on Session activity timeline."""

import app.models.iot_device  # noqa: F401 — iot_hubs / iot_devices tables

from app.livewell.iot_activity_log import log_iot_ingest_event
from app.models.user_session import UserSessionEvent
from app.services.session_activity_service import SessionActivityService


def test_log_iot_ingest_creates_system_event(db, seed_tenant):
    """SOS ingest appends a system event with meta on the tenant system session."""
    tenant = seed_tenant["tenant"]
    elder = seed_tenant["elder"]

    sys_session = SessionActivityService.ensure_system_session(db, tenant_id=tenant.id)
    assert sys_session is not None
    db.flush()

    log_iot_ingest_event(
        db,
        tenant_id=tenant.id,
        event_type="SOS_BUTTON",
        elder_id=elder.id,
        mac_address="aa:bb:cc:dd:ee:ff",
        hub_id="mg7-1",
        incident_id="dsos-abc",
        raw_payload={"mac": "aa:bb:cc:dd:ee:ff", "sos": True},
    )
    db.flush()

    events = (
        db.query(UserSessionEvent)
        .filter(UserSessionEvent.session_id == sys_session.id)
        .all()
    )
    assert len(events) >= 1
    last = events[-1]
    assert last.event_kind == "system"
    assert "IoT" in last.action
    assert last.meta is not None
    assert last.meta.get("mac_address") == "aa:bb:cc:dd:ee:ff"
