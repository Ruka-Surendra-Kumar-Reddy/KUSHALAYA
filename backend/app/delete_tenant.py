"""Remove a pilot/test tenant and all its data.

Usage:
  python -m app.delete_tenant --id 5 --confirm-name "Pilot Agency Demo"
  python -m app.delete_tenant --id 1 --confirm-name "Sunrise Elder Care" --allow-protected
"""

import argparse
import json
import sys

from app.core.database import SessionLocal
from app.services.tenant_purge_service import TenantPurgeService


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete a tenant and all tenant data")
    parser.add_argument("--id", type=int, required=True, help="Tenant id")
    parser.add_argument(
        "--confirm-name",
        required=True,
        help="Exact tenant name (safety check)",
    )
    parser.add_argument(
        "--allow-protected",
        action="store_true",
        help="Allow deleting protected demo tenants (e.g. Sunrise Elder Care)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = TenantPurgeService.delete_tenant(
            db,
            args.id,
            args.confirm_name,
            allow_protected=args.allow_protected,
        )
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
