"""Products, coupons and orders — see app/livewell/commerce.py for the pricing rules."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_roles
from app.livewell import commerce
from app.models.user import User

router = APIRouter(tags=["Products & orders"])


class ProductIn(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    cost_paise: int | None = None
    margin_bp: int | None = None
    active: bool | None = None
    fixes: list[str] | None = None


class CouponIn(BaseModel):
    code: str | None = None
    kind: str | None = None
    value: int | None = None
    expires_at: datetime | None = None
    max_uses: int | None = None
    active: bool | None = None
    note: str | None = None


class OrderLine(BaseModel):
    product_id: int
    qty: int = Field(default=1, ge=1, le=99)


class OrderIn(BaseModel):
    elder_id: int
    lines: list[OrderLine]
    discount_paise: int = 0
    discount_bp: int = 0
    discount_reason: str | None = None
    coupon_code: str | None = None
    request_id: str | None = None
    note: str | None = None


class OrderQuote(BaseModel):
    lines: list[OrderLine]
    discount_paise: int = 0
    discount_bp: int = 0
    coupon_code: str | None = None


class StatusIn(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=200)
    force: bool = False


class InstallIn(BaseModel):
    scheduled_at: datetime
    caregiver_id: int | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=600)
    note: str | None = Field(default=None, max_length=500)
    force: bool = False


@router.get("/products")
def list_products(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    return commerce.for_viewer(user, commerce.list_products(db, user, include_inactive=include_inactive))


@router.post("/products", status_code=201)
def create_product(data: ProductIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return commerce.save_product(db, user, None, data.model_dump(exclude_unset=True))


@router.put("/products/{product_id}")
def update_product(
    product_id: int, data: ProductIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return commerce.save_product(db, user, product_id, data.model_dump(exclude_unset=True))


@router.post("/products/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    content = await file.read()
    return commerce.set_product_image(db, user, product_id, content, file.content_type or "", file.filename or "photo")


@router.delete("/products/{product_id}/image")
def remove_product_image(product_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return commerce.set_product_image(db, user, product_id, None, "", "")


@router.get("/product-images/{product_id}")
def product_image(product_id: int, db: Session = Depends(get_db)):
    """Public: product photos are catalogue pictures, shown in <img> tags without a token."""
    content, mime = commerce.product_image_bytes(db, product_id)
    return Response(content=content, media_type=mime, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/coupons")
def list_coupons(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return commerce.list_coupons(db, user)


@router.post("/coupons", status_code=201)
def create_coupon(data: CouponIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return commerce.save_coupon(db, user, None, data.model_dump(exclude_unset=True))


@router.put("/coupons/{coupon_id}")
def update_coupon(
    coupon_id: int, data: CouponIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return commerce.save_coupon(db, user, coupon_id, data.model_dump(exclude_unset=True))


@router.post("/orders/quote")
def quote_order(data: OrderQuote, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    """Price a basket without saving it (for the order form)."""
    return commerce.for_viewer(user, commerce.price_order(
        db,
        commerce._tenant(user),
        [li.model_dump() for li in data.lines],
        discount_paise=data.discount_paise,
        discount_bp=data.discount_bp,
        coupon_code=data.coupon_code,
    ))


@router.get("/orders")
def list_orders(
    elder_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    return commerce.for_viewer(user, commerce.list_orders(db, user, elder_id=elder_id, status=status))


@router.post("/orders", status_code=201)
def create_order(data: OrderIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    payload = data.model_dump()
    payload["lines"] = [li.model_dump() for li in data.lines]
    return commerce.for_viewer(user, commerce.create_order(db, user, payload))


@router.post("/orders/{order_id}/status")
def order_status(
    order_id: int, data: StatusIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return commerce.for_viewer(user, commerce.set_order_status(db, user, order_id, data.status, data.reason, force=data.force))


@router.post("/orders/{order_id}/install")
def order_install(
    order_id: int, data: InstallIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    """Book or move the installation: date, time and caregiver. 409 "Book anyway?" on a clash."""
    return commerce.for_viewer(user, commerce.schedule_install(db, user, order_id, data.model_dump(exclude_unset=True)))


@router.get("/suggestions")
def client_suggestions(
    elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))
):
    """Products suggested by the client's latest assessment, with room photos for before/after."""
    from app.livewell.suggestions import suggestions_for_elder

    elder = commerce._elder(db, user, elder_id)
    return suggestions_for_elder(db, elder.tenant_id, elder.id)


@router.get("/products/fixes")
def product_fixes(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    """Assessment questions, and which of them each product fixes (saved list or keyword default)."""
    from app.livewell.suggestions import _questions, fixes_for
    from app.models.commerce import Product

    tid = commerce._tenant(user)
    commerce.ensure_default_products(db, tid)
    questions = _questions(db, tid)
    products = db.query(Product).filter(Product.tenant_id == tid).all()
    return {
        "questions": [{"id": k, "label": v} for k, v in questions.items()],
        "fixes": {str(p.id): {"ids": fixes_for(p, questions), "custom": bool(p.fixes)} for p in products},
    }
