"""Wipe all operational data, keep configuration and a short list of staff logins.

Owner request 2026-11-01: "clear everything in prod except Krishna, Bharani,
Chandhan and Raju". Configuration stays (tenants, catalog, vendors, rubric,
settings, plans, blog, contract templates, IoT hubs); people and activity go
(clients, families, caregivers, prospects, visits, assessments, incidents,
wallets, documents and their files, messages, sessions, alerts, audit noise).

Always three steps, never one:

    python scripts/reset_prod_keep_staff.py --list-users
    python scripts/reset_prod_keep_staff.py --keep a@x,b@y,c@z,d@w --dry-run
    python scripts/reset_prod_keep_staff.py --keep a@x,b@y,c@z,d@w --apply --i-have-a-backup

Run on the server as safehomeops from backend/ with the .env sourced and
PYTHONPATH=. (see docs/deploy/PROD_RESET.md). --apply refuses without a backup
flag and the environment variable CONFIRM=RESET-PROD.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import func, inspect, select, text

from app.core.database import Base, SessionLocal
from app.core.deploy import deploy_vertical
from app.models.packs import ensure_models_registered

ensure_models_registered(deploy_vertical())

# Tables whose rows are configuration and survive the reset.
KEEP_TABLES = {
    "tenants",
    "users",  # filtered: only the --keep emails survive
    "app_global_settings",
    "skills",
    "subscription_plans",
    "tenant_subscriptions",
    "subscription_invoices",
    "invoice_counters",
    "coupons",
    "products",
    "vendors",
    "contract_templates",
    "family_questions",
    "blog_posts",
    "blog_images",
    "background_jobs",
    "iot_hubs",
    "iot_devices",  # kept but unassigned from the deleted clients
}

# Columns on kept tables that point at a client and must be cleared.
UNASSIGN = {("iot_devices", "elder_id")}


def _tables():
    return list(reversed(Base.metadata.sorted_tables))


def _count(db, table) -> int:
    return int(db.execute(select(func.count()).select_from(table)).scalar() or 0)


def list_users(db) -> None:
    users = Base.metadata.tables["users"]
    tenants = Base.metadata.tables["tenants"]
    rows = db.execute(
        select(users.c.id, users.c.tenant_id, users.c.email, users.c.first_name, users.c.last_name, users.c.role, users.c.status)
        .order_by(users.c.tenant_id, users.c.role, users.c.id)
    ).all()
    names = {r.id: r.name for r in db.execute(select(tenants.c.id, tenants.c.name)).all()}
    print(f"{'id':>4}  {'tenant':<22} {'role':<14} {'status':<9} email  (name)")
    for r in rows:
        print(f"{r.id:>4}  {str(names.get(r.tenant_id, r.tenant_id)):<22} {r.role:<14} {r.status:<9} {r.email}  ({r.first_name} {r.last_name})")
    print(f"\n{len(rows)} users. Pick the ones to KEEP and pass their emails to --keep.")


def plan(db, keep_emails: list[str]) -> tuple[list[int], list[tuple[str, int]], list]:
    users = Base.metadata.tables["users"]
    found = db.execute(
        select(users.c.id, users.c.email).where(func.lower(users.c.email).in_([e.lower() for e in keep_emails]))
    ).all()
    missing = set(e.lower() for e in keep_emails) - {r.email.lower() for r in found}
    if missing:
        sys.exit(f"ABORT: these --keep emails do not exist: {sorted(missing)}")
    keep_ids = [r.id for r in found]

    counts: list[tuple[str, int]] = []
    for t in _tables():
        n = _count(db, t)
        if t.name == "users":
            doomed = int(db.execute(select(func.count()).select_from(users).where(users.c.id.not_in(keep_ids))).scalar() or 0)
            counts.append(("users (delete)", doomed))
        elif t.name not in KEEP_TABLES and n:
            counts.append((t.name, n))
    doomed_users = db.execute(
        select(users.c.id, users.c.email, users.c.role).where(users.c.id.not_in(keep_ids)).order_by(users.c.id)
    ).all()
    return keep_ids, counts, doomed_users


def apply(db, keep_ids: list[int]) -> None:
    from app.core.storage import get_storage

    meta = Base.metadata
    users = meta.tables["users"]
    documents = meta.tables["documents"]

    # 1. files first, while the rows still tell us the keys
    storage = get_storage()
    keys = [r[0] for r in db.execute(select(documents.c.storage_key)).all() if r[0]]
    removed = 0
    for key in keys:
        try:
            storage.delete(key)
            removed += 1
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            print(f"  file not removed {key}: {exc}")
    print(f"  files removed: {removed}/{len(keys)}")

    # 2. detach kept rows from doomed users / clients so FKs do not block
    first_keep = keep_ids[0]
    for t in meta.sorted_tables:
        if t.name not in KEEP_TABLES or t.name == "users":
            continue
        for col in t.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name == "users":
                    if col.nullable:
                        db.execute(t.update().where(col.not_in(keep_ids)).values({col.name: None}))
                    else:
                        db.execute(t.update().where(col.not_in(keep_ids)).values({col.name: first_keep}))
                if (t.name, col.name) in UNASSIGN:
                    db.execute(t.update().values({col.name: None}))

    # 3. data tables, children before parents
    for t in _tables():
        if t.name in KEEP_TABLES:
            continue
        db.execute(t.delete())

    # 4. users: everyone except the keep list; clear their own back-references first
    db.execute(users.update().values(elder_id=None, caregiver_id=None))
    db.execute(users.delete().where(users.c.id.not_in(keep_ids)))

    # 5. the hub JSON lives on elders, which are gone; nothing else to scrub.
    db.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-users", action="store_true")
    ap.add_argument("--keep", default="", help="comma-separated emails to keep")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--i-have-a-backup", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.list_users:
            list_users(db)
            return
        keep = [e.strip() for e in args.keep.split(",") if e.strip()]
        if not keep:
            sys.exit("--keep is required (or use --list-users first)")
        keep_ids, counts, doomed = plan(db, keep)
        print(f"KEEP users: {keep_ids} <- {keep}")
        print("DELETE rows:")
        for name, n in counts:
            print(f"  {name:<36} {n:>8}")
        print(f"DELETE users ({len(doomed)}):")
        for r in doomed:
            print(f"  {r.id:>4} {r.role:<14} {r.email}")
        print("KEEP tables untouched:", ", ".join(sorted(KEEP_TABLES - {'users'})))
        if not args.apply:
            print("\nDry run only. Nothing changed.")
            return
        if not args.i_have_a_backup or os.environ.get("CONFIRM") != "RESET-PROD":
            sys.exit("Refusing: --apply needs --i-have-a-backup and CONFIRM=RESET-PROD in the environment.")
        if inspect(db.get_bind()).dialect.name != "postgresql":
            print("note: not PostgreSQL, continuing anyway")
        apply(db, keep_ids)
        print("\nDone. Re-run with --dry-run to confirm the counts are zero.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
