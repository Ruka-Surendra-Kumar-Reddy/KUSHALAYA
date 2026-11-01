from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import raise_not_found
from app.core.rbac import ADMIN_ROLES, SYSTEM_ADMIN, WRITE_ROLES, require_roles, resolve_tenant_id
from app.core.team_scope import team_user_ids
from app.models.user import User
from app.schemas.activity import SessionDetailResponse, SessionEventResponse, SessionSummaryResponse
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/activity", tags=["Session activity"])

#: Event kinds a non-admin may see; everything else is the technical API log.
_PLAIN_EVENT_KINDS = {"action", "ai_result", "system"}


def _summary(row, *, admin: bool) -> SessionSummaryResponse:
    out = SessionSummaryResponse.model_validate(row)
    if not admin:  # managers never see IPs or browser strings
        out.ip_address = None
        out.user_agent = None
    return out


def _events(events, *, admin: bool) -> list[SessionEventResponse]:
    out: list[SessionEventResponse] = []
    for e in events:
        ev = SessionEventResponse.model_validate(e)
        if not admin:
            if ev.event_kind not in _PLAIN_EVENT_KINDS:
                continue
            ev.meta = None
            ev.request_id = None
            ev.method = None
            ev.path = None
            ev.status_code = None
            ev.duration_ms = None
        out.append(ev)
    return out


@router.get("/sessions", response_model=list[SessionSummaryResponse])
def list_sessions(
    actor_type: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    if actor_type and actor_type not in {"family", "assessor", "staff", "system"}:
        from app.core.responses import raise_bad_request

        raise_bad_request("actor_type must be family, assessor, staff, or system")
    tid = resolve_tenant_id(current_user, tenant_id)
    if current_user.role != SYSTEM_ADMIN:
        tid = current_user.tenant_id
    admin = current_user.role in ADMIN_ROLES
    rows = SessionActivityService.list_sessions(
        db,
        tenant_id=tid,
        actor_type=actor_type,
        user_id=user_id,
        user_ids=None if admin else (team_user_ids(db, current_user) or set()),
        limit=limit,
        offset=offset,
    )
    out = [_summary(r, admin=admin) for r in rows]
    _attach_recent_actions(db, out)
    return out


def _attach_recent_actions(db: Session, rows: list[SessionSummaryResponse], per_session: int = 3) -> None:
    """One query for the page: the last few user actions of each session."""
    from app.models.user_session import UserSessionEvent

    ids = [r.id for r in rows]
    if not ids:
        return
    events = (
        db.query(UserSessionEvent.session_id, UserSessionEvent.action, UserSessionEvent.summary)
        .filter(UserSessionEvent.session_id.in_(ids), UserSessionEvent.event_kind == "action")
        .order_by(UserSessionEvent.occurred_at.desc())
        .limit(len(ids) * 20)
        .all()
    )
    by_id: dict[str, list[str]] = {}
    for sid, action, summary in events:
        got = by_id.setdefault(sid, [])
        action, summary = (action or "").strip(), (summary or "").strip()
        text = f"{action} · {summary}" if summary and summary != action and len(summary) <= 80 else (action or summary)
        if text and len(got) < per_session and text not in got:
            got.append(text[:140])
    for r in rows:
        r.recent_actions = by_id.get(r.id, [])


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: str,
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    tid = resolve_tenant_id(current_user, tenant_id)
    if current_user.role != SYSTEM_ADMIN:
        tid = current_user.tenant_id
    admin = current_user.role in ADMIN_ROLES
    row = SessionActivityService.get_session(db, session_id, tenant_id=tid)
    if not row or (not admin and row.user_id not in (team_user_ids(db, current_user) or set())):
        raise_not_found("Session not found")
    events = SessionActivityService.list_events(db, session_id, limit=300)
    return SessionDetailResponse(
        **_summary(row, admin=admin).model_dump(),
        events=_events(events, admin=admin),
    )
