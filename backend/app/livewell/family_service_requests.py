"""Family-requested services / visits (P1) — stored on elder.custom_attributes.safe_home.service_requests."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.money import format_minor
from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

logger = logging.getLogger(__name__)

# What a family can ask for. The first group is offered in the portal (service /
# product / assessment visit); the rest stay valid for older requests.
REQUEST_GROUPS = {
    "care_visit": "service",
    "physiotherapy": "service",
    "discharge_help": "service",
    "safety_recheck": "service",
    "assessment": "assessment",
    "product": "product",
}
SERVICE_TYPES = (
    ("care_visit", "Care visit"),
    ("physiotherapy", "Physiotherapy session"),
    ("discharge_help", "Hospital-discharge and recovery help"),
    ("safety_recheck", "Home safety re-check"),
    ("assessment", "Home safety assessment"),
    ("product", "Product"),
    # Any service from the catalog (nursing, physio, transport...), picked by product_id.
    ("catalog_service", "Service"),
    ("wellness_visit", "Wellness / care visit"),
    ("home_repair", "Home repair"),
    ("product_install", "Product / safety install"),
    ("nurse_pt", "Nurse / physiotherapy"),
    ("haircut_grooming", "Haircut / grooming"),
    ("grocery_errand", "Grocery / errand"),
    ("details_change", "Health details change"),
    ("other", "Other"),
)
OFFERED_TYPES = tuple(REQUEST_GROUPS)

SERVICE_TYPE_IDS = {t[0] for t in SERVICE_TYPES}
SERVICE_LABELS = dict(SERVICE_TYPES)

STATUSES = frozenset({"requested", "confirmed", "declined", "cancelled", "done"})

# Wallet payment state, separate from scheduling state.
#   not_required      — no price quoted yet
#   awaiting_approval — staff quoted a price, family must approve and pay
#   paid              — family approved, wallet debited upfront
#   refunded          — cancelled after payment, money returned to the wallet
PAYMENT_STATUSES = frozenset(
    {"not_required", "awaiting_approval", "paid", "refunded"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _new_id() -> str:
    return f"fsr_{uuid.uuid4().hex[:12]}"


def _safe_home(elder: Elder) -> dict:
    attrs = elder.custom_attributes or {}
    block = attrs.get("safe_home")
    return dict(block) if isinstance(block, dict) else {}


def _requests(elder: Elder) -> list[dict]:
    sh = _safe_home(elder)
    rows = sh.get("service_requests")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


MAX_STORED_REQUESTS = 200
OPEN_REQUEST_STATUSES = ("requested", "confirmed")
CLOSED_STATUSES = ("done", "cancelled", "declined")


def lock_elder(db: Session, elder: Elder) -> Elder:
    """Re-read the elder row under a row lock before a read-modify-write of custom_attributes,
    so two writers can't overwrite each other's change (SQLite has no row locks)."""
    q = db.query(Elder).filter(Elder.id == elder.id).populate_existing()
    bind = db.get_bind()
    if bind is not None and bind.dialect.name != "sqlite":
        q = q.with_for_update()
    return q.one()


def _cap(rows: list[dict]) -> list[dict]:
    """Keep every open request and the newest closed ones, up to MAX_STORED_REQUESTS rows."""
    if len(rows) <= MAX_STORED_REQUESTS:
        return rows
    open_ids = {id(r) for r in rows if str(r.get("status") or "requested") in OPEN_REQUEST_STATUSES}
    room = max(0, MAX_STORED_REQUESTS - len(open_ids))
    kept, closed = [], 0
    for r in rows:  # newest first
        if id(r) in open_ids:
            kept.append(r)
        elif closed < room:
            kept.append(r)
            closed += 1
    return kept


def _save_requests(db: Session, elder: Elder, rows: list[dict]) -> None:
    rows = _cap(rows)
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    block["service_requests"] = rows
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    db.refresh(elder)


def _normalize(raw: dict) -> dict:
    st = str(raw.get("service_type") or "other").strip()
    if st not in SERVICE_TYPE_IDS:
        st = "other"
    status = str(raw.get("status") or "requested").strip().lower()
    if status not in STATUSES:
        status = "requested"
    payment_status = str(raw.get("payment_status") or "not_required").strip().lower()
    if payment_status not in PAYMENT_STATUSES:
        payment_status = "not_required"
    # A cancelled / declined / finished request has nothing left to approve.
    if payment_status == "awaiting_approval" and status in ("cancelled", "declined", "done"):
        payment_status = "not_required"
    try:
        quoted = int(raw.get("quoted_amount_minor") or 0)
    except (TypeError, ValueError):
        quoted = 0
    return {
        "id": str(raw.get("id") or _new_id()),
        "service_type": st,
        "service_label": (
            f"{'Product' if st == 'product' else 'Service'}: {str(raw.get('product_name')).strip()}"
            if st in ("product", "catalog_service") and str(raw.get("product_name") or "").strip()
            else SERVICE_LABELS.get(st, "Other")
        ),
        "group": REQUEST_GROUPS.get(st, "service"),
        "product_name": str(raw.get("product_name") or "").strip(),
        "product_id": _int_or_none(raw.get("product_id")),
        "product_code": str(raw.get("product_code") or "").strip(),
        # Several catalog items in one request (AI room preview "Request these fixes").
        "items": [
            {
                "product_id": _int_or_none(i.get("product_id")),
                "product_code": str(i.get("product_code") or "").strip(),
                "name": str(i.get("name") or "").strip()[:120],
            }
            for i in (raw.get("items") or [])
            if isinstance(i, dict)
        ][:20],
        "source": str(raw.get("source") or "").strip()[:40],
        # No preferred time means "any time" - never invent one.
        "preferred_at": (
            _parse_dt(raw.get("preferred_at")).isoformat() if _parse_dt(raw.get("preferred_at")) else None
        ),
        "notes": str(raw.get("notes") or "").strip(),
        "status": status,
        "created_at": (_parse_dt(raw.get("created_at")) or _now()).isoformat(),
        "created_by": str(raw.get("created_by") or ""),
        "staff_note": str(raw.get("staff_note") or "").strip(),
        "visit_id": str(raw.get("visit_id") or "").strip() or None,
        "quoted_amount_minor": max(0, quoted),
        "payment_status": payment_status,
        "wallet_transaction_id": str(raw.get("wallet_transaction_id") or "").strip() or None,
        # Paid on the website (Razorpay, pay-as-you-go visit): the amount taken online.
        # Kept apart from quoted_amount_minor so a cancel never refunds it to the wallet
        # — an online payment is refunded through Razorpay.
        "paid_online_minor": max(0, _int_or_none(raw.get("paid_online_minor")) or 0),
        "paid_online_ref": str(raw.get("paid_online_ref") or "").strip()[:40],
        "updated_at": (_parse_dt(raw.get("updated_at")) or _now()).isoformat(),
    }


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _catalog_item(db: Session, tenant_id: int, product_id: int | None, name: str):
    """The on-sale catalog row a family picked: by id, else (older pages) by exact name."""
    from app.models.commerce import Product

    q = db.query(Product).filter(Product.tenant_id == tenant_id, Product.active.is_(True))
    if product_id:
        return q.filter(Product.id == product_id).first()
    if name:
        return q.filter(Product.name == name).first()
    return None


def _to_response(row: dict) -> dict:
    n = _normalize(row)
    return {
        "id": n["id"],
        "service_type": n["service_type"],
        "service_label": n["service_label"],
        "group": n["group"],
        "product_name": n["product_name"],
        "product_id": n["product_id"],
        "product_code": n["product_code"],
        "items": n["items"],
        "preferred_at": _parse_dt(n["preferred_at"]),
        "notes": n["notes"],
        "status": n["status"],
        "created_at": _parse_dt(n["created_at"]),
        "created_by": n["created_by"] or None,
        "staff_note": n["staff_note"] or None,
        "visit_id": n["visit_id"],
        "quoted_amount_minor": n["quoted_amount_minor"],
        "quoted_amount_display": (
            format_minor(n["quoted_amount_minor"]) if n["quoted_amount_minor"] else None
        ),
        "payment_status": n["payment_status"],
        "paid_online_minor": n["paid_online_minor"],
        "paid_online_display": format_minor(n["paid_online_minor"]) if n["paid_online_minor"] else None,
        "updated_at": _parse_dt(n["updated_at"]),
    }


def add_paid_online_request(
    db: Session,
    elder: Elder,
    *,
    service_type: str,
    notes: str,
    preferred_at: datetime | None,
    amount_minor: int,
    reference: str,
    created_by: str,
) -> dict:
    """A visit the customer already paid for on the website: a normal "requested" row
    (ops Visits -> Requests schedules it as usual), marked paid online. Does not
    commit — the caller commits it with the payment."""
    elder = lock_elder(db, elder)
    row = _normalize(
        {
            "id": _new_id(),
            "service_type": service_type if service_type in SERVICE_TYPE_IDS else "other",
            "preferred_at": preferred_at.isoformat() if preferred_at else None,
            "notes": notes,
            "source": "website",
            "status": "requested",
            "payment_status": "paid",
            "paid_online_minor": int(amount_minor),
            "paid_online_ref": reference,
            "created_at": _iso(),
            "created_by": created_by,
            "updated_at": _iso(),
        }
    )
    rows = _requests(elder)
    rows.insert(0, row)
    rows = _cap(rows)
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    block["service_requests"] = rows
    attrs["safe_home"] = block
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    return row


class FamilyServiceRequestService:
    @staticmethod
    def catalog() -> list[dict]:
        return [
            {"id": i, "label": lab, "group": REQUEST_GROUPS[i]}
            for i, lab in SERVICE_TYPES
            if i in REQUEST_GROUPS
        ]

    @staticmethod
    def list_for_family(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        rows = [_normalize(r) for r in _requests(elder)]
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return [_to_response(r) for r in rows]

    @staticmethod
    def create_for_family(
        db: Session,
        user: User,
        *,
        service_type: str,
        preferred_at: str | None,
        notes: str | None,
        product_name: str | None = None,
        product_id: int | None = None,
    ) -> dict:
        elder = lock_elder(db, ElderPortalService.get_linked_elder(db, user))
        st = (service_type or "").strip()
        if st not in SERVICE_TYPE_IDS:
            raise_bad_request("Unknown service type")
        name = (product_name or "").strip()[:120]
        code = ""
        if product_id or st in ("product", "catalog_service"):
            from app.livewell.commerce import is_service_product

            item = _catalog_item(db, elder.tenant_id, product_id, name)
            if product_id and not item:
                raise_bad_request("That item is no longer available")
            if item:
                # The catalog row decides the name, code and kind, so ops sees exactly what was asked.
                st = "catalog_service" if is_service_product(item) else "product"
                name, code, product_id = item.name[:120], item.product_code or "", item.id
            elif st == "catalog_service":
                raise_bad_request("Pick a service")
        pref = _parse_dt(preferred_at)
        row = _normalize(
            {
                "id": _new_id(),
                "service_type": st,
                "preferred_at": pref.isoformat() if pref else None,
                "notes": notes or "",
                "product_name": name,
                "product_id": product_id,
                "product_code": code,
                "status": "requested",
                "created_at": _iso(),
                "created_by": user.email,
                "updated_at": _iso(),
            }
        )
        rows = _requests(elder)
        rows.insert(0, row)
        _save_requests(db, elder, rows)

        from app.livewell.family_notify import notify_family, notify_manager

        from app.livewell.care_jobs import _when

        when = f"preferred {_when(pref)} IST" if pref else "any time"
        notify_family(
            db,
            elder,
            "Request received",
            f"{row['service_label']} — {when}. Your care team will schedule it and let you know.",
            event="request",
            actor_email=user.email,
            path="/services",
        )
        notify_manager(
            db,
            elder,
            f"New request: {row['service_label']}",
            f"{elder.first_name} {elder.last_name}: {row['service_label']}, {when}."
            + (f" Note: {row['notes']}" if row["notes"] else "")
            + " Schedule it from the ops dashboard.",
        )
        return _to_response(row)

    @staticmethod
    def create_bundle_for_family(
        db: Session,
        user: User,
        *,
        product_ids: list[int],
        notes: str = "",
        source: str = "ai_preview",
    ) -> dict:
        """ONE request carrying several catalog items (ids and codes), e.g. every fix in an
        approved AI room preview. Ops schedules it like any product request."""
        elder = lock_elder(db, ElderPortalService.get_linked_elder(db, user))
        items = []
        for pid in dict.fromkeys(int(p) for p in product_ids if p):
            item = _catalog_item(db, elder.tenant_id, pid, "")
            if not item:
                raise_bad_request("One of these items is no longer available")
            items.append({"product_id": item.id, "product_code": item.product_code or "", "name": item.name})
        if not items:
            raise_bad_request("Nothing to request")
        codes = [i["product_code"] for i in items if i["product_code"]]
        name = f"Safety fixes ({len(items)} item{'s' if len(items) != 1 else ''})"
        row = _normalize(
            {
                "id": _new_id(),
                "service_type": "product",
                "notes": (notes or "").strip()
                + (chr(10) if notes else "")
                + "Items: " + ", ".join(f"{i['name']} ({i['product_code']})" if i["product_code"] else i["name"] for i in items),
                "product_name": name,
                "product_id": items[0]["product_id"],
                "product_code": ",".join(codes)[:200],
                "items": items,
                "source": source,
                "status": "requested",
                "created_at": _iso(),
                "created_by": user.email,
                "updated_at": _iso(),
            }
        )
        rows = _requests(elder)
        rows.insert(0, row)
        _save_requests(db, elder, rows)

        from app.livewell.family_notify import notify_family, notify_manager

        notify_family(
            db,
            elder,
            "Request received",
            f"{row['service_label']}. Your care team will call to confirm and schedule the work.",
            event="request",
            actor_email=user.email,
            path="/services",
        )
        notify_manager(
            db,
            elder,
            f"New request: {row['service_label']}",
            f"{elder.first_name} {elder.last_name}: {', '.join(i['name'] for i in items)}"
            " (from an approved AI room preview). Quote and schedule it from the ops dashboard.",
        )
        return _to_response(row)

    @staticmethod
    def cancel_for_family(db: Session, user: User, request_id: str) -> dict:
        from app.livewell.wallet_service import WalletService

        elder = lock_elder(db, ElderPortalService.get_linked_elder(db, user))
        rows = _requests(elder)
        found = None
        for r in rows:
            if str(r.get("id")) == str(request_id):
                if str(r.get("status")) not in ("requested", "confirmed"):
                    raise_bad_request("Only requested or confirmed items can be cancelled")
                found = r
                break
        if not found:
            raise_not_found("Request not found")

        current = _normalize(found)

        # Cancelling something already paid for returns the money as a new
        # ledger entry — balances are never edited backwards.
        if current["payment_status"] == "paid" and current["quoted_amount_minor"] > 0:
            wallet = WalletService.get_or_create(db, elder)
            WalletService.record(
                db,
                wallet,
                kind="refund",
                amount_minor=current["quoted_amount_minor"],
                idempotency_key=f"refund:service_request:{current['id']}",
                reference_type="service_request",
                reference_id=current["id"],
                note=f"Refunded to your KushAlaya wallet — {current['service_label']} cancelled",
                user=user,
                commit=False,
            )
            found["payment_status"] = "refunded"

        found["status"] = "cancelled"
        found["updated_at"] = _iso()
        _save_requests(db, elder, rows)

        # A booked job for this request is cancelled too, and the staff are told.
        from app.livewell.care_jobs import _when, cancel_for_request
        from app.livewell.email_notifications import email_staff, staff_path

        job = cancel_for_request(db, elder, current["id"])
        db.commit()
        name = f"{elder.first_name} {elder.last_name}".strip()
        label = current["service_label"]
        if job:
            what = f"The {job.title.lower()} booked for {_when(job.scheduled_at)} IST is cancelled too — the caregiver's list is updated."
        else:
            what = "It had not been booked yet, so nothing else changes."
        refund = (
            f" {format_minor(current['quoted_amount_minor'])} was refunded to the family wallet."
            if found.get("payment_status") == "refunded"
            else ""
        )
        email_staff(
            db,
            elder,
            "request_cancelled",
            f"Family cancelled: {label} — {name}",
            f"{user.first_name or 'The family'} cancelled the request for {label}.\n{what}{refund}",
            path=staff_path(elder, "timeline"),
        )
        return _to_response(found)

    @staticmethod
    def pay_from_wallet(db: Session, user: User, request_id: str) -> dict:
        """Family approves the quoted price — wallet is debited upfront."""
        from app.livewell.wallet_service import WalletService

        elder = lock_elder(db, ElderPortalService.get_linked_elder(db, user))
        rows = _requests(elder)
        found = None
        for r in rows:
            if str(r.get("id")) == str(request_id):
                found = r
                break
        if not found:
            raise_not_found("Request not found")

        current = _normalize(found)
        if current["payment_status"] == "paid":
            return _to_response(found)
        if current["payment_status"] != "awaiting_approval":
            raise_bad_request("This request has no price to approve yet")
        if current["quoted_amount_minor"] <= 0:
            raise_bad_request("This request has no price to approve yet")
        if current["status"] in ("cancelled", "declined"):
            raise_bad_request("This request is no longer active")

        wallet = WalletService.get_or_create(db, elder)
        entry = WalletService.record(
            db,
            wallet,
            kind="debit",
            amount_minor=current["quoted_amount_minor"],
            # One debit per request, no matter how many times approve is tapped.
            idempotency_key=f"debit:service_request:{current['id']}",
            reference_type="service_request",
            reference_id=current["id"],
            note=current["service_label"],
            user=user,
            commit=False,
        )

        found["payment_status"] = "paid"
        found["wallet_transaction_id"] = entry.public_id
        found["updated_at"] = _iso()
        _save_requests(db, elder, rows)
        return _to_response(found)

    @staticmethod
    def _elder_for_staff(db: Session, user: User, elder_id: int) -> Elder:
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Client not found")
        assert_tenant_access(user, elder.tenant_id)
        tid = resolve_tenant_id(user)
        if tid is not None and elder.tenant_id != tid:
            raise_not_found("Client not found")
        from app.core.team_scope import assert_elder_in_team

        assert_elder_in_team(db, user, elder.id)
        return elder

    @staticmethod
    def list_for_staff(db: Session, user: User, elder_id: int) -> list[dict]:
        elder = FamilyServiceRequestService._elder_for_staff(db, user, elder_id)
        rows = [_normalize(r) for r in _requests(elder)]
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return [_to_response(r) for r in rows]

    @staticmethod
    def staff_update(
        db: Session,
        user: User,
        elder_id: int,
        request_id: str,
        *,
        status: str,
        staff_note: str | None = None,
        quoted_amount_minor: int | None = None,
    ) -> dict:
        from app.livewell.visit_service import HomeSafetyVisitService

        elder = lock_elder(db, FamilyServiceRequestService._elder_for_staff(db, user, elder_id))
        status_n = (status or "").strip().lower()
        if status_n not in STATUSES:
            raise_bad_request("Invalid status")
        if quoted_amount_minor is not None and quoted_amount_minor < 0:
            raise_bad_request("Quoted amount cannot be negative")

        rows = _requests(elder)
        found = None
        for r in rows:
            if str(r.get("id")) != str(request_id):
                continue
            found = r
            break
        if not found:
            raise_not_found("Request not found")

        previous = str(found.get("status") or "")
        # A finished, cancelled or declined request is closed — only its note may change.
        if previous in CLOSED_STATUSES and status_n != previous:
            raise_bad_request(f"This request is already {previous} and can't be changed")
        if previous == "confirmed" and status_n == "requested":
            raise_bad_request("A confirmed request can't go back to requested")
        found["status"] = status_n

        # Staff declining or cancelling something the family already paid for
        # returns the money as a refund ledger entry (same key as a family cancel,
        # so it can never be refunded twice). The elder row is locked above.
        refunded_minor = 0
        current = _normalize(found)
        if (
            status_n in ("declined", "cancelled")
            and current["payment_status"] == "paid"
            and current["quoted_amount_minor"] > 0
        ):
            from app.livewell.wallet_service import WalletService

            wallet = WalletService.get_or_create(db, elder)
            WalletService.record(
                db,
                wallet,
                kind="refund",
                amount_minor=current["quoted_amount_minor"],
                idempotency_key=f"refund:service_request:{current['id']}",
                reference_type="service_request",
                reference_id=current["id"],
                note=f"Refunded to your KushAlaya wallet — {current['service_label']} {status_n}",
                user=user,
                commit=False,
            )
            found["payment_status"] = "refunded"
            refunded_minor = current["quoted_amount_minor"]
        if staff_note is not None:
            found["staff_note"] = staff_note.strip()

        # Quoting a price puts the request in front of the family to approve and
        # pay. An already-paid request keeps its price — re-quoting it would
        # silently change what the family agreed to.
        if quoted_amount_minor is not None:
            if _normalize(found)["payment_status"] == "paid":
                raise_bad_request("This request is already paid — issue a refund instead")
            found["quoted_amount_minor"] = int(quoted_amount_minor)
            found["payment_status"] = (
                "awaiting_approval" if quoted_amount_minor > 0 else "not_required"
            )

        found["updated_at"] = _iso()

        if status_n == "confirmed" and not found.get("visit_id"):
            visit_type_map = {
                "wellness_visit": "Wellness visit",
                "home_repair": "Modification follow-up",
                "product_install": "Product installation",
                "nurse_pt": "Wellness visit",
                "haircut_grooming": "Other",
                "grocery_errand": "Other",
                "other": "Other",
            }
            visit = HomeSafetyVisitService.create_for_elder(
                db,
                user,
                elder.id,
                {
                    "visit_type": visit_type_map.get(found.get("service_type"), "Other"),
                    "status": "scheduled",
                    "visited_at": found.get("preferred_at"),
                    "summary": (
                        f"Family request: {_normalize(found)['service_label']}"
                        f"{' (' + found['product_code'] + ')' if found.get('product_code') else ''}. "
                        f"{found.get('notes') or ''}"
                    ).strip(),
                    "staff_name": f"{user.first_name} {user.last_name}".strip() or user.email,
                    "wellness_notes": found.get("staff_note") or "",
                },
            )
            found["visit_id"] = visit.get("id")
        _save_requests(db, elder, rows)
        if status_n != previous:
            FamilyServiceRequestService._tell_family(
                db, elder, found, status_n, refunded_minor=refunded_minor
            )
        return _to_response(found)

    @staticmethod
    def _tell_family(
        db: Session, elder: Elder, row: dict, status: str, *, refunded_minor: int = 0
    ) -> None:
        """Portal alert + email when staff confirm, decline or finish a request, with the date."""
        from app.livewell.care_jobs import _when
        from app.livewell.family_notify import notify_family

        label = _normalize(row)["service_label"]
        note = (row.get("staff_note") or "").strip()
        if status == "confirmed":
            when = _parse_dt(row.get("preferred_at"))
            title = f"{label} confirmed"
            body = (
                f"{label} is confirmed for {_when(when)} IST." if when else f"{label} is confirmed and on your schedule."
            )
        elif status == "declined":
            title = f"{label}: we couldn't book this"
            body = note or f"We couldn't schedule {label.lower()} this time. Your Family Partner will be in touch."
            note = ""
        elif status == "done":
            title = f"{label} done"
            body = f"{label} was completed on {_when(_now())} IST."
        elif status == "cancelled" and refunded_minor:
            title = f"{label} cancelled"
            body = f"Your care team cancelled {label.lower()}."
        else:
            return
        if refunded_minor:
            body += f"\n{format_minor(refunded_minor)} was refunded to your KushAlaya wallet."
        if note:
            body += f"\nNote from your care team: {note}"
        try:
            notify_family(db, elder, title, body, event="request", path="/services")
        except Exception:  # a failed notice must never fail the update
            logger.exception("request_notify_failed elder=%s", elder.id)
