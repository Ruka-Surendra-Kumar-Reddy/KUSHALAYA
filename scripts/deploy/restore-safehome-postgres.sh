#!/usr/bin/env bash
# Restore SafeHome / LiveWell360 PostgreSQL from a backup created by
# backup-safehome-postgres.sh.
#
# Usage:
#   # List available backups
#   sudo bash scripts/deploy/restore-safehome-postgres.sh --list
#
#   # Restore latest backup (interactive confirm)
#   sudo bash scripts/deploy/restore-safehome-postgres.sh
#
#   # Restore a specific file (skip prompt with --yes)
#   sudo bash scripts/deploy/restore-safehome-postgres.sh --file /var/backups/safehomeops/postgres/safehomeops-….sql.gz --yes
#
#   # Also re-run migrations after restore
#   sudo bash scripts/deploy/restore-safehome-postgres.sh --yes --migrate
#
# WARNING: This replaces the current database contents for APP_DB_NAME.
# See docs/deploy/POSTGRES_BACKUP.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=postgres-backup-lib.sh
source "$SCRIPT_DIR/postgres-backup-lib.sh"

FILE=""
YES=0
LIST_ONLY=0
RUN_MIGRATE=0
KEEP_API=0

usage() {
  sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file|-f) FILE="${2:-}"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --list|-l) LIST_ONLY=1; shift ;;
    --migrate) RUN_MIGRATE=1; shift ;;
    --keep-api) KEEP_API=1; shift ;;
    --help|-h) usage ;;
    *) die "Unknown argument: $1 (try --help)" ;;
  esac
done

load_safehome_backup_config
ensure_backup_dir

latest_backup() {
  local newest=""
  local f
  # Portable: compare mtime via ls -t (GNU/BSD)
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    newest="$f"
    break
  done < <(ls -1t "$BACKUP_DIR"/${BACKUP_PREFIX}-*.sql.gz "$BACKUP_DIR"/${BACKUP_PREFIX}-*.dump 2>/dev/null || true)
  echo "$newest"
}

if [[ "$LIST_ONLY" == "1" ]]; then
  echo "Backup directory: $BACKUP_DIR"
  if [[ -d "$BACKUP_DIR" ]]; then
    ls -lah "$BACKUP_DIR"/${BACKUP_PREFIX}-*.{sql.gz,dump} 2>/dev/null || echo "(no backups found)"
  else
    echo "(directory missing)"
  fi
  exit 0
fi

if [[ -z "$FILE" ]]; then
  FILE="$(latest_backup || true)"
fi
[[ -n "$FILE" && -f "$FILE" ]] || die "No backup file found. Pass --file PATH or run a backup first."

DB_URL="$(resolve_database_url)"
PSQL="$(psql_cmd)"

echo ""
echo "About to RESTORE PostgreSQL database '${APP_DB_NAME}'"
echo "  From: $FILE"
echo "  URL:  postgresql://${APP_DB_USER}:****@…/${APP_DB_NAME}"
echo "  API:  $([ "$KEEP_API" == "1" ] && echo keep running || echo stop safehomeops-api during restore)"
echo ""
if [[ "$YES" != "1" ]]; then
  read -r -p "Type RESTORE to continue: " confirm
  [[ "$confirm" == "RESTORE" ]] || die "Aborted"
fi

require_root

api_was_active=0
if [[ "$KEEP_API" != "1" ]] && [[ "${BACKUP_STOP_API}" == "1" ]]; then
  if systemctl is-active --quiet safehomeops-api 2>/dev/null; then
    api_was_active=1
    log "Stopping safehomeops-api"
    systemctl stop safehomeops-api
  fi
fi

restore_plain() {
  local path=$1
  log "Dropping and recreating database ${APP_DB_NAME}"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${APP_DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${APP_DB_NAME};
CREATE DATABASE ${APP_DB_NAME} OWNER ${APP_DB_USER};
SQL
  log "Loading plain SQL dump"
  if [[ "$path" == *.gz ]]; then
    gunzip -c "$path" | sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$APP_DB_NAME"
  else
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$APP_DB_NAME" -f "$path"
  fi
}

restore_custom() {
  local path=$1
  local restore
  restore="$(pg_restore_cmd)"
  log "Dropping and recreating database ${APP_DB_NAME}"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${APP_DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${APP_DB_NAME};
CREATE DATABASE ${APP_DB_NAME} OWNER ${APP_DB_USER};
SQL
  log "Loading custom-format dump with pg_restore"
  # --no-owner so objects are owned by the restoring role / DB owner
  "$restore" --dbname="$DB_URL" --no-owner --no-acl --exit-on-error "$path" \
    || "$restore" --dbname="postgresql://${APP_DB_USER}@127.0.0.1:5432/${APP_DB_NAME}" \
         --no-owner --no-acl --exit-on-error "$path"
}

case "$FILE" in
  *.sql.gz|*.sql)
    restore_plain "$FILE"
    ;;
  *.dump)
    restore_custom "$FILE"
    ;;
  *)
    die "Unrecognized backup extension (expected .sql.gz, .sql, or .dump): $FILE"
    ;;
esac

# Ensure ownership for app role (plain dumps may create objects as postgres)
log "Re-granting ownership to ${APP_DB_USER}"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$APP_DB_NAME" -c \
  "ALTER DATABASE ${APP_DB_NAME} OWNER TO ${APP_DB_USER};" || true
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$APP_DB_NAME" <<SQL || true
DO \$\$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO ${APP_DB_USER}';
  END LOOP;
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP
    EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO ${APP_DB_USER}';
  END LOOP;
END
\$\$;
SQL

if [[ "$RUN_MIGRATE" == "1" ]]; then
  log "Running python -m app.init_db as ${APP_USER}"
  sudo -u "$APP_USER" -H bash -lc "
    cd '${APP_ROOT}/backend'
    source .venv/bin/activate
    export WORKFORCEOS_CORE=\"\${WORKFORCEOS_CORE:-/opt/workforceos-core}\"
    python -m app.init_db
  "
fi

if [[ "$api_was_active" == "1" ]]; then
  log "Starting safehomeops-api"
  systemctl start safehomeops-api
fi

log "Restore complete from $FILE"
echo ""
echo "Verify:"
echo "  curl -fsS http://127.0.0.1:${API_PORT:-8010}/health"
echo "  sudo -u postgres psql -d ${APP_DB_NAME} -c '\\dt'"
echo ""
echo "Note: photo/files under ${UPLOADS_DIR} are not in the DB dump — restore those separately if needed."
