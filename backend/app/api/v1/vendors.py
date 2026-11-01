"""Sales -> Vendors: the tenant's vendor list. Staff with edit roles write; viewers read."""

from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles, resolve_tenant_id
from app.models.user import User
from app.models.vendor import FEE_BASES, VENDOR_SERVICES, VENDOR_STATUSES, Vendor

router = APIRouter(prefix="/vendors", tags=["Vendors"])

SERVICE_CODES = {c for c, _ in VENDOR_SERVICES}
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


def _out(v: Vendor) -> dict:
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
    }


def _apply(row: Vendor, data: VendorIn) -> None:
    for k, val in data.model_dump().items():
        setattr(row, k, val)
    if "other" not in row.services:
        row.services_other = None
    if row.fee_paise is None:
        row.fee_basis = None


def _get(db: Session, user: User, vendor_id: int) -> Vendor:
    row = db.get(Vendor, vendor_id)
    tid = resolve_tenant_id(user)
    if row is None or (tid is not None and row.tenant_id != tid):
        raise HTTPException(status_code=404, detail="Vendor not found")
    return row


@router.get("/options")
def options(user: User = Depends(require_roles(*READ_ROLES))):
    return {
        "services": [{"code": c, "label": lbl} for c, lbl in VENDOR_SERVICES],
        "fee_bases": [{"code": c, "label": lbl} for c, lbl in FEE_BASES],
    }


@router.get("")
def list_vendors(
    q: str | None = Query(default=None, max_length=100),
    service: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=10),
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
    return [_out(r) for r in rows]


@router.post("", status_code=201)
def create_vendor(data: VendorIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    if user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Sign in as a staff member of a tenant to add vendors")
    row = Vendor(tenant_id=user.tenant_id, created_by_user_id=user.id)
    _apply(row, data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _out(_get(db, user, vendor_id))


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: int, data: VendorIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    row = _get(db, user, vendor_id)
    _apply(row, data)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/{vendor_id}/deactivate")
def deactivate_vendor(vendor_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    row = _get(db, user, vendor_id)
    row.status = "inactive"
    db.commit()
    db.refresh(row)
    return _out(row)
