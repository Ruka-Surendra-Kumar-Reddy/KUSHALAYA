#!/usr/bin/env bash
# Rebuild and restart SafeHomeOps as the safehomeops app user (no root shell).
# Restarts safehomeops-api, safehomeops-web, and safehomeops-iot-ingestor when installed.
#
# Run after git pull:
#   cd /opt/safehomeops/app
#   bash scripts/start-livewell.sh
#
# Options:
#   --skip-frontend     Restart systemd units only
#   --full              rm -rf node_modules and npm ci even if the lockfile is unchanged
#   --backend-migrate   pip install + python -m app.init_db
#   --no-restart        Build only (do not systemctl restart)
#   --help
#
# Optional $APP_ROOT/.deploy-env (KEY=VALUE, no secrets) overrides SERVICE_PREFIX,
# API_PORT, WEB_PORT, APP_DOMAIN and SMOKE_* — this is how the staging copy at
# /opt/safehomeops-staging/app restarts safehomeops-staging-* on :8020/:3020
# (written by scripts/deploy/install-staging.sh). Production has no such file.
# After the health checks, scripts/deploy/smoke-test.sh runs (non-fatal warning
# on failure; SKIP_SMOKE=1 to skip).
#
# First-time on the VM (as root/opc), install passwordless restart:
#   sudo bash scripts/deploy/install-safehome-sudoers.sh
# Or run once: sudo bash scripts/deploy/start-livewell-services.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -f "$APP_ROOT/.deploy-env" ]]; then
  # shellcheck disable=SC1091
  source "$APP_ROOT/.deploy-env"
fi
SERVICE_PREFIX="${SERVICE_PREFIX:-safehomeops}"
WORKFORCEOS_CORE="${WORKFORCEOS_CORE:-/opt/workforceos-core}"
APP_DOMAIN="${APP_DOMAIN:-livewellops.tekmatrix.ai}"
API_PORT="${API_PORT:-8010}"
WEB_PORT="${WEB_PORT:-3010}"

SKIP_FRONTEND=0
BACKEND_MIGRATE=0
NO_RESTART=0
FULL=0

log() { echo "==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# Shared /opt/workforceos-core must be opc:opc + group-writable so safehomeops
# can npm-build contracts (safehomeops ∈ opc). After a root clone, fix perms.
fix_workforceos_core_perms() {
  local path="${1:-$WORKFORCEOS_CORE}"
  [[ -d "$path" ]] || return 0
  getent group opc >/dev/null 2>&1 || groupadd opc
  id safehomeops &>/dev/null && usermod -aG opc safehomeops 2>/dev/null || true
  chown -R opc:opc "$path"
  chmod -R g+rwX "$path"
  find "$path" -type d -exec chmod g+s {} \;
  log "Fixed permissions on $path (opc:opc, group write)"
}

# Builds must run as safehomeops (re-exec before parsing so flags survive).
if [[ "$(id -un)" != "safehomeops" ]]; then
  if [[ $EUID -ne 0 ]] && [[ "$(id -un)" != "opc" ]]; then
    die "Run as safehomeops (or root/opc). Current user: $(id -un)"
  fi
  id safehomeops &>/dev/null || die "OS user safehomeops missing"
  # Root/opc can repair core ownership after a wipe/re-clone before dropping privileges.
  if [[ -d "$WORKFORCEOS_CORE" ]]; then
    if [[ $EUID -eq 0 ]]; then
      fix_workforceos_core_perms "$WORKFORCEOS_CORE"
    else
      sudo chown -R opc:opc "$WORKFORCEOS_CORE"
      sudo chmod -R g+rwX "$WORKFORCEOS_CORE"
      sudo find "$WORKFORCEOS_CORE" -type d -exec chmod g+s {} \;
      sudo usermod -aG opc safehomeops 2>/dev/null || true
      log "Fixed permissions on $WORKFORCEOS_CORE (opc:opc, group write)"
    fi
  fi
  exec sudo -u safehomeops -H bash "$0" "$@"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    --full) FULL=1; shift ;;
    --backend-migrate) BACKEND_MIGRATE=1; shift ;;
    --no-restart) NO_RESTART=1; shift ;;
    --help|-h) usage ;;
    *) die "Unknown argument: $1 (try --help)" ;;
  esac
done

[[ -d "$APP_ROOT/backend" ]] || die "Not a SafeHomeOps app root: $APP_ROOT"
[[ -f "$APP_ROOT/backend/.env" ]] || die "Missing backend/.env at $APP_ROOT/backend/.env"

ensure_frontend_env() {
  local fe_env="$APP_ROOT/frontend/.env.local"
  if [[ ! -f "$fe_env" ]]; then
    echo "NEXT_PUBLIC_API_URL=https://${APP_DOMAIN}" >"$fe_env"
    log "Wrote $fe_env"
  fi
}

run_backend_migrate() {
  [[ "$BACKEND_MIGRATE" == "1" ]] || return 0
  log "Backend deps + init_db"
  cd "$APP_ROOT/backend"
  if [[ ! -d .venv ]]; then
    python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export WORKFORCEOS_CORE
  bash "$APP_ROOT/scripts/install-backend-deps.sh"
  python -m app.init_db
}

build_frontend() {
  [[ "$SKIP_FRONTEND" == "1" ]] && {
    log "Skipping frontend build"
    return 0
  }
  ensure_frontend_env

  local core="$WORKFORCEOS_CORE"
  if [[ -f "$APP_ROOT/workforceos-core/typescript/package.json" ]]; then
    core="$(readlink -f "$APP_ROOT/workforceos-core" 2>/dev/null || echo "$APP_ROOT/workforceos-core")"
  fi
  [[ -f "$core/typescript/package.json" ]] \
    || die "workforceos-core not found at $core (set WORKFORCEOS_CORE=...)"

  log "Linking workforceos-core"
  export WORKFORCEOS_CORE="$core"
  bash "$APP_ROOT/scripts/link-workforceos-core.sh"

  if [[ ! -w "$core/typescript" ]]; then
    die "$core/typescript is not writable by $(id -un). As root/opc run once:
  sudo chown -R opc:opc $core
  sudo chmod -R g+rwX $core
  sudo usermod -aG opc safehomeops
Then re-login as safehomeops (or: sudo bash $0) and retry."
  fi

  log "Building @workforceos/contracts (as safehomeops)"
  cd "$core/typescript"
  npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts
  npm run build

  cd "$APP_ROOT/frontend"

  # Dependencies: `npm ci` deletes node_modules first, which the RUNNING
  # server is still resolving modules from — so only do it when the lockfile
  # actually changed (or on --full). Otherwise the deploy is outage-free.
  local lock_sha stamp="node_modules/.deploy-lock.sha256"
  lock_sha="$(sha256sum package-lock.json | cut -d' ' -f1)"
  if [[ "$FULL" == "1" || ! -d node_modules || "$(cat "$stamp" 2>/dev/null)" != "$lock_sha" ]]; then
    log "Installing frontend deps (npm ci — lockfile changed or --full; brief outage)"
    rm -rf node_modules
    npm ci
    echo "$lock_sha" >"$stamp"
  else
    log "Frontend deps unchanged (lockfile sha match) — keeping node_modules"
  fi

  # Build into a staging folder and swap it in atomically. Building straight
  # into .next replaced the manifests underneath the live server: for the
  # minutes the build took, HTML pointed at chunk hashes that no longer
  # existed, CSS/JS answered 400 and visitors saw an unstyled page (dark
  # sidebar, bare links) — including anyone logging in at that moment.
  log "Building frontend into .next-staging"
  rm -rf .next-staging
  mkdir -p .next-staging
  if [[ -d .next/cache ]]; then
    cp -r .next/cache .next-staging/cache   # keep the webpack cache: faster builds
  fi
  NEXT_DIST_DIR=.next-staging npm run build

  log "Swapping .next-staging -> .next"
  rm -rf .next-previous
  if [[ -d .next ]]; then
    mv .next .next-previous
  fi
  mv .next-staging .next
  rm -rf .next-previous
}

systemd_units_to_restart() {
  local units=("${SERVICE_PREFIX}-api" "${SERVICE_PREFIX}-web")
  if [[ -f "/etc/systemd/system/${SERVICE_PREFIX}-iot-ingestor.service" ]]; then
    units+=("${SERVICE_PREFIX}-iot-ingestor")
  fi
  printf '%s\n' "${units[@]}"
}

restart_units() {
  [[ "$NO_RESTART" == "1" ]] && {
    log "Skipping systemctl restart (--no-restart)"
    return 0
  }

  if [[ ! -f "/etc/systemd/system/${SERVICE_PREFIX}-api.service" ]]; then
    echo ""
    echo "ERROR: systemd units not installed yet."
    echo "  First-time (as opc/root):"
    echo "    sudo bash $APP_ROOT/scripts/deploy/start-livewell-services.sh --skip-frontend"
    echo "    sudo bash $APP_ROOT/scripts/deploy/install-safehome-sudoers.sh"
    echo "  Then as safehomeops: bash scripts/start-livewell.sh --skip-frontend"
    return 1
  fi

  mapfile -t units < <(systemd_units_to_restart)
  local unit_list="${units[*]}"

  if sudo -n systemctl restart "${units[@]}" 2>/dev/null; then
    log "Restarted ${unit_list} (passwordless sudo)"
  elif sudo systemctl restart "${units[@]}"; then
    log "Restarted ${unit_list} (sudo)"
  else
    echo ""
    echo "WARN: could not restart systemd units. Install sudoers once as root:"
    echo "  sudo bash $APP_ROOT/scripts/deploy/install-safehome-sudoers.sh"
    echo "Then re-run: bash scripts/start-livewell.sh --skip-frontend"
    echo "Or as root: sudo systemctl restart ${unit_list}"
    return 1
  fi
  sleep 2
  systemctl --no-pager --full status "${units[@]}" || true
}

health_check() {
  log "Health checks"
  local i api_ok=0
  for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
      echo "  API :${API_PORT} OK"
      api_ok=1
      break
    fi
    sleep 1
  done
  if [[ "$api_ok" != "1" ]]; then
    echo "  API :${API_PORT} FAILED (is ${SERVICE_PREFIX}-api running?)"
    echo "  Recent API logs:"
    journalctl -u "${SERVICE_PREFIX}-api" -n 40 --no-pager 2>/dev/null || true
  fi
  if curl -fsS -o /dev/null "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null; then
    echo "  Web :${WEB_PORT} OK"
  else
    echo "  Web :${WEB_PORT} FAILED (is ${SERVICE_PREFIX}-web running?)"
  fi
  if [[ -f "/etc/systemd/system/${SERVICE_PREFIX}-iot-ingestor.service" ]]; then
    if systemctl is-active --quiet "${SERVICE_PREFIX}-iot-ingestor" 2>/dev/null; then
      echo "  IoT ingestor OK"
    else
      echo "  IoT ingestor FAILED (is ${SERVICE_PREFIX}-iot-ingestor running?)"
      journalctl -u "${SERVICE_PREFIX}-iot-ingestor" -n 40 --no-pager 2>/dev/null || true
    fi
  fi
}

smoke_test() {
  # Public-host smoke test (scripts/deploy/smoke-test.sh). A failure here is a
  # warning, not an error: the services are up, but verify before walking away.
  [[ "${SKIP_SMOKE:-0}" == "1" ]] && return 0
  [[ "$NO_RESTART" == "1" ]] && return 0
  local smoke="$APP_ROOT/scripts/deploy/smoke-test.sh"
  [[ -f "$smoke" ]] || return 0
  local release
  release="$(tr -d '[:space:]' <"$APP_ROOT/frontend/public/release.txt" 2>/dev/null || true)"
  log "Smoke test${release:+ (release $release)}"
  if ! bash "$smoke" ${release:+--release "$release"}; then
    echo "WARN: smoke test FAILED — check the table above before leaving; rollback: sudo bash $APP_ROOT/scripts/deploy/rollback-livewell.sh"
  fi
}

main() {
  log "SafeHomeOps start (user=$(id -un) APP_ROOT=$APP_ROOT SERVICE_PREFIX=$SERVICE_PREFIX)"
  run_backend_migrate
  build_frontend
  restart_units || true
  health_check
  smoke_test
  log "Done."
  echo ""
  echo "  Local API:  http://127.0.0.1:${API_PORT}/health"
  echo "  Local web:  http://127.0.0.1:${WEB_PORT}/"
  echo "  Logs:       journalctl -u ${SERVICE_PREFIX}-api -f"
  if [[ -f "/etc/systemd/system/${SERVICE_PREFIX}-iot-ingestor.service" ]]; then
    echo "  IoT logs:   journalctl -u ${SERVICE_PREFIX}-iot-ingestor -f"
  fi
}

main "$@"
