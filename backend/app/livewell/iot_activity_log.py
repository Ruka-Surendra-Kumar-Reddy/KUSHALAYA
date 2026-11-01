"""Write IoT ingest + registry actions to Session activity (system / staff timeline)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.elder import Elder
from app.services.session_activity_service import (
    SessionActivityService,
    is_verbose_activity_log,
)


def _trim_meta(meta: dict[str, Any]) -> dict[str, Any]:
    if is_verbose_activity_log():
        return meta
    raw = meta.get("raw_payload")
    if raw is not None:
        try:
            blob = json.dumps(raw, default=str)
        except (TypeError, ValueError):
            blob = str(raw)
        if len(blob) > 400:
            meta = {**meta, "raw_payload": f"{blob[:397]}… (set ACTIVITY_LOG_MODE=verbose for full JSON)"}
    return meta


def log_iot_ingest_event(
    db: Session,
    *,
    tenant_id: int,
    event_type: str,
    elder_id: int | None = None,
    mac_address: str | None = None,
    hub_id: str | None = None,
    device_id: str | None = None,
    incident_id: str | None = None,
    note: str | None = None,
    raw_payload: dict | None = None,
    accepted: bool = True,
    detail: str | None = None,
) -> None:
    """Append IoT MQTT/API ingest to the tenant system session timeline."""
    sys_session = SessionActivityService.ensure_system_session(db, tenant_id=tenant_id)
    if not sys_session:
        return

    et = (event_type or "UNKNOWN").strip().upper()
    if accepted and et in {"SOS_BUTTON", "FALL_SUSPECTED", "IMMOBILITY_WARNING", "DEVICE_OFFLINE"}:
        action = f"IoT {et.replace('_', ' ').title()}"
    elif not accepted:
        action = "IoT event ignored"
    else:
        action = f"IoT {et}"

    parts: list[str] = []
    if elder_id:
        parts.append(f"elder #{elder_id}")
    if mac_address:
        parts.append(f"mac={mac_address}")
    if hub_id:
        parts.append(f"hub={hub_id}")
    if incident_id:
        parts.append(f"incident={incident_id}")
    if detail:
        parts.append(detail)
    summary = " · ".join(parts) if parts else note

    meta: dict[str, Any] = {
        "source": "iot_mqtt",
        "event_type": et,
        "accepted": accepted,
    }
    if mac_address:
        meta["mac_address"] = mac_address
    if hub_id:
        meta["hub_id"] = hub_id
    if device_id:
        meta["device_id"] = device_id
    if raw_payload is not None:
        meta["raw_payload"] = raw_payload

    SessionActivityService.record_event(
        db,
        session_id=sys_session.id,
        tenant_id=tenant_id,
        event_kind="system",
        action=action[:120],
        entity_type="elder" if elder_id else "iot",
        entity_id=str(elder_id) if elder_id else mac_address,
        summary=summary,
        meta=_trim_meta(meta),
        commit=False,
    )


def log_iot_ingest_for_elder(
    db: Session,
    *,
    elder_id: int,
    event_type: str,
    mac_address: str | None = None,
    hub_id: str | None = None,
    device_id: str | None = None,
    incident_id: str | None = None,
    note: str | None = None,
    raw_payload: dict | None = None,
) -> None:
    elder = db.query(Elder).filter(Elder.id == elder_id).first()
    if not elder:
        return
    log_iot_ingest_event(
        db,
        tenant_id=int(elder.tenant_id),
        event_type=event_type,
        elder_id=elder_id,
        mac_address=mac_address,
        hub_id=hub_id,
        device_id=device_id,
        incident_id=incident_id,
        note=note,
        raw_payload=raw_payload,
        accepted=True,
    )


def log_iot_ingest_ignored(
    db: Session,
    *,
    event_type: str,
    mac_address: str | None = None,
    raw_payload: dict | None = None,
    detail: str | None = None,
) -> None:
    """Best-effort log when event type is skipped (no elder / unknown type)."""
    tenant_id: int | None = None
    elder_id: int | None = None
    if mac_address:
        from app.livewell.iot_registry_service import IotRegistryService

        elder_id = IotRegistryService.resolve_elder_id(db, mac_address)
        if elder_id:
            elder = db.query(Elder).filter(Elder.id == elder_id).first()
            if elder:
                tenant_id = int(elder.tenant_id)
    if tenant_id is None:
        # Fall back to first tenant with an open system session pattern — skip if unknown
        return
    log_iot_ingest_event(
        db,
        tenant_id=tenant_id,
        event_type=event_type,
        elder_id=elder_id,
        mac_address=mac_address,
        raw_payload=raw_payload,
        accepted=False,
        detail=detail,
    )
