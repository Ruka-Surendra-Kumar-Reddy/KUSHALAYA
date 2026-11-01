"""Contracts signed in the app (vendor agreements, client service contracts).

- ``/contracts/*`` — staff: templates, the admin's saved signature, send / sign / cancel.
- ``/home-safety/sign/{token}`` — the no-login signing link (under the Safe Home prefix
  so nginx routes it, like ``/home-safety/track``).
- ``/home-safety/family/contracts`` — the family sees their client's signed contracts.

Logic lives in ``app.livewell.contracts``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_elder_portal, require_roles
from app.livewell import contracts as svc
from app.models.user import User
from app.services.login_throttle import client_ip

router = APIRouter(prefix="/contracts", tags=["Contracts"])
public_router = APIRouter(prefix="/home-safety/sign", tags=["Contracts — signing link"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])


def _ua(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:400]


def _pdf(content: bytes, name: str) -> Response:
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


class TemplateIn(BaseModel):
    kind: str | None = Field(default=None, max_length=20)
    title: str = Field(max_length=200)
    body: str = Field(max_length=100_000)


class SignatoryIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    designation: str = Field(max_length=120)
    signature_png: str | None = Field(default=None, max_length=600_000)
    signature_text: str | None = Field(default=None, max_length=200)


class PreviewIn(BaseModel):
    template_id: int
    elder_id: int | None = None
    vendor_id: int | None = None
    signer_name: str | None = Field(default=None, max_length=200)
    fields: dict[str, str] = Field(default_factory=dict)


class ContractIn(PreviewIn):
    signer_name: str = Field(max_length=200)
    signer_email: str | None = Field(default=None, max_length=255)
    signer_mobile: str | None = Field(default=None, max_length=30)
    signer_relation: str | None = Field(default=None, max_length=60)
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=100_000)
    #: draft | submit (waiting for KushAlaya signature) | sign_and_send (admins)
    action: str = Field(default="draft", pattern="^(draft|submit|sign_and_send)$")


class ContractEdit(BaseModel):
    signer_name: str | None = Field(default=None, max_length=200)
    signer_email: str | None = Field(default=None, max_length=255)
    signer_mobile: str | None = Field(default=None, max_length=30)
    signer_relation: str | None = Field(default=None, max_length=60)
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=100_000)


class SignIn(BaseModel):
    name: str = Field(max_length=200)
    signature_png: str | None = Field(default=None, max_length=600_000)
    signature_text: str | None = Field(default=None, max_length=200)
    agree: bool = False


# --- staff ---------------------------------------------------------------------------


@router.get("/meta")
def contracts_meta(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return svc.meta(db, user)


@router.get("/templates")
def list_templates(
    kind: str | None = Query(default=None, max_length=20),
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.list_templates(db, user, kind, include_archived)


@router.post("/templates", status_code=201)
def create_template(data: TemplateIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.create_template(db, user, data.model_dump())


@router.post("/templates/import-docx")
async def import_docx(file: UploadFile = File(...), user: User = Depends(require_roles(*WRITE_ROLES))):
    """Text of an uploaded Word file, to paste into the editor (nothing is saved)."""
    content = await file.read(svc.MAX_DOCX_BYTES + 1)
    return {"text": svc.docx_to_text(content), "file_name": file.filename or ""}


@router.get("/templates/{template_id}/versions")
def template_versions(template_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return svc.template_versions(db, user, template_id)


@router.put("/templates/{template_id}")
def update_template(
    template_id: int, data: TemplateIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return svc.update_template(db, user, template_id, data.model_dump())


@router.post("/templates/{template_id}/archive")
def archive_template(
    template_id: int, archived: bool = True, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return svc.archive_template(db, user, template_id, archived)


@router.get("/signatory")
def my_signatory(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return {"can_sign": svc.is_signatory(user), "signatory": svc.signatory_out(svc.get_signatory(db, user))}


@router.put("/signatory")
def save_signatory(data: SignatoryIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.save_signatory(db, user, data.model_dump())


@router.post("/preview")
def preview(data: PreviewIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.preview(db, user, data.model_dump())


@router.get("")
def list_contracts(
    elder_id: int | None = None,
    vendor_id: int | None = None,
    status: str | None = Query(default=None, max_length=20),
    kind: str | None = Query(default=None, max_length=20),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.list_contracts(db, user, elder_id=elder_id, vendor_id=vendor_id, status=status, kind=kind)


@router.post("", status_code=201)
def create_contract(
    data: ContractIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return svc.create_contract(db, user, data.model_dump(), ip=client_ip(request), ua=_ua(request))


@router.get("/{contract_id}")
def get_contract(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return svc.get_contract(db, user, contract_id)


@router.put("/{contract_id}")
def update_contract(
    contract_id: int, data: ContractEdit, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return svc.update_contract(db, user, contract_id, data.model_dump(exclude_none=True))


@router.post("/{contract_id}/submit")
def submit(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.submit(db, user, contract_id)


@router.post("/{contract_id}/sign-and-send")
def sign_and_send(
    contract_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return svc.sign_and_send(db, user, contract_id, ip=client_ip(request), ua=_ua(request))


@router.post("/{contract_id}/resend")
def resend(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.resend(db, user, contract_id)


@router.post("/{contract_id}/cancel")
def cancel(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return svc.cancel(db, user, contract_id)


@router.get("/{contract_id}/pdf")
def staff_pdf(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _pdf(*svc.staff_pdf(db, user, contract_id))


# --- signing link (no login) ------------------------------------------------------------


@public_router.get("/{token}")
def public_view(token: str, db: Session = Depends(get_db)):
    return svc.public_view(db, token)


@public_router.post("/{token}")
def public_sign(token: str, data: SignIn, request: Request, db: Session = Depends(get_db)):
    return svc.public_sign(db, token, data.model_dump(), ip=client_ip(request), ua=_ua(request))


@public_router.get("/{token}/pdf")
def public_pdf(token: str, db: Session = Depends(get_db)):
    return _pdf(*svc.public_pdf(db, token))


# --- family -------------------------------------------------------------------------------


def _family_elder(db: Session, user: User):
    from app.services.elder_portal_service import ElderPortalService

    return ElderPortalService.get_linked_elder(db, user)


@family_router.get("/contracts")
def family_contracts(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return svc.family_list(db, _family_elder(db, user))


@family_router.get("/contracts/{contract_id}/pdf")
def family_contract_pdf(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    return _pdf(*svc.family_pdf(db, _family_elder(db, user), contract_id))
