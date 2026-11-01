#!/usr/bin/env bash
# Nightly off-server encrypted backup of the production database + uploads (#105).
#
#   1. pg_dump (custom format, compressed) using DATABASE_URL read from backend/.env
#   2. tar.gz of the uploads directory
#   3. encrypt both (gpg AES-256 symmetric, or age) with BACKUP_KEY_FILE
#   4. upload to BACKUP_RCLONE_REMOTE/daily/<YYYY-MM-DD>/ ; first run of each ISO week
#      is also copied to weekly/<YYYY-Www>/
#   5. prune: keep BACKUP_KEEP_DAILY (14) daily + BACKUP_KEEP_WEEKLY (8) weekly
#   6. write BACKUP_STATUS_FILE (read by the admin "Last backup" badge)
#
# Usage (as root; normally run by safehomeops-backup.timer at 02:30 IST):
#   sudo bash scripts/backup/backup-db.sh
#   sudo bash scripts/backup/backup-db.sh --dry-run   # check config/tools only
#
# See docs/BACKUP.md.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=backup-lib.sh
source "$SCRIPT_DIR/backup-lib.sh"

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

WORK=""
PGPASS_TMP=""
STARTED="$(now_iso)"
DONE=0
REPORT_FAILURE=$((1 - DRY_RUN))   # off for --dry-run and "another backup is running"
FAIL_MSG=""

# Runs on every exit (success, error, Ctrl-C, systemd stop): never leave a
# plaintext dump/tar or the password file behind, and record a failed run.
cleanup() {
  local rc=$?
  trap - EXIT INT TERM ERR
  if [[ -n "$WORK" ]]; then
    rm -f "$WORK/db.dump" "$WORK/uploads.tar.gz"
    [[ "$DONE" == 1 ]] || rm -rf "$WORK"
  fi
  [[ -n "$PGPASS_TMP" ]] && rm -f "$PGPASS_TMP"
  if [[ "$DONE" != 1 && "$REPORT_FAILURE" == 1 && -n "${BACKUP_STATUS_FILE:-}" ]]; then
    [[ "$rc" == 0 ]] && rc=1
    write_status "last_attempt_at=$STARTED" "last_status=failed" \
      "message=${FAIL_MSG:-Backup failed (exit $rc)}; see journalctl -u safehomeops-backup" || true
  fi
  exit "$rc"
}
on_error() {
  local rc=$?
  FAIL_MSG="Backup failed (exit $rc) at line ${BASH_LINENO[0]}"
  exit "$rc"
}
trap cleanup EXIT
trap 'FAIL_MSG="Backup interrupted"; exit 130' INT
trap 'FAIL_MSG="Backup stopped (SIGTERM)"; exit 143' TERM
trap on_error ERR

require_root
load_offsite_backup_config
PGPASS_TMP="$(mktemp "${TMPDIR:-/tmp}/safehomeops-pgpass.XXXXXX")"
RAW_DB_URL="$(libpq_url)"
DB_URL="$(pgpass_url "$RAW_DB_URL" "$PGPASS_TMP")"   # no password in it
unset RAW_DB_URL
export PGPASSFILE="$PGPASS_TMP"
DUMP="$(pg_dump_cmd)"
EXT="$(enc_ext)"

if [[ "$DRY_RUN" == "1" ]]; then
  log "Config OK. Remote: $BACKUP_RCLONE_REMOTE  cipher: $BACKUP_CIPHER  uploads: $BACKUP_UPLOADS_DIR"
  rc lsf "$BACKUP_RCLONE_REMOTE" --dirs-only >/dev/null && log "Remote reachable"
  exit 0
fi

exec 9>"$BACKUP_LOCK_FILE"
flock -n 9 || { REPORT_FAILURE=0; die "Another backup is running"; }

DAY="$(TZ=Asia/Kolkata date +%F)"
WEEK="$(TZ=Asia/Kolkata date +%G-W%V)"
WORK="$BACKUP_WORK_DIR/$DAY"

umask 077
rm -rf "$WORK"
mkdir -p "$WORK"

log "Dumping database"
"$DUMP" --dbname="$DB_URL" --format=custom --compress=6 --no-owner --no-acl --file="$WORK/db.dump"
DB_BYTES="$(stat -c %s "$WORK/db.dump")"
[[ "$DB_BYTES" -gt 1024 ]] || { echo "Dump suspiciously small ($DB_BYTES bytes)" >&2; false; }

UP_BYTES=0
if [[ -d "$BACKUP_UPLOADS_DIR" ]]; then
  log "Archiving uploads from $BACKUP_UPLOADS_DIR"
  tar -C "$(dirname "$BACKUP_UPLOADS_DIR")" -czf "$WORK/uploads.tar.gz" "$(basename "$BACKUP_UPLOADS_DIR")"
  UP_BYTES="$(stat -c %s "$WORK/uploads.tar.gz")"
else
  log "No uploads directory at $BACKUP_UPLOADS_DIR (skipped)"
fi

log "Encrypting ($BACKUP_CIPHER)"
for f in db.dump uploads.tar.gz; do
  [[ -f "$WORK/$f" ]] || continue
  encrypt_file "$WORK/$f" "$WORK/$f.$EXT"
  rm -f "$WORK/$f"
done

( cd "$WORK" && sha256sum ./*."$EXT" >SHA256SUMS )
cat >"$WORK/manifest.json" <<JSON
{"created_at": "$STARTED", "day": "$DAY", "host": "$(hostname -s)", "cipher": "$BACKUP_CIPHER",
 "db_bytes": $DB_BYTES, "uploads_bytes": $UP_BYTES}
JSON

log "Uploading to $BACKUP_RCLONE_REMOTE/daily/$DAY"
rc copy "$WORK" "$BACKUP_RCLONE_REMOTE/daily/$DAY" --retries 5 --low-level-retries 10
rc check "$WORK" "$BACKUP_RCLONE_REMOTE/daily/$DAY" --one-way

if ! rc lsf "$BACKUP_RCLONE_REMOTE/weekly" --dirs-only 2>/dev/null | grep -qx "$WEEK/"; then
  log "Weekly copy → weekly/$WEEK"
  rc copy "$BACKUP_RCLONE_REMOTE/daily/$DAY" "$BACKUP_RCLONE_REMOTE/weekly/$WEEK"
fi

prune() { # subdir keep
  local keep=$2 old
  mapfile -t old < <(rc lsf "$BACKUP_RCLONE_REMOTE/$1" --dirs-only 2>/dev/null | sort -r | tail -n +"$((keep + 1))")
  for d in "${old[@]}"; do
    [[ -n "$d" ]] || continue
    log "Pruning $1/$d"
    rc purge "$BACKUP_RCLONE_REMOTE/$1/${d%/}"
  done
}
prune daily "$BACKUP_KEEP_DAILY"
prune weekly "$BACKUP_KEEP_WEEKLY"

rm -rf "$WORK"
DONE=1
write_status "last_attempt_at=$STARTED" "last_success_at=$(now_iso)" "last_status=ok" \
  "db_bytes=$DB_BYTES" "uploads_bytes=$UP_BYTES" "remote=$BACKUP_RCLONE_REMOTE" "last_day=$DAY" \
  "message=Backup uploaded to daily/$DAY"
log "Backup OK: daily/$DAY (db ${DB_BYTES} bytes, uploads ${UP_BYTES} bytes)"
