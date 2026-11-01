"""Family receipts and device status response shapes (amounts are integer paise)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FamilyReceiptResponse(BaseModel):
    id: str
    receipt_number: str
    date: datetime | None = None
    kind: str
    kind_label: str
    description: str
    amount_minor: int
    amount_display: str
    balance_after_minor: int | None = None
    currency: str = "INR"
    status: str = "success"
    payment_method: str | None = None
    payment_reference: str | None = None
    service_request_id: str | None = None
    service_label: str | None = None
    service_status: str | None = None
    service_preferred_at: datetime | None = None
    elder_id: int
    elder_name: str
    tenant_name: str = ""
    paid_by: str | None = None


class FamilyDeviceResponse(BaseModel):
    id: int
    label: str
    device_type: str
    kind: str = "watch"  # watch | sensor | gateway
    battery_level: int | None = None
    online: bool = False
    last_seen_at: datetime | None = None
    offline_seconds: int = 180
    hub_label: str | None = None
    hub_online: bool | None = None
    hub_last_seen_at: datetime | None = None
