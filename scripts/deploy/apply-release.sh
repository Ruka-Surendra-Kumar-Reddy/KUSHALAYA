#!/usr/bin/env bash
# Apply a release tarball built by scripts/release.sh — run ON the VM as root.
# This is CLAUDE.md's four deploy steps in one command, with the checks in:
#
#   sudo bash scripts/deploy/apply-release.sh /tmp/rel-YYYYMMDD-HHMM.tar.gz [start-livewell flags]
#
#   1. snapshot the current tree  (snapshot-before-deploy.sh -> /opt/safehomeops/releases)
#   2. extract the tarball over $APP_ROOT and chown to safehomeops
#   3. verify backend/.env + frontend/.env.local are untouched (size+mtime) and,
#      when /tmp/<id>.manifest is beside the tarball, sha256-verify every file
#   4. bash scripts/start-livewell.sh [flags]   (--skip-frontend | --backend-migrate | --full | --no-restart)
#   5. scripts/deploy/smoke-test.sh --release <id>   (non-fatal warning on failure)
#
# Options: --no-snapshot   skip step 1 (only when you just took one by hand)
#          --no-smoke      skip step 5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-lib.sh
source "$SCRIPT_DIR/release-lib.sh"

TARBALL=""
SNAPSHOT=1
SMOKE=1
declare -a START_FLAGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-snapshot) SNAPSHOT=0; shift ;;
    --no-smoke) SMOKE=0; shift ;;
    --skip-frontend|--backend-migrate|--full|--no-restart) START_FLAGS+=("$1"); shift ;;
    --help|-h) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) rl_die "Unknown argument: $1" ;;
    *) [[ -z "$TARBALL" ]] || rl_die "One tarball only"; TARBALL="$1"; shift ;;
  esac
done

[[ $EUID -eq 0 ]] || rl_die "Run as root: sudo bash $0 <tarball>"
[[ -n "$TARBALL" && -f "$TARBALL" ]] || rl_die "Tarball not found: ${TARBALL:-<none>}"
[[ -d "$APP_ROOT/backend" ]] || rl_die "Not an app root: $APP_ROOT"

id_from_name="$(basename "$TARBALL" .tar.gz)"
MANIFEST="$(dirname "$TARBALL")/$id_from_name.manifest"

# Refuse anything secret-looking BEFORE touching the tree.
if tar -tzf "$TARBALL" | grep -E "$RELEASE_SECRET_GREP" >/dev/null; then
  echo "ERROR: tarball contains secret-looking paths — refusing to extract:" >&2
  tar -tzf "$TARBALL" | grep -E "$RELEASE_SECRET_GREP" | sed 's/^/    /' >&2
  exit 1
fi

rl_log "Applying $TARBALL to $APP_ROOT (current release: $(current_release_id))"

# 1. snapshot
if [[ "$SNAPSHOT" == "1" ]]; then
  bash "$SCRIPT_DIR/snapshot-before-deploy.sh"
else
  rl_log "Skipping snapshot (--no-snapshot); recording env stat only"
  env_stat_record
fi

# 2. extract + chown
rl_log "Extracting"
tar -xzf "$TARBALL" -C "$APP_ROOT"
# Only chown what the payload can contain — never the whole app dir.
declare -a own=()
for p in "${RELEASE_PATHS[@]}"; do [[ -e "$APP_ROOT/$p" ]] && own+=("$APP_ROOT/$p"); done
chown -R "$APP_USER:$APP_USER" "${own[@]}"

# 3. verify env files + manifest
env_stat_check || rl_die "Env files changed — roll back NOW: sudo bash $SCRIPT_DIR/rollback-livewell.sh --to latest"
if [[ -f "$MANIFEST" ]]; then
  rl_log "Verifying manifest $MANIFEST"
  if (cd "$APP_ROOT" && grep -v '^#' "$MANIFEST" | sha256sum -c --quiet --strict -); then
    rl_log "Manifest OK ($(grep -vc '^#' "$MANIFEST") files)"
  else
    rl_die "Manifest mismatch after extract — the tree is not what was built. Roll back."
  fi
else
  echo "WARN: no manifest beside the tarball ($MANIFEST) — skipping sha256 verification"
fi
new_id="$(current_release_id)"
rl_log "Tree is now release $new_id"

# 4. rebuild + restart (start-livewell.sh re-execs itself as safehomeops)
rl_log "start-livewell.sh ${START_FLAGS[*]:-}"
if ! bash "$APP_ROOT/scripts/start-livewell.sh" "${START_FLAGS[@]}"; then
  echo "ERROR: start-livewell.sh failed. Snapshots for rollback:" >&2
  list_snapshots | head -3 | sed 's/^/    /' >&2
  exit 1
fi

# 5. smoke test (start-livewell.sh already ran it once; this pass pins the id)
if [[ "$SMOKE" == "1" && -f "$SCRIPT_DIR/smoke-test.sh" ]]; then
  rl_log "Smoke test (release $new_id)"
  if ! bash "$SCRIPT_DIR/smoke-test.sh" --release "$new_id"; then
    echo "WARN: smoke test reported failures — inspect above; rollback: sudo bash $SCRIPT_DIR/rollback-livewell.sh" >&2
  fi
fi
rl_log "Release $new_id applied."
