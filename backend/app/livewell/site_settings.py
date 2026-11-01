"""Public website settings (FIX 107/108): service areas, assessment price, trial
banner, testimonials and company details — plus referral codes and the lead funnel.

Stored on the agency: ``tenant.workflow_config["site"]``. The public site reads
the primary tenant (the same one website enquiries land in).

Nothing here is invented for the public page: testimonials render only when an
admin has entered real ones, the price shows only once set ("Free"
until then), and the trial banner is off until switched on.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.livewell.care_plan_catalog import HOME_ASSESSMENT
from app.models.tenant import Tenant

KEY = "site"

DEFAULT_TRIAL_TEXT = "Try us for a month. If KushLife visits aren't right for your family, stop any time."
PRICE_UNSET_LABEL = "Free"  # the default: no payment step (owner, 27 Oct 2026)
# KushCare Discovery home assessment when Ops hasn't set a price (care_plan_catalog): free.
DEFAULT_ASSESSMENT_PRICE_PAISE = HOME_ASSESSMENT["price_paise"]
# Certificate of Incorporation (22 Oct 2026). No GSTIN yet.
COMPANY_LEGAL_NAME = "KushAlaya Private Limited"
COMPANY_CIN = "U88100TS2026PTC224774"
COMPANY_ADDRESS = (
    "Plot no. 65, H.No 2-17-8d, Dharmapuri Colony, Uppal, Beside SR Heights, Uppal, "
    "K.V. Rangareddy – 500039, Telangana, India"
)
MAX_PRICE_PAISE = 10_000_000  # ₹1,00,000 — a typo guard, not a business rule
MAX_AREAS = 60
MAX_PINCODES = 400
MAX_TESTIMONIALS = 12
SLOT_WINDOWS = ("morning", "afternoon", "evening")

_PIN_RE = re.compile(r"^[1-9]\d{5}$")
_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_LANDLINE_RE = re.compile(r"^(?:\+?91|0)([1-9]\d{9})$")


def _grievance_phone(raw: str) -> str:
    """Mobile -> "+91 XXXXX XXXXX"; international -> E.164; an Indian landline
    with STD code -> "+91 <10 digits>". Blank stays blank."""
    from app.livewell.public_enquiry_service import normalise_phone

    if not raw:
        return ""
    try:
        return normalise_phone(raw) or ""
    except ValueError:
        m = _LANDLINE_RE.match(re.sub(r"[\s\-().]", "", raw))
        if m:
            return f"+91 {m.group(1)}"
        raise ValueError(
            "The grievance officer's phone doesn't look right — use a 10-digit mobile, "
            "a landline with STD code, or +country code for numbers abroad."
        ) from None


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def clean_pincode(value) -> str:
    """Digits only; "" when it is not a 6-digit Indian PIN code."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if _PIN_RE.match(digits) else ""


def _raw(tenant: Tenant | None) -> dict:
    return dict(((tenant.workflow_config or {}) if tenant else {}).get(KEY) or {})


def get_settings(tenant: Tenant | None) -> dict:
    """Full settings for the ops Settings page (admins and managers)."""
    raw = _raw(tenant)
    trial = dict(raw.get("trial") or {})
    company = dict(raw.get("company") or {})
    price = raw.get("assessment_price_paise")
    return {
        "city": _text(raw.get("city"), 60) or "Hyderabad",
        "areas": [
            {
                "name": _text(a.get("name"), 80),
                "pincodes": [p for p in (a.get("pincodes") or []) if clean_pincode(p)],
                "manager_user_id": a.get("manager_user_id"),
            }
            for a in (raw.get("areas") or [])
            if isinstance(a, dict)
        ],
        "assessment_price_paise": int(price) if isinstance(price, int) and price >= 0 else None,
        "trial": {
            "enabled": bool(trial.get("enabled")),
            "text": _text(trial.get("text"), 240) or DEFAULT_TRIAL_TEXT,
        },
        "testimonials": [
            {
                "quote": _text(t.get("quote"), 600),
                "name": _text(t.get("name"), 80),
                "place": _text(t.get("place"), 80),
            }
            for t in (raw.get("testimonials") or [])
            if isinstance(t, dict) and _text(t.get("quote"), 600) and _text(t.get("name"), 80)
        ],
        "company": {
            "legal_name": _text(company.get("legal_name"), 120),
            "address": _text(company.get("address"), 300),
            "gstin": _text(company.get("gstin"), 15),
            "grievance_name": _text(company.get("grievance_name"), 80),
            "grievance_email": _text(company.get("grievance_email"), 120),
            "grievance_phone": _text(company.get("grievance_phone"), 30),
        },
    }


def save_settings(db: Session, tenant: Tenant, body: dict) -> dict:
    """Validate and store. Only the sections sent change."""
    from app.models.user import User

    current = _raw(tenant)

    if "city" in body:
        current["city"] = _text(body.get("city"), 60)

    if "areas" in body:
        areas = []
        for a in (body.get("areas") or [])[:MAX_AREAS]:
            if not isinstance(a, dict):
                continue
            name = _text(a.get("name"), 80)
            if not name:
                continue
            raw_pins = a.get("pincodes") or []
            if isinstance(raw_pins, str):
                raw_pins = re.split(r"[\s,;]+", raw_pins)
            pins: list[str] = []
            for p in raw_pins:
                if not str(p).strip():
                    continue
                pin = clean_pincode(p)
                if not pin:
                    raise ValueError(f"“{p}” is not a 6-digit PIN code ({name}).")
                if pin not in pins:
                    pins.append(pin)
            manager_id = a.get("manager_user_id") or None
            if manager_id is not None:
                manager = db.get(User, int(manager_id))
                if manager is None or manager.tenant_id != tenant.id:
                    raise ValueError(f"The manager chosen for {name} is not in this agency.")
                manager_id = int(manager.id)
            areas.append({"name": name, "pincodes": pins[:MAX_PINCODES], "manager_user_id": manager_id})
        current["areas"] = areas

    if "assessment_price_paise" in body:
        price = body.get("assessment_price_paise")
        if price in (None, ""):
            current["assessment_price_paise"] = None
        else:
            try:
                price = int(price)
            except (TypeError, ValueError):
                raise ValueError("The assessment price must be a whole number of paise.") from None
            if price < 0 or price > MAX_PRICE_PAISE:
                raise ValueError("The assessment price must be between ₹0 and ₹1,00,000.")
            current["assessment_price_paise"] = price

    if "trial" in body:
        trial = dict(body.get("trial") or {})
        current["trial"] = {"enabled": bool(trial.get("enabled")), "text": _text(trial.get("text"), 240)}

    if "testimonials" in body:
        out = []
        for t in (body.get("testimonials") or [])[:MAX_TESTIMONIALS]:
            if not isinstance(t, dict):
                continue
            quote, name = _text(t.get("quote"), 600), _text(t.get("name"), 80)
            if not quote and not name:
                continue
            if not quote or not name:
                raise ValueError("Each testimonial needs the family's words and a name.")
            out.append({"quote": quote, "name": name, "place": _text(t.get("place"), 80)})
        current["testimonials"] = out

    if "company" in body:
        c = dict(body.get("company") or {})
        gstin = _text(c.get("gstin"), 20).upper().replace(" ", "")
        if gstin and not _GSTIN_RE.match(gstin):
            raise ValueError("That GSTIN doesn't look right (15 characters, e.g. 36ABCDE1234F1Z5).")
        grievance_email = _text(c.get("grievance_email"), 120)
        if grievance_email and not _EMAIL_RE.match(grievance_email):
            raise ValueError("The grievance officer's email doesn't look right (for example grievance@kushalaya.com).")
        current["company"] = {
            "legal_name": _text(c.get("legal_name"), 120),
            "address": _text(c.get("address"), 300),
            "gstin": gstin,
            "grievance_name": _text(c.get("grievance_name"), 80),
            "grievance_email": grievance_email,
            "grievance_phone": _grievance_phone(_text(c.get("grievance_phone"), 30)),
        }

    cfg = dict(tenant.workflow_config or {})
    cfg[KEY] = current
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)
    return get_settings(tenant)


def assessment_price(price_paise: int | None) -> int:
    """The price Ops set, or the default (free) when none is set."""
    return DEFAULT_ASSESSMENT_PRICE_PAISE if price_paise is None else int(price_paise)


def price_label(price_paise: int | None) -> str:
    price_paise = assessment_price(price_paise)
    if not price_paise:
        return PRICE_UNSET_LABEL
    rupees, paise = divmod(int(price_paise), 100)
    text = f"{rupees:,}"
    # Indian grouping: 1,00,000 rather than 100,000.
    if rupees >= 1000:
        head, tail = str(rupees)[:-3], str(rupees)[-3:]
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
        text = f"{head},{tail}"
    return f"₹{text}" + (f".{paise:02d}" if paise else "")


def public_config(tenant: Tenant | None) -> dict:
    """What the public site may show. No pincodes-to-manager mapping, no user ids."""
    from app.livewell.care_team_contact import get_contact

    s = get_settings(tenant)
    contact = get_contact(tenant)
    price = assessment_price(s["assessment_price_paise"])
    return {
        "whatsapp": contact["whatsapp"],
        "whatsapp_link": contact["whatsapp_link"],
        "whatsapp_is_default": bool(contact["is_default"]),
        "phone": contact["phone"],
        "phone_tel": contact["phone_tel"],
        "city": s["city"],
        "areas": [a["name"] for a in s["areas"]],
        # Free by default (owner, 27 Oct 2026); paid only if Ops sets a price.
        "assessment_price_paise": price if price else None,
        "assessment_price_label": price_label(price),
        "assessment_is_paid": bool(price),
        "slot_windows": list(SLOT_WINDOWS),
        "trial": s["trial"] if s["trial"]["enabled"] else {"enabled": False, "text": ""},
        "testimonials": s["testimonials"],
        "company": _public_company(tenant, s["company"]),
    }


def _public_company(tenant: Tenant | None, company: dict) -> dict:
    """Website company block: anything typed in Settings → Website, otherwise the
    legal name / address / GSTIN from Settings → Business details (only values the
    owner actually entered — never the agency's placeholder name)."""
    business = dict(((tenant.workflow_config or {}) if tenant else {}).get("business") or {})
    out = dict(company)
    for key, limit in (("legal_name", 120), ("address", 300), ("gstin", 15)):
        if not out.get(key):
            out[key] = _text(business.get(key), limit)
    # Last resort: the registered company (never a placeholder GSTIN).
    out["legal_name"] = out.get("legal_name") or COMPANY_LEGAL_NAME
    out["address"] = out.get("address") or COMPANY_ADDRESS
    out["cin"] = COMPANY_CIN
    return out


def check_pincode(tenant: Tenant | None, pincode) -> dict:
    pin = clean_pincode(pincode)
    s = get_settings(tenant)
    for area in s["areas"]:
        if pin and pin in area["pincodes"]:
            return {
                "pincode": pin,
                "served": True,
                "area": area["name"],
                "message": "We serve your area.",
                "manager_user_id": area["manager_user_id"],
            }
    return {
        "pincode": pin,
        "served": False,
        "area": None,
        "message": "We work with families across India. We'll call you to arrange the visit.",
        "manager_user_id": None,
    }


# --- Referral codes ---------------------------------------------------------
#
# A code is "K" + the client id in base 36 + an 8-character base32 HMAC
# signature (keyed on SECRET_KEY), so nothing has to be stored and a code cannot
# be guessed from another family's. Without a SECRET_KEY no codes are issued or
# accepted (fail closed). Old 4-hex-character codes are no longer valid.

_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SIG_LEN = 8


def _sig(elder_id: int) -> str | None:
    secret = (settings.SECRET_KEY or "").strip()
    if not secret:
        return None
    digest = hmac.new(secret.encode(), f"referral:{elder_id}".encode(), hashlib.sha256).digest()
    return base64.b32encode(digest).decode()[:SIG_LEN]


def _b36(n: int) -> str:
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = _B36[r] + out
        if n == 0:
            return out


def referral_code(elder_id: int) -> str | None:
    sig = _sig(int(elder_id))
    return f"K{_b36(int(elder_id))}{sig}" if sig else None


def parse_referral_code(code) -> int | None:
    text = re.sub(r"[^0-9A-Za-z]", "", str(code or "")).upper()
    if len(text) < 2 + SIG_LEN or len(text) > 24 or not text.startswith("K"):
        return None
    body, sig = text[1:-SIG_LEN], text[-SIG_LEN:]
    try:
        elder_id = int(body, 36)
    except ValueError:
        return None
    expected = _sig(elder_id) if elder_id > 0 else None
    if not expected or not hmac.compare_digest(sig, expected):
        return None
    return elder_id


def referrer_name(db: Session, code: str | None, tenant_id: int) -> str | None:
    """The referring client's name, only when the code is valid and in this tenant."""
    from app.models.elder import Elder

    elder_id = parse_referral_code(code)
    if not elder_id:
        return None
    elder = db.get(Elder, elder_id)
    if elder is None or elder.tenant_id != tenant_id:
        return None
    return f"{elder.first_name} {elder.last_name}".strip()


# --- Lead funnel --------------------------------------------------------------

FUNNEL_STEPS = ("NEW", "CONTACTED", "ASSESSMENT_BOOKED", "CLIENT")
_CONTACTED = {"CONTACTED", "ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE", "PROPOSAL_SENT", "FOLLOW_UP_1", "FOLLOW_UP_2", "WON"}
_BOOKED = {"ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE", "PROPOSAL_SENT", "FOLLOW_UP_1", "FOLLOW_UP_2", "WON"}


def lead_source(row) -> str:
    """One short label for where a lead came from."""
    if getattr(row, "referral_code", None):
        return "referral"
    if getattr(row, "utm_source", None):
        return str(row.utm_source).lower()[:40]
    ref = str(getattr(row, "referrer_url", None) or "")
    m = re.match(r"https?://(?:www\.)?([^/:]+)", ref)
    if m and "kushalaya" not in m.group(1):
        return m.group(1).lower()[:40]
    src = str(getattr(row, "source", None) or "")
    return "website" if src.startswith("website") else (src.lower()[:40] or "manual")


def funnel(db: Session, user, *, months: int = 6, include_closed: bool = False) -> dict:
    """NEW → CONTACTED → ASSESSMENT BOOKED → CLIENT, per month the lead arrived.

    Cumulative: a client also counts as contacted and booked. Tenant-scoped;
    a care manager sees leads they own plus unassigned ones.
    """
    from app.core.rbac import resolve_tenant_id
    from app.core.team_scope import is_scoped_manager
    from app.models.elder_prospect import ElderProspect
    from sqlalchemy import or_

    q = db.query(ElderProspect)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(ElderProspect.tenant_id == tid)
    if is_scoped_manager(user):
        q = q.filter(or_(ElderProspect.owner_user_id == user.id, ElderProspect.owner_user_id.is_(None)))

    months = max(1, min(int(months or 6), 24))
    now = datetime.utcnow()
    keys: list[str] = []
    y, m = now.year, now.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    rows = {k: {s: 0 for s in FUNNEL_STEPS} for k in keys}
    sources: Counter = Counter()

    start = f"{keys[0]}-01"
    excluded = 0
    for p in q.filter(ElderProspect.created_at >= datetime.fromisoformat(start)).all():
        key = p.created_at.strftime("%Y-%m") if p.created_at else None
        if key not in rows:
            continue
        # Closed / archived leads (test, spam, duplicates) skew conversion: left out unless asked.
        closed = (p.status == "LOST" or p.stage == "LOST") and not p.converted_elder_id
        if closed and not include_closed:
            excluded += 1
            continue
        r = rows[key]
        r["NEW"] += 1
        client = p.stage == "WON" or bool(p.converted_elder_id)
        booked = client or p.stage in _BOOKED or bool(getattr(p, "assessment_slot", None))
        if client or booked or p.stage in _CONTACTED:
            r["CONTACTED"] += 1
        if booked:
            r["ASSESSMENT_BOOKED"] += 1
        if client:
            r["CLIENT"] += 1
        sources[lead_source(p)] += 1

    totals = {s: sum(rows[k][s] for k in keys) for s in FUNNEL_STEPS}
    return {
        "steps": list(FUNNEL_STEPS),
        "months": [{"month": k, **rows[k]} for k in keys],
        "totals": totals,
        "sources": [{"source": s, "count": c} for s, c in sources.most_common()],
        "excluded_closed": excluded,
        "include_closed": include_closed,
    }
