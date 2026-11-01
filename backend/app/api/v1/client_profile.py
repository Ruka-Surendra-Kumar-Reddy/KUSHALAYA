"""Ops client profile: one read with everything about a client."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.client_profile import build_client_profile, set_home_location
from app.models.user import User

router = APIRouter(prefix="/home-safety/clients", tags=["Safe Home — Clients"])


@router.get("/{elder_id}/profile")
def get_client_profile(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.core.team_scope import assert_elder_in_team

    assert_elder_in_team(db, current_user, elder_id)
    return build_client_profile(db, current_user, elder_id)


class HomeLocationRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=100, ge=30, le=1000)


@router.put("/{elder_id}/home-location")
def put_home_location(
    elder_id: int,
    data: HomeLocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return set_home_location(
        db, current_user, elder_id, lat=data.lat, lng=data.lng, radius_m=data.radius_m
    )


def _team_client(db: Session, user: User, elder_id: int):
    from app.core.rbac import assert_tenant_access
    from app.core.responses import raise_not_found
    from app.core.team_scope import assert_elder_in_team
    from app.models.elder import Elder

    elder = db.get(Elder, elder_id)
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(user, elder.tenant_id)
    assert_elder_in_team(db, user, elder_id)
    return elder


@router.get("/{elder_id}/kushlife")
def get_client_kushlife(
    elder_id: int,
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """KushLife trend for staff: last visits, streaks, open flags (amber and red)."""
    from app.livewell.kushlife import kushlife_view

    return kushlife_view(db, _team_client(db, current_user, elder_id), limit=max(1, min(limit, 24)), staff=True)


class FlagAck(BaseModel):
    key: str = Field(min_length=3, max_length=120)


@router.post("/{elder_id}/kushlife/acknowledge")
def ack_client_kushlife_flag(
    elder_id: int,
    data: FlagAck,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.kushlife import acknowledge_flag

    return acknowledge_flag(db, _team_client(db, current_user, elder_id), data.key, current_user)


@router.get("/{elder_id}/kushlife/baseline")
def get_client_kushlife_baseline(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """"Normal for Amma": computed from the last visits, with any staff override."""
    from app.livewell.kushlife import baseline_for

    return baseline_for(db, _team_client(db, current_user, elder_id))


@router.put("/{elder_id}/kushlife/baseline")
def put_client_kushlife_baseline(
    elder_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Override any of bp_sys, bp_dia, spo2, pulse, sleep, appetite, mood; null clears one."""
    from app.livewell.kushlife import set_baseline_override

    return set_baseline_override(db, _team_client(db, current_user, elder_id), body, current_user)


@router.get("/kushlife-weekly/pending")
def get_kushlife_weekly_pending(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Weekly summaries waiting for approval in my team; overdue after Tuesday 18:00 IST."""
    from app.livewell.kushlife_weekly import pending_for

    return pending_for(db, current_user)


@router.get("/{elder_id}/kushlife/weekly")
def get_client_kushlife_weekly(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Weekly summaries (drafts and approved) plus last week's card as the family sees it."""
    from app.livewell.kushlife_weekly import last_week_start, staff_list, week_stats

    elder = _team_client(db, current_user, elder_id)
    return {"summaries": staff_list(db, elder), "card": week_stats(db, elder, last_week_start(), staff=True)}


class WeeklyText(BaseModel):
    text: str | None = Field(default=None, max_length=4000)


@router.put("/{elder_id}/kushlife/weekly/{summary_id}")
def put_client_kushlife_weekly(
    elder_id: int,
    summary_id: int,
    data: WeeklyText,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.kushlife_weekly import edit_summary

    return edit_summary(db, _team_client(db, current_user, elder_id), summary_id, data.text or "", current_user)


@router.post("/{elder_id}/kushlife/weekly/{summary_id}/approve")
def approve_client_kushlife_weekly(
    elder_id: int,
    summary_id: int,
    data: WeeklyText | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Approve and send to the family (portal + email, if they get weekly summaries)."""
    from app.livewell.kushlife_weekly import approve_summary

    return approve_summary(
        db, _team_client(db, current_user, elder_id), summary_id, current_user, data.text if data else None
    )


@router.get("/{elder_id}/score-explain")
def get_client_score_explain(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """'Why this score?' for staff, with every answer and its points."""
    from app.livewell.score_explain import explain

    return explain(db, _team_client(db, current_user, elder_id), staff=True)


@router.get("/{elder_id}/journey")
def get_client_journey(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.journey import journey_for_elder

    return journey_for_elder(db, _team_client(db, current_user, elder_id))


@router.get("/{elder_id}/assessments")
def get_client_assessments(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Assessments tab: every assessment, booked assessment jobs, and the latest two compared."""
    from app.livewell.client_profile import client_assessments

    return client_assessments(db, _team_client(db, current_user, elder_id))
