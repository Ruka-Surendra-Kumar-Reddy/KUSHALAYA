"""Delete a tenant (including protected demo) and re-seed Sunrise demo data.

Usage:
  python -m app.reset_sunrise_demo --confirm-name "Sunrise Elder Care"

Delete only (no re-seed):
  python -m app.delete_tenant --id 1 --confirm-name "Sunrise Elder Care" --allow-protected
"""

import argparse
import json
import sys

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.seed_care_admin import SUNRISE_TENANT_NAME
from app.services.tenant_purge_service import TenantPurgeService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete Sunrise Elder Care tenant and re-seed demo data",
    )
    parser.add_argument(
        "--confirm-name",
        required=True,
        help=f'Must exactly match "{SUNRISE_TENANT_NAME}"',
    )
    parser.add_argument(
        "--id",
        type=int,
        default=None,
        help="Tenant id (default: lookup by Sunrise name)",
    )
    parser.add_argument(
        "--no-reseed",
        action="store_true",
        help="Delete tenant only; do not run seed_care_demo afterward",
    )
    args = parser.parse_args()

    if args.confirm_name != SUNRISE_TENANT_NAME:
        print(
            f'Error: confirm-name must be exactly "{SUNRISE_TENANT_NAME}"',
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        tenant = None
        if args.id is not None:
            tenant = db.query(Tenant).filter(Tenant.id == args.id).first()
        else:
            tenant = db.query(Tenant).filter(Tenant.name == SUNRISE_TENANT_NAME).first()

        if tenant:
            result = TenantPurgeService.delete_tenant(
                db,
                tenant.id,
                args.confirm_name,
                allow_protected=True,
            )
            print("Tenant deleted:")
            print(json.dumps(result, indent=2))
        else:
            print(f'No tenant named "{SUNRISE_TENANT_NAME}" — skipping delete.')
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    if args.no_reseed:
        return 0

    from app.seed_care_demo import seed_care_demo

    seed_care_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
