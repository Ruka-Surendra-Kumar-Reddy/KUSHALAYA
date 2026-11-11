"""Register MG7 hubs + B7 bands; optional Mosquitto passwd/ACL provisioning."""

from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.models.elder import Elder
from app.models.iot_device import IotDevice, IotHub


def normalize_mac(mac: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", (mac or "")).lower()
    if len(cleaned) != 12:
        raise_bad_request("mac_address must be 12 hex digits (e.g. AA:BB:CC:DD:EE:FF)")
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


# What the ops "Add device" form offers. Old rows say "B7" (= SOS watch).
DEVICE_KINDS = ("gateway", "watch", "sensor")
WATCH_TYPES = frozenset({"watch", "band", "b7", "sos_watch"})


def device_kind(device_type: str | None) -> str:
    t = (device_type or "").strip().lower()
    if t == "sensor":
        return "sensor"
    return "watch"  # B7 / band / watch / blank


def new_http_token() -> str:
    return secrets.token_urlsafe(32)


def gateway_http_url(token: str | None) -> str | None:
    if not token:
        return None
    host = (getattr(settings, "IOT_MQTT_PUBLIC_HOST", None) or "ops.kushalaya.com").strip()
    return f"https://{host}/api/v1/home-safety/gateway/{token}"


def _mqtt_runtime() -> Path:
    return Path(
        (getattr(settings, "IOT_MQTT_RUNTIME", None) or "").strip()
        or os.getenv("IOT_MQTT_RUNTIME", "/var/lib/safehomeops/mqtt")
    )


def _gen_password(n: int = 20) -> str:
    # URL-safe, no ambiguous punctuation for MinewLink paste
    return secrets.token_urlsafe(n)[:n]


def _slug(s: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_-]+", "-", (s or "").strip().lower()).strip("-")
    return out[:48] or "hub"


class IotRegistryService:
    @staticmethod
    def list_hubs(db: Session, tenant_id: int) -> list[IotHub]:
        return (
            db.query(IotHub)
            .filter(IotHub.tenant_id == tenant_id)
            .order_by(IotHub.id.desc())
            .all()
        )

    @staticmethod
    def list_devices(db: Session, tenant_id: int) -> list[IotDevice]:
        return (
            db.query(IotDevice)
            .filter(IotDevice.tenant_id == tenant_id)
            .order_by(IotDevice.id.desc())
            .all()
        )

    @staticmethod
    def device_map_for_tenant(db: Session, tenant_id: int | None = None) -> dict[str, int]:
        q = db.query(IotDevice).filter(IotDevice.status == "active")
        if tenant_id is not None:
            q = q.filter(IotDevice.tenant_id == tenant_id)
        out: dict[str, int] = {}
        for d in q.all():
            if d.elder_id is None:
                continue  # not given to a client: never alerts anyone
            out[normalize_mac(d.mac_address)] = int(d.elder_id)
        return out

    @staticmethod
    def resolve_elder_id(db: Session, mac: str | None) -> int | None:
        if not mac:
            return None
        try:
            m = normalize_mac(mac)
        except Exception:
            return None
        row = (
            db.query(IotDevice)
            .filter(IotDevice.mac_address == m, IotDevice.status == "active")
            .first()
        )
        return int(row.elder_id) if row and row.elder_id else None

    @staticmethod
    def register_hub(
        db: Session,
        *,
        tenant_id: int,
        label: str = "MG7 hub",
        home_key: str = "home1",
        hub_key: str | None = None,
        serial_number: str | None = None,
        notes: str | None = None,
        provision_mqtt: bool = True,
    ) -> dict:
        home = _slug(home_key) or "home1"
        hkey = _slug(hub_key or f"mg7-{secrets.token_hex(2)}") or "mg7-1"
        username = f"mg7_{home}_{hkey}".replace("-", "_")[:80]
        # Keep username unique per tenant
        existing = (
            db.query(IotHub)
            .filter(IotHub.tenant_id == tenant_id, IotHub.mqtt_username == username)
            .first()
        )
        if existing:
            username = f"{username}_{secrets.token_hex(2)}"

        password = _gen_password(24)
        topic = f"livewell/homes/{home}/hubs/{hkey}/ble"
        hub = IotHub(
            tenant_id=tenant_id,
            home_key=home,
            hub_key=hkey,
            label=(label or "MG7 hub").strip()[:200],
            serial_number=(serial_number or None),
            mqtt_username=username,
            mqtt_password=password,
            mqtt_topic=topic,
            status="active",
            notes=notes,
        )
        db.add(hub)
        db.commit()
        db.refresh(hub)

        mqtt_result = {"ok": False, "detail": "skipped"}
        if provision_mqtt:
            mqtt_result = IotRegistryService.provision_hub_mqtt(db, hub)

        return IotRegistryService._hub_dict(hub, include_secret=True, mqtt=mqtt_result)

    @staticmethod
    def register_device(
        db: Session,
        *,
        tenant_id: int,
        elder_id: int | None,
        mac_address: str,
        hub_id: int | None = None,
        label: str = "B7 band",
        device_type: str = "B7",
        notes: str | None = None,
        strict: bool = False,
    ) -> dict:
        """Add a watch / sensor. ``strict`` (the Add device form): a MAC that is
        already registered is an error, not a silent re-bind."""
        if elder_id is not None:
            IotRegistryService._elder_or_404(db, tenant_id, elder_id)

        mac = normalize_mac(mac_address)
        clash = db.query(IotDevice).filter(IotDevice.mac_address == mac).first()
        if clash:
            if clash.tenant_id != tenant_id:
                raise_conflict("This MAC is already registered to another tenant")
            if strict:
                raise_conflict(IotRegistryService._dupe_message(db, clash))
            # Update binding (idempotent re-register)
            if hub_id is not None:
                hub = (
                    db.query(IotHub)
                    .filter(IotHub.id == hub_id, IotHub.tenant_id == tenant_id)
                    .first()
                )
                if not hub:
                    raise_not_found("Hub not found")
                clash.hub_id = hub.id
            clash.elder_id = elder_id
            clash.label = (label or clash.label).strip()[:200]
            clash.device_type = (device_type or "B7").strip()[:40]
            clash.status = "active"
            if notes is not None:
                clash.notes = notes
            db.commit()
            db.refresh(clash)
            return IotRegistryService._device_dict(clash)

        if hub_id is not None:
            hub = (
                db.query(IotHub)
                .filter(IotHub.id == hub_id, IotHub.tenant_id == tenant_id)
                .first()
            )
            if not hub:
                raise_not_found("Hub not found")
        else:
            hub = None

        device = IotDevice(
            tenant_id=tenant_id,
            hub_id=hub.id if hub else None,
            elder_id=elder_id,
            device_type=(device_type or "B7").strip()[:40],
            label=(label or "B7 band").strip()[:200],
            mac_address=mac,
            status="active",
            notes=notes,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return IotRegistryService._device_dict(device)

    @staticmethod
    def _elder_or_404(db: Session, tenant_id: int, elder_id: int) -> Elder:
        elder = db.query(Elder).filter(Elder.id == elder_id, Elder.tenant_id == tenant_id).first()
        if not elder:
            raise_not_found("Client not found")
        return elder

    @staticmethod
    def _dupe_message(db: Session, clash: IotDevice | IotHub) -> str:
        owner = ""
        if clash.elder_id:
            elder = db.get(Elder, clash.elder_id)
            if elder:
                owner = f" for {(elder.first_name or '').strip()} {(elder.last_name or '').strip()}".rstrip()
        name = (clash.label or "").strip() or "a device"
        return f"This MAC is already added as \"{name}\"{owner}. Find it in the list to move or remove it."

    @staticmethod
    def add_device(
        db: Session,
        *,
        tenant_id: int,
        kind: str,
        mac_address: str,
        label: str | None = None,
        elder_id: int | None = None,
    ) -> dict:
        """The ops "Add device" form: gateway, SOS watch or sensor; client optional."""
        k = (kind or "").strip().lower()
        if k not in DEVICE_KINDS:
            raise_bad_request("Type must be gateway, watch or sensor")
        mac = normalize_mac(mac_address)
        hub_clash = db.query(IotHub).filter(IotHub.mac_address == mac).first()
        if hub_clash:
            if hub_clash.tenant_id != tenant_id:
                raise_conflict("This MAC is already registered to another tenant")
            raise_conflict(IotRegistryService._dupe_message(db, hub_clash))
        if k != "gateway":
            return IotRegistryService.register_device(
                db,
                tenant_id=tenant_id,
                elder_id=elder_id,
                mac_address=mac,
                label=(label or "").strip() or ("SOS watch" if k == "watch" else "Sensor"),
                device_type=k,
                strict=True,
            )
        dev_clash = db.query(IotDevice).filter(IotDevice.mac_address == mac).first()
        if dev_clash:
            if dev_clash.tenant_id != tenant_id:
                raise_conflict("This MAC is already registered to another tenant")
            raise_conflict(IotRegistryService._dupe_message(db, dev_clash))
        if elder_id is not None:
            IotRegistryService._elder_or_404(db, tenant_id, elder_id)
        compact = mac.replace(":", "")
        hub = IotHub(
            tenant_id=tenant_id,
            home_key="home1",
            hub_key=f"gw-{compact}",
            label=((label or "").strip() or "Gateway")[:200],
            mqtt_username=f"gw_{compact}",
            mqtt_password=_gen_password(24),
            mqtt_topic=f"/mg7/{compact}/status",
            status="active",
            mac_address=mac,
            http_token=new_http_token(),
            elder_id=elder_id,
        )
        db.add(hub)
        db.commit()
        db.refresh(hub)
        return {**IotRegistryService._hub_dict(hub, include_secret=True), "kind": "gateway"}

    @staticmethod
    def assign_device(db: Session, *, tenant_id: int, device_id: int, elder_id: int | None) -> dict:
        """Give a watch/sensor to a client, move it, or take it back (None)."""
        device = (
            db.query(IotDevice)
            .filter(IotDevice.id == device_id, IotDevice.tenant_id == tenant_id)
            .first()
        )
        if not device:
            raise_not_found("Device not found")
        if elder_id is not None:
            IotRegistryService._elder_or_404(db, tenant_id, elder_id)
        if device.elder_id != elder_id:
            # New wearer: the old wearer's motion clock and alert latches do not apply.
            device.last_motion_at = None
            device.motion_xyz = None
            device.sos_active_at = None
            device.immobility_alerted_at = None
        device.elder_id = elder_id
        device.status = "active"
        db.commit()
        db.refresh(device)
        return IotRegistryService._device_dict(device)

    @staticmethod
    def _hub_or_404(db: Session, tenant_id: int, hub_id: int) -> IotHub:
        hub = db.query(IotHub).filter(IotHub.id == hub_id, IotHub.tenant_id == tenant_id).first()
        if not hub:
            raise_not_found("Gateway not found")
        return hub

    @staticmethod
    def assign_hub(db: Session, *, tenant_id: int, hub_id: int, elder_id: int | None) -> dict:
        hub = IotRegistryService._hub_or_404(db, tenant_id, hub_id)
        if elder_id is not None:
            IotRegistryService._elder_or_404(db, tenant_id, elder_id)
        hub.elder_id = elder_id
        db.commit()
        db.refresh(hub)
        return IotRegistryService._hub_dict(hub, include_secret=True)

    @staticmethod
    def regenerate_http_token(db: Session, *, tenant_id: int, hub_id: int) -> dict:
        """New upload link for a gateway; the old link stops working at once."""
        hub = IotRegistryService._hub_or_404(db, tenant_id, hub_id)
        hub.http_token = new_http_token()
        db.commit()
        db.refresh(hub)
        return IotRegistryService._hub_dict(hub, include_secret=True)

    @staticmethod
    def find_hub_by_token(db: Session, token: str | None) -> IotHub | None:
        t = (token or "").strip()
        if len(t) < 24:
            return None
        hub = db.query(IotHub).filter(IotHub.http_token == t).first()
        if hub is None or (hub.status or "active") != "active":
            return None
        if not secrets.compare_digest(hub.http_token or "", t):
            return None
        return hub

    @staticmethod
    def heard(db: Session, *, tenant_id: int, device_id: int | None = None, hub_id: int | None = None) -> dict:
        """The "Test" button: when this device was last heard, and how."""
        from app.livewell.family_devices import _is_online, _offline_seconds

        offline = _offline_seconds(db)
        now = datetime.now(timezone.utc)
        if hub_id is not None:
            hub = IotRegistryService._hub_or_404(db, tenant_id, hub_id)
            return {
                "id": hub.id,
                "kind": "gateway",
                "last_seen_at": hub.last_seen_at,
                "online": _is_online(hub.last_seen_at, offline, now=now),
                "battery_level": None,
                "rssi": None,
                "checked_at": now,
            }
        device = (
            db.query(IotDevice)
            .filter(IotDevice.id == device_id, IotDevice.tenant_id == tenant_id)
            .first()
        )
        if not device:
            raise_not_found("Device not found")
        hub = db.get(IotHub, device.hub_id) if device.hub_id else None
        return {
            "id": device.id,
            "kind": device_kind(device.device_type),
            "last_seen_at": device.last_seen_at,
            "online": _is_online(device.last_seen_at, offline, now=now),
            "battery_level": device.battery_level,
            "rssi": device.last_rssi,
            "via": hub.label if hub else None,
            "checked_at": now,
        }

    @staticmethod
    def update_mac_for_elder(
        db: Session,
        *,
        tenant_id: int,
        elder_id: int,
        mac_address: str,
        device_id: int | None = None,
        label: str | None = None,
    ) -> dict:
        """Change the B7 MAC bound to an elder (replace band without a new kit)."""
        elder = (
            db.query(Elder)
            .filter(Elder.id == elder_id, Elder.tenant_id == tenant_id)
            .first()
        )
        if not elder:
            raise_not_found("Elder not found in this tenant")

        mac = normalize_mac(mac_address)
        clash = db.query(IotDevice).filter(IotDevice.mac_address == mac).first()
        if clash and clash.tenant_id != tenant_id:
            raise_conflict("This MAC is already registered to another tenant")
        if clash and clash.elder_id != elder_id:
            # Move MAC from another elder in this tenant onto this elder
            if device_id is not None and clash.id != device_id:
                raise_conflict("This MAC belongs to another device row; remove or reassign it first")

        q = (
            db.query(IotDevice)
            .filter(
                IotDevice.tenant_id == tenant_id,
                IotDevice.elder_id == elder_id,
                IotDevice.status == "active",
            )
            .order_by(IotDevice.id.desc())
        )
        if device_id is not None:
            device = q.filter(IotDevice.id == device_id).first()
            if not device:
                raise_not_found("Device not found for this elder")
        else:
            devices = q.all()
            if not devices:
                # No existing band — create a MAC-only bind (no new hub)
                return IotRegistryService.register_device(
                    db,
                    tenant_id=tenant_id,
                    elder_id=elder_id,
                    mac_address=mac,
                    label=label or "B7 band",
                )
            if len(devices) > 1:
                raise_bad_request(
                    "Elder has multiple bands; pass device_id to choose which MAC to update"
                )
            device = devices[0]

        if clash and clash.id != device.id:
            # Same tenant, different row already has this MAC — re-point that row
            # and deactivate the old elder device if different
            if clash.elder_id != elder_id:
                clash.elder_id = elder_id
            if label:
                clash.label = label.strip()[:200]
            clash.status = "active"
            if device.id != clash.id:
                device.status = "inactive"
            db.commit()
            db.refresh(clash)
            return IotRegistryService._device_dict(clash)

        if device.mac_address != mac:
            # A new physical band: the old one's battery and last-seen no longer apply.
            device.battery_level = None
            device.last_seen_at = None
        device.mac_address = mac
        if label:
            device.label = label.strip()[:200]
        device.status = "active"
        db.commit()
        db.refresh(device)
        return IotRegistryService._device_dict(device)

    @staticmethod
    def delete_device(db: Session, *, tenant_id: int, device_id: int) -> dict:
        """Remove a band binding so the MAC no longer maps to an elder (SOS stops)."""
        device = (
            db.query(IotDevice)
            .filter(IotDevice.id == device_id, IotDevice.tenant_id == tenant_id)
            .first()
        )
        if not device:
            raise_not_found("Device not found")
        snapshot = IotRegistryService._device_dict(device)
        db.delete(device)
        db.commit()
        return snapshot

    @staticmethod
    def delete_hub(db: Session, *, tenant_id: int, hub_id: int) -> dict:
        """Retire a hub. Linked bands keep their elder MAC bind but lose hub_id.

        Does not remove the Mosquitto user from passwd (manual if needed).
        """
        hub = (
            db.query(IotHub)
            .filter(IotHub.id == hub_id, IotHub.tenant_id == tenant_id)
            .first()
        )
        if not hub:
            raise_not_found("Hub not found")
        snapshot = IotRegistryService._hub_dict(hub, include_secret=False)
        linked = (
            db.query(IotDevice)
            .filter(IotDevice.tenant_id == tenant_id, IotDevice.hub_id == hub_id)
            .all()
        )
        for d in linked:
            d.hub_id = None
        db.delete(hub)
        db.commit()
        snapshot["unlinked_devices"] = len(linked)
        return snapshot

    @staticmethod
    def register_kit(
        db: Session,
        *,
        tenant_id: int,
        elder_id: int,
        mac_address: str,
        hub_label: str = "MG7 hub",
        band_label: str = "B7 band",
        home_key: str = "home1",
        hub_serial: str | None = None,
        provision_mqtt: bool = True,
        use_shared_broker: bool | None = None,
    ) -> dict:
        """One-shot: hub + B7 bind; MinewLink cheat-sheet from broker settings (source of truth)."""
        from app.livewell.iot_broker_settings import (
            ensure_shared_hub_acl,
            get_broker_settings,
            minewlink_cheat_sheet,
            publish_topic_for_mac,
        )

        broker = get_broker_settings(db)
        shared = broker.get("use_shared_hub", True) if use_shared_broker is None else bool(use_shared_broker)

        if shared:
            # Reuse one hub row per tenant with the shared MQTT username
            existing = (
                db.query(IotHub)
                .filter(
                    IotHub.tenant_id == tenant_id,
                    IotHub.mqtt_username == broker["hub_username"],
                )
                .first()
            )
            if existing:
                # Shared MQTT user covers every physical MG7. Keep hub row stable —
                # MinewLink topic is per-band from the cheat-sheet, not this row.
                if broker.get("hub_password"):
                    existing.mqtt_password = broker["hub_password"]
                if not (existing.label or "").strip() or existing.label.strip() in {
                    "MG7 hub",
                    "Shared MG7",
                }:
                    existing.label = (hub_label or "Shared MG7 (all homes)").strip()[:200]
                db.commit()
                db.refresh(existing)
                hub = IotRegistryService._hub_dict(existing, include_secret=True)
                mqtt_result = {"ok": True, "detail": "reused shared hub credentials"}
                if provision_mqtt:
                    mqtt_result = ensure_shared_hub_acl(db)
                    hub["mqtt_provision"] = mqtt_result
            else:
                # Create hub with shared credentials (not a random user)
                home = _slug(home_key) or "home1"
                hkey = "shared"
                password = broker["hub_password"] or _gen_password(24)
                topic = publish_topic_for_mac(broker, mac_address, home_key=home, hub_key=hkey)
                row = IotHub(
                    tenant_id=tenant_id,
                    home_key=home,
                    hub_key=hkey,
                    label=(hub_label or "Shared MG7 (all homes)").strip()[:200],
                    serial_number=hub_serial,
                    mqtt_username=broker["hub_username"],
                    mqtt_password=password,
                    mqtt_topic=topic,
                    status="active",
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                mqtt_result = {"ok": False, "detail": "skipped"}
                if provision_mqtt:
                    mqtt_result = ensure_shared_hub_acl(db)
                    if mqtt_result.get("ok"):
                        row.provisioned_at = datetime.now(timezone.utc)
                        db.commit()
                        db.refresh(row)
                hub = IotRegistryService._hub_dict(row, include_secret=True, mqtt=mqtt_result)
        else:
            hub = IotRegistryService.register_hub(
                db,
                tenant_id=tenant_id,
                label=hub_label,
                home_key=home_key,
                serial_number=hub_serial,
                provision_mqtt=provision_mqtt,
            )

        device = IotRegistryService.register_device(
            db,
            tenant_id=tenant_id,
            elder_id=elder_id,
            mac_address=mac_address,
            hub_id=hub["id"],
            label=band_label,
        )
        # Stamp residence key on the band for multi-home ops (shared MQTT hub row is one).
        home_slug = _slug(home_key) or "home1"
        if home_slug and home_slug != "home1":
            row = db.query(IotDevice).filter(IotDevice.id == device["id"]).first()
            if row:
                note = (row.notes or "").strip()
                tag = f"home={home_slug}"
                if tag not in note:
                    row.notes = f"{note}; {tag}".strip("; ").strip() if note else tag
                    db.commit()
                    db.refresh(row)
                    device = IotRegistryService._device_dict(row, hub_label=hub.get("label"))
        else:
            device = {**device, "hub_label": hub.get("label")}

        minewlink = minewlink_cheat_sheet(
            db,
            mac_address=device["mac_address"],
            home_key=home_slug,
            hub_key=hub.get("hub_key") or "shared",
        )
        return {
            "hub": hub,
            "device": device,
            "minewlink": minewlink,
            "beaconset": {
                "mac_address": device["mac_address"],
                "enable_sos_advertising": True,
                "motion_acc": "FFE1 A103 XYZ delta (immobility); iBeacon 1/2 is always-on heartbeat",
            },
            "next_steps": [
                "In BeaconSET Plus: confirm B7 MAC matches; SOS iBeacon major=1 minor=1. Leave Minew accelerometer (A103) advertising on.",
                "In MinewLink: use Host/Port/TLS/User/Password/Topic from minewlink above "
                "(from Wearables → MQTT broker settings — single source of truth).",
                "Topic must be /mg7/{THIS band MAC}/status — each kit uses its own band MAC.",
                "Leave MinewLink subscribe/reply empty unless you configured them in broker settings.",
                "Press B7 SOS; walk with the band then rest. Family Alerts: SOS immediately; immobility after the Wearables delay during active hours.",
            ],
        }

    @staticmethod
    def provision_hub_mqtt(db: Session, hub: IotHub) -> dict:
        """Add/update mosquitto passwd + ACL for this hub. Best-effort on the VM."""
        from app.livewell.iot_mqtt_provision import provision_hub_user

        result = provision_hub_user(hub.mqtt_username, hub.mqtt_password or "")
        if result.get("ok"):
            hub.provisioned_at = datetime.now(timezone.utc)
            db.add(hub)
            db.commit()
            db.refresh(hub)
        return result

    @staticmethod
    def _hub_dict(hub: IotHub, *, include_secret: bool = False, mqtt: dict | None = None) -> dict:
        d = {
            "id": hub.id,
            "tenant_id": hub.tenant_id,
            "home_key": hub.home_key,
            "hub_key": hub.hub_key,
            "label": hub.label,
            "serial_number": hub.serial_number,
            "mqtt_username": hub.mqtt_username,
            "mqtt_topic": hub.mqtt_topic,
            "status": hub.status,
            "last_seen_at": hub.last_seen_at,
            "notes": hub.notes,
            "provisioned_at": hub.provisioned_at,
            "created_at": hub.created_at,
            "mac_address": hub.mac_address,
            "elder_id": hub.elder_id,
            "http_enabled": bool(hub.http_token),
            "bands_heard": hub.bands_heard,
        }
        if include_secret:
            d["mqtt_password"] = hub.mqtt_password
            d["http_url"] = gateway_http_url(hub.http_token)
        if mqtt is not None:
            d["mqtt_provision"] = mqtt
        return d

    @staticmethod
    def _device_dict(device: IotDevice, *, hub_label: str | None = None) -> dict:
        return {
            "id": device.id,
            "tenant_id": device.tenant_id,
            "hub_id": device.hub_id,
            "hub_label": hub_label,
            "elder_id": device.elder_id,
            "device_type": device.device_type,
            "kind": device_kind(device.device_type),
            "last_rssi": device.last_rssi,
            "label": device.label,
            "mac_address": device.mac_address,
            "status": device.status,
            "battery_level": device.battery_level,
            "last_seen_at": device.last_seen_at,
            "notes": device.notes,
            "created_at": device.created_at,
        }

    @staticmethod
    def devices_for_api(db: Session, tenant_id: int) -> list[dict]:
        hubs = {h.id: h.label for h in IotRegistryService.list_hubs(db, tenant_id)}
        return [
            IotRegistryService._device_dict(d, hub_label=hubs.get(d.hub_id) if d.hub_id else None)
            for d in IotRegistryService.list_devices(db, tenant_id)
        ]

    @staticmethod
    def touch_device_seen(
        db: Session,
        *,
        mac_address: str | None,
        battery_level: int | None = None,
        seen_at: datetime | None = None,
        hub_key: str | None = None,
        commit: bool = True,
    ) -> IotDevice | None:
        """Record that a band (and the hub that relayed it) was heard from.

        Called from the ingest path for anything that proves the band is
        alive — SOS, motion, heartbeat — never for DEVICE_OFFLINE, which is
        the absence of exactly that. Feeds the family "Devices" card.
        """
        device = IotRegistryService.find_device_by_mac(db, mac_address)
        if device is None:
            return None
        when = seen_at or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if device.last_seen_at is None or when >= device.last_seen_at.replace(
            tzinfo=device.last_seen_at.tzinfo or timezone.utc
        ):
            device.last_seen_at = when
        if battery_level is not None:
            try:
                device.battery_level = max(0, min(100, int(battery_level)))
            except (TypeError, ValueError):
                pass
        hub = None
        if device.hub_id:
            hub = db.query(IotHub).filter(IotHub.id == device.hub_id).first()
        if hub is None and hub_key:
            key = str(hub_key).strip()
            hub = (
                db.query(IotHub)
                .filter(IotHub.tenant_id == device.tenant_id, IotHub.hub_key == key)
                .first()
            )
        if hub is not None:
            if hub.last_seen_at is None or when >= hub.last_seen_at.replace(
                tzinfo=hub.last_seen_at.tzinfo or timezone.utc
            ):
                hub.last_seen_at = when
        if commit:
            db.commit()
        else:
            db.flush()
        return device

    @staticmethod
    def find_device_by_mac(db: Session, mac: str | None) -> IotDevice | None:
        if not mac:
            return None
        try:
            cleaned = normalize_mac(mac)
        except Exception:
            return None
        return (
            db.query(IotDevice)
            .filter(IotDevice.mac_address == cleaned, IotDevice.status == "active")
            .first()
        )
