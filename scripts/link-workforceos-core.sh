#!/usr/bin/env bash
# Point frontend file:../workforceos-core/typescript at a contracts tree.
#
# Prefer this repo's vendored workforceos-core (includes LIVEWELL360).
# Only fall back to WORKFORCEOS_CORE / /opt/workforceos-core when vendored
# core is missing — shared /opt core is often Elder Care–centric and lacks LIVEWELL360.
#
#   bash scripts/link-workforceos-core.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LINK="$REPO_ROOT/workforceos-core"

has_livewell() {
  local root=$1
  [[ -f "$root/contracts/verticals.json" ]] \
    && grep -q '"LIVEWELL360"' "$root/contracts/verticals.json" \
    && [[ -f "$root/typescript/package.json" ]]
}

# Real (non-symlink) vendored tree — keep it; never replace with ln -sfn.
if [[ -d "$LINK" && ! -L "$LINK" ]] && has_livewell "$LINK"; then
  echo "Using vendored $LINK (LIVEWELL360)"
  exit 0
fi

# Broken symlink to old core: remove so we can re-link or restore from git.
if [[ -L "$LINK" ]]; then
  target="$(readlink -f "$LINK" 2>/dev/null || true)"
  if [[ -n "$target" ]] && has_livewell "$target"; then
    echo "Linked $LINK -> $target (LIVEWELL360)"
    exit 0
  fi
  echo "Removing stale workforceos-core symlink -> ${target:-unknown}"
  rm -f "$LINK"
fi

resolve_core() {
  if [[ -n "${WORKFORCEOS_CORE:-}" ]] && has_livewell "${WORKFORCEOS_CORE}"; then
    echo "$WORKFORCEOS_CORE"
    return
  fi
  local candidate
  for candidate in "$REPO_ROOT/../workforceos-core" "/opt/workforceos-core"; do
    if has_livewell "$candidate"; then
      echo "$(cd "$candidate" && pwd)"
      return
    fi
  done
  return 1
}

if CORE="$(resolve_core)"; then
  ln -sfn "$CORE" "$LINK"
  echo "Linked $LINK -> $CORE (LIVEWELL360)"
  exit 0
fi

echo "ERROR: No workforceos-core with LIVEWELL360 found." >&2
echo "  workforceos-core/ is gitignored in this app repo — do not use git checkout." >&2
echo "  Restore: ln -sfn /opt/workforceos-core $LINK" >&2
echo "  Then ensure /opt/workforceos-core/contracts/verticals.json includes LIVEWELL360," >&2
echo "  rebuild typescript there, and re-run start-livewell-services.sh" >&2
exit 1
