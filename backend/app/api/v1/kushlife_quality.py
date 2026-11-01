"""KushLife K3 + Phase 5 (#100 #106): monthly letter, vitals trend, voice notes, ratings, NPS, quality."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.client_profile import _team_client
from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_caregiver_portal, require_elder_portal, require_roles
from app.livewell import kushlife_monthly as km
from app.livewell import visit_feedback as fb
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService

router = APIRouter(prefix="/home-safety", tags=["Safe Home — KushLife quality"])
jobs_router = APIRouter(prefix="/jobs", tags=["Jobs"])
caregiver_router = APIRouter(prefix="/caregiver-portal", tags=["Caregiver portal"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])


def _pdf(content: bytes, name: str) -> Response:
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "private, no-store"})


def _audio(content: bytes, mime: str) -> Response:
    return Response(content, media_type=mime, headers={"Cache-Control": "private, no-store"})


def _letter_name(row) -> str:
    return f"kushlife-letter-{row.month_start.strftime('%Y-%m')}.pdf"


# --- staff: monthly letter ---------------------------------------------------------------


class LetterEdit(BaseModel):
    text: str | None = Field(default=None, max_length=6000)
    manager_note: str | None = Field(default=None, max_length=2000)
    next_plan: str | None = Field(default=None, max_length=2000)


@router.get("/quality/monthly-pending")
def get_monthly_pending(db: Session = Depends(get_db), current_user: User = Depends(require_roles(*READ_ROLES))):
    """Monthly letters waiting for approval in my team; overdue after the 5th, 18:00 IST."""
    return km.pending_for(db, current_user)


@router.get("/clients/{elder_id}/kushlife/monthly")
def get_client_monthly(elder_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(*READ_ROLES))):
    return {"letters": km.staff_list(db, _team_client(db, current_user, elder_id))}


@router.put("/clients/{elder_id}/kushlife/monthly/{letter_id}")
def put_client_monthly(elder_id: int, letter_id: int, data: LetterEdit, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(*WRITE_ROLES))):
    return km.edit_letter(db, _team_client(db, current_user, elder_id), letter_id, data.model_dump(), current_user)


@router.post("/clients/{elder_id}/kushlife/monthly/{letter_id}/approve")
def approve_client_monthly(elder_id: int, letter_id: int, data: LetterEdit | None = None,
                           db: Session = Depends(get_db), current_user: User = Depends(require_roles(*WRITE_ROLES))):
    """Approve and send to the family (portal + email, if they get monthly letters)."""
    return km.approve_letter(db, _team_client(db, current_user, elder_id), letter_id, current_user,
                             data.model_dump() if data else None)


@router.get("/clients/{elder_id}/kushlife/monthly/{letter_id}/pdf")
def pdf_client_monthly(elder_id: int, letter_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(*READ_ROLES))):
    elder = _team_client(db, current_user, elder_id)
    row = km._get(db, elder, letter_id)
    return _pdf(km.letter_pdf(db, elder, row), _letter_name(row))


@router.get("/clients/{elder_id}/kushlife/vitals")
def get_client_vitals(elder_id: int, days: int = 92, db: Session = Depends(get_db),
                      current_user: User = Depends(require_roles(*READ_ROLES))):
    """BP / oxygen / pulse from KushLife visits (last ~3 months) with the client's normal."""
    return km.vitals_series(db, _team_client(db, current_user, elder_id), days=max(14, min(days, 366)))


# --- staff: voice notes, feedback, quality ------------------------------------------------


class ShareBody(BaseModel):
    share: bool


@router.get("/clients/{elder_id}/voice-notes")
def get_client_voice_notes(elder_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles(*READ_ROLES))):
    return fb.staff_voice_notes(db, _team_client(db, current_user, elder_id))


@router.get("/voice-notes/{note_id}/audio")
def get_voice_audio(note_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles(*READ_ROLES))):
    return _audio(*fb.staff_audio(db, current_user, note_id))


@router.post("/voice-notes/{note_id}/share")
def share_voice(note_id: int, data: ShareBody, db: Session = Depends(get_db),
                current_user: User = Depends(require_roles(*WRITE_ROLES))):
    """Tick "share with family": only then can the family hear it."""
    return fb.share_voice_note(db, current_user, note_id, data.share)


@router.get("/clients/{elder_id}/feedback")
def get_client_feedback(elder_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles(*READ_ROLES))):
    return fb.client_feedback(db, _team_client(db, current_user, elder_id))


@router.post("/feedback/{kind}/{row_id}/review")
def review_feedback(kind: str, row_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles(*WRITE_ROLES))):
    """Low rating / detractor seen by the care manager: drops off "Needs attention"."""
    return fb.mark_reviewed(db, current_user, kind, row_id)


@router.get("/clients/{elder_id}/quality")
def get_client_quality(elder_id: int, days: int = 30, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(*READ_ROLES))):
    return fb.client_quality(db, _team_client(db, current_user, elder_id), days=max(7, min(days, 366)))


@router.get("/quality")
def get_agency_quality(days: int = 30, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(*READ_ROLES))):
    """On time %, KushLife %, average family rating, incidents (my team) and agency NPS."""
    return fb.agency_quality(db, current_user, days=max(7, min(days, 366)))


# --- recording a voice note (caregiver, or staff running the visit) ---------------------------


async def _voice(db: Session, user: User, job_id: int, file: UploadFile, duration_s: int | None) -> dict:
    # Read in chunks and stop as soon as the cap is passed (never buffer a huge upload).
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > fb.VOICE_MAX_BYTES:
            raise HTTPException(status_code=413, detail="The recording is too large (keep it under 60 seconds)")
        chunks.append(chunk)
    content = b"".join(chunks)
    return fb.add_voice_note(db, user, job_id, file_name=file.filename or "voice-note", content=content,
                             content_type=file.content_type, duration_s=duration_s)


@caregiver_router.post("/jobs/{job_id}/voice-notes")
async def caregiver_voice_note(job_id: int, file: UploadFile = File(...), duration_s: int | None = Form(None),
                               db: Session = Depends(get_db), user: User = Depends(require_caregiver_portal)):
    return await _voice(db, user, job_id, file, duration_s)


@jobs_router.post("/{job_id}/voice-notes")
async def staff_voice_note(job_id: int, file: UploadFile = File(...), duration_s: int | None = Form(None),
                           db: Session = Depends(get_db), current_user: User = Depends(require_roles(*WRITE_ROLES))):
    return await _voice(db, current_user, job_id, file, duration_s)


# --- family -------------------------------------------------------------------------------


class NpsBody(BaseModel):
    score: int | None = Field(default=None, ge=0, le=10)  # null = "not now"
    reason: str = Field(default="", max_length=1000)


@family_router.get("/kushlife/vitals")
def family_vitals(db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    return km.vitals_series(db, ElderPortalService.get_linked_elder(db, current_user))


@family_router.get("/kushlife/letters")
def family_letters(db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    """Approved monthly letters only (drafts are never shown)."""
    return km.family_list(db, ElderPortalService.get_linked_elder(db, current_user))


@family_router.get("/kushlife/letters/{letter_id}")
def family_letter(letter_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    elder = ElderPortalService.get_linked_elder(db, current_user)
    row = km.family_get(db, elder, letter_id)
    return {**km.as_dict(row, staff=False), "elder_name": f"{elder.first_name or ''} {elder.last_name or ''}".strip()}


@family_router.get("/kushlife/letters/{letter_id}/pdf")
def family_letter_pdf(letter_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(require_elder_portal)):
    elder = ElderPortalService.get_linked_elder(db, current_user)
    row = km.family_get(db, elder, letter_id)
    return _pdf(km.letter_pdf(db, elder, row), _letter_name(row))


@family_router.get("/voice-notes/{note_id}/audio")
def family_voice_audio(note_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_elder_portal)):
    """Only notes the care manager shared with the family."""
    return _audio(*fb.family_audio(db, ElderPortalService.get_linked_elder(db, current_user), note_id))


@family_router.get("/feedback/nps")
def family_nps_status(db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    return fb.nps_status(db, current_user, ElderPortalService.get_linked_elder(db, current_user))


@family_router.post("/feedback/nps")
def family_nps_answer(data: NpsBody, db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    return fb.answer_nps(db, current_user, ElderPortalService.get_linked_elder(db, current_user), data.score, data.reason)
