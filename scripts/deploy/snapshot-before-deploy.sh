#!/usr/bin/env bash
# Snapshot the deployed tree for rollback — run ON the VM, as root, BEFORE
# extracting a new payload over /opt/safehomeops/app. (start-livewell.sh has
# no snapshot step: it runs after the extract, when the old files are gone.)
#
#   sudo bash scripts/deploy/snapshot-before-deploy.sh            # keep newest 5
#   sudo bash scripts/deploy/snapshot-before-deploy.sh --keep 10
#
# Writes /opt/safehomeops/releases/rollback-<ts>-<current release id>.tar.gz
# containing the same paths a release ships (release-lib.sh RELEASE_PATHS),
# records backend/.env + frontend/.env.local size+mtime for the post-extract
# check, and prunes older snapshots. Env files are never in the snapshot.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-lib.sh
source "$SCRIPT_DIR/release-lib.sh"

KEEP="$SNAPSHOT_KEEP"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP="${2:?}"; shift 2 ;;
    --help|-h) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) rl_die "Unknown argument: $1" ;;
  esac
done

[[ $EUID -eq 0 ]] || rl_die "Run as root: sudo bash $0"
[[ -d "$APP_ROOT/backend" ]] || rl_die "Not an app root: $APP_ROOT"

mkdir -p "$RELEASES_DIR"
chmod 750 "$RELEASES_DIR"

ts="$(date +%Y%m%d-%H%M%S)"
current="$(current_release_id)"
dest="$RELEASES_DIR/rollback-${ts}-${current}.tar.gz"

declare -a present=()
for p in "${RELEASE_PATHS[@]}"; do
  [[ -e "$APP_ROOT/$p" ]] && present+=("$p")
done
[[ ${#present[@]} -gt 0 ]] || rl_die "Nothing to snapshot under $APP_ROOT"

declare -a excl=()
for e in "${RELEASE_EXCLUDES[@]}"; do excl+=("--exclude=$e"); done

rl_log "Snapshot of $APP_ROOT (release $current) -> $dest"
tar -czf "$dest.tmp" "${excl[@]}" -C "$APP_ROOT" -- "${present[@]}"
mv "$dest.tmp" "$dest"
chmod 640 "$dest"

if tar -tzf "$dest" | grep -E "$RELEASE_SECRET_GREP" >/dev/null; then
  rm -f "$dest"
  rl_die "Snapshot contained a secret-looking path — deleted. Check RELEASE_EXCLUDES."
fi

env_stat_record
rl_log "Recorded env file stat:"
env_stat | sed 's/^/    /'

prune_snapshots "$KEEP"
echo "$dest"
