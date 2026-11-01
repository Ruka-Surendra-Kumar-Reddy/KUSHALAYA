#!/usr/bin/env bash
# Shared definitions for the tarball release flow. Sourced by:
#   scripts/release.sh                  (laptop: build the payload)
#   scripts/deploy/snapshot-before-deploy.sh
#   scripts/deploy/apply-release.sh     (VM: snapshot + extract + rebuild + smoke)
#   scripts/deploy/rollback-livewell.sh
# Do not execute directly.

[[ -n "${RELEASE_LIB_LOADED:-}" ]] && return 0
RELEASE_LIB_LOADED=1

# --- What a release contains -------------------------------------------------
# The payload set from CLAUDE.md ("Deploying" -> step 1) plus the files that
# have to travel with a code change to be usable at all: the deploy scripts
# themselves, the nginx/systemd templates, next.config.mjs (redirects and
# headers), the package manifests (start-livewell.sh runs `npm ci` only when
# package-lock.json changes, so shipping it is what makes new deps install)
# and the docs. Secrets never come from these paths — see RELEASE_EXCLUDES.
RELEASE_PATHS=(
  frontend/app
  frontend/components
  frontend/lib
  frontend/messages
  frontend/public
  frontend/styles
  frontend/middleware.ts
  frontend/next.config.mjs
  frontend/package.json
  frontend/package-lock.json
  frontend/tsconfig.json
  backend/app
  backend/tests
  backend/requirements.txt
  scripts
  deploy
  docs
  CLAUDE.md
)

# tar --exclude patterns. `.env*` covers backend/.env, frontend/.env.local and
# iot_ingestor.env; the mqtt entries are the gitignored broker secrets.
RELEASE_EXCLUDES=(
  node_modules .next .next-staging .next-previous .venv __pycache__ '*.pyc' '*.db'
  .env .env.local '.env.*' '*.env' uploads test_uploads tsconfig.tsbuildinfo
  _ssh releases '*.tar.gz' '*.zip'
  deploy/mqtt/passwd deploy/mqtt/.credentials
  '*.key' '*.pem' 'id_rsa*' 'id_ed25519*'
)

# Anything matching this in the tarball listing aborts the release.
RELEASE_SECRET_GREP='(^|/)(\.env|_ssh|iot_ingestor\.env|deploy/mqtt/passwd$|deploy/mqtt/\.credentials)|\.key$|\.pem$|id_rsa|id_ed25519'

# --- Where things live on the VM ----------------------------------------------
: "${APP_ROOT:=/opt/safehomeops/app}"
# The staging copy keeps its ports/unit names/smoke hosts in $APP_ROOT/.deploy-env
# (written by install-staging.sh; production has none). Same file start-livewell.sh reads.
if [[ -f "$APP_ROOT/.deploy-env" ]]; then
  # shellcheck disable=SC1091
  source "$APP_ROOT/.deploy-env"
fi
: "${APP_USER:=safehomeops}"
# Snapshots + env stat live beside the app dir, so production and staging never
# share them: /opt/safehomeops/releases and /opt/safehomeops-staging/releases.
: "${RELEASES_DIR:=$(dirname "$APP_ROOT")/releases}"
: "${SNAPSHOT_KEEP:=5}"
: "${SERVICE_PREFIX:=safehomeops}"                 # safehomeops-api / -web / -iot-ingestor

# The two files a deploy must never touch. Verified by size + mtime before and
# after every extract (CLAUDE.md -> Traps: "Never ship .env or .env.local").
ENV_FILES=(backend/.env frontend/.env.local)

rl_log() { echo "==> $*"; }
rl_die() { echo "ERROR: $*" >&2; exit 1; }

# "size mtime path" for each env file that exists.
env_stat() {
  local f
  for f in "${ENV_FILES[@]}"; do
    if [[ -f "$APP_ROOT/$f" ]]; then
      stat -c '%s %Y %n' "$APP_ROOT/$f"
    else
      echo "MISSING - $APP_ROOT/$f"
    fi
  done
}

env_stat_record() {
  mkdir -p "$RELEASES_DIR"
  env_stat >"$RELEASES_DIR/.env-stat"
}

# Compare against the last env_stat_record. Prints a diff and returns 1 when
# anything changed — that means a payload shipped an env file. Roll back.
env_stat_check() {
  local before="$RELEASES_DIR/.env-stat"
  [[ -f "$before" ]] || { echo "WARN: no env stat recorded (run env_stat_record first)"; return 0; }
  if diff -u "$before" <(env_stat) >/dev/null; then
    rl_log "Env files unchanged:"
    env_stat | sed 's/^/    /'
    return 0
  fi
  echo "ERROR: backend/.env or frontend/.env.local CHANGED during this deploy:" >&2
  diff -u "$before" <(env_stat) >&2 || true
  return 1
}

current_release_id() {
  local f="$APP_ROOT/frontend/public/release.txt"
  if [[ -f "$f" ]]; then tr -d '[:space:]' <"$f"; else echo "unknown"; fi
}

# Newest first. Legacy /tmp/rollback-*.tar.gz (pre-release.sh deploys) are
# listed too so an older snapshot is still usable.
list_snapshots() {
  ls -1t "$RELEASES_DIR"/rollback-*.tar.gz /tmp/rollback-*.tar.gz 2>/dev/null || true
}

prune_snapshots() {
  local keep="${1:-$SNAPSHOT_KEEP}"
  local extra
  extra=$(ls -1t "$RELEASES_DIR"/rollback-*.tar.gz 2>/dev/null | tail -n +"$((keep + 1))" || true)
  [[ -n "$extra" ]] || return 0
  rl_log "Pruning snapshots beyond the newest $keep:"
  echo "$extra" | sed 's/^/    /'
  echo "$extra" | xargs -r rm -f
}
