"""IoT ingest + staff registry for MG7 hubs and B7 bands."""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, WRITE_ROLES, require_roles, resolve_tenant_id
from app.livewell.iot_broker_settings import (
    ensure_shared_hub_acl,
    get_broker_settings,
    ingest_watch_policy,
    load_from_credentials_file,
    minewlink_cheat_sheet,
    save_broker_settings,
)
from app.livewell.iot_registry_service import IotRegistryService
from app.models.user import User
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/iot", tags=["IoT"])


# ----- Ingest (MQTT bridge) -----


class IotEventRequest(BaseModel):
    event_type: str = Field(
        ...,
        description="SOS_BUTTON | IMMOBILITY_WARNING | DEVICE_OFFLINE | FALL_SUSPECTED",
    )
    elder_id: int | None = None
    device_id: str | None = None
    hub_id: str | None = None
    mac_address: str | None = None
    occurred_at: datetime | None = None
    rssi: int | None = None
    battery_level: int | None = None
    note: str | None = None
    raw_payload: dict | None = None
    dedupe_key: str | None = None


class IotEventResponse(BaseModel):
    accepted: bool
    incident_id: str | None = None
    duplicate: bool = False
    detail: str | None = None


def _require_iot_key(x_iot_ingest_key: str | None = Header(default=None, alias="X-IoT-Ingest-Key")) -> None:
    expected = (settings.IOT_INGEST_API_KEY or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="IoT ingest is not configured (IOT_INGEST_API_KEY)",
        )
    if not x_iot_ingest_key or not secrets.compare_digest(x_iot_ingest_key, expected):
        raise HTTPException(status_code=403, detail="Invalid IoT ingest key")


@router.post("/events", response_model=IotEventResponse)
def ingest_iot_event(
    body: IotEventRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_iot_key),
):
    from app.livewell.iot_gateway_http import accept_device_event

    out = accept_device_event(
        db,
        event_type=body.event_type,
        mac_address=body.mac_address,
        elder_id=body.elder_id,
        device_id=body.device_id,
        hub_id=body.hub_id,
        occurred_at=body.occurred_at,
        battery_level=body.battery_level,
        note=body.note,
        raw_payload=body.raw_payload,
        dedupe_key=body.dedupe_key,
        source="mqtt",
    )
    return IotEventResponse(
        accepted=bool(out.get("accepted")),
        incident_id=out.get("incident_id"),
        duplicate=bool(out.get("duplicate")),
        detail=out.get("detail"),
    )


@router.get("/device-map")
def iot_device_map(
    db: Session = Depends(get_db),
    _: None = Depends(_require_iot_key),
):
    """MAC → elder_id for the MQTT ingestor (replaces static IOT_DEVICE_MAP)."""
    return {
        "devices": IotRegistryService.device_map_for_tenant(db, tenant_id=None),
        "policy": ingest_watch_policy(get_broker_settings(db)),
    }


# ----- Staff registry -----


class RegisterHubRequest(BaseModel):
    label: str = "MG7 hub"
    home_key: str = "home1"
    hub_key: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    provision_mqtt: bool = True


class RegisterDeviceRequest(BaseModel):
    elder_id: int
    mac_address: str
    hub_id: int | None = None
    label: str = "B7 band"
    device_type: str = "B7"
    notes: str | None = None


class RegisterKitRequest(BaseModel):
    """One new MG7 + one B7 for an elder — returns MinewLink settings."""

    elder_id: int
    mac_address: str
    hub_label: str = "MG7 hub"
    band_label: str = "B7 band"
    home_key: str = "home1"
    hub_serial: str | None = None
    provision_mqtt: bool = True
    use_shared_broker: bool | None = None


class BrokerSettingsUpdate(BaseModel):
    broker_host: str
    broker_port: int = 8883
    tls: bool = True
    hub_username: str
    hub_password: str = ""
    ingestor_username: str = "livewell_ingestor"
    ingestor_password: str = ""
    ingestor_mqtt_topic: str = "livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status"
    dedupe_seconds: int = 65
    immobility_enabled: bool = True
    immobility_minutes: int = 30
    offline_enabled: bool = True
    offline_seconds: int = 180
    quiet_period_minutes: int = 60
    active_hours_start: int = 7
    active_hours_end: int = 21
    timezone: str = "Asia/Kolkata"
    watch_policy_version: int = 2
    topic_mode: str = "minew_status"
    subscribe_topic: str = ""
    reply_topic: str = ""
    use_shared_hub: bool = True
    notes: str | None = None
    # Blank passwords keep the stored ones; with this flag, take them from .credentials.app.
    from_credentials_file: bool = False


class UpdateMacForElderRequest(BaseModel):
    """Replace (or create) the B7 MAC bound to an elder."""

    elder_id: int
    mac_address: str
    device_id: int | None = None
    label: str | None = None


def _log_staff_iot(
    request: Request,
    db: Session,
    user: User,
    *,
    action: str,
    summary: str,
    entity_type: str = "iot",
    entity_id: str | None = None,
) -> None:
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=user,
        action=action,
        summary=summary,
        entity_type=entity_type,
        entity_id=entity_id,
        commit=False,
    )


@router.get("/hubs")
def list_hubs(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    secret = user.role in ADMIN_ROLES
    return [IotRegistryService._hub_dict(h, include_secret=secret) for h in IotRegistryService.list_hubs(db, tid)]


# Broker settings are GLOBAL (one AppGlobalSetting row for every tenant), so they are
# admin-only, and passwords never leave the server: GET/PUT answer with "" plus
# `<field>_set` / `<field>_masked`; a PUT with a blank password keeps the stored one.
_BROKER_PASSWORDS = ("hub_password", "ingestor_password")


def _mask_broker(data: dict) -> dict:
    out = dict(data)
    for field in _BROKER_PASSWORDS:
        value = str(out.get(field) or "")
        out[field] = ""
        out[f"{field}_set"] = bool(value)
        out[f"{field}_masked"] = "••••••••" if value else ""
    return out


@router.get("/broker-settings")
def get_iot_broker_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Single source of truth for MinewLink MQTT fields (Wearables). Passwords masked."""
    return _mask_broker(get_broker_settings(db))


WATCH_FIELDS = (
    "immobility_enabled", "immobility_minutes", "offline_enabled", "offline_seconds",
    "active_hours_start", "active_hours_end", "dedupe_seconds",
)


class WatchSettingsUpdate(BaseModel):
    immobility_enabled: bool
    immobility_minutes: int = Field(ge=1, le=1440)
    offline_enabled: bool
    offline_seconds: int = Field(ge=30, le=3600)
    active_hours_start: int = Field(ge=0, le=23)
    active_hours_end: int = Field(ge=0, le=23)


@router.get("/watch-settings")
def get_watch_settings(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    """Band alerts (not moving, offline): the band-watch part of the broker settings."""
    current = get_broker_settings(db)
    return {k: current[k] for k in WATCH_FIELDS}


@router.put("/watch-settings")
def put_watch_settings(
    body: WatchSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Changes only the band-alert fields; broker host and passwords stay as they are."""
    saved = save_broker_settings(db, {**get_broker_settings(db), **body.model_dump()})
    _log_staff_iot(request, db, user, action="Updated band alerts",
                   summary=f"not moving {body.immobility_minutes} min, offline {body.offline_seconds}s")
    db.commit()
    return {k: saved[k] for k in WATCH_FIELDS}


@router.put("/broker-settings")
def put_iot_broker_settings(
    body: BrokerSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    payload = body.model_dump(exclude={"from_credentials_file"})
    current = get_broker_settings(db)
    file_creds = load_from_credentials_file() if body.from_credentials_file else {}
    for field in _BROKER_PASSWORDS:
        if not payload.get(field):
            payload[field] = file_creds.get(field) or current.get(field) or ""
    saved = _mask_broker(save_broker_settings(db, payload))
    _log_staff_iot(
        request,
        db,
        user,
        action="Updated IoT broker settings",
        summary=f"{saved.get('hub_username')} @ {saved.get('broker_host')}:{saved.get('broker_port')}",
    )
    db.commit()
    return saved


@router.post("/broker-settings/load-credentials-file")
def load_broker_from_credentials_file(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Prefill from /var/lib/safehomeops/mqtt/.credentials.app (does not save until PUT).

    Passwords come back masked; send `from_credentials_file: true` on the PUT to use them.
    """
    return _mask_broker(load_from_credentials_file())


@router.post("/broker-settings/apply-mosquitto")
def apply_broker_to_mosquitto(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Best-effort: Mosquitto hub + ingestor users; sync iot_ingestor.env and restart ingestor."""
    result = ensure_shared_hub_acl(db)
    _log_staff_iot(
        request,
        db,
        user,
        action="Applied IoT broker to Mosquitto",
        summary=result.get("detail") or ("ok" if result.get("ok") else "failed"),
    )
    db.commit()
    return result


@router.get("/minewlink-preview")
def minewlink_preview(
    mac_address: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Preview MinewLink fields for a band MAC using broker settings."""
    return minewlink_cheat_sheet(db, mac_address=mac_address)


@router.get("/devices")
def list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    return IotRegistryService.devices_for_api(db, tid)


@router.post("/hubs")
def create_hub(
    body: RegisterHubRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    hub = IotRegistryService.register_hub(
        db,
        tenant_id=tid,
        label=body.label,
        home_key=body.home_key,
        hub_key=body.hub_key,
        serial_number=body.serial_number,
        notes=body.notes,
        provision_mqtt=body.provision_mqtt,
    )
    _log_staff_iot(
        request,
        db,
        user,
        action="Registered IoT hub",
        summary=f"{body.label} · topic {hub.get('mqtt_topic', '')}",
        entity_id=str(hub.get("id", "")),
    )
    return hub


@router.post("/devices")
def create_device(
    body: RegisterDeviceRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    device = IotRegistryService.register_device(
        db,
        tenant_id=tid,
        elder_id=body.elder_id,
        mac_address=body.mac_address,
        hub_id=body.hub_id,
        label=body.label,
        device_type=body.device_type,
        notes=body.notes,
    )
    _log_staff_iot(
        request,
        db,
        user,
        action="Registered IoT band",
        summary=f"{body.mac_address} → elder #{body.elder_id}",
        entity_type="elder",
        entity_id=str(body.elder_id),
    )
    return device


@router.post("/register-kit")
def register_kit(
    body: RegisterKitRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Automate adding a new B7 + MG7: DB rows + MQTT user/ACL + MinewLink cheat-sheet."""
    tid = resolve_tenant_id(user)
    result = IotRegistryService.register_kit(
        db,
        tenant_id=tid,
        elder_id=body.elder_id,
        mac_address=body.mac_address,
        hub_label=body.hub_label,
        band_label=body.band_label,
        home_key=body.home_key,
        hub_serial=body.hub_serial,
        provision_mqtt=body.provision_mqtt,
        use_shared_broker=body.use_shared_broker,
    )
    _log_staff_iot(
        request,
        db,
        user,
        action="Registered IoT kit",
        summary=f"{body.mac_address} → elder #{body.elder_id} · hub #{result['hub']['id']}",
        entity_type="elder",
        entity_id=str(body.elder_id),
    )
    return result


@router.put("/devices/mac")
def update_mac_for_elder(
    body: UpdateMacForElderRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Update the B7 MAC for an elder (new band, same client)."""
    tid = resolve_tenant_id(user)
    device = IotRegistryService.update_mac_for_elder(
        db,
        tenant_id=tid,
        elder_id=body.elder_id,
        mac_address=body.mac_address,
        device_id=body.device_id,
        label=body.label,
    )
    _log_staff_iot(
        request,
        db,
        user,
        action="Updated IoT band MAC",
        summary=f"elder #{body.elder_id} → {device['mac_address']}",
        entity_type="elder",
        entity_id=str(body.elder_id),
    )
    return device


@router.post("/devices/{device_id}/test")
def send_band_test(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """"Send test" on Bands: a test email to the people who get this client's alerts."""
    from app.livewell.band_checks import send_test

    tid = resolve_tenant_id(user)
    out = send_test(db, tid, device_id)
    _log_staff_iot(request, db, user, action="Sent band test alert", summary=f"band #{device_id}", entity_id=str(device_id))
    db.commit()
    return out


class AddDeviceRequest(BaseModel):
    """The ops "Add device" form."""

    kind: str = Field(..., description="gateway | watch | sensor")
    mac_address: str
    label: str | None = None
    elder_id: int | None = None


class AssignRequest(BaseModel):
    elder_id: int | None = None  # None = take it back (not assigned)


@router.post("/add-device")
def add_device(
    body: AddDeviceRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    out = IotRegistryService.add_device(
        db,
        tenant_id=tid,
        kind=body.kind,
        mac_address=body.mac_address,
        label=body.label,
        elder_id=body.elder_id,
    )
    if user.role not in ADMIN_ROLES:
        out.pop("http_url", None)
        out.pop("mqtt_password", None)
    _log_staff_iot(
        request,
        db,
        user,
        action="Added IoT device",
        summary=f"{body.kind} {out.get('mac_address')}" + (f" → client #{body.elder_id}" if body.elder_id else ""),
        entity_id=str(out.get("id", "")),
    )
    db.commit()
    return out


@router.put("/devices/{device_id}/assign")
def assign_device(
    device_id: int,
    body: AssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Give a watch / sensor to a client, move it, or unassign it (elder_id null)."""
    tid = resolve_tenant_id(user)
    out = IotRegistryService.assign_device(db, tenant_id=tid, device_id=device_id, elder_id=body.elder_id)
    _log_staff_iot(
        request,
        db,
        user,
        action="Assigned IoT device" if body.elder_id else "Unassigned IoT device",
        summary=f"{out.get('mac_address')} → " + (f"client #{body.elder_id}" if body.elder_id else "not assigned"),
        entity_type="elder" if body.elder_id else "iot",
        entity_id=str(body.elder_id or device_id),
    )
    db.commit()
    return out


@router.put("/hubs/{hub_id}/assign")
def assign_hub(
    hub_id: int,
    body: AssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(user)
    out = IotRegistryService.assign_hub(db, tenant_id=tid, hub_id=hub_id, elder_id=body.elder_id)
    if user.role not in ADMIN_ROLES:
        out.pop("http_url", None)
        out.pop("mqtt_password", None)
    _log_staff_iot(
        request,
        db,
        user,
        action="Assigned gateway" if body.elder_id else "Unassigned gateway",
        summary=f"{out.get('label')} → " + (f"client #{body.elder_id}" if body.elder_id else "not assigned"),
        entity_id=str(hub_id),
    )
    db.commit()
    return out


@router.post("/hubs/{hub_id}/http-token")
def regenerate_hub_http_token(
    hub_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """New HTTP upload link for a gateway; the old one stops working at once."""
    tid = resolve_tenant_id(user)
    out = IotRegistryService.regenerate_http_token(db, tenant_id=tid, hub_id=hub_id)
    _log_staff_iot(request, db, user, action="New gateway upload link", summary=str(out.get("label")), entity_id=str(hub_id))
    db.commit()
    return out


@router.get("/devices/{device_id}/heard")
def device_heard(
    device_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """The "Test" button: when the device was last heard."""
    return IotRegistryService.heard(db, tenant_id=resolve_tenant_id(user), device_id=device_id)


@router.get("/hubs/{hub_id}/heard")
def hub_heard(
    hub_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return IotRegistryService.heard(db, tenant_id=resolve_tenant_id(user), hub_id=hub_id)


@router.delete("/devices/{device_id}")
def delete_device(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Unbind / remove a B7 band so SOS for that MAC stops resolving to the elder."""
    tid = resolve_tenant_id(user)
    removed = IotRegistryService.delete_device(db, tenant_id=tid, device_id=device_id)
    _log_staff_iot(
        request,
        db,
        user,
        action="Removed IoT band",
        summary=f"{removed.get('mac_address')} · elder #{removed.get('elder_id')}",
        entity_type="elder",
        entity_id=str(removed.get("elder_id") or ""),
    )
    db.commit()
    return {"ok": True, "removed": removed}


@router.delete("/hubs/{hub_id}")
def delete_hub(
    hub_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Delete an MG7 hub row; bands stay bound by MAC but lose hub link."""
    tid = resolve_tenant_id(user)
    removed = IotRegistryService.delete_hub(db, tenant_id=tid, hub_id=hub_id)
    _log_staff_iot(
        request,
        db,
        user,
        action="Removed IoT hub",
        summary=f"{removed.get('label')} · {removed.get('mqtt_username')}",
        entity_id=str(hub_id),
    )
    db.commit()
    return {"ok": True, "removed": removed}
