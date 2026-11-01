#!/usr/bin/env bash
# Roll the deployed tree back to a snapshot — run ON the VM as root.
#
#   sudo bash scripts/deploy/rollback-livewell.sh                 # list snapshots, newest first
#   sudo bash scripts/deploy/rollback-livewell.sh --to FILE       # restore FILE, rebuild, smoke test
#   sudo bash scripts/deploy/rollback-livewell.sh --to latest     # newest snapshot
#   ... --to FILE --skip-frontend      passed through to start-livewell.sh (backend-only rollback)
#   ... --to FILE --yes                no confirmation prompt
#
# Snapshots come from snapshot-before-deploy.sh (/opt/safehomeops/releases/
# rollback-<ts>-<release>.tar.gz); older hand-made /tmp/rollback-*.tar.gz are
# listed too. Restoring = extract over /opt/safehomeops/app with the same chown
# a deploy uses, verify backend/.env + frontend/.env.local size+mtime are
# unchanged, re-run start-livewell.sh, then smoke-test.sh.
#
# Database: a snapshot holds CODE only. If the bad release ran a migration
# (--backend-migrate) that the old code cannot live with, restore the DB too:
#   sudo bash scripts/deploy/restore-safehome-postgres.sh --list

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-lib.sh
source "$SCRIPT_DIR/release-lib.sh"

TO=""
YES=0
declare -a START_FLAGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --to) TO="${2:?--to needs a file or latest}"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --skip-frontend|--backend-migrate|--full|--no-restart) START_FLAGS+=("$1"); shift ;;
    --list|-l) TO=""; shift ;;
    --help|-h) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) rl_die "Unknown argument: $1 (try --help)" ;;
  esac
done

[[ $EUID -eq 0 ]] || rl_die "Run as root: sudo bash $0"

if [[ -z "$TO" ]]; then
  echo "Deployed release: $(current_release_id)"
  echo "Snapshots (newest first):"
  found=0
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    found=1
    printf '  %s  %6s  %s\n' "$(date -r "$f" '+%Y-%m-%d %H:%M')" "$(du -h "$f" | cut -f1)" "$f"
  done < <(list_snapshots)
  [[ "$found" == "1" ]] || echo "  (none — snapshot-before-deploy.sh has not run yet)"
  echo ""
  echo "Restore one:  sudo bash $0 --to <file> [--skip-frontend]"
  exit 0
fi

if [[ "$TO" == "latest" ]]; then
  TO="$(list_snapshots | head -1 || true)"
  [[ -n "$TO" ]] || rl_die "No snapshots found"
fi
[[ -f "$TO" ]] || rl_die "Snapshot not found: $TO"
[[ -d "$APP_ROOT/backend" ]] || rl_die "Not an app root: $APP_ROOT"

if tar -tzf "$TO" | grep -E "$RELEASE_SECRET_GREP" >/dev/null; then
  rl_die "Snapshot contains secret-looking paths — refusing: $TO"
fi

echo ""
echo "About to ROLL BACK $APP_ROOT"
echo "  Deployed now: $(current_release_id)"
echo "  Restore from: $TO"
echo "  Then run:     start-livewell.sh ${START_FLAGS[*]:-}"
echo ""
if [[ "$YES" != "1" ]]; then
  read -r -p "Type ROLLBACK to continue: " confirm
  [[ "$confirm" == "ROLLBACK" ]] || rl_die "Aborted"
fi

# Keep a snapshot of the bad state too (so a rollback is itself reversible),
# and record the env stat we verify against after extracting.
rl_log "Snapshotting the current (bad) tree first"
bash "$SCRIPT_DIR/snapshot-before-deploy.sh" >/dev/null

rl_log "Extracting $TO"
tar -xzf "$TO" -C "$APP_ROOT"
declare -a own=()
for p in "${RELEASE_PATHS[@]}"; do [[ -e "$APP_ROOT/$p" ]] && own+=("$APP_ROOT/$p"); done
chown -R "$APP_USER:$APP_USER" "${own[@]}"

env_stat_check || rl_die "Env files changed during rollback extract — inspect $APP_ROOT/backend/.env and frontend/.env.local before restarting"

restored="$(current_release_id)"
rl_log "Tree is now release $restored — rebuilding"
bash "$APP_ROOT/scripts/start-livewell.sh" "${START_FLAGS[@]}"

if [[ -f "$SCRIPT_DIR/smoke-test.sh" ]]; then
  rl_log "Smoke test"
  bash "$SCRIPT_DIR/smoke-test.sh" --release "$restored" || echo "WARN: smoke test failed after rollback" >&2
fi
rl_log "Rollback to $restored complete."
