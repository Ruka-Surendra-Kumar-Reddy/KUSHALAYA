"""Staff APIs for wet-signed customer document scans."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.signed_doc_service import HomeSafetySignedDocService
from app.models.user import User
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/home-safety/signed-docs", tags=["Safe Home — Signed Docs"])


@router.post("", response_model=DocumentResponse)
async def upload_signed_doc(
    file: UploadFile = File(...),
    form_code: str = Form(...),
    assessment_id: str | None = Form(None),
    prospect_id: int | None = Form(None),
    elder_id: int | None = Form(None),
    notes: str | None = Form(None),
    signed_at: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    content = await file.read()
    doc = HomeSafetySignedDocService.upload(
        db,
        current_user,
        file_name=file.filename or "signed-doc.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        form_code=form_code,
        assessment_id=assessment_id,
        prospect_id=prospect_id,
        elder_id=elder_id,
        notes=notes,
        signed_at=signed_at,
    )
    return DocumentResponse.from_document(doc)


@router.get("/by-assessment/{assessment_id}")
def list_signed_docs_for_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    docs = HomeSafetySignedDocService.list_for_assessment(
        db, current_user, assessment_id=assessment_id
    )
    return [HomeSafetySignedDocService.to_dict(d) for d in docs]


@router.get("/{document_id}/file")
def read_signed_doc_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    content, mime, file_name = HomeSafetySignedDocService.read_for_staff(
        db, current_user, document_id
    )
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )
