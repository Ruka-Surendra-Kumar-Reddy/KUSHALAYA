"""Team: managers, caregivers and who reports to whom (Admin / Manager / Caregiver)."""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (
    WRITE_ROLES,
    CARE_MANAGER,
    CAREGIVER,
    READ_ROLES,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    assert_tenant_access,
    require_roles,
    resolve_tenant_id,
)
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.core.security import hash_password


def _random_password() -> str:
    from app.services.account_setup import random_password

    return random_password()
from app.core.team_scope import assert_caregiver_in_team, scope_caregiver_query, team_elder_ids
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User
from app.services.caregiver_service import CaregiverService

router = APIRouter(prefix="/team", tags=["Team"])

ADMIN_ROLES = (SYSTEM_ADMIN, TENANT_ADMIN)


class TeamCaregiverCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str | None = None
    # Optional: caregivers who don't use the app need no login.
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    manager_user_id: int | None = None


class ManagerAssign(BaseModel):
    manager_user_id: int | None = None


class TeamCaregiverUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    # "INACTIVE" = Mark as left (their login is switched off too); "ACTIVE" brings them back.
    status: str | None = None


def _manager_or_none(db: Session, actor: User, manager_user_id: int | None) -> int | None:
    if manager_user_id is None:
        return None
    m = db.query(User).filter(User.id == manager_user_id, User.role == CARE_MANAGER).first()
    if not m:
        raise_bad_request("Manager not found")
    assert_tenant_access(actor, m.tenant_id)
    return m.id


def _caregiver_row(db: Session, cg: Caregiver) -> dict:
    login = db.query(User).filter(User.caregiver_id == cg.id, User.role == CAREGIVER).first()
    return {
        "id": cg.id,
        "first_name": cg.first_name,
        "last_name": cg.last_name,
        "phone": cg.phone,
        "email": cg.email,
        "status": cg.status,
        "manager_user_id": cg.manager_user_id,
        "login_email": login.email if login else None,
        "login_user_id": login.id if login else None,
        "login_status": login.status if login else None,
    }


@router.get("/managers")
def list_managers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    q = db.query(User).filter(
        User.role == CARE_MANAGER, User.status == "ACTIVE", User.access_profile.is_(None)
    )
    tid = resolve_tenant_id(current_user)
    if tid is not None:
        q = q.filter(User.tenant_id == tid)
    rows = []
    for u in q.order_by(User.first_name).all():
        cg_count = (
            db.query(Caregiver)
            .filter(Caregiver.manager_user_id == u.id, Caregiver.status != "INACTIVE")
            .count()
        )
        rows.append(
            {
                "id": u.id,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "caregivers": cg_count,
                "clients": len(team_elder_ids(db, u) or set()),
            }
        )
    return rows


@router.get("/caregivers")
def list_team_caregivers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    q = db.query(Caregiver).filter(Caregiver.status != "INACTIVE")
    tid = resolve_tenant_id(current_user)
    if tid is not None:
        q = q.filter(Caregiver.tenant_id == tid)
    q = scope_caregiver_query(db, current_user, q)
    return [_caregiver_row(db, cg) for cg in q.order_by(Caregiver.first_name).all()]


@router.post("/caregivers", status_code=201)
def create_team_caregiver(
    data: TeamCaregiverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Caregiver profile and their field-app login in one step.

    Same rule as POST /caregivers: admins create for anyone; a manager's new
    caregiver always joins the manager's own team."""
    tid = resolve_tenant_id(current_user)
    if tid is None:
        raise_bad_request("Pick an agency first")
    email = data.email.lower() if data.email else None
    if email and db.query(User).filter(func.lower(User.email) == email).first():
        raise_conflict("Email already registered")
    if current_user.role == CARE_MANAGER:
        manager_id = current_user.id
    else:
        manager_id = _manager_or_none(db, current_user, data.manager_user_id)
    cg = Caregiver(
        tenant_id=tid,
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        phone=data.phone,
        email=email,
        status="ACTIVE",
        manager_user_id=manager_id,
    )
    db.add(cg)
    db.flush()
    login = None
    if email:
        login = User(
            email=email,
            password_hash=hash_password(data.password or _random_password()),
            first_name=cg.first_name,
            last_name=cg.last_name,
            role=CAREGIVER,
            tenant_id=tid,
            caregiver_id=cg.id,
        )
        db.add(login)
        db.flush()
    CaregiverService.audit(db, current_user, cg, "caregiver_created", None, CaregiverService.snapshot(cg, login))
    db.commit()
    db.refresh(cg)
    if email and not data.password:
        from app.services.account_setup import send_account_setup

        who = (current_user.first_name or "").strip() or "Your care manager"
        send_account_setup(db, login, phone=data.phone, intro=f"{who} added you as a caregiver on KushAlaya.")
    return _caregiver_row(db, cg)


@router.patch("/caregivers/{caregiver_id}")
def update_team_caregiver(
    caregiver_id: int,
    data: TeamCaregiverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Edit a caregiver's name / phone / email, or mark them as left. Managers: own team only."""
    cg = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
    if not cg:
        raise_not_found("Caregiver not found")
    assert_tenant_access(current_user, cg.tenant_id)
    assert_caregiver_in_team(db, current_user, cg.id)
    login = CaregiverService.login_for(db, cg)
    before = CaregiverService.snapshot(cg, login)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("first_name") is not None:
        cg.first_name = updates["first_name"].strip()
    if "last_name" in updates:
        cg.last_name = (updates["last_name"] or "").strip()
    if "phone" in updates:
        cg.phone = (updates["phone"] or "").strip() or None
    if "email" in updates:
        CaregiverService.apply_email(db, cg, login, updates["email"])
    if updates.get("status") is not None:
        CaregiverService.apply_status(cg, login, updates["status"], current_user)
    if login:
        login.first_name, login.last_name = cg.first_name, cg.last_name
    CaregiverService.audit(db, current_user, cg, "caregiver_updated", before, CaregiverService.snapshot(cg, login))
    db.commit()
    db.refresh(cg)
    return _caregiver_row(db, cg)


@router.put("/caregivers/{caregiver_id}/manager")
def set_caregiver_manager(
    caregiver_id: int,
    data: ManagerAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    cg = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
    if not cg:
        raise_not_found("Caregiver not found")
    assert_tenant_access(current_user, cg.tenant_id)
    before = CaregiverService.snapshot(cg, None)
    cg.manager_user_id = _manager_or_none(db, current_user, data.manager_user_id)
    CaregiverService.audit(db, current_user, cg, "caregiver_manager_changed", before, CaregiverService.snapshot(cg, None))
    db.commit()
    return _caregiver_row(db, cg)


@router.put("/clients/{elder_id}/manager")
def set_client_manager(
    elder_id: int,
    data: ManagerAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    elder = db.query(Elder).filter(Elder.id == elder_id).first()
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(current_user, elder.tenant_id)
    elder.manager_user_id = _manager_or_none(db, current_user, data.manager_user_id)
    db.commit()
    return {"id": elder.id, "manager_user_id": elder.manager_user_id}



class KnowThemIn(BaseModel):
    approach: str = ""
    likes: str = ""
    avoid: str = ""
    routine: str = ""
    notes: str = ""


def _team_elder(db: Session, user: User, elder_id: int) -> Elder:
    from app.core.team_scope import assert_elder_in_team

    elder = db.query(Elder).filter(Elder.id == elder_id).first()
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(user, elder.tenant_id)
    assert_elder_in_team(db, user, elder.id)
    return elder


@router.get("/clients/{elder_id}/know-them")
def get_know_them(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.visit_reports import know_them

    return know_them(_team_elder(db, current_user, elder_id))


@router.put("/clients/{elder_id}/know-them")
def put_know_them(
    elder_id: int,
    data: KnowThemIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.visit_reports import save_know_them

    return save_know_them(db, _team_elder(db, current_user, elder_id), data.model_dump())


class HazardStatusIn(BaseModel):
    status: str
    order_id: int | None = None


@router.get("/clients/{elder_id}/hazards")
def get_hazards(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.visit_reports import list_hazards

    return list_hazards(_team_elder(db, current_user, elder_id))


@router.post("/clients/{elder_id}/hazards/{hazard_id}")
def set_hazard_status(
    elder_id: int,
    hazard_id: str,
    data: HazardStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.visit_reports import set_hazard

    return set_hazard(db, _team_elder(db, current_user, elder_id), hazard_id, data.status, data.order_id)


# --- Clients and their family logins ------------------------------------------------


class FamilyLoginIn(BaseModel):
    name: str = ""
    email: EmailStr
    password: str = Field(min_length=8)
    relationship: str = "family"


class ClientIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    medical_conditions: str | None = None
    manager_user_id: int | None = None
    family: FamilyLoginIn | None = None


class PasswordIn(BaseModel):
    password: str = Field(min_length=8)


def _family_users_many(db: Session, elder_ids: list[int]) -> dict[int, list[User]]:
    """Family logins per client: FamilyElderLink rows, plus legacy users.elder_id. Two queries."""
    from sqlalchemy import or_

    from app.models.family_elder_link import FamilyElderLink

    out: dict[int, list[User]] = {eid: [] for eid in elder_ids}
    if not elder_ids:
        return out
    links = (
        db.query(FamilyElderLink.elder_id, FamilyElderLink.user_id)
        .filter(FamilyElderLink.elder_id.in_(elder_ids))
        .order_by(FamilyElderLink.id)
        .all()
    )
    link_uids = {uid for _, uid in links}
    users = (
        db.query(User)
        .filter(User.role == "ELDER_PORTAL", or_(User.id.in_(link_uids or {-1}), User.elder_id.in_(elder_ids)))
        .order_by(User.id)
        .all()
    )
    by_id = {u.id: u for u in users}
    seen: set[tuple[int, int]] = set()
    for eid, uid in links:
        if uid in by_id and (eid, uid) not in seen:
            seen.add((eid, uid))
            out[eid].append(by_id[uid])
    for u in users:
        if u.elder_id in out and (u.elder_id, u.id) not in seen:
            seen.add((u.elder_id, u.id))
            out[u.elder_id].append(u)
    return out


def _login_dict(u: User, activity: dict[int, dict]) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": f"{u.first_name} {u.last_name}".strip(),
        "relationship": u.portal_relationship or "family",
        "active": u.status == "ACTIVE",
        **activity.get(u.id, {"last_seen_at": None, "sign_ins_30d": 0}),
    }


def _family_logins_many(db: Session, elder_ids: list[int]) -> dict[int, list[dict]]:
    users = _family_users_many(db, elder_ids)
    activity = _login_activity(db, list({u.id for us in users.values() for u in us}))
    return {eid: [_login_dict(u, activity) for u in us] for eid, us in users.items()}


def _family_logins(db: Session, elder_id: int) -> list[dict]:
    return _family_logins_many(db, [elder_id])[elder_id]


def _login_activity(db: Session, user_ids: list[int]) -> dict[int, dict]:
    """Last time each family login used the portal, and sign-ins in the last 30 days."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from app.models.user_session import UserSession

    if not user_ids:
        return {}
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(
            UserSession.user_id,
            func.max(UserSession.last_seen_at),
            func.sum(case((UserSession.started_at >= since, 1), else_=0)),
        )
        .filter(UserSession.user_id.in_(user_ids))
        .group_by(UserSession.user_id)
        .all()
    )
    out = {}
    for uid, last, n in rows:
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        out[uid] = {"last_seen_at": last.isoformat() if last else None, "sign_ins_30d": int(n or 0)}
    return out


def _client_row(db: Session, e: Elder, actor: User | None = None, badges: bool = False) -> dict:
    return _client_rows(db, [e], actor, badges=badges)[0]


def _client_rows(db: Session, elders: list[Elder], actor: User | None = None, badges: bool = False) -> list[dict]:
    """List rows with a constant number of queries, however many clients."""
    ids = [e.id for e in elders]
    mgr_ids = {e.manager_user_id for e in elders if e.manager_user_id}
    managers = {u.id: u for u in db.query(User).filter(User.id.in_(mgr_ids)).all()} if mgr_ids else {}
    logins = _family_logins_many(db, ids)
    facts = _badge_facts(db, elders) if badges else {}
    # Regular caregivers (ACTIVE assignments) for every client in one query.
    from app.models.assignment import Assignment

    carers: dict[int, list[dict]] = {}
    if ids:
        for eid, cid, first, last in (
            db.query(Assignment.elder_id, Caregiver.id, Caregiver.first_name, Caregiver.last_name)
            .join(Caregiver, Caregiver.id == Assignment.caregiver_id)
            .filter(Assignment.elder_id.in_(ids), Assignment.status == "ACTIVE")
            .order_by(Assignment.id)
            .all()
        ):
            carers.setdefault(eid, []).append({"id": cid, "name": f"{first or ''} {last or ''}".strip()})
    rows = []
    for e in elders:
        m = managers.get(e.manager_user_id)
        row = {
            "id": e.id,
            "first_name": e.first_name,
            "last_name": e.last_name,
            "phone": e.phone,
            "address": e.address,
            "status": e.status,
            "emergency_contact_name": e.emergency_contact_name,
            "emergency_contact_phone": e.emergency_contact_phone,
            "manager_user_id": e.manager_user_id,
            "manager_name": f"{m.first_name} {m.last_name}".strip() if m else "",
            "family_logins": logins.get(e.id, []),
            "manager": {"id": m.id, "name": f"{m.first_name} {m.last_name}".strip()} if m else None,
            "caregivers": carers.get(e.id, []),
        }
        if actor is not None:
            row["mine"] = e.manager_user_id == actor.id
        if badges:
            row.update(_client_badges(e, facts))
        rows.append(row)
    return rows


def _aware(dt):
    from datetime import datetime, timezone

    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _badge_facts(db: Session, elders: list[Elder]) -> dict:
    """Grouped queries for every client at once: next visit, open alerts, last
    assessment, booked assessment, and the latest KushLife visits."""
    from datetime import datetime, timezone

    from app.models.care_job import CareJob
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord as Rec
    from app.models.incident import Incident

    ids = [e.id for e in elders]
    now = datetime.now(timezone.utc)
    if not ids:
        return {"now": now, "next_visit": {}, "alerts": {}, "sos": {}, "last_done": {}, "booked": set(), "visits": {}}
    open_job = CareJob.status.notin_(("cancelled", "missed", "completed"))
    next_visit = dict(
        db.query(CareJob.elder_id, func.min(CareJob.scheduled_at))
        .filter(CareJob.elder_id.in_(ids), open_job, CareJob.scheduled_at >= now)
        .group_by(CareJob.elder_id)
        .all()
    )
    # Open alerts and, of those, SOS / emergencies (severity critical) in one grouped query.
    alert_rows = (
        db.query(
            Incident.elder_id,
            func.count(Incident.id),
            func.sum(case((Incident.severity == "critical", 1), else_=0)),
        )
        .filter(Incident.elder_id.in_(ids), Incident.status.notin_(("resolved", "closed")))
        .group_by(Incident.elder_id)
        .all()
    )
    alerts = {r[0]: r[1] for r in alert_rows}
    sos = {r[0]: int(r[2] or 0) for r in alert_rows}
    last_done = dict(
        db.query(Rec.elder_id, func.max(func.coalesce(Rec.completed_at, Rec.updated_at)))
        .filter(Rec.elder_id.in_(ids), Rec.status == "completed")
        .group_by(Rec.elder_id)
        .all()
    )
    booked = {
        r[0]
        for r in db.query(CareJob.elder_id)
        .filter(CareJob.elder_id.in_(ids), CareJob.kind == "assessment", open_job)
        .distinct()
        .all()
    }
    return {
        "now": now,
        "next_visit": next_visit,
        "alerts": alerts,
        "sos": sos,
        "last_done": last_done,
        "booked": booked,
        "visits": _recent_kushlife_many(db, ids),
    }


def _recent_kushlife_many(db: Session, ids: list[int], per_elder: int = 3) -> dict[int, list[dict]]:
    """Latest completed visits with a KushLife check, per client, in one windowed query
    (same shape as kushlife.recent_visits, just the fields open_flags reads)."""
    from app.livewell.kushlife import CHECKS, _complete_legacy, plain_checks, visit_level
    from app.models.care_job import CareJob

    rn = (
        func.row_number()
        .over(partition_by=CareJob.elder_id, order_by=(CareJob.completed_at.desc(), CareJob.id.desc()))
        .label("rn")
    )
    sub = (
        db.query(CareJob.id.label("id"), rn)
        .filter(CareJob.elder_id.in_(ids), CareJob.status == "completed", CareJob.kind.in_(("visit", "install")))
        .subquery()
    )
    jobs = (
        db.query(CareJob)
        .join(sub, sub.c.id == CareJob.id)
        .filter(sub.c.rn <= per_elder * 3)
        .order_by(CareJob.elder_id, sub.c.rn)
        .all()
    )
    out: dict[int, list[dict]] = {}
    for j in jobs:
        rep = j.report or {}
        rec = rep.get("kushlife")
        if not rec and _complete_legacy(rep.get("checks")):
            rec = {"checks": {k: {"status": rep["checks"][k], "chips": [], "note": ""} for k in CHECKS}}
        if not rec or not isinstance(rec.get("checks"), dict):
            continue
        lst = out.setdefault(j.elder_id, [])
        if len(lst) >= per_elder:
            continue
        level, reasons = visit_level(rec)
        when = _aware(j.completed_at or j.scheduled_at)
        lst.append(
            {
                "job_id": j.id,
                "date": when.isoformat() if when else None,
                "checks": plain_checks(rec),
                "level": level,
                "reasons": reasons,
            }
        )
    return out


def _client_badges(e: Elder, facts: dict) -> dict:
    from app.livewell.dashboard_attention import awaiting_reply
    from app.livewell.family_care_hub import FamilyCareHubService, _hub
    from app.livewell.family_service_requests import _normalize as normalize_request
    from app.livewell.family_service_requests import _requests as raw_requests
    from app.livewell.kushlife import open_flags, status_word
    from app.livewell.reassessment import HEADS_UP, INTERVAL

    last = _aware(facts["last_done"].get(e.id))
    booked = e.id in facts["booked"]
    flags = [f for f in open_flags(e, facts["visits"].get(e.id, [])) if not f.get("acknowledged_at")]
    sh = (e.custom_attributes or {}).get("safe_home") if isinstance(e.custom_attributes, dict) else None
    score = (sh or {}).get("safety_score") if isinstance(sh, dict) else None
    nv = _aware(facts["next_visit"].get(e.id))
    hub = _hub(e)
    unread = int(FamilyCareHubService._unread_by_staff(hub) or 0)
    thread = sorted(
        (m for m in hub.get("messages") or [] if isinstance(m, dict)),
        key=lambda m: str(m.get("created_at") or ""),
    )
    last_msg = thread[-1] if thread else None
    return {
        "next_visit_at": nv.isoformat() if nv else None,
        "open_alerts": int(facts["alerts"].get(e.id) or 0),
        "assessment_overdue": bool(last and last + INTERVAL < facts["now"]) and not booked,
        "needs_first_assessment": last is None and not booked,
        "kushlife_status": status_word(flags) if flags else None,
        "score": score.get("total") if isinstance(score, dict) else None,
        # Same rules as the dashboard: SOS = open critical incident, request = still "requested",
        # reassessment = first needed or due within 3 weeks and not booked. Read from the
        # elder's own JSON, so no extra queries.
        "open_sos": int(facts["sos"].get(e.id) or 0),
        "open_requests": sum(1 for r in raw_requests(e) if normalize_request(r)["status"] == "requested"),
        "unread_messages": unread,
        # Same rule as the Dashboard's message rows (dashboard_attention.awaiting_reply):
        # unread family messages, or the family spoke last and nobody has answered yet.
        "awaiting_reply": awaiting_reply({"unread_count": unread, "last_message": last_msg}) if last_msg else False,
        "reassessment_due": not booked and (last is None or last + INTERVAL - facts["now"] <= HEADS_UP),
    }


def _add_family_login(db: Session, actor: User, elder: Elder, fam: FamilyLoginIn) -> None:
    email = fam.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise_conflict(f"{email} is already used by another login")
    from app.livewell.family_elder_access import ensure_family_elder_link

    first, _, last = (fam.name or "Family").strip().partition(" ")
    u = User(
        email=email,
        password_hash=hash_password(fam.password),
        first_name=first or "Family",
        last_name=last,
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        portal_relationship=(fam.relationship or "family")[:50],
    )
    db.add(u)
    db.flush()
    ensure_family_elder_link(db, u, elder)


@router.get("/clients")
def list_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.core.team_scope import scope_elder_query

    q = db.query(Elder).filter(Elder.status != "INACTIVE")
    tid = resolve_tenant_id(current_user)
    if tid is not None:
        q = q.filter(Elder.tenant_id == tid)
    q = scope_elder_query(db, current_user, q)
    return _client_rows(db, q.order_by(Elder.first_name).limit(500).all(), current_user, badges=True)


class BulkCareTeamIn(BaseModel):
    elder_ids: list[int] = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(manager|caregiver)$")
    manager_user_id: int | None = None
    caregiver_id: int | None = None
    note: str | None = Field(default=None, max_length=4000)


@router.post("/clients/bulk-care-team")
def bulk_care_team(
    data: BulkCareTeamIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Change care manager (admins) or add a caregiver for several clients; reports failures."""
    from fastapi import HTTPException

    from app.livewell import care_team as ct

    if data.action == "manager" and not ct.is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only an admin can change the care manager")
    return ct.bulk(
        db, current_user, data.elder_ids, action=data.action,
        manager_user_id=data.manager_user_id, caregiver_id=data.caregiver_id, note=data.note,
    )


@router.get("/caregivers/{caregiver_id}/clients")
def caregiver_clients(
    caregiver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell import care_team as ct

    cg = db.get(Caregiver, caregiver_id)
    if not cg:
        raise_not_found("Caregiver not found")
    assert_tenant_access(current_user, cg.tenant_id)
    assert_caregiver_in_team(db, current_user, cg.id)
    return ct.caregiver_clients(db, current_user, cg.id)


@router.post("/clients", status_code=201)
def create_client(
    data: ClientIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """New client, and (optionally) the family member's login in one step."""
    tid = resolve_tenant_id(current_user)
    if tid is None:
        raise_bad_request("Pick an agency first")
    manager_id = data.manager_user_id
    if current_user.role == CARE_MANAGER:
        manager_id = current_user.id
    elif manager_id is not None:
        manager_id = _manager_or_none(db, current_user, manager_id)
    elder = Elder(
        tenant_id=tid,
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        phone=data.phone,
        address=data.address,
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=data.emergency_contact_phone,
        medical_conditions=data.medical_conditions,
        status="ACTIVE",
        manager_user_id=manager_id,
    )
    db.add(elder)
    db.flush()
    if data.family:
        _add_family_login(db, current_user, elder, data.family)
    db.commit()
    db.refresh(elder)
    return _client_row(db, elder)


@router.get("/clients/{elder_id}/family-logins")
def list_family_logins(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    elder = _team_elder(db, current_user, elder_id)
    return _family_logins(db, elder.id)


@router.post("/clients/{elder_id}/family-logins", status_code=201)
def add_family_login(
    elder_id: int,
    data: FamilyLoginIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    elder = _team_elder(db, current_user, elder_id)
    _add_family_login(db, current_user, elder, data)
    db.commit()
    return _client_row(db, elder)


def _linked_login(db: Session, user: User, elder_id: int, user_id: int) -> User:
    """A family login that serves this client (link row or legacy users.elder_id); caller in team."""
    elder = _team_elder(db, user, elder_id)
    u = db.get(User, user_id)
    if not u or u.role != "ELDER_PORTAL" or u.id not in {x.id for x in _family_users_many(db, [elder.id])[elder.id]}:
        raise_not_found("Family login not found")
    return u


@router.put("/clients/{elder_id}/family-logins/{user_id}/password")
def reset_family_password(
    elder_id: int,
    user_id: int,
    data: PasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    u = _linked_login(db, current_user, elder_id, user_id)
    u.password_hash = hash_password(data.password)
    db.commit()
    return {"ok": True}


@router.put("/family-logins/{user_id}/password")
def reset_family_password_admin(
    user_id: int,
    data: PasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Older route, kept for admins only (the client page uses the per-client route)."""
    u = db.get(User, user_id)
    if not u or u.role != "ELDER_PORTAL":
        raise_not_found("Family login not found")
    assert_tenant_access(current_user, u.tenant_id)
    u.password_hash = hash_password(data.password)
    db.commit()
    return {"ok": True}


class LoginStatusIn(BaseModel):
    active: bool


@router.put("/clients/{elder_id}/family-logins/{user_id}/status")
def set_family_login_status(
    elder_id: int,
    user_id: int,
    data: LoginStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Deactivate (cannot sign in) or reactivate a family login. A login that also
    serves clients outside the caller's team can only be changed by an admin."""
    from app.core.team_scope import team_elder_ids
    from app.models.family_elder_link import FamilyElderLink

    u = _linked_login(db, current_user, elder_id, user_id)
    visible = team_elder_ids(db, current_user)
    if visible is not None:
        served = {r[0] for r in db.query(FamilyElderLink.elder_id).filter(FamilyElderLink.user_id == u.id).all()}
        if u.elder_id:
            served.add(u.elder_id)
        if served - visible:
            raise_bad_request("This login also serves another client outside your team. Ask an admin to change it.")
    u.status = "ACTIVE" if data.active else "INACTIVE"
    db.commit()
    return {"id": u.id, "active": u.status == "ACTIVE"}


# --- Email notifications (Settings → Email notifications) -------------------


def _tenant_for(db: Session, user: User):
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, user.tenant_id) if user.tenant_id else None
    if not tenant:
        raise_not_found("Agency not found")
    return tenant


def _email_settings(tenant) -> dict:
    from app.livewell import email_notifications as en

    return {
        **en.get_rules(tenant),
        "staff_events": en.STAFF_EVENTS,
        "family_events": en.FAMILY_EVENTS,
        "status": en.provider_status(),
    }


@router.get("/email-notifications")
def get_email_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return _email_settings(_tenant_for(db, current_user))


@router.put("/email-notifications")
def put_email_notifications(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.livewell.email_notifications import save_rules

    tenant = _tenant_for(db, current_user)
    save_rules(db, tenant, body)
    return _email_settings(tenant)


@router.get("/security-settings")
def get_security_settings(
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Settings -> Security: sessions never time out for inactivity (owner, 2026-10-26)."""
    return {"idle_timeout": False}


class TestEmailBody(BaseModel):
    to: EmailStr


@router.post("/email-notifications/test")
def test_email_notification(
    body: TestEmailBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.livewell.email_notifications import OPS_URL, provider_status, render_html
    from app.services.notifications import channel_config
    from app.services.notifications.factory import get_email_provider

    channel_config.clear_cache()
    text = f"This is a test from KushAlaya Ops, sent by {current_user.first_name or current_user.email}.\nIf you can read this, email notifications work."
    result = get_email_provider().send(
        to=str(body.to),
        subject="KushAlaya: Test email",
        body=text,
        html=render_html("Test email", text, link=OPS_URL, link_label="Open KushAlaya Ops"),
    )
    return {"sent_to": str(body.to), "ok": result.success, "detail": result.detail or "", **provider_status()}


# --- Email & SMS connections (Zoho SMTP / MSG91), platform-wide ---------------


@router.get("/channels")
def get_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.services.notifications import channel_config

    return {"email": channel_config.public_view("email", db), "sms": channel_config.public_view("sms", db)}


@router.get("/channels/status")
def get_channel_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Connected yes/no only (no secrets), so every staff role can see the
    "SOS SMS are OFF" warning on the Dashboard and Alerts."""
    from app.services.notifications import channel_config

    def on(kind: str) -> bool:
        v = channel_config.public_view(kind, db)
        return bool((v.get("enabled") and v.get("secret_set")) or v.get("env_configured"))

    return {"sms_connected": on("sms"), "email_connected": on("email")}


@router.put("/channels/{kind}")
def put_channel(
    kind: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.services.notifications import channel_config

    if kind not in channel_config.KEYS:
        raise_not_found("Unknown channel")
    if kind == "email" and body.get("port") not in (None, "") and int(body["port"]) not in (25, 465, 587, 2525):
        raise_bad_request("Port must be 587 (TLS) or 465 (SSL)")
    if kind == "sms" and body.get("sender_id") and len(str(body["sender_id"]).strip()) != 6:
        raise_bad_request("MSG91 sender ID is 6 letters (your DLT header)")
    return channel_config.save(kind, body, by=current_user.email, db=db)


class TestSmsBody(BaseModel):
    to: str = Field(min_length=10, max_length=15)


@router.post("/channels/sms/test")
def test_sms_channel(
    body: TestSmsBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.services.notifications import channel_config
    from app.services.notifications.factory import get_sms_provider

    channel_config.clear_cache()
    digits = "".join(ch for ch in body.to if ch.isdigit())[-10:]
    result = get_sms_provider().send(to=f"91{digits}", body="KushAlaya test SMS: your SMS connection works.")
    return {"ok": result.success, "detail": result.detail or ""}


# --- SOS escalation tree (Settings → Email notifications) --------------------


@router.get("/escalation")
def get_escalation_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.incident_service import escalation_tree

    return escalation_tree(db, current_user.tenant_id)


@router.put("/escalation")
def put_escalation_tree(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.livewell.incident_service import save_escalation_tree

    if not current_user.tenant_id:
        raise_bad_request("Choose an agency first")
    return save_escalation_tree(db, current_user.tenant_id, body)


@router.get("/care-team-contact")
def get_care_team_contact(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Phone + WhatsApp number families see on Home, Alerts and the header."""
    from app.livewell.care_team_contact import get_contact

    return get_contact(_tenant_for(db, current_user))


@router.put("/care-team-contact")
def put_care_team_contact(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    from app.livewell.care_team_contact import save_contact

    try:
        return save_contact(db, _tenant_for(db, current_user), body)
    except ValueError as exc:
        raise_bad_request(str(exc))
