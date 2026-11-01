"""Team scope: a Manager sees only their own team; Admins see everything.

A manager's clients are the ones assigned (ACTIVE) to caregivers who report to
them, plus clients whose `manager_user_id` is the manager (e.g. clients the
manager created before any caregiver was assigned).
"""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core.rbac import CARE_MANAGER, ELDER_PORTAL
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User


def is_scoped_manager(user: User) -> bool:
    return user.role == CARE_MANAGER


def team_caregiver_ids(db: Session, user: User) -> set[int] | None:
    """Caregiver ids the user may see; None means no restriction."""
    if not is_scoped_manager(user):
        return None
    rows = db.query(Caregiver.id).filter(Caregiver.manager_user_id == user.id).all()
    return {r[0] for r in rows}


def team_elder_ids(db: Session, user: User) -> set[int] | None:
    """Client (elder) ids the user may see; None means no restriction."""
    if not is_scoped_manager(user):
        return None
    cg_ids = team_caregiver_ids(db, user) or set()
    ids: set[int] = set()
    if cg_ids:
        ids |= {
            r[0]
            for r in db.query(Assignment.elder_id)
            .filter(Assignment.caregiver_id.in_(cg_ids), Assignment.status == "ACTIVE")
            .all()
        }
    ids |= {r[0] for r in db.query(Elder.id).filter(Elder.manager_user_id == user.id).all()}
    return ids


def team_user_ids(db: Session, user: User) -> set[int] | None:
    """User accounts whose activity the user may see; None means no restriction.

    A manager sees themselves, their caregivers' logins, and the family logins of
    their team's clients.
    """
    if not is_scoped_manager(user):
        return None
    from app.models.family_elder_link import FamilyElderLink

    ids: set[int] = {user.id}
    cg_ids = team_caregiver_ids(db, user) or set()
    if cg_ids:
        ids |= {r[0] for r in db.query(User.id).filter(User.caregiver_id.in_(cg_ids)).all()}
    elder_ids = team_elder_ids(db, user) or set()
    if elder_ids:
        ids |= {
            r[0]
            for r in db.query(User.id)
            .filter(User.role == ELDER_PORTAL, User.elder_id.in_(elder_ids))
            .all()
        }
        ids |= {
            r[0]
            for r in db.query(FamilyElderLink.user_id).filter(FamilyElderLink.elder_id.in_(elder_ids)).all()
        }
    return ids


def scope_elder_query(db: Session, user: User, query: Query, column=Elder.id) -> Query:
    """Restrict a query over clients (or rows keyed by elder id) to the user's team."""
    ids = team_elder_ids(db, user)
    if ids is None:
        return query
    return query.filter(column.in_(ids or {-1}))


def scope_caregiver_query(db: Session, user: User, query: Query) -> Query:
    if not is_scoped_manager(user):
        return query
    return query.filter(or_(Caregiver.manager_user_id == user.id))


def assert_elder_in_team(db: Session, user: User, elder_id: int) -> None:
    ids = team_elder_ids(db, user)
    if ids is not None and elder_id not in ids:
        raise HTTPException(status_code=404, detail="Client not found")


def assert_caregiver_in_team(db: Session, user: User, caregiver_id: int) -> None:
    ids = team_caregiver_ids(db, user)
    if ids is not None and caregiver_id not in ids:
        raise HTTPException(status_code=404, detail="Caregiver not found")


def assert_entity_in_team(db: Session, user: User, entity_type: str, entity_id: int) -> None:
    """Documents and similar records hang off a client or caregiver: apply that team rule."""
    kind = (entity_type or "").lower()
    if kind == "elder":
        assert_elder_in_team(db, user, entity_id)
    elif kind == "caregiver":
        assert_caregiver_in_team(db, user, entity_id)


def entity_in_team(db: Session, user: User, entity_type: str, entity_id: int) -> bool:
    try:
        assert_entity_in_team(db, user, entity_type, entity_id)
        return True
    except HTTPException:
        return False
