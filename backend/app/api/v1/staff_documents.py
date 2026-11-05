"""Team → Documents: owners upload and read each person's HR papers. All optional."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import SYSTEM_ADMIN, TENANT_ADMIN, require_roles, resolve_tenant_id
from app.core.storage import get_storage
from app.models.caregiver import Caregiver
from app.models.staff_document import DOC_TYPES, PERSON_TYPES, StaffDocument
from app.models.user import User

router = APIRouter(prefix="/staff-documents", tags=["Team"])

OWNER_ROLES = (SYSTEM_ADMIN, TENANT_ADMIN)
#: Scans and photos, checked by file signature too.
FILE_TYPES = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8", "image/png": b"\x89PNG"}
MAX_BYTES = 10 * 1024 * 1024


def _person_tenant(db: Session, user: User, person_type: str, person_id: int) -> int:
    """The person's tenant, or 404 when they do not exist or belong to another tenant."""
    if person_type not in PERSON_TYPES:
        raise HTTPException(status_code=404, detail="Person not found.")
    person = db.get(User if person_type == "staff" else Caregiver, person_id)
    tid = resolve_tenant_id(user)
    if person is None or person.tenant_id is None or (tid is not None and person.tenant_id != tid):
        raise HTTPException(status_code=404, detail="Person not found.")
    return person.tenant_id


def _doc(db: Session, user: User, doc_id: int) -> StaffDocument:
    row = db.get(StaffDocument, doc_id)
    tid = resolve_tenant_id(user)
    if row is None or (tid is not None and row.tenant_id != tid):
        raise HTTPException(status_code=404, detail="Document not found.")
    return row


def _out(d: StaffDocument) -> dict:
    return {
        "id": d.id,
        "doc_type": d.doc_type,
        "file_name": d.file_name,
        "size_bytes": d.size_bytes,
        "uploaded_by": d.uploaded_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("/file/{doc_id}")
def download(doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*OWNER_ROLES))):
    row = _doc(db, user, doc_id)
    content, _mime = get_storage().read(row.storage_key)
    return Response(
        content=content,
        media_type=row.mime,
        headers={"Content-Disposition": f'attachment; filename="{row.file_name}"'},
    )


@router.delete("/file/{doc_id}", status_code=204)
def remove(doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*OWNER_ROLES))):
    db.delete(_doc(db, user, doc_id))
    db.commit()


@router.get("/{person_type}/{person_id}")
def list_documents(
    person_type: str, person_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*OWNER_ROLES))
):
    tenant_id = _person_tenant(db, user, person_type, person_id)
    rows = db.scalars(
        select(StaffDocument)
        .where(
            StaffDocument.tenant_id == tenant_id,
            StaffDocument.person_type == person_type,
            StaffDocument.person_id == person_id,
        )
        .order_by(StaffDocument.id.desc())
    ).all()
    return [_out(r) for r in rows]


@router.post("/{person_type}/{person_id}", status_code=201)
async def upload(
    person_type: str,
    person_id: int,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OWNER_ROLES)),
):
    tenant_id = _person_tenant(db, user, person_type, person_id)
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail="Choose what kind of document this is.")
    content = await file.read()
    mime = (file.content_type or "").lower()
    magic = FILE_TYPES.get(mime)
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty.")
    if not magic or not content.startswith(magic):
        raise HTTPException(status_code=422, detail="Upload a PDF, JPG or PNG.")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="The file must be 10 MB or smaller.")
    name = re.sub(r"[^\w. -]", "_", file.filename or "document")[-120:]
    row = StaffDocument(
        tenant_id=tenant_id, person_type=person_type, person_id=person_id, doc_type=doc_type, file_name=name,
        storage_key="", mime=mime, size_bytes=len(content),
        uploaded_by=f"{user.first_name} {user.last_name}".strip() or user.email,
    )
    db.add(row)
    db.flush()
    row.storage_key, _url = get_storage().save(tenant_id, "staff_document", row.id, name, content, mime)
    db.commit()
    db.refresh(row)
    return _out(row)
