from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, CARE_MANAGER, READ_ROLES, WRITE_ROLES, require_roles
from app.models.user import User
from app.schemas.caregiver_identity import DocumentExtractionUpdate
from app.schemas.document import DocumentResponse, VerifyDocumentRequest
from app.services.caregiver_identity_service import CaregiverIdentityService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    content = await file.read()
    doc = DocumentService.upload(
        db,
        current_user,
        entity_type,
        entity_id,
        document_type,
        file.filename or "upload",
        content,
        file.content_type or "application/octet-stream",
    )
    return DocumentResponse.from_document(doc)


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[DocumentResponse])
def list_entity_documents(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    rows = DocumentService.list_for_entity(db, current_user, entity_type, entity_id)
    return [DocumentResponse.from_document(d) for d in rows]


@router.get("/pending", response_model=list[DocumentResponse])
def list_pending_documents(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CARE_MANAGER, *ADMIN_ROLES)),
):
    rows = DocumentService.list_pending(db, current_user, limit)
    return [DocumentResponse.from_document(d) for d in rows]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    doc = DocumentService.get_document(db, document_id, current_user)
    return DocumentResponse.from_document(doc)


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    content, mime, file_name = DocumentService.read_file(
        db, document_id, current_user
    )
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
        },
    )


@router.post("/{document_id}/verify", response_model=DocumentResponse)
def verify_document(
    document_id: int,
    data: VerifyDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CARE_MANAGER, *ADMIN_ROLES)),
):
    doc = DocumentService.verify(db, document_id, data, current_user)
    return DocumentResponse.from_document(doc)


@router.post("/{document_id}/ocr", response_model=DocumentResponse)
def run_document_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    doc = DocumentService.run_ocr(db, document_id, current_user)
    return DocumentResponse.from_document(doc)


@router.patch("/{document_id}/extraction", response_model=DocumentResponse)
def update_document_extraction(
    document_id: int,
    data: DocumentExtractionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    doc = CaregiverIdentityService.update_document_extraction(
        db,
        document_id,
        data,
        current_user,
    )
    return DocumentResponse.from_document(doc)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    DocumentService.delete_document(db, document_id, current_user)
    return {"status": "deleted"}
