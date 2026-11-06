"""Sales -> Vendors: the tenant's vendor list. Staff with edit roles write; viewers read."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles, resolve_tenant_id
from app.core.storage import get_storage
from app.livewell import team_alerts
from app.models.contract import Contract
from app.models.user import User
from app.models.vendor import FEE_BASES, VENDOR_SERVICES, VENDOR_STATUSES, Vendor

router = APIRouter(prefix="/vendors", tags=["Vendors"])

SERVICE_CODES = {c for c, _ in VENDOR_SERVICES}
#: Who can own a vendor contact.
OWNER_ROLES = ("SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER", "VIEWER")
BASIS_CODES = {c for c, _ in FEE_BASES}
#: 2-digit state code, 10-char PAN, entity digit, Z, check character.
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


class VendorIn(BaseModel):
    company_name: str = Field(max_length=200)
    address: str | None = Field(default=None, max_length=2000)
    owner_name: str | None = Field(default=None, max_length=200)
    phone1: str = Field(max_length=30)
    phone2: str | None = Field(default=None, max_length=30)
    gstin: str | None = Field(default=None, max_length=20)
    services: list[str] = Field(default_factory=list)
    services_other: str | None = Field(default=None, max_length=200)
    fee_paise: int | None = Field(default=None, ge=0)
    fee_basis: str | None = None
    last_payment_date: date | None = None
    status: str = "active"
    owner_user_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("company_name", "phone1")
    @classmethod
    def _required(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Required")
        return v

    @field_validator("address", "owner_name", "phone2", "services_other", "notes")
    @classmethod
    def _optional(cls, v: str | None) -> str | None:
        return _clean(v)

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        v = (_clean(v) or "").replace(" ", "").upper()
        if not v:
            return None
        if not GSTIN_RE.match(v):
            raise ValueError("GSTIN must be 15 characters, e.g. 36ABCDE1234F1Z5")
        return v

    @field_validator("services")
    @classmethod
    def _services(cls, v: list[str]) -> list[str]:
        bad = [s for s in v if s not in SERVICE_CODES]
        if bad:
            raise ValueError(f"Unknown service: {', '.join(bad)}")
        return [c for c, _ in VENDOR_SERVICES if c in v]  # list order, no duplicates

    @field_validator("fee_basis")
    @classmethod
    def _basis(cls, v: str | None) -> str | None:
        v = _clean(v)
        if v and v not in BASIS_CODES:
            raise ValueError("Choose per visit, monthly, one-time or per job")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in VENDOR_STATUSES:
            raise ValueError("Status is active or inactive")
        return v


#: Paper agreements are scans: PDF, or a photo of each page. Checked by file signature too.
AGREEMENT_TYPES = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8", "image/png": b"\x89PNG"}
MAX_AGREEMENT_BYTES = 10 * 1024 * 1024


def _contract_states(db: Session, vendor_ids: list[int]) -> dict[int, str]:
    """vendor id -> "signed" or "sent", from agreements signed or waiting in the app."""
    if not vendor_ids:
        return {}
    now = datetime.now(timezone.utc)
    states: dict[int, str] = {}
    rows = db.execute(
        select(Contract.vendor_id, Contract.status, Contract.expires_at).where(
            Contract.vendor_id.in_(vendor_ids), Contract.status.in_(("sent", "viewed", "signed"))
        )
    ).all()
    for vendor_id, status, expires_at in rows:
        if status == "signed":
            states[vendor_id] = "signed"
        elif expires_at is None or expires_at.replace(tzinfo=expires_at.tzinfo or timezone.utc) >= now:
            states.setdefault(vendor_id, "sent")
    return states


def _staff_names(db: Session, tenant_id: int | None) -> dict[int, str]:
    stmt = select(User)
    if tenant_id is not None:
        stmt = stmt.where(User.tenant_id == tenant_id)
    return {u.id: f"{u.first_name} {u.last_name}".strip() or u.email for u in db.scalars(stmt).all()}


def _out(v: Vendor, contract_state: str | None = None, names: dict[int, str] | None = None) -> dict:
    names = names or {}
    return {
        "id": v.id,
        "company_name": v.company_name,
        "address": v.address,
        "owner_name": v.owner_name,
        "phone1": v.phone1,
        "phone2": v.phone2,
        "gstin": v.gstin,
        "services": list(v.services or []),
        "services_other": v.services_other,
        "fee_paise": v.fee_paise,
        "fee_basis": v.fee_basis,
        "last_payment_date": v.last_payment_date.isoformat() if v.last_payment_date else None,
        "status": v.status,
        "notes": v.notes,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
        "created_by_user_id": v.created_by_user_id,
        "added_by_name": names.get(v.created_by_user_id),
        "owner_user_id": v.owner_user_id,
        "owner_staff_name": names.get(v.owner_user_id),
        "agreement_status": "signed" if v.signed_agreement_key else (contract_state or "pending"),
        "signed_agreement_name": v.signed_agreement_name,
        "signed_agreement_at": v.signed_agreement_at.isoformat() if v.signed_agreement_at else None,
        "signed_agreement_by": v.signed_agreement_by,
    }


def _one(db: Session, v: Vendor) -> dict:
    return _out(v, _contract_states(db, [v.id]).get(v.id), _staff_names(db, v.tenant_id))


def _apply(row: Vendor, data: VendorIn) -> None:
    for k, val in data.model_dump(exclude={"owner_user_id"}).items():
        setattr(row, k, val)
    if "other" not in row.services:
        row.services_other = None
    if row.fee_paise is None:
        row.fee_basis = None


def _set_owner(db: Session, row: Vendor, owner_id: int | None) -> None:
    """Blank keeps the current owner; a new one must be active staff of this tenant."""
    if owner_id is None:
        return
    owner = db.get(User, owner_id)
    if owner is None or owner.tenant_id != row.tenant_id or owner.role not in OWNER_ROLES:
        raise HTTPException(status_code=422, detail="Choose a staff member as the owner.")
    row.owner_user_id = owner_id


def _get(db: Session, user: User, vendor_id: int) -> Vendor:
    row = db.get(Vendor, vendor_id)
    tid = resolve_tenant_id(user)
    if row is None or (tid is not None and row.tenant_id != tid):
        raise HTTPException(status_code=404, detail="Vendor not found")
    return row


@router.get("/options")
def options(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    stmt = select(User).where(User.status == "ACTIVE", User.role.in_(OWNER_ROLES))
    tid = resolve_tenant_id(user)
    if tid is not None:
        stmt = stmt.where(User.tenant_id == tid)
    staff = [{"id": u.id, "name": f"{u.first_name} {u.last_name}".strip() or u.email} for u in db.scalars(stmt).all()]
    return {
        "staff": sorted(staff, key=lambda s: s["name"].lower()),
        "services": [{"code": c, "label": lbl} for c, lbl in VENDOR_SERVICES],
        "fee_bases": [{"code": c, "label": lbl} for c, lbl in FEE_BASES],
    }


@router.get("")
def list_vendors(
    q: str | None = Query(default=None, max_length=100),
    service: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=10),
    agreement: str | None = Query(default=None, max_length=10),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    stmt = select(Vendor)
    tid = resolve_tenant_id(user)
    if tid is not None:
        stmt = stmt.where(Vendor.tenant_id == tid)
    if status in VENDOR_STATUSES:
        stmt = stmt.where(Vendor.status == status)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                Vendor.company_name.ilike(like),
                Vendor.owner_name.ilike(like),
                Vendor.phone1.ilike(like),
                Vendor.phone2.ilike(like),
                Vendor.gstin.ilike(like),
                Vendor.address.ilike(like),
            )
        )
    rows = db.scalars(stmt.order_by(Vendor.company_name)).all()
    if service:  # JSON list: filter in Python (works on SQLite and Postgres alike)
        rows = [r for r in rows if service in (r.services or [])]
    states = _contract_states(db, [r.id for r in rows])
    names = _staff_names(db, tid)
    out = [_out(r, states.get(r.id), names) for r in rows]
    if agreement == "signed":
        out = [o for o in out if o["agreement_status"] == "signed"]
    elif agreement == "open":
        out = [o for o in out if o["agreement_status"] != "signed"]
    return out


@router.post("", status_code=201)
def create_vendor(data: VendorIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Sign in as a staff member of a tenant to add vendors")
    row = Vendor(tenant_id=user.tenant_id, created_by_user_id=user.id, owner_user_id=user.id)
    _apply(row, data)
    _set_owner(db, row, data.owner_user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    team_alerts.alert_team(
        db, row.tenant_id, "vendor_new", f"New vendor: {row.company_name}",
        f"Added by {user.first_name} {user.last_name}".strip(), path="/kushalaya/vendors",
    )
    return _one(db, row)


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _one(db, _get(db, user, vendor_id))


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: int, data: VendorIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    row = _get(db, user, vendor_id)
    _apply(row, data)
    _set_owner(db, row, data.owner_user_id)
    db.commit()
    db.refresh(row)
    return _one(db, row)


@router.post("/{vendor_id}/deactivate")
def deactivate_vendor(vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    row = _get(db, user, vendor_id)
    row.status = "inactive"
    db.commit()
    db.refresh(row)
    return _one(db, row)


@router.post("/{vendor_id}/signed-agreement")
async def upload_signed_agreement(
    vendor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    row = _get(db, user, vendor_id)
    content = await file.read()
    mime = (file.content_type or "").lower()
    magic = AGREEMENT_TYPES.get(mime)
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty.")
    if not magic or not content.startswith(magic):
        raise HTTPException(status_code=422, detail="Upload a PDF, JPG or PNG of the signed agreement.")
    if len(content) > MAX_AGREEMENT_BYTES:
        raise HTTPException(status_code=422, detail="The file must be 10 MB or smaller.")
    name = re.sub(r"[^\w. -]", "_", file.filename or "signed-agreement")[-120:]
    key, _url = get_storage().save(row.tenant_id, "vendor_agreement", row.id, name, content, mime)
    row.signed_agreement_key = key
    row.signed_agreement_name = name
    row.signed_agreement_mime = mime
    row.signed_agreement_at = datetime.now(timezone.utc)
    row.signed_agreement_by = f"{user.first_name} {user.last_name}".strip() or user.email
    db.commit()
    db.refresh(row)
    return _one(db, row)


@router.get("/{vendor_id}/signed-agreement")
def download_signed_agreement(
    vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))
):
    row = _get(db, user, vendor_id)
    if not row.signed_agreement_key:
        raise HTTPException(status_code=404, detail="No signed agreement uploaded.")
    content, mime = get_storage().read(row.signed_agreement_key)
    return Response(
        content=content,
        media_type=row.signed_agreement_mime or mime,
        headers={"Content-Disposition": f'attachment; filename="{row.signed_agreement_name or "signed-agreement"}"'},
    )


@router.delete("/{vendor_id}/signed-agreement")
def remove_signed_agreement(
    vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    row = _get(db, user, vendor_id)
    row.signed_agreement_key = row.signed_agreement_name = row.signed_agreement_mime = None
    row.signed_agreement_at = row.signed_agreement_by = None
    db.commit()
    db.refresh(row)
    return _one(db, row)
