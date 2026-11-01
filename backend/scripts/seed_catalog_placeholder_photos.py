"""Seed missing catalog photos with labeled product cards.

Use this when the local DB has SKUs but no HOME_SAFETY_CATALOG_IMAGE rows.

    cd backend
    python scripts/seed_catalog_placeholder_photos.py --confirm
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
from app.livewell.catalog_service import normalize_catalog
from app.livewell.catalog_types import SERVICE_PREFIXES
from app.livewell.global_catalog_store import ensure_global_catalog_dict
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_constants import LEGACY_TENANT_NAMES, TENANT_ADMIN_EMAIL, TENANT_NAME

SERVICE_BG = (13, 110, 110)
PRODUCT_BG = (26, 58, 60)
CARD_SIZE = (960, 640)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:4] or [text]


def render_card(code: str, name: str, category: str, kind: str) -> bytes:
    bg = SERVICE_BG if kind == "service" else PRODUCT_BG
    img = Image.new("RGB", CARD_SIZE, bg)
    draw = ImageDraw.Draw(img)
    pad = 56
    code_font = _font(36)
    kind_font = _font(22)
    name_font = _font(42)
    cat_font = _font(24)
    brand_font = _font(20)

    draw.text((pad, pad), "LiveWell360", font=brand_font, fill=(210, 232, 232))
    draw.text((pad, 110), (code or "SKU").upper(), font=code_font, fill=(255, 255, 255))
    draw.text(
        (pad, 162),
        "SERVICE" if kind == "service" else "PRODUCT",
        font=kind_font,
        fill=(176, 216, 216),
    )

    lines = _wrap(draw, name or "Catalog item", name_font, CARD_SIZE[0] - pad * 2)
    y = 230
    for line in lines:
        draw.text((pad, y), line, font=name_font, fill=(255, 255, 255))
        y += 52

    draw.text((pad, CARD_SIZE[1] - pad - 28), category or "", font=cat_font, fill=(196, 224, 224))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _resolve_dest_tenant(db, *, tenant_id: int | None) -> Tenant:
    if tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise SystemExit(f"Tenant id={tenant_id} not found")
        return tenant
    for name in (TENANT_NAME, *LEGACY_TENANT_NAMES):
        tenant = db.query(Tenant).filter(Tenant.name == name).first()
        if tenant:
            return tenant
    tenant = (
        db.query(Tenant).filter(Tenant.vertical == "LIVEWELL360").order_by(Tenant.id).first()
    )
    if tenant:
        return tenant
    raise SystemExit("No LiveWell tenant found")


def _resolve_user(db, tenant: Tenant) -> User:
    user = db.query(User).filter(User.email == TENANT_ADMIN_EMAIL).first()
    if user and (user.role == "SYSTEM_ADMIN" or user.tenant_id == tenant.id):
        return user
    user = (
        db.query(User)
        .filter(
            User.tenant_id == tenant.id,
            User.role.in_(("TENANT_ADMIN", "CARE_MANAGER", "SYSTEM_ADMIN")),
        )
        .order_by(User.id)
        .first()
    )
    if user:
        return user
    raise SystemExit("No staff user found")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed missing catalog photos")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--tenant-id", type=int)
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Pass --confirm")

    db = SessionLocal()
    try:
        tenant = _resolve_dest_tenant(db, tenant_id=args.tenant_id)
        user = _resolve_user(db, tenant)

        class _CatalogActor:
            def __init__(self, src: User, tid: int):
                self.id = src.id
                self.email = src.email
                self.role = "TENANT_ADMIN"
                self.tenant_id = tid

        actor = _CatalogActor(user, int(tenant.id))
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        ok = 0
        skipped = 0
        for product in catalog.get("products") or []:
            pid = str(product.get("id") or "")
            if not pid:
                continue
            if product.get("image_ids"):
                skipped += 1
                continue
            code = str(product.get("product_code") or "")
            prefix = str(product.get("category_prefix") or "").upper()
            kind = "service" if prefix in SERVICE_PREFIXES else "product"
            content = render_card(
                code,
                str(product.get("name") or pid),
                str(product.get("category") or prefix),
                kind,
            )
            HomeSafetyCatalogImageService.upload_for_product(
                db,
                actor,
                product_id=pid,
                file_name=f"{code or pid}.jpg",
                content=content,
                content_type="image/jpeg",
            )
            ok += 1
            print(f"  photo {code or pid}", flush=True)
        print(f"Done. seeded={ok} skipped={skipped}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
