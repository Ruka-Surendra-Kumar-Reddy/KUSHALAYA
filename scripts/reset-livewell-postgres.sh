#!/usr/bin/env bash
# Full reset of local LiveWell360 / SafeHomeOps Postgres DB, then init + seed.
#
# Usage (stop API first):
#   export PGPASSWORD='postgres_superuser_password'   # if needed
#   export APP_DB_PASSWORD='your_app_db_password'
#   bash scripts/reset-livewell-postgres.sh
#
# By default seed_livewell ALSO loads master data from LiveWell360_Configuration.xlsx
# (rubric, catalog, solutions, …). That is why Catalog shows products after reset.
#
# For empty master data (test Upload + Approve):
#   SKIP_MASTER_SEED=1 APP_DB_PASSWORD='...' bash scripts/reset-livewell-postgres.sh
#
# Optional overrides:
#   APP_DB_NAME APP_DB_USER APP_DB_PASSWORD PGHOST PGPORT PG_SUPERUSER BACKEND_DIR DEPLOY_VERTICAL
#   SKIP_MASTER_SEED=1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$ROOT_DIR/backend}"

APP_DB_NAME="${APP_DB_NAME:-safehomeops}"
APP_DB_USER="${APP_DB_USER:-safehomeops}"
APP_DB_PASSWORD="${APP_DB_PASSWORD:-}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"
DEPLOY_VERTICAL="${DEPLOY_VERTICAL:-LIVEWELL360}"
SKIP_MASTER_SEED="${SKIP_MASTER_SEED:-0}"

if [[ -z "${APP_DB_PASSWORD}" ]]; then
  echo "Error: set APP_DB_PASSWORD (app role password for ${APP_DB_USER})." >&2
  echo "  Example: APP_DB_PASSWORD='...' bash scripts/reset-livewell-postgres.sh" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "Error: psql not found on PATH." >&2
  exit 1
fi

if [[ ! -d "$BACKEND_DIR" ]]; then
  echo "Error: backend dir not found: $BACKEND_DIR" >&2
  exit 1
fi

export DATABASE_URL="postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@${PGHOST}:${PGPORT}/${APP_DB_NAME}"
export DEPLOY_VERTICAL

echo "==> Terminating connections to ${APP_DB_NAME}"
psql -h "$PGHOST" -p "$PGPORT" -U "$PG_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${APP_DB_NAME}' AND pid <> pg_backend_pid();" \
  || true

echo "==> DROP DATABASE ${APP_DB_NAME}"
psql -h "$PGHOST" -p "$PGPORT" -U "$PG_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${APP_DB_NAME};"

echo "==> CREATE DATABASE ${APP_DB_NAME} OWNER ${APP_DB_USER}"
psql -h "$PGHOST" -p "$PGPORT" -U "$PG_SUPERUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE ${APP_DB_NAME} OWNER ${APP_DB_USER};"

echo "==> init_db + seed_livewell in ${BACKEND_DIR}"
cd "$BACKEND_DIR"

if [[ -f .venv/bin/activate ]]; then
  # Linux / macOS / Git Bash (Unix layout)
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f .venv/Scripts/activate ]]; then
  # Git Bash on Windows
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
fi

python -m app.init_db
python -m app.seed_livewell

if [[ "${SKIP_MASTER_SEED}" == "1" || "${SKIP_MASTER_SEED}" == "true" ]]; then
  echo "==> Clearing master data (workflow_config) for Upload-first testing"
  python - <<'PY'
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SessionLocal
from app.models.tenant import Tenant

db = SessionLocal()
try:
    for tenant in db.query(Tenant).all():
        tenant.workflow_config = {}
        flag_modified(tenant, "workflow_config")
        print(f"  cleared workflow_config for tenant {tenant.id} ({tenant.name})")
    db.commit()
finally:
    db.close()
PY
  echo "    Master data is empty — use Master Data → Upload / Stage factory → Approve"
else
  echo "==> Master data was seeded from LiveWell360_Configuration.xlsx (catalog expected)."
  echo "    To start empty next time: SKIP_MASTER_SEED=1 APP_DB_PASSWORD=... bash scripts/reset-livewell-postgres.sh"
fi

echo "==> Done."
echo "    DATABASE_URL=postgresql://${APP_DB_USER}:***@${PGHOST}:${PGPORT}/${APP_DB_NAME}"
echo "    Login: admin@sunrise-care.example / demo1234"
echo "    Use a private window (clear old JWT / localStorage)."
echo "    Note: Catalog UI may still show frontend factory defaults until API returns []; check Master Data sync banner."
