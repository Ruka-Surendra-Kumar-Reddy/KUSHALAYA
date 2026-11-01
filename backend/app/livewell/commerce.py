"""Products, coupons and orders (see app/models/commerce.py).

Pricing rules (owner, 2026-10-01):
- selling price = cost × (1 + margin); prices are entered before GST
- GST 18% is added on top of the discounted amount
- a manager may discount up to 10%; more needs an admin's approval
- coupons are created by admins and applied by staff
- an order never goes below its cost
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rbac import CARE_MANAGER, SYSTEM_ADMIN, TENANT_ADMIN, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.team_scope import assert_elder_in_team, team_elder_ids
from app.models.commerce import Coupon, Order, Product
from app.models.elder import Elder
from app.models.user import User

GST_BP = 1800
MANAGER_DISCOUNT_LIMIT_BP = 1000

# The 9 products the owner sells (the website's 7, the SOS wearable and the assessment).
DEFAULT_PRODUCTS = [
    ("KushAlaya Assessment (KAA)", "Service"),
    ("Fixed grab bar", "Bathroom"),
    ("Fold-up toilet rail", "Bathroom"),
    ("Shower chair", "Bathroom"),
    ("Anti-slip bath mat", "Bathroom"),
    ("Anti-slip floor treatment", "Bathroom"),
    ("Bathroom emergency pull cord", "Bathroom"),
    ("Adult bed rail", "Bedroom"),
    ("SOS wearable (fall alert band)", "Wearable"),
]

# The 9 above, linked to their entry in default_catalog.json (same thing, older name).
LEGACY_CODES = {
    "KushAlaya Assessment (KAA)": "SVC-001",
    "Fixed grab bar": "BTH-001",
    "Fold-up toilet rail": "BTH-003",
    "Shower chair": "BTH-005",
    "Anti-slip floor treatment": "BTH-008",
    "Adult bed rail": "BED-001",
    "SOS wearable (fall alert band)": "SMT-006",
}

# Products the assessment recommends that the workbook catalog lacks (KushLife kit and
# solution-library items). Prices are estimates for the owner to review.
# EMG-006 / SMT-012 (2026-10-09) and HLT-001..004 / BTH-012 / BTH-013 (2026-10-11) moved
# into default_catalog.json so assessment findings can link to them. Keep codes unique.
EXTRA_CATALOG: list[tuple[str, str, str, int, str]] = []
SERVICE_PREFIXES = {"SVC", "WEL", "HM", "NUR", "PHY", "DX", "PM", "TRN"}
_CATALOG: list[dict] | None = None


def _cost_for_price(price_paise_: int, margin_bp: int = 3000) -> int:
    """Cost that gives exactly this selling price at the default margin (catalog lists prices, not costs)."""
    cost = int(round(price_paise_ * 10000 / (10000 + margin_bp)))
    for c in (cost, cost - 1, cost + 1):
        if price_paise(c, margin_bp) == price_paise_:
            return c
    return cost


def catalog_products() -> list[dict]:
    """Product rows for every catalog entry (default_catalog.json + EXTRA_CATALOG), in catalog order."""
    global _CATALOG
    if _CATALOG is None:
        import json
        from pathlib import Path

        raw = json.loads((Path(__file__).parent / "default_catalog.json").read_text(encoding="utf-8"))["products"]
        items = [
            (p["product_code"], p["name"], p["category"], int(p.get("price_inr") or 0),
             p.get("short_description") or "", p.get("price_label") or "")
            for p in sorted(raw, key=lambda p: p.get("sort_order") or 0)
        ]
        items += [(*e, "Installed from") for e in EXTRA_CATALOG]
        out = []
        for i, (code, name, category, rupees, desc, label) in enumerate(items):
            if desc.strip().lower() == name.strip().lower():
                desc = ""
            if label and not label.lower().startswith("installed"):
                desc = f"{desc} · {label}" if desc else label
            # PM-004 is a share of the project cost, not a fixed price: list it, but off.
            fixed = not label.endswith("of project")
            out.append({
                "product_code": code, "name": name, "category": category, "description": desc,
                "cost_paise": _cost_for_price(rupees * 100) if fixed else 0, "margin_bp": 3000,
                "sort_order": 100 + i, "active": fixed,
            })
        _CATALOG = out
    return _CATALOG


def catalog_image_url(product_code: str | None) -> str | None:
    """Reference picture shipped with the site: one image per product or service code
    (generated and checked Oct 2026). An uploaded photo on the product still wins."""
    if not product_code:
        return None
    return f"/marketing/products/catalog/{product_code.lower()}.webp"


def is_admin(user: User) -> bool:
    return user.role in (SYSTEM_ADMIN, TENANT_ADMIN)


# Our cost and margin are admin-only business data (security fix 2026-10-07).
STAFF_HIDDEN_KEYS = frozenset({"cost_paise", "margin_bp", "margin_paise"})


def for_viewer(user: User, data):
    """Drop cost/margin fields (at any depth) unless the viewer is an admin."""
    if is_admin(user):
        return data
    if isinstance(data, dict):
        return {k: for_viewer(user, v) for k, v in data.items() if k not in STAFF_HIDDEN_KEYS}
    if isinstance(data, list):
        return [for_viewer(user, v) for v in data]
    return data


def price_paise(cost_paise: int, margin_bp: int) -> int:
    """Selling price before GST, rounded to the nearest rupee."""
    raw = cost_paise * (10000 + margin_bp) / 10000
    return int(round(raw / 100.0)) * 100


def _tenant(user: User) -> int:
    tid = resolve_tenant_id(user)
    if tid is None:
        raise_bad_request("Pick an agency first")
    return tid


# --- Products --------------------------------------------------------------------


# Pictures already on the marketing site (frontend/public/marketing/...), by product name.
DEFAULT_IMAGES = {
    "KushAlaya Assessment (KAA)": "/marketing/how-01-assess-700.webp",
    "Fixed grab bar": "/marketing/products/grab-bar.webp",
    "Fold-up toilet rail": "/marketing/products/toilet-rail.webp",
    "Shower chair": "/marketing/products/shower-chair.webp",
    "Anti-slip bath mat": "/marketing/products/anti-slip-mat.webp",
    "Anti-slip floor treatment": "/marketing/products/anti-slip-gel.webp",
    "Bathroom emergency pull cord": "/marketing/products/pull-cord.webp",
    "Adult bed rail": "/marketing/products/bed-rail.webp",
    "Night light": "/marketing/products/night-light.webp",
}
# Catalog codes whose picture is one of the marketing photos above.
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def product_image_url(p: Product) -> str | None:
    if p.image_key:
        return f"/api/v1/product-images/{p.id}?v={p.image_version or 0}"
    # The per-code catalog image wins; the old name-based photo only covers rows with no code.
    return catalog_image_url(p.product_code) or DEFAULT_IMAGES.get(p.name)


def is_service_product(p: Product) -> bool:
    """A visit or service (nursing, physio, transport...) rather than a thing we deliver."""
    prefix = (p.product_code or "").split("-")[0].upper()
    return prefix in SERVICE_PREFIXES or (p.category or "").strip().lower() == "service"


def family_product_row(p: Product) -> dict:
    """What a family may see about a catalog item: selling price before GST, never cost or margin.

    Built field by field (not from product_row) so cost/margin can never leak, whoever asks.
    An item with no cost set yet has price 0, shown as "Price on request".
    """
    from app.livewell.family_catalog_copy import blurb_for, included_for, unit_for

    kind = "service" if is_service_product(p) else "product"
    price = price_paise(p.cost_paise, p.margin_bp) if p.cost_paise else 0
    # Plain words for families; the ops text (often technical, with "· Per visit") is the fallback.
    ops_text = (p.description or "").split(" · ")[0].strip()
    return {
        "id": p.id,
        "product_code": p.product_code or "",
        "name": p.name,
        "category": p.category or "",
        "description": blurb_for(p.product_code, p.name, ops_text),
        "kind": kind,
        "unit": unit_for(p.product_code),
        "included": included_for(p.product_code, kind),
        "image_url": product_image_url(p),
        "price_paise": price,
        "price_with_gst_paise": price + price * GST_BP // 10000,
    }


def set_product_image(db: Session, user: User, product_id: int, content: bytes | None, mime: str, name: str) -> dict:
    """Upload (or with content=None, remove) a product photo. Admins only."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only admins can change product photos")
    p = db.get(Product, product_id)
    if not p or p.tenant_id != _tenant(user):
        raise_not_found("Product not found")
    if content is None:
        p.image_key = None
    else:
        if mime not in IMAGE_TYPES:
            raise_bad_request("Use a JPG, PNG or WebP photo")
        if len(content) > MAX_IMAGE_BYTES:
            raise_bad_request("Photo must be 5 MB or smaller")
        from app.core.storage import get_storage

        key, _url = get_storage().save(p.tenant_id, "product", p.id, name or "photo", content, mime)
        p.image_key = key
    p.image_version = (p.image_version or 0) + 1
    db.commit()
    return product_row(p)


def product_image_bytes(db: Session, product_id: int) -> tuple[bytes, str]:
    p = db.get(Product, product_id)
    if not p or not p.image_key:
        raise_not_found("No photo")
    from app.core.storage import get_storage

    return get_storage().read(p.image_key)


def product_row(p: Product) -> dict:
    return {
        "id": p.id,
        "image_url": product_image_url(p),
        "has_own_image": bool(p.image_key),
        "name": p.name,
        "product_code": p.product_code,
        "category": p.category,
        "description": p.description,
        "cost_paise": p.cost_paise,
        "margin_bp": p.margin_bp,
        "price_paise": price_paise(p.cost_paise, p.margin_bp),
        "active": p.active,
        "fixes": list(p.fixes or []),
        "sort_order": p.sort_order,
    }


def ensure_default_products(db: Session, tenant_id: int) -> None:
    """Add any catalog product this tenant is missing (matched by code or name).

    Existing rows — and the prices on them — are never changed; products are retired
    with `active`, never deleted, so a missing row really is new.
    """
    rows = db.query(Product.name, Product.product_code).filter(Product.tenant_id == tenant_id).all()
    names = {r.name.lower() for r in rows}
    codes = {r.product_code for r in rows if r.product_code}
    added = False
    if not rows:  # new tenant: the original 9 first, then the rest of the catalog
        for i, (name, category) in enumerate(DEFAULT_PRODUCTS):
            db.add(Product(tenant_id=tenant_id, name=name, category=category, sort_order=i, margin_bp=3000,
                           product_code=LEGACY_CODES.get(name)))
            names.add(name.lower())
            codes.add(LEGACY_CODES.get(name))
        added = True
    else:
        # Rows seeded before product_code existed: link them to their catalog entry.
        for p in db.query(Product).filter(Product.tenant_id == tenant_id, Product.product_code.is_(None),
                                          Product.name.in_(list(LEGACY_CODES))):
            if LEGACY_CODES[p.name] not in codes:
                p.product_code = LEGACY_CODES[p.name]
                codes.add(p.product_code)
                added = True
    for item in catalog_products():
        if item["product_code"] in codes or item["name"].lower() in names:
            continue
        db.add(Product(tenant_id=tenant_id, **item))
        added = True
    if added:
        try:
            db.commit()
        except IntegrityError:
            # Two page requests seeded at the same moment; the other one won.
            db.rollback()


def list_products(db: Session, user: User, *, include_inactive: bool = False) -> list[dict]:
    tid = _tenant(user)
    ensure_default_products(db, tid)
    q = db.query(Product).filter(Product.tenant_id == tid)
    if not include_inactive:
        q = q.filter(Product.active.is_(True))
    return [product_row(p) for p in q.order_by(Product.sort_order, Product.id).all()]


def save_product(db: Session, user: User, product_id: int | None, data: dict) -> dict:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only admins can change products and prices")
    tid = _tenant(user)
    if product_id:
        p = db.get(Product, product_id)
        if not p or p.tenant_id != tid:
            raise_not_found("Product not found")
    elif not (data.get("name") or "").strip():
        raise_bad_request("Name is required")
    if data.get("name") is not None:
        name = str(data["name"]).strip()[:160]
        if not name:
            raise_bad_request("Name is required")
        dup = db.query(Product).filter(Product.tenant_id == tid, Product.name == name)
        if product_id:
            dup = dup.filter(Product.id != product_id)
        if dup.first():
            raise_bad_request("A product with that name already exists")
    if not product_id:
        p = Product(tenant_id=tid, sort_order=db.query(Product).filter(Product.tenant_id == tid).count())
        db.add(p)
    before = {"cost_paise": p.cost_paise, "margin_bp": p.margin_bp, "active": p.active} if product_id else None
    for f, limit in (("name", 160), ("category", 60), ("description", 2000)):
        if data.get(f) is not None:
            setattr(p, f, str(data[f]).strip()[:limit])
    if data.get("cost_paise") is not None:
        if int(data["cost_paise"]) < 0:
            raise_bad_request("Cost can't be negative")
        p.cost_paise = int(data["cost_paise"])
    if data.get("margin_bp") is not None:
        if not 0 <= int(data["margin_bp"]) <= 50000:
            raise_bad_request("Margin must be between 0% and 500%")
        p.margin_bp = int(data["margin_bp"])
    if data.get("active") is not None:
        p.active = bool(data["active"])
    if data.get("fixes") is not None:
        p.fixes = [str(x) for x in data["fixes"]][:200]
    after = {"cost_paise": p.cost_paise, "margin_bp": p.margin_bp, "active": p.active}
    if before != after:
        from app.services.audit_service import AuditService

        db.flush()
        AuditService.log(
            db, tenant_id=tid, user_id=user.id, entity_type="product", entity_id=p.id,
            action="product_price" if product_id else "product_created", old_value=before, new_value=after,
        )
    db.commit()
    db.refresh(p)
    return product_row(p)


# --- Coupons ---------------------------------------------------------------------


def coupon_row(c: Coupon) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "kind": c.kind,
        "value": c.value,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "max_uses": c.max_uses,
        "used_count": c.used_count,
        "active": c.active,
        "note": c.note,
    }


def list_coupons(db: Session, user: User) -> list[dict]:
    tid = _tenant(user)
    return [coupon_row(c) for c in db.query(Coupon).filter(Coupon.tenant_id == tid).order_by(Coupon.id.desc()).all()]


def save_coupon(db: Session, user: User, coupon_id: int | None, data: dict) -> dict:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only admins can create coupons")
    tid = _tenant(user)
    if coupon_id:
        c = db.get(Coupon, coupon_id)
        if not c or c.tenant_id != tid:
            raise_not_found("Coupon not found")
    else:
        code = (data.get("code") or "").strip().upper()
        if not code or len(code) > 40 or not code.replace("-", "").isalnum():
            raise_bad_request("Use letters and numbers for the code, e.g. DIWALI10")
        if db.query(Coupon).filter(Coupon.tenant_id == tid, Coupon.code == code).first():
            raise_bad_request("That code already exists")
        c = Coupon(tenant_id=tid, code=code, kind="percent", used_count=0, value=0)
    # Check everything before changing the row, so a refused edit leaves it as it was.
    kind = data["kind"] if data.get("kind") is not None else (c.kind or "percent")
    if kind not in ("percent", "amount"):
        raise_bad_request("Coupon is either a % or a ₹ amount")
    value = int(data["value"]) if data.get("value") is not None else (c.value or 0)
    if data.get("value") is not None and value <= 0:
        raise_bad_request("Enter a discount above zero")
    if kind == "percent" and value > 10000:
        raise_bad_request("A % coupon can be at most 100%")
    mu = data.get("max_uses") if "max_uses" in data else c.max_uses
    if "max_uses" in data and mu is not None:
        mu = int(mu)
        if mu < 1:
            raise_bad_request("Times it can be used must be 1 or more (leave it empty for no limit)")
        if mu < (c.used_count or 0):
            raise_bad_request(f"This coupon has already been used {c.used_count} times — the limit can't be lower")
    if not value:
        raise_bad_request("Enter the discount")
    if not coupon_id:
        db.add(c)
    c.kind = kind
    c.value = value
    c.max_uses = mu
    if "expires_at" in data:
        c.expires_at = data["expires_at"]
    if data.get("active") is not None:
        c.active = bool(data["active"])
    if data.get("note") is not None:
        c.note = str(data["note"]).strip()[:200]
    db.commit()
    db.refresh(c)
    return coupon_row(c)


def _valid_coupon(db: Session, tenant_id: int, code: str) -> Coupon:
    c = db.query(Coupon).filter(Coupon.tenant_id == tenant_id, Coupon.code == code.strip().upper()).first()
    if not c or not c.active:
        raise_bad_request("Coupon not found")
    exp = c.expires_at
    if exp is not None:
        exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise_bad_request("This coupon has expired")
    if c.max_uses is not None and c.used_count >= c.max_uses:
        raise_bad_request("This coupon has been used up")
    return c


# --- Orders ----------------------------------------------------------------------


def price_order(
    db: Session,
    tenant_id: int,
    lines_in: list[dict],
    *,
    discount_paise: int = 0,
    discount_bp: int = 0,
    coupon_code: str | None = None,
) -> dict:
    """Price an order. Raises when the discount would go below cost."""
    lines, subtotal, cost = [], 0, 0
    for li in lines_in:
        p = db.get(Product, int(li["product_id"]))
        if not p or p.tenant_id != tenant_id or not p.active:
            raise_bad_request("Product not found")
        qty = max(1, int(li.get("qty") or 1))
        unit = price_paise(p.cost_paise, p.margin_bp)
        if unit <= 0:
            # "Price on request": nothing can be ordered until a price is set.
            raise_bad_request(f"{p.name} has no price yet, so it can't be ordered. Set a price under Products first.")
        lines.append({"product_id": p.id, "name": p.name, "qty": qty, "unit_paise": unit, "cost_paise": p.cost_paise})
        subtotal += unit * qty
        cost += p.cost_paise * qty
    if not lines:
        raise_bad_request("Add at least one product")
    discount = max(0, int(discount_paise or 0))
    if discount_bp:
        discount += subtotal * max(0, int(discount_bp)) // 10000
    # The staff-entered part, before any coupon: this is what needs approval above 10%.
    manual = min(discount, subtotal)
    coupon = None
    if coupon_code:
        coupon = _valid_coupon(db, tenant_id, coupon_code)
        discount += subtotal * coupon.value // 10000 if coupon.kind == "percent" else coupon.value
    discount = min(discount, subtotal)
    if subtotal - discount < cost:
        raise_bad_request(
            f"That discount takes the price below cost. The most you can give is ₹{(subtotal - cost) // 100}."
        )
    taxable = subtotal - discount
    gst = taxable * GST_BP // 10000
    return {
        "lines": lines,
        "subtotal_paise": subtotal,
        "cost_paise": cost,
        "discount_paise": discount,
        "discount_bp": (discount * 10000 // subtotal) if subtotal else 0,
        "manual_discount_bp": (manual * 10000 // subtotal) if subtotal else 0,
        "coupon_code": coupon.code if coupon else None,
        "gst_bp": GST_BP,
        "gst_paise": gst,
        "total_paise": taxable + gst,
        "margin_paise": taxable - cost,
    }


def order_row(db: Session, o: Order) -> dict:
    elder = db.get(Elder, o.elder_id)
    return {
        "id": o.id,
        "elder_id": o.elder_id,
        "elder_name": f"{elder.first_name} {elder.last_name}".strip() if elder else "",
        "status": o.status,
        "lines": o.lines or [],
        "subtotal_paise": o.subtotal_paise,
        "cost_paise": o.cost_paise,
        "discount_paise": o.discount_paise,
        "discount_bp": (o.discount_paise * 10000 // o.subtotal_paise) if o.subtotal_paise else 0,
        "discount_reason": o.discount_reason,
        "coupon_code": o.coupon_code,
        "gst_paise": o.gst_paise,
        "total_paise": o.total_paise,
        "margin_paise": o.subtotal_paise - o.discount_paise - o.cost_paise,
        "request_id": o.request_id,
        "job_id": o.job_id,
        "note": o.note,
        "quoted_at": o.quoted_at.isoformat() if o.quoted_at else None,
        "family_note": o.family_note or "",
        "paid_paise": o.paid_paise or 0,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _elder(db: Session, user: User, elder_id: int) -> Elder:
    e = db.get(Elder, elder_id)
    if not e:
        raise_not_found("Client not found")
    assert_tenant_access(user, e.tenant_id)
    assert_elder_in_team(db, user, e.id)
    return e


def create_order(db: Session, user: User, data: dict) -> dict:
    elder = _elder(db, user, int(data["elder_id"]))
    priced = price_order(
        db,
        elder.tenant_id,
        data.get("lines") or [],
        discount_paise=int(data.get("discount_paise") or 0),
        discount_bp=int(data.get("discount_bp") or 0),
        coupon_code=data.get("coupon_code") or None,
    )
    # Anyone but an admin needs approval when their own discount is above 10%, coupon or not.
    needs_approval = not is_admin(user) and priced["manual_discount_bp"] > MANAGER_DISCOUNT_LIMIT_BP
    o = Order(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        status="pending_approval" if needs_approval else "approved",
        lines=priced["lines"],
        subtotal_paise=priced["subtotal_paise"],
        cost_paise=priced["cost_paise"],
        discount_paise=priced["discount_paise"],
        discount_reason=(data.get("discount_reason") or "").strip()[:200],
        coupon_code=priced["coupon_code"],
        gst_bp=priced["gst_bp"],
        gst_paise=priced["gst_paise"],
        total_paise=priced["total_paise"],
        request_id=data.get("request_id"),
        note=(data.get("note") or "").strip(),
        created_by_user_id=user.id,
        approved_by_user_id=None if needs_approval else user.id,
    )
    db.add(o)
    db.flush()
    if priced["discount_paise"]:
        _audit(db, user, o, "order_discount", None, {
            "discount_paise": priced["discount_paise"],
            "manual_discount_bp": priced["manual_discount_bp"],
            "coupon_code": priced["coupon_code"],
            "reason": o.discount_reason,
            "status": o.status,
        })
    if priced["coupon_code"]:
        # Atomic: two orders racing for the last use can't both get it.
        res = db.execute(
            update(Coupon)
            .where(
                Coupon.tenant_id == elder.tenant_id,
                Coupon.code == priced["coupon_code"],
                or_(Coupon.max_uses.is_(None), Coupon.used_count < Coupon.max_uses),
            )
            .values(used_count=Coupon.used_count + 1)
            .execution_options(synchronize_session=False)
        )
        if res.rowcount != 1:
            db.rollback()
            raise_bad_request("This coupon has been used up")
    db.commit()
    db.refresh(o)
    if needs_approval:
        _email_approval_needed(db, user, o, elder)
    return order_row(db, o)


def _email_approval_needed(db: Session, user: User, o: Order, elder: Elder) -> None:
    """Admins hear straight away that a discount is waiting for them."""
    from app.livewell.email_notifications import email_staff, staff_path

    by = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
    pct = (o.discount_paise * 100 / o.subtotal_paise) if o.subtotal_paise else 0
    email_staff(
        db, elder, "approval",
        f"Discount to approve: order #{o.id} — {_elder_name(elder)}",
        f"{by} gave a {pct:.0f}% discount ({_rupees(o.discount_paise)} off {_rupees(o.subtotal_paise)}) "
        f"on order #{o.id} for {_elder_name(elder)}. Total now {_rupees(o.total_paise)} including GST."
        + (f"\nReason: {o.discount_reason}" if o.discount_reason else "")
        + "\nDiscounts above 10% need an admin. Open the client's Orders to approve or cancel it.",
        path=staff_path(elder, "orders"),
    )


def list_orders(db: Session, user: User, *, elder_id: int | None = None, status: str | None = None) -> list[dict]:
    tid = _tenant(user)
    q = db.query(Order).filter(Order.tenant_id == tid)
    if elder_id:
        _elder(db, user, elder_id)
        q = q.filter(Order.elder_id == elder_id)
    team = team_elder_ids(db, user)
    if team is not None:
        q = q.filter(Order.elder_id.in_(team or {-1}))
    if status:
        q = q.filter(Order.status == status)
    return [order_row(db, o) for o in q.order_by(Order.id.desc()).limit(300).all()]


# Allowed order moves. Waiting-for-approval orders can only be approved (admin) or cancelled;
# cancelled and completed are final.
ORDER_TRANSITIONS = {
    "pending_approval": {"approved", "cancelled"},
    "approved": {"quoted", "scheduled", "completed", "cancelled"},
    "quoted": {"family_accepted", "cancelled"},
    "family_accepted": {"scheduled", "cancelled"},
    "scheduled": {"completed", "cancelled", "approved"},
    "completed": set(),
    "cancelled": set(),
}
STATUS_WORDS = {
    "pending_approval": "waiting for approval",
    "approved": "approved",
    "quoted": "sent to the family",
    "family_accepted": "accepted by the family",
    "scheduled": "scheduled",
    "completed": "completed",
    "cancelled": "cancelled",
}


def _audit(db: Session, user: User, o: Order, action: str, old: dict | None, new: dict | None) -> None:
    from app.services.audit_service import AuditService

    AuditService.log(
        db, tenant_id=o.tenant_id, user_id=user.id, entity_type="order", entity_id=o.id,
        action=action, old_value=old, new_value=new,
    )


def _lock_order(db: Session, order_id: int) -> Order | None:
    """Fresh read of the order under a row lock (no-op lock on SQLite). Every status change
    goes through here so staff-cancel, family-pay and decline can't overwrite each other."""
    q = db.query(Order).filter(Order.id == order_id).populate_existing()
    bind = db.get_bind()
    if bind is not None and bind.dialect.name != "sqlite":
        q = q.with_for_update()
    return q.first()


def _open_install_jobs(db: Session, o: Order) -> list:
    """Open install jobs booked for this order (linked by job_id or the "order-N" request id)."""
    from sqlalchemy import or_

    from app.livewell.care_jobs import OPEN_STATUSES
    from app.models.care_job import CareJob

    cond = CareJob.request_id == f"order-{o.id}"
    if o.job_id:
        cond = or_(cond, CareJob.id == o.job_id)
    return (
        db.query(CareJob)
        .filter(CareJob.elder_id == o.elder_id, CareJob.kind == "install", CareJob.status.in_(OPEN_STATUSES), cond)
        .order_by(CareJob.id.desc())
        .all()
    )


def _give_back_coupon(db: Session, o: Order) -> None:
    """An unpaid coupon order that is cancelled / rejected / declined frees its use.
    Callers run this only on the one transition into "cancelled", so it happens once."""
    if not o.coupon_code or (o.paid_paise or 0) > 0:
        return
    db.execute(
        update(Coupon)
        .where(Coupon.tenant_id == o.tenant_id, Coupon.code == o.coupon_code, Coupon.used_count > 0)
        .values(used_count=Coupon.used_count - 1)
        .execution_options(synchronize_session=False)
    )


def set_order_status(
    db: Session, user: User, order_id: int, status: str, reason: str | None = None, *, force: bool = False
) -> dict:
    o = _lock_order(db, order_id)
    if not o:
        raise_not_found("Order not found")
    _elder(db, user, o.elder_id)
    if status not in ORDER_TRANSITIONS:
        raise_bad_request("Unknown status")
    if status == "quoted" and (o.paid_paise or 0) > 0:
        raise_bad_request("This order is already paid — it can't be sent as a new quote")
    if status not in ORDER_TRANSITIONS.get(o.status, set()):
        raise_bad_request(f"An order that is {STATUS_WORDS.get(o.status, o.status)} can't be marked {STATUS_WORDS[status]}")
    if status == "family_accepted":
        raise_bad_request("Only the family can accept a quote (Approve & pay in the family app)")
    if status == "approved" and o.status == "pending_approval":
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Only an admin can approve a discount above 10%")
        o.approved_by_user_id = user.id
    old = o.status
    if status == "approved" and old == "scheduled" and (o.paid_paise or 0) > 0:
        # A paid order taken off the calendar goes back to "paid, we'll book a time"
        # — the family app has words for that, not for "approved".
        status = "family_accepted"
    if old == "scheduled" and status in ("cancelled", "approved", "family_accepted") and not force:
        busy = [j for j in _open_install_jobs(db, o) if j.status in ("on_the_way", "checked_in")]
        if busy:
            where = "on the way" if busy[0].status == "on_the_way" else "on site"
            raise HTTPException(status_code=409, detail=f"The installer is {where} — call them first")
    o.status = status
    if status == "quoted":
        o.quoted_at = datetime.now(timezone.utc)
    if status == "cancelled":
        _give_back_coupon(db, o)
    if status == "cancelled" and (o.paid_paise or 0) > 0 and o.wallet_transaction_id:
        # Paid from the wallet: money goes back as a new ledger row, never edited backwards.
        from app.livewell.wallet_service import WalletService

        wallet = WalletService.get_or_create(db, _elder(db, user, o.elder_id))
        WalletService.record(
            db, wallet, kind="refund", amount_minor=o.paid_paise,
            idempotency_key=f"refund:order:{o.id}",
            reference_type="order", reference_id=str(o.id),
            note=f"Refunded to your KushAlaya wallet — order #{o.id} cancelled", user=user, commit=False,
        )
    reason = (reason or "").strip()[:200]
    if status == "cancelled" and reason:
        word = "Rejected" if old == "pending_approval" else "Cancelled"
        o.note = f"{o.note}\n{word}: {reason}".strip() if o.note else f"{word}: {reason}"
    if old == "scheduled" and status in ("cancelled", "approved", "family_accepted"):
        # The installation visit goes with the order; the family is told it's off.
        from app.livewell.care_jobs import _notify_family, _when

        elder = db.get(Elder, o.elder_id)
        for job in _open_install_jobs(db, o):
            job.status = "cancelled"
            if elder:
                _notify_family(db, elder, f"{job.title} cancelled", f"{job.title} on {_when(job.scheduled_at)} was cancelled.")
        o.job_id = None
    _audit(db, user, o, f"order_{status}", {"status": old}, {"status": status, **({"reason": reason} if reason else {})})
    db.commit()
    db.refresh(o)
    if status == "quoted":
        _notify_quote_sent(db, o)
    elif status in ("scheduled", "completed", "cancelled") and old in ("quoted", "family_accepted", "scheduled"):
        _notify_order_change(db, o, status)
    return order_row(db, o)


def _notify_order_change(db: Session, o: Order, status: str) -> None:
    """The family hears when an order they saw is booked, done or cancelled (with the date)."""
    from app.livewell.care_jobs import _when
    from app.livewell.family_notify import notify_family

    elder = db.get(Elder, o.elder_id)
    if not elder:
        return
    items = ", ".join(str(ln.get("name") or "") for ln in (o.lines or []) if ln.get("name"))[:200] or f"order #{o.id}"
    today = _when(datetime.now(timezone.utc)) + " IST"
    if status == "scheduled":
        title, body = "Your order is booked", f"{items}: booked on {today}. Your care team will confirm the visit time."
    elif status == "completed":
        title, body = "Your order is done", f"{items}: completed on {today}."
    else:
        refund = f" {_rupees(o.paid_paise)} has been returned to your KushAlaya wallet." if (o.paid_paise or 0) > 0 else ""
        title, body = "Order cancelled", f"{items}: cancelled on {today}.{refund}"
    try:
        notify_family(db, elder, title, body, event="order", path="/services")
    except Exception:  # a failed notice must not undo the change
        import logging

        logging.getLogger(__name__).exception("order_notify_failed order=%s", o.id)


# --- Installation booking (date + caregiver), reschedule ----------------------------


def schedule_install(db: Session, user: User, order_id: int, data: dict) -> dict:
    """Book (or move) the installation visit for an order.

    approved / family_accepted → a new install job, order becomes "scheduled".
    scheduled → the open install job is moved (date and/or caregiver).
    The job is made by care_jobs (same clash check, family notice and "order-N" link
    that closes the order when the caregiver files the install report)."""
    from app.livewell import care_jobs
    from app.models.care_job import CareJob

    o = _lock_order(db, order_id)
    if not o:
        raise_not_found("Order not found")
    _elder(db, user, o.elder_id)
    if data.get("scheduled_at") is None:
        raise_bad_request("Pick a date and time")
    if o.status not in ("approved", "family_accepted", "scheduled"):
        raise_bad_request(
            f"An order that is {STATUS_WORDS.get(o.status, o.status)} can't be scheduled"
            + (" — an admin has to approve the discount first" if o.status == "pending_approval" else "")
        )
    existing = _open_install_jobs(db, o) if o.status == "scheduled" else []
    moving = bool(existing)
    if moving:
        patch = {"scheduled_at": data["scheduled_at"], "force": bool(data.get("force"))}
        if "caregiver_id" in data:
            patch["caregiver_id"] = data["caregiver_id"]
        job = care_jobs.update_job(db, user, existing[0].id, patch)
    else:
        job = care_jobs.create_job(db, user, {
            "elder_id": o.elder_id,
            "kind": "install",
            "scheduled_at": data["scheduled_at"],
            "caregiver_id": data.get("caregiver_id"),
            "duration_minutes": data.get("duration_minutes"),
            "force": bool(data.get("force")),
            "title": "Product installation",
            "request_id": f"order-{o.id}",
            "tasks": ", ".join(f"{li.get('qty', 1)} × {li.get('name', '')}" for li in (o.lines or [])),
            "product_ids": [li.get("product_id") for li in (o.lines or []) if li.get("product_id")],
            "staff_note": (data.get("note") or "").strip(),
        })
    # care_jobs committed; take the order lock again before moving the order on.
    o = _lock_order(db, order_id)
    if o.status not in ("approved", "family_accepted", "scheduled"):
        # Cancelled while we were booking: don't leave a visit for a dead order.
        row = db.get(CareJob, job["id"])
        if row and row.status in care_jobs.OPEN_STATUSES:
            row.status = "cancelled"
        db.commit()
        raise_bad_request(f"This order was {STATUS_WORDS.get(o.status, o.status)} meanwhile — nothing was booked")
    if not moving and o.status == "scheduled" and o.job_id and o.job_id != job["id"]:
        # Someone else booked this order while we were booking: keep theirs, drop ours.
        other = db.get(CareJob, o.job_id)
        if other and other.status in care_jobs.OPEN_STATUSES:
            row = db.get(CareJob, job["id"])
            if row and row.status in care_jobs.OPEN_STATUSES:
                row.status = "cancelled"
            db.commit()
            raise HTTPException(status_code=409, detail="This order was booked by someone else meanwhile — refresh to see the visit")
    old = o.status
    o.status = "scheduled"
    o.job_id = job["id"]
    _audit(db, user, o, "order_rescheduled" if moving else "order_scheduled", {"status": old}, {
        "status": "scheduled", "job_id": job["id"], "scheduled_at": job.get("scheduled_at"),
        "caregiver_id": job.get("caregiver_id"),
    })
    db.commit()
    db.refresh(o)
    return {"order": order_row(db, o), "job": job}


# --- Quotes for the family (send → Approve & pay / Not now) --------------------------
# The family sees product names, quantities, prices before GST, GST and the total.
# Never our cost or margin. Every amount comes from the stored order, never from the client.

FAMILY_STATUS_WORDS = {
    "quoted": "Waiting for you",
    "family_accepted": "Paid — we'll book a time",
    "scheduled": "Booked",
    "completed": "Done",
    "cancelled": "Cancelled",
}


def _rupees(paise: int) -> str:
    from app.core.money import format_minor

    return format_minor(int(paise or 0))


def _elder_name(elder: Elder | None) -> str:
    return f"{elder.first_name} {elder.last_name}".strip() if elder else ""


def _notify_quote_sent(db: Session, o: Order) -> None:
    from app.livewell.family_notify import notify_family

    elder = db.get(Elder, o.elder_id)
    if not elder:
        return
    try:
        notify_family(
            db,
            elder,
            "A quote is waiting for you",
            f"Your care team sent a quote for {_elder_name(elder)}: {_rupees(o.total_paise)} including GST. "
            "Open Requests in the family app to approve and pay, or say not now.",
            event="request",
            path="/services",
        )
    except Exception:  # a failed notification must not undo the quote
        import logging

        logging.getLogger(__name__).exception("quote_notify_failed order=%s", o.id)


def family_quote_row(db: Session, o: Order) -> dict:
    lines = []
    product_ids = [int(ln.get("product_id") or 0) for ln in (o.lines or [])]
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids or [-1])).all()}
    for ln in o.lines or []:
        qty = int(ln.get("qty") or 1)
        unit = int(ln.get("unit_paise") or 0)
        p = products.get(int(ln.get("product_id") or 0))
        lines.append({
            "name": ln.get("name") or (p.name if p else ""),
            "qty": qty,
            "unit_paise": unit,
            "line_paise": unit * qty,
            "image_url": product_image_url(p) if p else None,
        })
    return {
        "id": o.id,
        "status": o.status,
        "status_label": FAMILY_STATUS_WORDS.get(o.status, o.status.replace("_", " ")),
        "needs_action": o.status == "quoted",
        "lines": lines,
        "subtotal_paise": o.subtotal_paise,
        "discount_paise": o.discount_paise,
        "gst_bp": o.gst_bp,
        "gst_paise": o.gst_paise,
        "total_paise": o.total_paise,
        "paid_paise": o.paid_paise or 0,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "quoted_at": o.quoted_at.isoformat() if o.quoted_at else None,
        "family_note": o.family_note or "",
        "invoice_available": False,
    }


def _family_order(db: Session, user: User, order_id: int) -> tuple[Order, Elder]:
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    o = _lock_order(db, order_id)
    if not o or o.elder_id != elder.id or o.quoted_at is None:
        raise_not_found("Quote not found")
    return o, elder


def list_family_quotes(db: Session, user: User) -> list[dict]:
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    rows = (
        db.query(Order)
        .filter(Order.elder_id == elder.id, Order.quoted_at.isnot(None))
        .order_by(Order.id.desc())
        .limit(50)
        .all()
    )
    # Waiting-for-you quotes first.
    rows.sort(key=lambda o: 0 if o.status == "quoted" else 1)
    return [family_quote_row(db, o) for o in rows]


def _family_audit(db: Session, user: User, o: Order, action: str, old: dict, new: dict) -> None:
    from app.services.audit_service import AuditService

    AuditService.log(
        db, tenant_id=o.tenant_id, user_id=user.id, entity_type="order", entity_id=o.id,
        action=action, old_value=old, new_value=new,
    )


def _already_paid(o: Order) -> bool:
    return (o.paid_paise or 0) > 0 and o.status != "cancelled"


def _pay_quote(db: Session, user: User, o: Order, elder: Elder) -> dict:
    """Pay a locked, quoted order from the wallet. The amount is the stored order total."""
    from app.core.config import settings
    from app.livewell.email_notifications import email_staff
    from app.livewell.wallet_service import WalletService, _lock_wallet

    if _already_paid(o):
        return {"paid": True, "quote": family_quote_row(db, o)}
    if o.status != "quoted":
        raise_bad_request("This quote is no longer open")
    total = int(o.total_paise or 0)
    # Check the balance on the freshly locked wallet row, not a cached one.
    wallet = _lock_wallet(db, WalletService.get_or_create(db, elder).id)
    if wallet.balance_minor < total:
        shortfall = total - wallet.balance_minor
        topup = max(shortfall, int(settings.WALLET_MIN_RECHARGE_MINOR))
        db.commit()  # release the locks; nothing was changed
        return {
            "paid": False,
            "balance_paise": wallet.balance_minor,
            "shortfall_paise": shortfall,
            "topup_paise": topup,
            "message": f"Top up {_rupees(shortfall)} to pay",
            "quote": family_quote_row(db, o),
        }
    entry = None
    if total > 0:
        entry = WalletService.record(
            db, wallet, kind="debit", amount_minor=total,
            idempotency_key=f"debit:order:{o.id}",
            reference_type="order", reference_id=str(o.id),
            note=(f"Quote #{o.id} — " + ", ".join(f"{ln.get('qty', 1)} × {ln.get('name', '')}" for ln in (o.lines or [])))[:300],
            user=user, commit=False,
        )
    o.status = "family_accepted"
    o.paid_paise = total
    o.paid_at = datetime.now(timezone.utc)
    o.wallet_transaction_id = entry.public_id if entry else None
    _family_audit(db, user, o, "order_family_accepted", {"status": "quoted"},
                  {"status": "family_accepted", "paid_paise": total,
                   "wallet_transaction_id": o.wallet_transaction_id})
    db.commit()
    db.refresh(o)
    email_staff(
        db, elder, "request",
        f"Quote #{o.id} accepted and paid — {_elder_name(elder)}",
        f"The family approved quote #{o.id} and paid {_rupees(total)} from the wallet. Book a time from the client's Orders.",
        path=f"/kushalaya/customers/{elder.id}?tab=orders",
    )
    return {"paid": True, "quote": family_quote_row(db, o)}


def family_accept_quote(db: Session, user: User, order_id: int) -> dict:
    """Approve & pay. Pays from the wallet when it covers the total; otherwise says how much to top up."""
    o, elder = _family_order(db, user, order_id)
    return _pay_quote(db, user, o, elder)


def pay_quote_after_topup(db: Session, entry) -> None:
    """A top-up started from "Approve & pay" has settled: pay that quote on the server.
    Idempotent (one debit key per order); the family app's second call is the fallback."""
    import logging

    from app.models.family_wallet import FamilyWallet

    if entry is None or entry.status != "success" or entry.reference_type != "quote_topup":
        return
    try:
        wallet = db.get(FamilyWallet, entry.wallet_id)
        o = _lock_order(db, int(entry.reference_id or 0))
        user = db.get(User, entry.created_by_user_id) if entry.created_by_user_id else None
        if not wallet or not o or not user or o.elder_id != wallet.elder_id or o.status != "quoted":
            db.rollback()
            return
        _pay_quote(db, user, o, db.get(Elder, o.elder_id))
    except Exception:
        db.rollback()
        logging.getLogger(__name__).exception("quote_autopay_failed entry=%s", entry.public_id)


def family_decline_quote(db: Session, user: User, order_id: int, note: str | None) -> dict:
    from app.livewell.email_notifications import email_staff

    o, elder = _family_order(db, user, order_id)
    if o.status == "cancelled":
        return family_quote_row(db, o)
    if o.status != "quoted":
        raise_bad_request("This quote is no longer open")
    o.status = "cancelled"
    _give_back_coupon(db, o)
    o.family_note = (note or "").strip()[:300]
    _family_audit(db, user, o, "order_family_declined", {"status": "quoted"},
                  {"status": "cancelled", "family_note": o.family_note})
    db.commit()
    db.refresh(o)
    email_staff(
        db, elder, "request",
        f"Quote #{o.id} declined — {_elder_name(elder)}",
        f"The family said not now to quote #{o.id} ({_rupees(o.total_paise)})."
        + (f" Their note: {o.family_note}" if o.family_note else ""),
        path=f"/kushalaya/customers/{elder.id}?tab=orders",
    )
    return family_quote_row(db, o)
