"""Family portal access to one or more elders."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.responses import WorkforceHTTPError, raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.user import User


def ensure_family_elder_link(db: Session, user: User, elder: Elder, *, commit: bool = False) -> FamilyElderLink:
    """Ensure (user, elder) link exists. Optionally set active elder if user has none."""
    row = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == user.id, FamilyElderLink.elder_id == elder.id)
        .first()
    )
    if row is None:
        row = FamilyElderLink(user_id=user.id, elder_id=elder.id)
        db.add(row)
        db.flush()
    if user.elder_id is None:
        user.elder_id = elder.id
    if commit:
        db.commit()
        db.refresh(row)
    return row


def backfill_links_from_active(db: Session, user: User) -> None:
    """Create a link for user.elder_id when legacy users have no link rows yet."""
    if user.elder_id is None:
        return
    existing = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == user.id, FamilyElderLink.elder_id == user.elder_id)
        .first()
    )
    if existing is None:
        db.add(FamilyElderLink(user_id=user.id, elder_id=user.elder_id))
        db.flush()


def _same_tenant(user: User, elder: Elder | None) -> bool:
    """A link row must never reach across organizations, whatever created it."""
    if elder is None:
        return False
    if user.tenant_id is None:
        return False
    return elder.tenant_id == user.tenant_id


def list_linked_elders(db: Session, user: User) -> list[Elder]:
    backfill_links_from_active(db, user)
    rows = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == user.id)
        .order_by(FamilyElderLink.id.asc())
        .all()
    )
    if not rows and user.elder_id is not None:
        elder = db.query(Elder).filter(Elder.id == user.elder_id).first()
        return [elder] if _same_tenant(user, elder) else []
    elders: list[Elder] = []
    for row in rows:
        elder = db.query(Elder).filter(Elder.id == row.elder_id).first()
        if _same_tenant(user, elder):
            elders.append(elder)
    return elders


def links_for_elder(db: Session, elder_id: int) -> list[FamilyElderLink]:
    return (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.elder_id == elder_id)
        .order_by(FamilyElderLink.id.asc())
        .all()
    )


def primary_link_for_elder(db: Session, elder_id: int) -> FamilyElderLink | None:
    """The circle's primary member. Falls back to the oldest link and flags it,
    so households created before `is_primary` existed keep working."""
    rows = links_for_elder(db, elder_id)
    if not rows:
        return None
    for row in rows:
        if row.is_primary:
            return row
    rows[0].is_primary = True
    db.flush()
    return rows[0]


def is_primary_member(db: Session, user: User, elder: Elder) -> bool:
    primary = primary_link_for_elder(db, elder.id)
    if primary is not None:
        return primary.user_id == user.id
    # No link rows at all: the legacy single-login household — that login runs it.
    return user.elder_id == elder.id


def unlink_family_user(db: Session, member: User, elder: Elder, *, commit: bool = True) -> bool:
    """Remove a member's access to one elder.

    Also moves their active elder off it (or `backfill_links_from_active` would
    quietly recreate the link on the next request), and deactivates the login
    when no elder is left — a family account with nothing to see should not be
    able to sign in.
    """
    row = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == member.id, FamilyElderLink.elder_id == elder.id)
        .first()
    )
    if row is None and member.elder_id != elder.id:
        return False
    was_primary = bool(row and row.is_primary)
    if row is not None:
        db.delete(row)
        db.flush()
    remaining = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == member.id)
        .order_by(FamilyElderLink.id.asc())
        .all()
    )
    if member.elder_id == elder.id:
        member.elder_id = remaining[0].elder_id if remaining else None
    if not remaining:
        member.status = "INACTIVE"
    if was_primary:
        # Hand the circle to the next-oldest member rather than leaving it headless.
        primary_link_for_elder(db, elder.id)
    if commit:
        db.commit()
    return True


def find_family_user_for_elder(db: Session, elder_id: int) -> User | None:
    """First family-portal login linked to this client."""
    from app.core.rbac import ELDER_PORTAL

    links = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.elder_id == elder_id)
        .order_by(FamilyElderLink.id.asc())
        .all()
    )
    for link in links:
        user = (
            db.query(User)
            .filter(User.id == link.user_id, User.role == ELDER_PORTAL)
            .first()
        )
        if user:
            return user
    return (
        db.query(User)
        .filter(User.elder_id == elder_id, User.role == ELDER_PORTAL)
        .first()
    )


def user_can_access_elder(db: Session, user: User, elder_id: int) -> bool:
    backfill_links_from_active(db, user)
    if (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == user.id, FamilyElderLink.elder_id == elder_id)
        .first()
    ):
        return True
    return user.elder_id == elder_id


def resolve_active_elder(db: Session, user: User) -> Elder:
    """Active elder is users.elder_id, must be one of the linked elders."""
    backfill_links_from_active(db, user)
    elders = list_linked_elders(db, user)
    if not elders:
        raise_bad_request("No elder profile linked")

    if user.elder_id is not None:
        for e in elders:
            if e.id == user.elder_id:
                return e
        # Active id not in links — fall back to first linked
        user.elder_id = elders[0].id
        db.flush()
        return elders[0]

    user.elder_id = elders[0].id
    db.flush()
    return elders[0]


def set_active_elder(db: Session, user: User, elder_id: int) -> Elder:
    if not user_can_access_elder(db, user, elder_id):
        raise WorkforceHTTPError("Elder is not linked to this family account", status_code=403)
    elder = db.query(Elder).filter(Elder.id == elder_id).first()
    if not elder:
        raise_not_found("Elder profile not found")
    if user.tenant_id and elder.tenant_id != user.tenant_id:
        raise WorkforceHTTPError("Elder belongs to another organization", status_code=403)
    user.elder_id = elder.id
    db.commit()
    db.refresh(user)
    return elder


def elders_payload(db: Session, user: User) -> list[dict]:
    elders = list_linked_elders(db, user)
    active_id = user.elder_id
    out: list[dict] = []
    for e in elders:
        attrs = e.custom_attributes if isinstance(e.custom_attributes, dict) else {}
        sh = attrs.get("safe_home") if isinstance(attrs.get("safe_home"), dict) else {}
        safety = sh.get("safety_score") if isinstance(sh.get("safety_score"), dict) else {}
        out.append(
            {
                "id": e.id,
                "name": f"{e.first_name} {e.last_name}".strip(),
                "address": e.address,
                "is_active": e.id == active_id,
                "has_published_score": bool(
                    (safety.get("total") is not None and not safety.get("is_demo"))
                    or sh.get("improvement_plan")
                ),
                "score_total": safety.get("total"),
            }
        )
    return out
