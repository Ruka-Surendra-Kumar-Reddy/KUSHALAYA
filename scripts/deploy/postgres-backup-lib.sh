#!/usr/bin/env bash
# Shared helpers for SafeHome / LiveWell360 PostgreSQL backup & restore.
# Sourced by backup-safehome-postgres.sh / restore-safehome-postgres.sh / install cron.

set -euo pipefail

POSTGRES_BACKUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

require_root() {
  [[ $EUID -eq 0 ]] || die "Run as root (sudo)"
}

# Load KEY=VALUE from a file without executing it (skips comments / blanks).
_load_env_file() {
  local file=$1
  [[ -f "$file" ]] || return 0
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    key="${key#"${key%%[![:space:]]*}"}"
    # Strip optional surrounding quotes
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    # Do not override already-exported vars
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done <"$file"
}

load_safehome_backup_config() {
  local env_file="${SAFEHOME_ENV_FILE:-/etc/workforceos/safehome.env}"
  local app_root="${APP_ROOT:-/opt/safehomeops/app}"
  local backend_env="${BACKEND_ENV_FILE:-$app_root/backend/.env}"

  _load_env_file "$env_file"
  _load_env_file "$backend_env"

  : "${APP_ROOT:=/opt/safehomeops/app}"
  : "${APP_USER:=safehomeops}"
  : "${APP_DB_USER:=safehomeops}"
  : "${APP_DB_NAME:=safehomeops}"
  : "${BACKUP_DIR:=/var/backups/safehomeops/postgres}"
  : "${BACKUP_RETENTION_DAYS:=14}"
  : "${BACKUP_FORMAT:=plain}" # plain | custom
  : "${BACKUP_PREFIX:=safehomeops}"
  : "${BACKUP_CRON_SCHEDULE:=15 2 * * *}"
  : "${BACKUP_STOP_API:=1}" # restore only: stop safehomeops-api during restore
  : "${UPLOADS_DIR:=/var/lib/safehomeops/uploads}"

  # Prefer explicit DATABASE_URL; else build from APP_DB_* if password is known.
  if [[ -z "${DATABASE_URL:-}" && -n "${APP_DB_PASSWORD:-}" && "${APP_DB_PASSWORD}" != CHANGE_ME_* ]]; then
    DATABASE_URL="postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@127.0.0.1:5432/${APP_DB_NAME}"
  fi
  export DATABASE_URL APP_ROOT APP_USER APP_DB_USER APP_DB_NAME
  export BACKUP_DIR BACKUP_RETENTION_DAYS BACKUP_FORMAT BACKUP_PREFIX
  export BACKUP_CRON_SCHEDULE BACKUP_STOP_API UPLOADS_DIR
}

resolve_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    echo "$DATABASE_URL"
    return 0
  fi
  die "DATABASE_URL not set. Set it in backend/.env or APP_DB_* in /etc/workforceos/safehome.env"
}

ensure_backup_dir() {
  mkdir -p "$BACKUP_DIR"
  if id "$APP_USER" &>/dev/null; then
    chown -R "$APP_USER:$APP_USER" "$BACKUP_DIR" 2>/dev/null || true
  fi
  chmod 750 "$BACKUP_DIR" 2>/dev/null || true
}

pg_dump_cmd() {
  if command -v pg_dump >/dev/null 2>&1; then
    echo pg_dump
  elif [[ -x /usr/bin/pg_dump ]]; then
    echo /usr/bin/pg_dump
  else
    die "pg_dump not found (install postgresql client tools)"
  fi
}

pg_restore_cmd() {
  if command -v pg_restore >/dev/null 2>&1; then
    echo pg_restore
  elif [[ -x /usr/bin/pg_restore ]]; then
    echo /usr/bin/pg_restore
  else
    die "pg_restore not found"
  fi
}

psql_cmd() {
  if command -v psql >/dev/null 2>&1; then
    echo psql
  elif [[ -x /usr/bin/psql ]]; then
    echo /usr/bin/psql
  else
    die "psql not found"
  fi
}
