from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.storage import get_storage
from app.release import RELEASE_ID


def check_database() -> tuple[bool, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        backend = (
            "postgresql"
            if settings.DATABASE_URL.startswith("postgresql")
            else "sqlite"
        )
        return True, backend
    except Exception as exc:
        return False, str(exc)


def check_storage() -> tuple[bool, str]:
    try:
        backend = settings.STORAGE_BACKEND
        if backend == "azure":
            storage = get_storage()
            if not hasattr(storage, "client"):
                return False, "azure client not initialized"
            return True, "azure"
        root = settings.UPLOAD_DIR
        from pathlib import Path

        path = Path(root)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".health_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, "local"
    except Exception as exc:
        return False, str(exc)


def readiness_report() -> dict:
    db_ok, db_detail = check_database()
    storage_ok, storage_detail = check_storage()
    checks = {
        "database": {"ok": db_ok, "detail": db_detail},
        "storage": {"ok": storage_ok, "detail": storage_detail},
    }
    all_ok = db_ok and storage_ok
    return {
        "status": "healthy" if all_ok else "degraded",
        "environment": settings.ENVIRONMENT,
        "release": RELEASE_ID,
        "checks": checks,
    }
