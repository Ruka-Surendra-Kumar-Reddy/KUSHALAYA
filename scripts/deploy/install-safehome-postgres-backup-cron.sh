#!/usr/bin/env bash
# Install (or remove) a daily cron job that runs backup-safehome-postgres.sh.
#
# Usage:
#   sudo bash scripts/deploy/install-safehome-postgres-backup-cron.sh
#   sudo bash scripts/deploy/install-safehome-postgres-backup-cron.sh --remove
#
# Schedule / paths come from /etc/workforceos/safehome.env (see BACKUP_* vars).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=postgres-backup-lib.sh
source "$SCRIPT_DIR/postgres-backup-lib.sh"

REMOVE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove) REMOVE=1; shift ;;
    --help|-h)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_root
load_safehome_backup_config

# Prefer the copy under APP_ROOT so cron survives after git pull on the app.
BACKUP_SCRIPT="${APP_ROOT}/scripts/deploy/backup-safehome-postgres.sh"
if [[ ! -x "$BACKUP_SCRIPT" && ! -f "$BACKUP_SCRIPT" ]]; then
  BACKUP_SCRIPT="${SCRIPT_DIR}/backup-safehome-postgres.sh"
fi
[[ -f "$BACKUP_SCRIPT" ]] || die "Backup script not found at $BACKUP_SCRIPT"

CRON_FILE="/etc/cron.d/safehomeops-postgres-backup"
LOG_FILE="/var/log/safehomeops-postgres-backup.log"

if [[ "$REMOVE" == "1" ]]; then
  rm -f "$CRON_FILE"
  log "Removed $CRON_FILE"
  exit 0
fi

ensure_backup_dir
touch "$LOG_FILE"
chmod 640 "$LOG_FILE"
if id "$APP_USER" &>/dev/null; then
  chown root:"$APP_USER" "$LOG_FILE" 2>/dev/null || true
fi

chmod +x "$BACKUP_SCRIPT" \
  "${APP_ROOT}/scripts/deploy/restore-safehome-postgres.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/backup-safehome-postgres.sh" \
  "$SCRIPT_DIR/restore-safehome-postgres.sh" 2>/dev/null || true

# cron.d requires a user field; run as root so peer/postgres helpers work.
cat >"$CRON_FILE" <<EOF
# SafeHome / LiveWell360 PostgreSQL backup — managed by install-safehome-postgres-backup-cron.sh
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
${BACKUP_CRON_SCHEDULE} root /bin/bash ${BACKUP_SCRIPT} >>${LOG_FILE} 2>&1
EOF
chmod 644 "$CRON_FILE"

log "Installed $CRON_FILE"
log "Schedule: ${BACKUP_CRON_SCHEDULE} (cron format)"
log "Script:   $BACKUP_SCRIPT"
log "Log:      $LOG_FILE"
echo ""
echo "Test now:"
echo "  sudo bash $BACKUP_SCRIPT"
echo "  sudo bash ${APP_ROOT}/scripts/deploy/restore-safehome-postgres.sh --list"
echo ""
echo "Optional offsite: set BACKUP_OFFSITE_CMD in /etc/workforceos/safehome.env"
