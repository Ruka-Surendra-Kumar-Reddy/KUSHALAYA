"""LiveWell IoT hubs (MG7) and bands (B7)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class IotHub(TimestampMixin, Base):
    """Minew MG7 (or compatible) BLE→MQTT gateway."""

    __tablename__ = "iot_hubs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mqtt_username", name="uq_iot_hubs_tenant_mqtt_user"),
        Index("ix_iot_hubs_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    home_key: Mapped[str] = mapped_column(String(64), default="home1")
    hub_key: Mapped[str] = mapped_column(String(64), default="mg7-1")
    label: Mapped[str] = mapped_column(String(200), default="MG7 hub")
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mqtt_username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Plain password stored for MinewLink re-display; rotate via API if needed.
    mqtt_password: Mapped[str] = mapped_column(String(200), nullable=False)
    mqtt_topic: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Physical gateway MAC (Minew G1 / MG3), optional.
    mac_address: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # Secret in the gateway's HTTP upload URL (/api/v1/home-safety/gateway/{token}).
    http_token: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    # Bands in the gateway's last upload, registered or not (shown on Wearables).
    bands_heard: Mapped[int | None] = mapped_column(nullable=True)
    # The client home this gateway is installed in (None = not placed yet).
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id"), nullable=True, index=True)


class IotDevice(TimestampMixin, Base):
    """Minew B7 (or compatible) wearable bound to an elder."""

    __tablename__ = "iot_devices"
    __table_args__ = (
        UniqueConstraint("mac_address", name="uq_iot_devices_mac"),
        Index("ix_iot_devices_tenant_elder", "tenant_id", "elder_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    hub_id: Mapped[int | None] = mapped_column(ForeignKey("iot_hubs.id"), nullable=True, index=True)
    # None = in stock / not given to a client yet. An unassigned device never alerts anyone.
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id"), index=True, nullable=True)
    device_type: Mapped[str] = mapped_column(String(40), default="B7")
    label: Mapped[str] = mapped_column(String(200), default="B7 band")
    mac_address: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="active", index=True)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Watch state for the HTTP gateway path (the MQTT ingestor keeps the same
    # state in memory). Persisted so an API restart does not reset the clocks.
    last_rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_motion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motion_xyz: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sos_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    immobility_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
