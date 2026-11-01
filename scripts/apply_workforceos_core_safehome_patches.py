#!/usr/bin/env python3
"""Copy SafeHome contract modules into workforceos-core.

Usage (from ElderCareOps root):

    export WORKFORCEOS_CORE=/path/to/workforceos-core
    python scripts/apply_workforceos_core_safehome_patches.py

JSON contract fragments under scripts/workforceos-core-safehome/patches/ must still be
merged manually into verticals.json, database_packs.json, and nav.json — see README.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_KIT = REPO_ROOT / "scripts" / "workforceos-core-safehome"


def resolve_core(path: str | None) -> Path:
    if path:
        return Path(path).resolve()
    for candidate in (
        REPO_ROOT / "workforceos-core",
        REPO_ROOT.parent / "workforceos-core",
        Path("/opt/workforceos-core"),
    ):
        if (candidate / "python" / "src" / "workforceos_core").is_dir():
            return candidate.resolve()
    raise SystemExit(
        "workforceos-core not found. Set WORKFORCEOS_CORE=/path/to/workforceos-core"
    )


def apply(core: Path) -> None:
    src = PATCH_KIT / "python" / "workforceos_core" / "safehome"
    dst = core / "python" / "src" / "workforceos_core" / "safehome"
    if not src.is_dir():
        raise SystemExit(f"Patch source missing: {src}")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"Copied safehome Python package -> {dst}")

    # TypeScript optional types
    ts_src = PATCH_KIT / "typescript" / "src" / "safehome"
    ts_dst = core / "typescript" / "src" / "safehome"
    if ts_src.is_dir():
        if ts_dst.exists():
            shutil.rmtree(ts_dst)
        shutil.copytree(ts_src, ts_dst)
        print(f"Copied safehome TypeScript types -> {ts_dst}")

    print()
    print("Manual steps remaining:")
    print(f"  1. Merge JSON fragments from {PATCH_KIT / 'patches'} into contracts/")
    print("  2. cd workforceos-core/typescript && npm run build")
    print("  3. pip install -e workforceos-core/python")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--core",
        type=Path,
        default=None,
        help="Path to workforceos-core (or set WORKFORCEOS_CORE)",
    )
    args = parser.parse_args()
    core_path = args.core or os.environ.get("WORKFORCEOS_CORE")
    apply(resolve_core(core_path))


if __name__ == "__main__":
    main()
