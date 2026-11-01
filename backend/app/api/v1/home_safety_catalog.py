from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
from app.livewell.catalog_service import HomeSafetyCatalogService
from app.models.user import User
from app.schemas.home_safety_catalog import SafetyCatalog

router = APIRouter(prefix="/home-safety/catalog", tags=["Safe Home — Catalog"])


@router.get("/public", response_model=SafetyCatalog)
def public_home_safety_catalog(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Read-only global catalog for assessor showcase (no auth).

    ``tenant_id`` is accepted for backward compatibility and ignored.
    """
    return HomeSafetyCatalogService.get_catalog(db, None, tenant_id=tenant_id)


@router.get("", response_model=SafetyCatalog)
def get_home_safety_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyCatalogService.get_catalog(db, current_user)


@router.put("", response_model=SafetyCatalog)
def save_home_safety_catalog(
    data: SafetyCatalog,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyCatalogService.save_catalog(db, current_user, data.model_dump())


@router.post("/products/{product_id}/image", response_model=SafetyCatalog)
async def upload_catalog_product_image(
    product_id: str,
    file: UploadFile = File(...),
    supplier_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    content = await file.read()
    return HomeSafetyCatalogImageService.upload_for_product(
        db,
        current_user,
        product_id=product_id,
        file_name=file.filename or "product.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        supplier_id=supplier_id,
    )


@router.delete("/products/{product_id}/images/{document_id}", response_model=SafetyCatalog)
def delete_catalog_product_one_image(
    product_id: str,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyCatalogImageService.remove_one(
        db, current_user, product_id=product_id, document_id=document_id
    )


@router.delete("/products/{product_id}/image", response_model=SafetyCatalog)
def delete_catalog_product_image(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyCatalogImageService.remove_all_for_product(
        db, current_user, product_id=product_id
    )


@router.get("/public/images/{document_id}")
def public_catalog_product_image(
    document_id: int,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Serve a global catalog product image. ``tenant_id`` is ignored if present."""
    content, mime, file_name = HomeSafetyCatalogImageService.read_public(
        db, document_id=document_id, tenant_id=tenant_id
    )
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )
