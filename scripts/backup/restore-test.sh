#!/usr/bin/env bash
# Weekly restore test of the latest off-server backup (#105).
#
#   1. find the newest daily/<day>/ on BACKUP_RCLONE_REMOTE and download it
#   2. verify SHA256SUMS, decrypt
#   3. restore db.dump into a THROWAWAY database (safehomeops_restore_test_<ts>)
#   4. sanity checks: table count, row counts of key tables vs the live database
#   5. list the uploads archive
#   6. drop the throwaway database (always, even on failure) and report
#
# The live database is only read (SELECT count(*)), never written.
#
# Usage (as root; normally run by safehomeops-restore-test.timer, Sundays 04:00 IST):
#   sudo bash scripts/backup/restore-test.sh
#   sudo bash scripts/backup/restore-test.sh --day 2026-10-05
#
# See docs/BACKUP.md.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=backup-lib.sh
source "$SCRIPT_DIR/backup-lib.sh"

DAY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --day) DAY="${2:?}"; shift 2 ;;
    --help|-h) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_root
load_offsite_backup_config
RAW_LIVE_URL="$(libpq_url)"
PSQL="$(psql_cmd)"
RESTORE="$(pg_restore_cmd)"
EXT="$(enc_ext)"

if [[ -z "$DAY" ]]; then
  DAY="$(rc lsf "$BACKUP_RCLONE_REMOTE/daily" --dirs-only | sort | tail -n 1)"
  DAY="${DAY%/}"
fi
[[ -n "$DAY" ]] || die "No backups found on $BACKUP_RCLONE_REMOTE/daily"

TS="$(date +%Y%m%d%H%M%S)"
TEST_DB="safehomeops_restore_test_${TS}"
WORK="$(mktemp -d "${BACKUP_WORK_DIR%/}-restore-XXXXXX" 2>/dev/null || mktemp -d)"
chmod 700 "$WORK"
# Password goes in a 0600 PGPASSFILE (removed in cleanup), never in psql's argv.
PGPASS_TMP="$WORK/.pgpass"
LIVE_URL="$(pgpass_url "$RAW_LIVE_URL" "$PGPASS_TMP")"
unset RAW_LIVE_URL
STARTED="$(now_iso)"
DETAIL=""

as_pg() { runuser -u "$RESTORE_PG_AS" -- "$@"; }

cleanup() {
  as_pg dropdb --if-exists -p "$RESTORE_PG_PORT" "$TEST_DB" >/dev/null 2>&1 || true
  rm -f "$PGPASS_TMP"
  rm -rf "$WORK"
}
fail() {
  write_status "restore_test_at=$STARTED" "restore_test_status=failed" "restore_test_day=$DAY" \
    "restore_test_detail=$1" || true
  cleanup
  die "Restore test FAILED: $1"
}
trap 'fail "error at line $LINENO"' ERR
trap cleanup EXIT
trap 'fail "interrupted"' INT TERM

log "Downloading daily/$DAY"
rc copy "$BACKUP_RCLONE_REMOTE/daily/$DAY" "$WORK"
( cd "$WORK" && sha256sum -c --quiet SHA256SUMS ) || fail "checksum mismatch"

log "Decrypting"
decrypt_file "$WORK/db.dump.$EXT" "$WORK/db.dump" || fail "could not decrypt db.dump (wrong key?)"

log "Restoring into throwaway database $TEST_DB"
as_pg createdb -p "$RESTORE_PG_PORT" "$TEST_DB"
# Fed on stdin so the postgres user never needs to read root's 0700 work dir.
as_pg "$RESTORE" -p "$RESTORE_PG_PORT" --no-owner --no-acl --exit-on-error -d "$TEST_DB" <"$WORK/db.dump" \
  || fail "pg_restore failed"

q_test() { as_pg "$PSQL" -p "$RESTORE_PG_PORT" -d "$TEST_DB" -tAc "$1"; }
q_live() { PGPASSFILE="$PGPASS_TMP" "$PSQL" "$LIVE_URL" -tAc "$1"; }

TABLES="$(q_test "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
[[ "$TABLES" -ge 20 ]] || fail "only $TABLES tables restored"

# Each key table must exist, have rows (tenants/users), and hold at least half the live
# count — a backup is at most a week old, so a big drop means a broken or empty dump.
for t in tenants users elders orders care_jobs documents audit_logs; do
  exists="$(q_test "SELECT to_regclass('public.$t') IS NOT NULL")"
  if [[ "$exists" != "t" ]]; then
    DETAIL+="$t:missing "
    [[ "$t" == tenants || "$t" == users ]] && fail "table $t missing"
    continue
  fi
  restored="$(q_test "SELECT count(*) FROM \"$t\"")"
  live="$(q_live "SELECT count(*) FROM \"$t\"" 2>/dev/null || echo 0)"
  DETAIL+="$t:$restored/$live "
  if [[ "$t" == tenants || "$t" == users ]] && [[ "$restored" -lt 1 ]]; then
    fail "$t is empty"
  fi
  if [[ "$live" -gt 10 && $((restored * 2)) -lt "$live" ]]; then
    fail "$t has $restored rows vs $live live"
  fi
done

if [[ -f "$WORK/uploads.tar.gz.$EXT" ]]; then
  decrypt_file "$WORK/uploads.tar.gz.$EXT" "$WORK/uploads.tar.gz" || fail "could not decrypt uploads"
  FILES="$(tar -tzf "$WORK/uploads.tar.gz" | grep -vc '/$' || true)"
  DETAIL+="upload_files:$FILES"
fi

trap - ERR
write_status "restore_test_at=$STARTED" "restore_test_status=ok" "restore_test_day=$DAY" \
  "restore_test_detail=${DETAIL% }"
log "Restore test OK for daily/$DAY ($TABLES tables) — restored/live: $DETAIL"
