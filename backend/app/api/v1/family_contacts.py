"""K2: family contact preferences (#88) and "Call me" / "Ask about…" (#91).

Family side (/home-safety/family/questions) is scoped to the signed-in member's
household; staff side (/home-safety/clients/{id}/…) to the user's tenant + team.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_elder_portal, require_roles
from app.models.user import User

family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])
staff_router = APIRouter(prefix="/home-safety/clients", tags=["Safe Home — Clients"])


def _team_client(db: Session, user: User, elder_id: int):
    from app.api.v1.client_profile import _team_client as team_client

    return team_client(db, user, elder_id)


class QuestionCreate(BaseModel):
    kind: str = Field(pattern="^(call_me|ask)$")
    body: str | None = Field(default=None, max_length=1000)
    window: str | None = Field(default=None, max_length=20)
    day: str | None = Field(default=None, max_length=20)
    visit_ref: str | None = Field(default=None, max_length=64)
    visit_label: str | None = Field(default=None, max_length=200)
    flag_key: str | None = Field(default=None, max_length=120)


@family_router.get("/questions")
def family_questions(db: Session = Depends(get_db), current_user: User = Depends(require_elder_portal)):
    from app.livewell.family_questions import list_for_family

    return list_for_family(db, current_user)


@family_router.post("/questions")
def family_ask(
    body: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.family_questions import ask

    return ask(db, current_user, body.model_dump())


@staff_router.get("/{elder_id}/family-contacts")
def client_family_contacts(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.family_contacts import list_contacts

    return list_contacts(db, _team_client(db, current_user, elder_id))


class ContactUpdate(BaseModel):
    key: str = Field(min_length=3, max_length=300)
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    channel: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    level: str | None = Field(default=None, max_length=20)


@staff_router.put("/{elder_id}/family-contacts")
def update_client_family_contact(
    elder_id: int,
    body: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.family_contacts import staff_save_contact

    elder = _team_client(db, current_user, elder_id)
    data = body.model_dump(exclude_unset=True)
    key = data.pop("key")
    return staff_save_contact(db, elder, key, data, current_user)


@staff_router.get("/{elder_id}/questions")
def client_questions(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.family_questions import list_for_elder

    return list_for_elder(db, _team_client(db, current_user, elder_id))


class QuestionReply(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    done: bool = True


@staff_router.post("/{elder_id}/questions/{question_id}/reply")
def reply_client_question(
    elder_id: int,
    question_id: int,
    body: QuestionReply,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.family_questions import reply

    elder = _team_client(db, current_user, elder_id)
    return reply(db, elder, current_user, question_id, body.body, done=body.done)


@staff_router.post("/{elder_id}/questions/{question_id}/done")
def done_client_question(
    elder_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.family_questions import mark_done

    return mark_done(db, _team_client(db, current_user, elder_id), current_user, question_id)
