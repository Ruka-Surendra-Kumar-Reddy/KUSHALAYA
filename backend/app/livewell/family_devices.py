"""Wearable / hub status for the family app — scoped to the active elder."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.elder import Elder
from app.models.iot_device import IotDevice, IotHub
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService


def _offline_seconds(db: Session) -> int:
    from app.livewell.iot_broker_settings import get_broker_settings

    try:
        value = int(get_broker_settings(db).get("offline_seconds") or 180)
    except Exception:
        value = 180
    return max(30, value)


def _is_online(last_seen: datetime | None, offline_seconds: int, *, now: datetime) -> bool:
    if last_seen is None:
        return False
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return now - last_seen <= timedelta(seconds=offline_seconds)


def _plain_label(label: str | None, kind: str) -> str:
    """Family-facing name: model codes (B7, MG7, G1, MG3) hidden."""
    rest = re.sub(r"\b(MG7|B7|G1|MG3)\b", "", label or "", flags=re.I)
    rest = re.sub(r"\s+", " ", rest).strip()
    fallback = {"gateway": "Home gateway", "sensor": "Sensor"}.get(kind, "SOS watch")
    if not rest or rest.lower() in {"band", "hub", "home hub", "gateway", "watch"}:
        return fallback
    return rest


def devices_for_elder(db: Session, elder: Elder) -> list[dict]:
    """Exactly this client's devices: watches/sensors given to them, then the
    gateway(s) placed in their home."""
    from app.livewell.iot_registry_service import device_kind

    offline_seconds = _offline_seconds(db)
    now = datetime.now(timezone.utc)
    rows = (
        db.query(IotDevice)
        .filter(
            IotDevice.tenant_id == elder.tenant_id,
            IotDevice.elder_id == elder.id,
            IotDevice.status == "active",
        )
        .order_by(IotDevice.id.asc())
        .all()
    )
    hub_ids = {d.hub_id for d in rows if d.hub_id}
    hubs = (
        {h.id: h for h in db.query(IotHub).filter(IotHub.id.in_(list(hub_ids))).all()}
        if hub_ids
        else {}
    )
    out: list[dict] = []
    for d in rows:
        hub = hubs.get(d.hub_id) if d.hub_id else None
        kind = device_kind(d.device_type)
        out.append(
            {
                "id": d.id,
                "kind": kind,
                "label": _plain_label(d.label, kind),
                "device_type": d.device_type or "B7",
                "battery_level": d.battery_level,
                "online": _is_online(d.last_seen_at, offline_seconds, now=now),
                "last_seen_at": d.last_seen_at,
                "offline_seconds": offline_seconds,
                "hub_label": hub.label if hub else None,
                "hub_online": (
                    _is_online(hub.last_seen_at, offline_seconds, now=now) if hub else None
                ),
                "hub_last_seen_at": hub.last_seen_at if hub else None,
            }
        )
    gateways = (
        db.query(IotHub)
        .filter(
            IotHub.tenant_id == elder.tenant_id,
            IotHub.elder_id == elder.id,
            IotHub.status == "active",
        )
        .order_by(IotHub.id.asc())
        .all()
    )
    for h in gateways:
        out.append(
            {
                "id": -h.id,  # distinct from watch ids in one list
                "kind": "gateway",
                "label": _plain_label(h.label, "gateway"),
                "device_type": "gateway",
                "battery_level": None,
                "online": _is_online(h.last_seen_at, offline_seconds, now=now),
                "last_seen_at": h.last_seen_at,
                "offline_seconds": offline_seconds,
                "hub_label": None,
                "hub_online": None,
                "hub_last_seen_at": None,
            }
        )
    return out


class FamilyDeviceService:
    @staticmethod
    def list_for_family(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        return devices_for_elder(db, elder)
