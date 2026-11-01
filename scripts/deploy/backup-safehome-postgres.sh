#!/usr/bin/env bash
# Config-driven PostgreSQL backup for SafeHome / LiveWell360.
#
# Config (first match wins for each var — already-exported env is kept):
#   /etc/workforceos/safehome.env
#   $APP_ROOT/backend/.env
#   CLI / environment overrides
#
# Usage:
#   sudo bash scripts/deploy/backup-safehome-postgres.sh
#   sudo BACKUP_FORMAT=custom bash scripts/deploy/backup-safehome-postgres.sh
#   sudo bash scripts/deploy/backup-safehome-postgres.sh --list
#
# See docs/deploy/POSTGRES_BACKUP.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=postgres-backup-lib.sh
source "$SCRIPT_DIR/postgres-backup-lib.sh"

LIST_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --list|-l) LIST_ONLY=1; shift ;;
    --help|-h)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) die "Unknown argument: $1" ;;
  esac
done

load_safehome_backup_config
ensure_backup_dir

if [[ "$LIST_ONLY" == "1" ]]; then
  echo "Backup directory: $BACKUP_DIR"
  ls -lah "$BACKUP_DIR" 2>/dev/null || echo "(empty)"
  exit 0
fi

DB_URL="$(resolve_database_url)"
DUMP="$(pg_dump_cmd)"
ts="$(date +%Y%m%d-%H%M%S)"
host="$(hostname -s 2>/dev/null || echo host)"

case "$BACKUP_FORMAT" in
  plain|sql)
    dest="${BACKUP_DIR}/${BACKUP_PREFIX}-${host}-${ts}.sql.gz"
    log "Dumping ${APP_DB_NAME} (plain SQL gzip) → $dest"
    "$DUMP" --dbname="$DB_URL" --format=plain --no-owner --no-acl \
      | gzip -c >"$dest.tmp"
    mv "$dest.tmp" "$dest"
    ;;
  custom|c)
    dest="${BACKUP_DIR}/${BACKUP_PREFIX}-${host}-${ts}.dump"
    log "Dumping ${APP_DB_NAME} (custom format) → $dest"
    "$DUMP" --dbname="$DB_URL" --format=custom --no-owner --no-acl --file="$dest.tmp"
    mv "$dest.tmp" "$dest"
    ;;
  *)
    die "BACKUP_FORMAT must be plain or custom (got: $BACKUP_FORMAT)"
    ;;
esac

chmod 640 "$dest" 2>/dev/null || true
if id "$APP_USER" &>/dev/null; then
  chown "$APP_USER:$APP_USER" "$dest" 2>/dev/null || true
fi

size="$(du -h "$dest" | awk '{print $1}')"
log "Backup OK ($size): $dest"

# Retention
if [[ "${BACKUP_RETENTION_DAYS}" =~ ^[0-9]+$ ]] && [[ "$BACKUP_RETENTION_DAYS" -gt 0 ]]; then
  log "Pruning backups older than ${BACKUP_RETENTION_DAYS} days in $BACKUP_DIR"
  find "$BACKUP_DIR" -type f \( -name "${BACKUP_PREFIX}-*.sql.gz" -o -name "${BACKUP_PREFIX}-*.dump" \) \
    -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete 2>/dev/null || true
fi

# Optional off-box copy (rsync/scp). Set BACKUP_OFFSITE_CMD to a shell snippet; $1 is the file path.
if [[ -n "${BACKUP_OFFSITE_CMD:-}" ]]; then
  log "Running offsite copy command"
  # shellcheck disable=SC2086
  bash -c "$BACKUP_OFFSITE_CMD" -- "$dest"
fi

echo "$dest"
