#!/usr/bin/env bash
# Install backend Python deps + editable workforceos-core.
#
# Set WORKFORCEOS_CORE to your clone path when it is not beside this repo:
#   export WORKFORCEOS_CORE=/opt/workforceos-core          # production VM
#   export WORKFORCEOS_CORE=C:/pers/workforceos-core       # Windows (Git Bash)
#
# Default search order (when unset): ../workforceos-core, ./workforceos-core, /opt/workforceos-core
#
# VM notes:
# - Activate the backend venv before running (Python 3.11), never system pip 3.9.
# - On production VMs, eldercareops / housekeepingops are in group opc; /opt/workforceos-core
#   is opc:opc with group write — editable pip installs usually need no sudo.
# - If core is not group-writable, this script falls back to sudo + the venv pip.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$REPO_ROOT/backend}"

resolve_core_root() {
  if [[ -n "${WORKFORCEOS_CORE:-}" ]]; then
    echo "$WORKFORCEOS_CORE"
    return
  fi
  local candidate
  for candidate in \
    "$REPO_ROOT/../workforceos-core" \
    "$REPO_ROOT/workforceos-core" \
    "/opt/workforceos-core"
  do
    if [[ -f "$candidate/contracts/verticals.json" ]]; then
      (cd "$candidate" && pwd)
      return
    fi
  done
  return 1
}

resolve_venv_pip() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/pip" ]]; then
    echo "${VIRTUAL_ENV}/bin/pip"
    return
  fi
  if [[ -x "$BACKEND_DIR/.venv/bin/pip" ]]; then
    echo "$BACKEND_DIR/.venv/bin/pip"
    return
  fi
  echo "Activate the backend venv first: source $BACKEND_DIR/.venv/bin/activate" >&2
  exit 1
}

install_workforceos_core() {
  local python_pkg=$1
  local venv_pip
  venv_pip="$(resolve_venv_pip)"

  # Stale egg-info from a failed install blocks setuptools.
  if [[ -d "$python_pkg/src/workforceos_core.egg-info" ]]; then
    if [[ -w "$python_pkg/src/workforceos_core.egg-info" ]]; then
      rm -rf "$python_pkg/src/workforceos_core.egg-info"
    elif command -v sudo &>/dev/null; then
      echo "Removing stale egg-info: $python_pkg/src/workforceos_core.egg-info" >&2
      sudo rm -rf "$python_pkg/src/workforceos_core.egg-info"
    fi
  fi

  local install_cmd=(
    "$venv_pip" install -e "$python_pkg" --no-deps --no-build-isolation
  )

  if [[ -w "$python_pkg" ]]; then
    "${install_cmd[@]}"
    return
  fi

  if ! command -v sudo &>/dev/null; then
    echo "Cannot write to $python_pkg for editable install. Fix ownership or run as root:" >&2
    echo "  sudo $venv_pip install -e $python_pkg --no-deps --no-build-isolation" >&2
    exit 1
  fi

  echo "Installing workforceos-core via sudo + venv pip (egg-info needs write under $python_pkg)" >&2
  sudo "${install_cmd[@]}"
}

CORE_ROOT="$(resolve_core_root)" || {
  echo "workforceos-core not found. Clone it or set WORKFORCEOS_CORE=/path/to/workforceos-core" >&2
  exit 1
}

PYTHON_PKG="$CORE_ROOT/python"
if [[ ! -f "$PYTHON_PKG/pyproject.toml" && ! -f "$PYTHON_PKG/setup.py" && ! -f "$PYTHON_PKG/setup.cfg" ]]; then
  echo "Invalid workforceos-core python package at: $PYTHON_PKG" >&2
  exit 1
fi

VENV_PIP="$(resolve_venv_pip)"
"$VENV_PIP" install --upgrade pip wheel setuptools
"$VENV_PIP" install -r "$BACKEND_DIR/requirements.txt"
install_workforceos_core "$PYTHON_PKG"
echo "Installed workforceos-core from $PYTHON_PKG"
