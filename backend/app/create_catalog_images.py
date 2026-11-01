"""Create or migrate SafeHome catalog product photos.

Uploads images into the current tenant as HOME_SAFETY_CATALOG_IMAGE documents and
rewrites catalog ``image_ids`` (new IDs — does not preserve foreign DB document IDs).

Modes
-----
1) From a folder of files keyed by ProductID::

    images/
      SH-GRAB-BAR.jpg
      SH-GRAB-BAR_2.png
      SH-NIGHTLIGHT/
        a.jpg
        b.jpg

2) From another database (e.g. ElderCare) + its upload directory::

    --from-db postgresql://... --from-upload-dir /var/lib/eldercareops/uploads

Usage (backend venv)::

    cd /opt/safehomeops/app/backend && source .venv/bin/activate

    python -m app.create_catalog_images --from-dir ./catalog-photos --confirm

    python -m app.create_catalog_images \\
      --from-db "$ELDER_DATABASE_URL" \\
      --from-upload-dir /var/lib/eldercareops/uploads \\
      --from-tenant-name "Sunrise Elder Care" \\
      --confirm

    python -m app.create_catalog_images --from-dir ./photos --dry-run
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal
from app.livewell.catalog_image_service import (
    HOME_SAFETY_CATALOG_IMAGE,
    HomeSafetyCatalogImageService,
)
from app.livewell.catalog_service import CATALOG_KEY, normalize_catalog
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_constants import TENANT_ADMIN_EMAIL, TENANT_NAME, LEGACY_TENANT_NAMES

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime in ("image/jpeg", "image/png"):
        return mime
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if path.suffix.lower() == ".png":
        return "image/png"
    return "application/octet-stream"


def _resolve_source_tenant(
    db: Session,
    *,
    tenant_id: int | None,
    tenant_name: str | None,
) -> Tenant:
    if tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise SystemExit(f"Source tenant id={tenant_id} not found")
        return tenant
    if tenant_name:
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not tenant:
            raise SystemExit(f'Source tenant name="{tenant_name}" not found')
        return tenant
    # Prefer a tenant that already has catalog products with photo ids
    for tenant in db.query(Tenant).order_by(Tenant.id).all():
        raw = (tenant.workflow_config or {}).get(CATALOG_KEY)
        if not isinstance(raw, dict):
            continue
        catalog = normalize_catalog(raw)
        if any(p.get("image_ids") for p in catalog.get("products") or []):
            print(
                f"Using source tenant {tenant.name!r} (id={tenant.id}) "
                "(first with catalog photos; pass --from-tenant-id to pin)"
            )
            return tenant
    raise SystemExit(
        "No source tenant with catalog photos found — pass --from-tenant-id or --from-tenant-name"
    )


def _resolve_dest_tenant(
    db: Session,
    *,
    tenant_id: int | None,
    tenant_name: str | None,
) -> Tenant:
    if tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise SystemExit(f"Tenant id={tenant_id} not found")
        return tenant
    names: list[str] = []
    if tenant_name:
        names.append(tenant_name)
    names.extend([TENANT_NAME, *LEGACY_TENANT_NAMES])
    for name in names:
        tenant = db.query(Tenant).filter(Tenant.name == name).first()
        if tenant:
            return tenant
    tenant = (
        db.query(Tenant)
        .filter(Tenant.vertical == "LIVEWELL360")
        .order_by(Tenant.id)
        .first()
    )
    if tenant:
        return tenant
    raise SystemExit("No SafeHome tenant found — pass --tenant-id or --tenant-name")


def _resolve_user(db: Session, tenant: Tenant, email: str | None) -> User:
    preferred = email or TENANT_ADMIN_EMAIL
    user = db.query(User).filter(User.email == preferred).first()
    if user:
        if user.role == "SYSTEM_ADMIN":
            return user
        if user.tenant_id == tenant.id:
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
    if not user:
        raise SystemExit(
            f"No staff user for tenant {tenant.id}. Seed first or pass --user-email."
        )
    return user


def _catalog_for(tenant: Tenant, db: Session | None = None) -> dict:
    from app.livewell.global_catalog_store import ensure_global_catalog_dict

    if db is not None:
        return normalize_catalog(ensure_global_catalog_dict(db))
    stored = (tenant.workflow_config or {}).get(CATALOG_KEY)
    if not isinstance(stored, dict):
        raise SystemExit(
            "No global catalog yet — run seed / Master Data seed, or save catalog first."
        )
    return normalize_catalog(stored)


def _product_ids(catalog: dict) -> set[str]:
    return {str(p["id"]) for p in catalog.get("products") or [] if p.get("id")}


def discover_from_dir(root: Path, known_product_ids: set[str]) -> dict[str, list[Path]]:
    """Map ProductID -> image files under root."""
    mapping: dict[str, list[Path]] = {pid: [] for pid in known_product_ids}

    # Subdirectories named exactly as ProductID
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name in known_product_ids:
            for f in sorted(child.rglob("*")):
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                    mapping[child.name].append(f)

    # Flat files: PRODUCT_ID.ext or PRODUCT_ID_*.ext / PRODUCT_ID-*.ext
    for f in sorted(root.iterdir()):
        if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
            continue
        stem = f.stem
        if stem in known_product_ids:
            mapping[stem].append(f)
            continue
        matched = None
        for pid in known_product_ids:
            if stem.startswith(pid + "_") or stem.startswith(pid + "-"):
                matched = pid
                break
        if matched:
            mapping[matched].append(f)

    return {pid: paths for pid, paths in mapping.items() if paths}


def _read_source_file(upload_root: Path, storage_key: str) -> tuple[bytes, str]:
    path = upload_root / storage_key
    if not path.is_file():
        raise FileNotFoundError(f"Missing source file: {path}")
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(suffix, "application/octet-stream")
    return path.read_bytes(), mime


def discover_from_db(
    source_db: Session,
    *,
    source_tenant: Tenant,
    upload_root: Path,
    known_product_ids: set[str],
) -> dict[str, list[tuple[str, bytes, str]]]:
    """Map ProductID -> list of (file_name, content, mime) from source DB."""
    raw = (source_tenant.workflow_config or {}).get(CATALOG_KEY)
    if not isinstance(raw, dict):
        raise SystemExit(f"Source tenant {source_tenant.id} has no catalog")
    source_catalog = normalize_catalog(raw)
    out: dict[str, list[tuple[str, bytes, str]]] = {}

    for product in source_catalog.get("products") or []:
        pid = str(product.get("id") or "")
        if not pid or pid not in known_product_ids:
            continue
        image_ids = [int(i) for i in (product.get("image_ids") or [])]
        if not image_ids:
            continue
        docs = (
            source_db.query(Document)
            .filter(
                Document.tenant_id == source_tenant.id,
                Document.document_type == HOME_SAFETY_CATALOG_IMAGE,
                Document.id.in_(image_ids),
            )
            .all()
        )
        by_id = {d.id: d for d in docs}
        items: list[tuple[str, bytes, str]] = []
        for image_id in image_ids:
            doc = by_id.get(image_id)
            if not doc:
                print(f"  warn: product {pid} missing document id={image_id}", file=sys.stderr)
                continue
            try:
                content, mime = _read_source_file(upload_root, doc.storage_key)
            except FileNotFoundError as exc:
                print(f"  warn: {exc}", file=sys.stderr)
                continue
            if mime not in ("image/jpeg", "image/png"):
                mime = _guess_mime(Path(doc.file_name))
            items.append((doc.file_name or f"{pid}.jpg", content, mime))
        if items:
            out[pid] = items
    return out


def apply_uploads(
    db: Session,
    user: User,
    tenant: Tenant,
    payloads: dict[str, list[tuple[str, bytes, str]]],
    *,
    replace: bool,
    dry_run: bool,
    limit_products: int | None,
) -> dict:
    catalog = _catalog_for(tenant, db)
    product_ids = list(payloads.keys())
    if limit_products is not None:
        product_ids = product_ids[:limit_products]

    summary = {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "products_touched": 0,
        "images_uploaded": 0,
        "skipped_empty": 0,
        "errors": [],
        "dry_run": dry_run,
        "by_product": {},
    }

    for pid in product_ids:
        files = payloads[pid]
        if not files:
            summary["skipped_empty"] += 1
            continue
        summary["by_product"][pid] = {"files": len(files), "uploaded": 0}
        if dry_run:
            summary["products_touched"] += 1
            summary["images_uploaded"] += len(files)
            summary["by_product"][pid]["uploaded"] = len(files)
            continue
        try:
            if replace:
                HomeSafetyCatalogImageService.remove_all_for_product(
                    db, user, product_id=pid
                )
                db.refresh(tenant)
            for file_name, content, mime in files:
                HomeSafetyCatalogImageService.upload_for_product(
                    db,
                    user,
                    product_id=pid,
                    file_name=file_name,
                    content=content,
                    content_type=mime,
                )
                summary["by_product"][pid]["uploaded"] += 1
                summary["images_uploaded"] += 1
            summary["products_touched"] += 1
            db.refresh(tenant)
        except Exception as exc:
            summary["errors"].append(f"{pid}: {exc}")
            print(f"  error {pid}: {exc}", file=sys.stderr)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload or migrate SafeHome catalog product photos by ProductID",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--from-dir",
        type=Path,
        help="Directory of images (flat files and/or ProductID subfolders)",
    )
    src.add_argument(
        "--from-db",
        help="Source DATABASE_URL (e.g. ElderCare Postgres) to copy catalog images from",
    )
    parser.add_argument(
        "--from-upload-dir",
        type=Path,
        help="Source UPLOAD_DIR root (required with --from-db)",
    )
    parser.add_argument("--from-tenant-id", type=int, help="Source tenant id")
    parser.add_argument("--from-tenant-name", help="Source tenant name")
    parser.add_argument("--tenant-id", type=int, help="Destination SafeHome tenant id")
    parser.add_argument("--tenant-name", help="Destination tenant name")
    parser.add_argument(
        "--user-email",
        help=f"Staff user that performs uploads (default {TENANT_ADMIN_EMAIL})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Clear existing product images before uploading",
    )
    parser.add_argument(
        "--product-id",
        action="append",
        default=[],
        help="Only process this ProductID (repeatable)",
    )
    parser.add_argument("--limit", type=int, help="Max products to process")
    parser.add_argument("--dry-run", action="store_true", help="List work without writing")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required for non-dry-run writes",
    )
    args = parser.parse_args()

    if args.from_db and not args.from_upload_dir:
        parser.error("--from-upload-dir is required with --from-db")
    if not args.dry_run and not args.confirm:
        parser.error("Pass --confirm to write, or --dry-run to preview")

    db = SessionLocal()
    try:
        tenant = _resolve_dest_tenant(db, tenant_id=args.tenant_id, tenant_name=args.tenant_name)
        user = _resolve_user(db, tenant, args.user_email)

        catalog = _catalog_for(tenant, db)
        known = _product_ids(catalog)
        if args.product_id:
            known = known & set(args.product_id)
            missing = set(args.product_id) - known
            if missing:
                print(f"warn: product ids not in catalog: {sorted(missing)}", file=sys.stderr)

        payloads: dict[str, list[tuple[str, bytes, str]]] = {}

        if args.from_dir:
            root = args.from_dir.expanduser().resolve()
            if not root.is_dir():
                raise SystemExit(f"Not a directory: {root}")
            discovered = discover_from_dir(root, known)
            for pid, paths in discovered.items():
                payloads[pid] = [
                    (p.name, p.read_bytes(), _guess_mime(p)) for p in paths
                ]
            print(f"From dir {root}: {len(payloads)} product(s) with images")
        else:
            upload_root = args.from_upload_dir.expanduser().resolve()
            if not upload_root.is_dir():
                raise SystemExit(f"Not a directory: {upload_root}")
            engine = create_engine(args.from_db)
            SourceSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            source_db = SourceSession()
            try:
                source_tenant = _resolve_source_tenant(
                    source_db,
                    tenant_id=args.from_tenant_id,
                    tenant_name=args.from_tenant_name,
                )
                payloads = discover_from_db(
                    source_db,
                    source_tenant=source_tenant,
                    upload_root=upload_root,
                    known_product_ids=known,
                )
                print(
                    f"From DB tenant {source_tenant.name} (id={source_tenant.id}): "
                    f"{len(payloads)} product(s) with images"
                )
            finally:
                source_db.close()
                engine.dispose()

        if not payloads:
            print("Nothing to upload — no matching ProductIDs with images.")
            return 0

        summary = apply_uploads(
            db,
            user,
            tenant,
            payloads,
            replace=args.replace,
            dry_run=args.dry_run,
            limit_products=args.limit,
        )
        print(json.dumps(summary, indent=2))
        if args.dry_run:
            print("Dry run only — re-run with --confirm to upload.")
        else:
            print(
                f"Done. Uploaded {summary['images_uploaded']} image(s) "
                f"across {summary['products_touched']} product(s). "
                "Check /kushalaya/showcase?tenant_id="
                f"{tenant.id}"
            )
        return 1 if summary["errors"] else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
