"""Product images for Safe Home catalog — global store (not tenant-owned)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import catalog_product_image_key, get_storage
from app.livewell.catalog_service import HomeSafetyCatalogService, normalize_catalog
from app.livewell.global_catalog_store import (
    ensure_global_catalog_dict,
    save_raw_global_catalog,
)
from app.models.document import Document
from app.models.user import User

HOME_SAFETY_CATALOG_IMAGE = "HOME_SAFETY_CATALOG_IMAGE"
CATALOG_ENTITY_TYPE = "catalog_product"


def _product_label(product_id: str) -> str:
    return f"catalog:{product_id}"


class HomeSafetyCatalogImageService:

    @staticmethod
    def _find_product(catalog: dict, product_id: str) -> dict | None:
        for product in catalog.get("products") or []:
            if product.get("id") == product_id:
                return product
        return None

    @staticmethod
    def _update_product_images(
        catalog: dict,
        product_id: str,
        image_ids: list[int],
    ) -> dict:
        updated_products = []
        for item in catalog["products"]:
            if item["id"] == product_id:
                updated_products.append({**item, "image_ids": image_ids})
            else:
                updated_products.append(item)
        return {**catalog, "products": updated_products}

    @staticmethod
    def upload_for_product(
        db: Session,
        user: User,
        *,
        product_id: str,
        file_name: str,
        content: bytes,
        content_type: str,
        supplier_id: str | None = None,
    ) -> dict:
        HomeSafetyCatalogService._tenant(db, user)
        HomeSafetyCatalogService._assert_can_edit(user)
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        product = HomeSafetyCatalogImageService._find_product(catalog, product_id)
        if not product:
            raise_not_found("Product not found in catalog")

        lowered = (file_name or "").lower()
        if content_type not in ("image/jpeg", "image/png", "image/webp") and not lowered.endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            raise_bad_request("File type not allowed. Use JPEG or PNG.")

        sid = (supplier_id or "").strip() or None
        storage = get_storage()
        key = catalog_product_image_key(product_id, file_name)
        storage_key, storage_url = storage.put(
            key,
            content,
            content_type or "application/octet-stream",
        )

        # tenant_id is audit-only (uploader); tenant purge must not delete these.
        ocr: dict = {"product_id": product_id, "global_catalog": True}
        if sid:
            ocr["supplier_id"] = sid
            ocr["photo_kind"] = "vendor"
        else:
            ocr["photo_kind"] = "generic"

        doc = Document(
            tenant_id=user.tenant_id,
            entity_type=CATALOG_ENTITY_TYPE,
            entity_id=0,
            document_type=HOME_SAFETY_CATALOG_IMAGE,
            document_name=_product_label(product_id),
            file_name=file_name,
            storage_key=storage_key,
            storage_url=storage_url,
            mime_type=content_type,
            file_size_bytes=len(content),
            verification_status="APPROVED",
            uploaded_by_user_id=user.id,
            uploaded_at=datetime.utcnow(),
            ocr_extracted_json=ocr,
        )
        db.add(doc)
        db.flush()

        image_ids = list(product.get("image_ids") or [])
        image_ids.append(doc.id)

        catalog = HomeSafetyCatalogImageService._update_product_images(
            catalog, product_id, image_ids
        )
        save_raw_global_catalog(db, catalog)
        return HomeSafetyCatalogService._enriched(db, catalog)

    @staticmethod
    def remove_one(
        db: Session,
        user: User,
        *,
        product_id: str,
        document_id: int,
    ) -> dict:
        HomeSafetyCatalogService._tenant(db, user)
        HomeSafetyCatalogService._assert_can_edit(user)
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        product = HomeSafetyCatalogImageService._find_product(catalog, product_id)
        if not product:
            raise_not_found("Product not found in catalog")

        image_ids = list(product.get("image_ids") or [])
        if document_id not in image_ids:
            raise_not_found("Image not found on this product")

        HomeSafetyCatalogImageService._delete_document(db, document_id)
        image_ids = [i for i in image_ids if i != document_id]

        catalog = HomeSafetyCatalogImageService._update_product_images(
            catalog, product_id, image_ids
        )
        save_raw_global_catalog(db, catalog)
        return HomeSafetyCatalogService._enriched(db, catalog)

    @staticmethod
    def remove_all_for_product(db: Session, user: User, *, product_id: str) -> dict:
        HomeSafetyCatalogService._tenant(db, user)
        HomeSafetyCatalogService._assert_can_edit(user)
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        product = HomeSafetyCatalogImageService._find_product(catalog, product_id)
        if not product:
            raise_not_found("Product not found in catalog")

        for image_id in list(product.get("image_ids") or []):
            HomeSafetyCatalogImageService._delete_document(db, int(image_id))

        catalog = HomeSafetyCatalogImageService._update_product_images(
            catalog, product_id, []
        )
        save_raw_global_catalog(db, catalog)
        return HomeSafetyCatalogService._enriched(db, catalog)

    @staticmethod
    def relink_orphaned_images(db: Session, catalog: dict) -> tuple[dict, int]:
        """Re-attach catalog image Documents when product.image_ids was cleared.

        Matches by ocr.product_id, document_name ``catalog:{product_id}``, or
        storage_key path ``…/products/{product_id}/…``.
        """
        docs = (
            db.query(Document)
            .filter(Document.document_type == HOME_SAFETY_CATALOG_IMAGE)
            .order_by(Document.id.asc())
            .all()
        )
        by_product: dict[str, list[int]] = {}
        for doc in docs:
            pid: str | None = None
            ocr = doc.ocr_extracted_json if isinstance(doc.ocr_extracted_json, dict) else {}
            raw_pid = ocr.get("product_id")
            if raw_pid not in (None, ""):
                pid = str(raw_pid).strip()
            if not pid and doc.document_name and str(doc.document_name).startswith("catalog:"):
                pid = str(doc.document_name).split(":", 1)[1].strip() or None
            if not pid and doc.storage_key:
                parts = str(doc.storage_key).replace("\\", "/").split("/")
                try:
                    idx = parts.index("products")
                    if idx + 1 < len(parts):
                        pid = parts[idx + 1].strip() or None
                except ValueError:
                    pass
            if not pid:
                continue
            by_product.setdefault(pid, []).append(int(doc.id))

        changed = 0
        products: list[dict] = []
        for product in catalog.get("products") or []:
            existing = [int(i) for i in (product.get("image_ids") or [])]
            if existing:
                products.append(product)
                continue
            orphans = by_product.get(str(product.get("id") or ""), [])
            if not orphans:
                products.append(product)
                continue
            # Deduplicate while preserving oldest→newest order
            seen: set[int] = set()
            linked: list[int] = []
            for image_id in orphans:
                if image_id not in seen:
                    linked.append(image_id)
                    seen.add(image_id)
            products.append({**product, "image_ids": linked})
            changed += 1
        return {**catalog, "products": products}, changed

    @staticmethod
    def _delete_document(db: Session, document_id: int) -> None:
        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.document_type == HOME_SAFETY_CATALOG_IMAGE,
            )
            .first()
        )
        if not doc:
            return
        storage = get_storage()
        try:
            storage.delete(doc.storage_key)
        except OSError:
            pass
        db.delete(doc)

    @staticmethod
    def _allowed_image_ids(catalog: dict) -> set[int]:
        allowed: set[int] = set()
        for product in catalog.get("products") or []:
            for image_id in product.get("image_ids") or []:
                allowed.add(int(image_id))
        return allowed

    @staticmethod
    def read_public(
        db: Session,
        *,
        document_id: int,
        tenant_id: int | None = None,
    ) -> tuple[bytes, str, str]:
        del tenant_id  # legacy query param ignored — images are global
        stored = HomeSafetyCatalogService.get_catalog(db, None)
        allowed_ids = HomeSafetyCatalogImageService._allowed_image_ids(stored)
        if document_id not in allowed_ids:
            raise_not_found("Image not found")

        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.document_type == HOME_SAFETY_CATALOG_IMAGE,
            )
            .first()
        )
        if not doc:
            raise_not_found("Image not found")

        storage = get_storage()
        content, mime = storage.read(doc.storage_key)
        return (
            content,
            mime or doc.mime_type or "application/octet-stream",
            doc.file_name,
        )
