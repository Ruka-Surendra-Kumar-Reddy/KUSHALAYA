"""Care team phone + WhatsApp number families see (Call / WhatsApp buttons).

Stored on the agency: ``tenant.workflow_config["care_team_contact"]``.
Defaults to the founder's public number (frontend/lib/marketing/founder.ts),
which is a deliberate public contact.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.tenant import Tenant

KEY = "care_team_contact"
DEFAULT_PHONE = "+91 83095 00488"
DEFAULT_WHATSAPP = "+91 83095 00488"
EMERGENCY_NUMBERS = [
    {"number": "112", "label": "All emergencies"},
    {"number": "108", "label": "Ambulance"},
]


def _clean(value) -> str:
    """Normalise to "+<country><number>". "" means "use the default".

    A leading 0 (trunk prefix) is dropped; 10 digits are taken as an Indian
    number (+91). The result must have 11–15 digits.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.fullmatch(r"\+?[\d\s\-().]{6,24}", text):
        raise ValueError("Use digits only, with the country code (e.g. +91 98765 43210)")
    digits = re.sub(r"\D", "", text)
    if not text.startswith("+"):
        digits = digits.lstrip("0")
        if len(digits) == 10:
            digits = "91" + digits
    if not 11 <= len(digits) <= 15:
        raise ValueError("That number looks too short or too long. Include the country code.")
    return "+" + digits


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def get_contact(tenant: Tenant | None) -> dict:
    raw = ((tenant.workflow_config or {}) if tenant else {}).get(KEY) or {}
    phone = str(raw.get("phone") or "").strip() or DEFAULT_PHONE
    whatsapp = str(raw.get("whatsapp") or "").strip() or DEFAULT_WHATSAPP
    return {
        "phone": phone,
        "whatsapp": whatsapp,
        "phone_tel": "+" + _digits(phone),
        "whatsapp_link": f"https://wa.me/{_digits(whatsapp)}",
        "is_default": not (raw.get("phone") or raw.get("whatsapp")),
        "emergency": EMERGENCY_NUMBERS,
    }


def save_contact(db: Session, tenant: Tenant, body: dict) -> dict:
    cfg = dict(tenant.workflow_config or {})
    current = dict(cfg.get(KEY) or {})
    # Only the fields sent change; PUT {"phone": ...} keeps the WhatsApp number.
    for field in ("phone", "whatsapp"):
        if field in body:
            current[field] = _clean(body.get(field))
    cfg[KEY] = current
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)
    return get_contact(tenant)
