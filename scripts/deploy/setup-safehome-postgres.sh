#!/usr/bin/env bash
# Create SafeHomeOps PostgreSQL role and database on an existing OL9 VM.
# Run as root after bootstrap-ol9.sh (PostgreSQL already installed):
#
#   sudo SAFEHOME_DB_PASSWORD="$(openssl rand -base64 24)" bash scripts/deploy/setup-safehome-postgres.sh
#
# Does not clone repos or start services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=workforceos-deploy-lib.sh
source "$SCRIPT_DIR/workforceos-deploy-lib.sh"

SH_DB_USER="${SH_DB_USER:-safehomeops}"
SH_DB_NAME="${SH_DB_NAME:-safehomeops}"
SH_DB_PASSWORD="${SAFEHOME_DB_PASSWORD:-${SH_DB_PASSWORD:-}}"
PRESERVE_DB_PASSWORD="${PRESERVE_DB_PASSWORD:-0}"

require_root

role_and_db_exist() {
  postgres_role_exists "$SH_DB_USER" && postgres_database_exists "$SH_DB_NAME"
}

if [[ -z "$SH_DB_PASSWORD" ]]; then
  if role_and_db_exist; then
    log "Role ${SH_DB_USER} and database ${SH_DB_NAME} already exist — continuing without password"
    PRESERVE_DB_PASSWORD=1
  else
    echo "Set SAFEHOME_DB_PASSWORD before running, e.g.:"
    echo "  sudo SAFEHOME_DB_PASSWORD=\$(openssl rand -base64 24) bash $0"
    echo ""
    echo "If you created the role/DB manually, set PRESERVE_DB_PASSWORD=1 instead."
    exit 1
  fi
fi

export PRESERVE_DB_PASSWORD

echo "==> SafeHomeOps PostgreSQL prep (idempotent)"

ensure_safehomeops_user
configure_workforceos_core_permissions /opt/workforceos-core
if [[ "${SKIP_DB_SETUP:-0}" != "1" ]]; then
  ensure_postgres_role_db "$SH_DB_USER" "$SH_DB_NAME" "$SH_DB_PASSWORD"
  configure_pg_hba_apps
else
  log "SKIP_DB_SETUP=1 — PostgreSQL role/database left unchanged"
fi

echo ""
echo "SafeHomeOps PostgreSQL connection string:"
echo "  postgresql://${SH_DB_USER}:<password>@127.0.0.1:5432/${SH_DB_NAME}"
echo ""
echo "Next: set DATABASE_URL in backend/.env, then python -m app.init_db"
echo "  sudo bash scripts/deploy/deploy-safehome.sh   # full VM deploy"
