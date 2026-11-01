"""Android app self-update: the app asks for the latest version on start and, when it
is newer, downloads the APK from here (Android then asks the person to install it).

Files live in APP_RELEASES_DIR (default backend/releases, outside the deploy tar):
  ops.json / family.json   {"version_code": 2, "version_name": "1.1", "sha256": "...", "notes": "..."}
  kushalaya-ops.apk / kushalaya-family.apk
mobile/scripts/build.mjs release writes both into mobile/dist/release/. Public on purpose:
the app checks before anyone signs in, and the APK holds no secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/app-release", tags=["App release"])

App = Literal["ops", "family"]


def releases_dir() -> Path:
    configured = str(getattr(settings, "APP_RELEASES_DIR", "") or "").strip()
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "releases"


def _manifest(app: str) -> dict:
    path = releases_dir() / f"{app}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        code = int(data["version_code"])
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(404, "No release published")
    if not (releases_dir() / f"kushalaya-{app}.apk").is_file():
        raise HTTPException(404, "No release published")
    return {
        "version_code": code,
        "version_name": str(data.get("version_name") or code),
        "sha256": str(data.get("sha256") or ""),
        "notes": str(data.get("notes") or ""),
        "url": f"/api/v1/app-release/android/{app}/download",
    }


@router.get("/android/{app}")
def latest(app: App) -> dict:
    return _manifest(app)


@router.get("/android/{app}/download")
def download(app: App) -> FileResponse:
    _manifest(app)
    return FileResponse(
        releases_dir() / f"kushalaya-{app}.apk",
        media_type="application/vnd.android.package-archive",
        filename=f"KushAlaya-{app.title()}.apk",
        headers={"Cache-Control": "no-cache"},
    )
