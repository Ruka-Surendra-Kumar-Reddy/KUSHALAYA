"""Remove SafeHome demo seed users (and optionally clients / super admin).

Usage:
  python -m app.purge_safehome_seed --confirm
  python -m app.purge_safehome_seed --confirm --include-clients
  python -m app.purge_safehome_seed --confirm --include-super-admin
  python -m app.purge_safehome_seed --confirm --include-clients --include-super-admin

Default removes tenant staff, family portal, and assessor login accounts created by
`python -m app.seed_safehome`. Does not delete the tenant row or master-data config.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_constants import (
    ASSESSOR_EMAIL,
    FAMILY_EMAILS,
    LEGACY_SUPER_ADMIN_EMAILS,
    SEED_CLIENTS,
    SEED_USER_EMAILS,
    SUPER_ADMIN_EMAIL,
    TENANT_NAME,
    LEGACY_TENANT_NAMES,
)


def _resolve_seed_tenant(db: Session) -> Tenant | None:
    tenant = db.query(Tenant).filter(Tenant.name == TENANT_NAME).first()
    if tenant:
        return tenant
    for name in LEGACY_TENANT_NAMES:
        tenant = db.query(Tenant).filter(Tenant.name == name).first()
        if tenant:
            return tenant
    return (
        db.query(Tenant)
        .filter(Tenant.vertical == "LIVEWELL360")
        .order_by(Tenant.id)
        .first()
    )


def _emails_to_purge(*, include_super_admin: bool) -> list[str]:
    emails = list(SEED_USER_EMAILS)
    if include_super_admin:
        emails.append(SUPER_ADMIN_EMAIL)
        emails.extend(LEGACY_SUPER_ADMIN_EMAILS)
    # De-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for email in emails:
        if email not in seen:
            seen.add(email)
            out.append(email)
    return out


def purge_safehome_seed(
    db: Session,
    *,
    include_clients: bool = False,
    include_super_admin: bool = False,
) -> dict:
    emails = _emails_to_purge(include_super_admin=include_super_admin)
    deleted_users: list[str] = []
    skipped_users: list[str] = []

    users = db.query(User).filter(User.email.in_(emails)).all()
    found = {u.email for u in users}
    for email in emails:
        if email not in found:
            skipped_users.append(email)

    # Clear staff links before deleting assessor caregiver / clients
    for user in users:
        user.elder_id = None
        user.caregiver_id = None
    db.flush()

    for user in users:
        deleted_users.append(user.email)
        db.delete(user)
    db.flush()

    deleted_clients: list[str] = []
    deleted_assessors: list[str] = []

    if include_clients:
        tenant = _resolve_seed_tenant(db)
        if tenant:
            for first_name, last_name in SEED_CLIENTS:
                # Drop any remaining portal users still pointing at these clients
                elders = (
                    db.query(Elder)
                    .filter(
                        Elder.tenant_id == tenant.id,
                        Elder.first_name == first_name,
                        Elder.last_name == last_name,
                    )
                    .all()
                )
                for elder in elders:
                    linked = (
                        db.query(User).filter(User.elder_id == elder.id).all()
                    )
                    for u in linked:
                        if u.email not in deleted_users:
                            deleted_users.append(u.email)
                        db.delete(u)
                    db.flush()
                    deleted_clients.append(f"{elder.first_name} {elder.last_name}#{elder.id}")
                    db.delete(elder)

            assessors = (
                db.query(Caregiver)
                .filter(
                    Caregiver.tenant_id == tenant.id,
                    Caregiver.email == ASSESSOR_EMAIL,
                )
                .all()
            )
            if not assessors:
                assessors = (
                    db.query(Caregiver)
                    .filter(
                        Caregiver.tenant_id == tenant.id,
                        Caregiver.first_name == "Anita",
                        Caregiver.last_name == "Devi",
                    )
                    .all()
                )
            for caregiver in assessors:
                linked = (
                    db.query(User)
                    .filter(User.caregiver_id == caregiver.id)
                    .all()
                )
                for u in linked:
                    if u.email not in deleted_users:
                        deleted_users.append(u.email)
                    db.delete(u)
                db.flush()
                deleted_assessors.append(
                    f"{caregiver.first_name} {caregiver.last_name}#{caregiver.id}"
                )
                db.delete(caregiver)

    db.commit()
    return {
        "deleted_users": sorted(set(deleted_users)),
        "missing_users": skipped_users,
        "deleted_clients": deleted_clients,
        "deleted_assessors": deleted_assessors,
        "family_emails": list(FAMILY_EMAILS),
        "include_clients": include_clients,
        "include_super_admin": include_super_admin,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove SafeHome seed users created by app.seed_safehome",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required safety flag — without this the command refuses to run",
    )
    parser.add_argument(
        "--include-clients",
        action="store_true",
        help="Also delete seeded clients (Lakshmi, Padmaja) and assessor caregiver row",
    )
    parser.add_argument(
        "--include-super-admin",
        action="store_true",
        help=f"Also delete {SUPER_ADMIN_EMAIL}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without writing",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("Error: pass --confirm to purge seed users", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if args.dry_run:
            emails = _emails_to_purge(include_super_admin=args.include_super_admin)
            existing = [
                u.email
                for u in db.query(User).filter(User.email.in_(emails)).order_by(User.email)
            ]
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "would_delete_users": existing,
                        "include_clients": args.include_clients,
                        "include_super_admin": args.include_super_admin,
                    },
                    indent=2,
                )
            )
            return 0

        result = purge_safehome_seed(
            db,
            include_clients=args.include_clients,
            include_super_admin=args.include_super_admin,
        )
        print(json.dumps(result, indent=2))
        print(
            f"Removed {len(result['deleted_users'])} user(s). "
            "Re-seed with: python -m app.seed_safehome"
        )
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
