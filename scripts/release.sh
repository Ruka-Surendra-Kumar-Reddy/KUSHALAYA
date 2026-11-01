#!/usr/bin/env bash
# Build a deploy tarball for the Kushalaya VM — run LOCALLY in Git Bash from the
# repo root. It does NOT upload or deploy anything; it prints the commands.
#
#   bash scripts/release.sh                     # full payload (CLAUDE.md set + scripts/deploy/docs)
#   bash scripts/release.sh --files a,b,c       # scoped payload: only those paths (+ the release stamp)
#   bash scripts/release.sh --id rel-20260930-0900   # fixed id (default: rel-YYYYMMDD-HHMM, local time)
#   bash scripts/release.sh --no-stamp          # do not rewrite release.txt / release.py (id = current)
#   bash scripts/release.sh --out DIR           # where to write (default: releases/ in the repo)
#
# What it does:
#   1. Stamps the release id into frontend/public/release.txt and
#      backend/app/release.py (RELEASE_ID) — /health reports it as "release"
#      and smoke-test.sh asserts it.
#   2. tar -czf releases/<id>.tar.gz with the exclusions from CLAUDE.md
#      (node_modules, .next, .venv, .env*, uploads, ...).
#   3. Lists the tarball and ABORTS if anything secret-looking is inside.
#   4. Writes releases/<id>.manifest — sha256 of every file in the tarball
#      (apply-release.sh verifies it on the VM after extracting).
#   5. Prints the scp/ssh commands to run next.
#
# Run the checks first (CLAUDE.md -> "Verifying a change"):
#   cd frontend && npx tsc --noEmit && npx vitest run
#   cd backend  && ./.venv/Scripts/python.exe -m pytest -q

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=deploy/release-lib.sh
source "$SCRIPT_DIR/deploy/release-lib.sh"

VM_HOST="${VM_HOST:-opc@129.213.45.105}"
VM_APP_ROOT="${VM_APP_ROOT:-/opt/safehomeops/app}"

OUT_DIR="$REPO_ROOT/releases"
RELEASE_ID=""
FILES_CSV=""
STAMP=1

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --files) FILES_CSV="${2:?--files needs a,b,c}"; shift 2 ;;
    --id) RELEASE_ID="${2:?}"; shift 2 ;;
    --out) OUT_DIR="${2:?}"; shift 2 ;;
    --no-stamp) STAMP=0; shift ;;
    --help|-h) usage ;;
    *) rl_die "Unknown argument: $1 (try --help)" ;;
  esac
done

cd "$REPO_ROOT"
[[ -d frontend && -d backend ]] || rl_die "Run from the SafeHomeOps repo root (got $REPO_ROOT)"

STAMP_FILES=(frontend/public/release.txt backend/app/release.py)

if [[ -z "$RELEASE_ID" ]]; then
  if [[ "$STAMP" == "1" ]]; then
    RELEASE_ID="rel-$(date +%Y%m%d-%H%M)"
  else
    RELEASE_ID="$(tr -d '[:space:]' <frontend/public/release.txt 2>/dev/null || echo dev)"
  fi
fi
[[ "$RELEASE_ID" =~ ^[A-Za-z0-9._-]+$ ]] || rl_die "Release id must be [A-Za-z0-9._-]: $RELEASE_ID"

# --- 1. stamp --------------------------------------------------------------
if [[ "$STAMP" == "1" ]]; then
  printf '%s\n' "$RELEASE_ID" >frontend/public/release.txt
  [[ -f backend/app/release.py ]] || rl_die "backend/app/release.py missing"
  sed -i -E "s/^RELEASE_ID = \".*\"\$/RELEASE_ID = \"${RELEASE_ID}\"/" backend/app/release.py
  grep -q "^RELEASE_ID = \"${RELEASE_ID}\"\$" backend/app/release.py \
    || rl_die "Failed to stamp RELEASE_ID into backend/app/release.py"
  rl_log "Stamped $RELEASE_ID into ${STAMP_FILES[*]}"
fi

# --- 2. choose paths --------------------------------------------------------
declare -a PATHS=()
if [[ -n "$FILES_CSV" ]]; then
  IFS=',' read -r -a PATHS <<<"$FILES_CSV"
  for p in "${PATHS[@]}"; do
    p="${p#./}"
    [[ -e "$p" ]] || rl_die "--files: no such path: $p"
    [[ "$p" == /* || "$p" == ..* ]] && rl_die "--files: paths must be repo-relative: $p"
    if printf '%s\n' "$p" | grep -Eq "$RELEASE_SECRET_GREP"; then
      rl_die "--files: refusing to ship a secret-looking path: $p"
    fi
  done
  # The stamp always travels, so /health and release.txt agree with the manifest.
  if [[ "$STAMP" == "1" ]]; then PATHS+=("${STAMP_FILES[@]}"); fi
  MODE="scoped (--files)"
else
  PATHS=("${RELEASE_PATHS[@]}")
  MODE="full"
fi

# Normalise: strip ./ and trailing /, drop missing optional paths, de-dupe.
declare -a CLEAN=()
for p in "${PATHS[@]}"; do
  p="${p#./}"; p="${p%/}"
  if [[ ! -e "$p" ]]; then
    echo "  (skipping missing path: $p)"
    continue
  fi
  if ! printf '%s\n' "${CLEAN[@]:-}" | grep -qxF -- "$p"; then CLEAN+=("$p"); fi
done
[[ ${#CLEAN[@]} -gt 0 ]] || rl_die "Nothing to package"

# --- 3. tar -----------------------------------------------------------------
mkdir -p "$OUT_DIR"
TARBALL="$OUT_DIR/$RELEASE_ID.tar.gz"
MANIFEST="$OUT_DIR/$RELEASE_ID.manifest"
[[ -e "$TARBALL" ]] && rl_die "Already exists: $TARBALL (pass --id for a new one)"

declare -a EXCL=()
for e in "${RELEASE_EXCLUDES[@]}"; do EXCL+=("--exclude=$e"); done

rl_log "Packaging ($MODE) -> $TARBALL"
printf '    %s\n' "${CLEAN[@]}"
tar -czf "$TARBALL" "${EXCL[@]}" -- "${CLEAN[@]}"

# --- 4. secret check (must print nothing) -----------------------------------
LISTING="$(tar -tzf "$TARBALL")"
if printf '%s\n' "$LISTING" | grep -E "$RELEASE_SECRET_GREP" >/dev/null; then
  echo "ERROR: secret-looking files inside the tarball — release ABORTED:" >&2
  printf '%s\n' "$LISTING" | grep -E "$RELEASE_SECRET_GREP" | sed 's/^/    /' >&2
  rm -f "$TARBALL"
  exit 1
fi
rl_log "Secret grep: clean"

# --- 5. manifest ------------------------------------------------------------
# sha256 of every regular file in the tarball (paths as stored, repo-relative).
{
  echo "# release: $RELEASE_ID"
  echo "# built:   $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(hostname 2>/dev/null || echo local)"
  echo "# mode:    $MODE"
  echo "# tarball: $(basename "$TARBALL")"
  printf '%s\n' "$LISTING" | grep -v '/$' | while IFS= read -r f; do
    [[ -f "$f" ]] && sha256sum -- "$f"
  done
} >"$MANIFEST"
FILE_COUNT=$(grep -vc '^#' "$MANIFEST" || true)
SIZE=$(du -h "$TARBALL" | cut -f1)
rl_log "Manifest: $MANIFEST ($FILE_COUNT files, tarball $SIZE)"

# --- 6. next steps ----------------------------------------------------------
FLAGS_HINT="[--skip-frontend | --backend-migrate | --full]"
cat <<CMDS

==> Release $RELEASE_ID is ready. Nothing has been uploaded. Next:

  KEY="\$(pwd)/_ssh/oracle_safehome_vm"

  # 1. upload payload + manifest
  scp -i "\$KEY" "$TARBALL" "$MANIFEST" $VM_HOST:/tmp/

  # 2. snapshot -> extract -> verify env files -> rebuild/restart -> smoke test
  #    (one command; see scripts/deploy/apply-release.sh --help)
  ssh -i "\$KEY" $VM_HOST "sudo bash $VM_APP_ROOT/scripts/deploy/apply-release.sh /tmp/$RELEASE_ID.tar.gz $FLAGS_HINT"

  # 3. confirm the live release id
  curl -s https://ops.kushalaya.com/health | grep -o '"release":"[^"]*"'    # -> "$RELEASE_ID"
  curl -s https://ops.kushalaya.com/release.txt                                # -> $RELEASE_ID

  # Roll back if needed:
  ssh -i "\$KEY" $VM_HOST "sudo bash $VM_APP_ROOT/scripts/deploy/rollback-livewell.sh"          # list
  ssh -i "\$KEY" $VM_HOST "sudo bash $VM_APP_ROOT/scripts/deploy/rollback-livewell.sh --to /opt/safehomeops/releases/rollback-<ts>.tar.gz"

  First time only (apply-release.sh is not on the VM yet): ship the scripts by hand
    ssh -i "\$KEY" $VM_HOST "sudo tar -xzf /tmp/$RELEASE_ID.tar.gz -C $VM_APP_ROOT scripts deploy && sudo chown -R $APP_USER:$APP_USER $VM_APP_ROOT/scripts $VM_APP_ROOT/deploy"
  then run step 2.
CMDS
