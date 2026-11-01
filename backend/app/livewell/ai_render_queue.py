"""In-process background queue for AI room preview renders.

The request creates a `queued` job row, commits, and calls `submit()`; a worker thread
in the API process claims the row (queued → running, atomically, so a second API
process can never run it twice), renders, and commits progress stages so the UI can
poll. One render at a time per tenant. On start-up, rows left queued/running by a
restart are picked up again (recent) or failed (stale).

Tests and ENVIRONMENT=test run the job inline in the request's session.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.home_safety_ai_job import HomeSafetyAIJob

log = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_tenant_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()
STALE_AFTER = timedelta(minutes=30)


def _inline() -> bool:
    import os

    from app.core.config import settings

    flag = os.environ.get("AI_RENDER_INLINE", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return (settings.ENVIRONMENT or "").strip().lower() == "test"


def _lock_for(tenant_id: int) -> threading.Lock:
    with _locks_guard:
        lock = _tenant_locks.get(tenant_id)
        if lock is None:
            lock = threading.Lock()
            _tenant_locks[tenant_id] = lock
        return lock


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ai-render")
    return _executor


def submit(db: Session, job_id: int, tenant_id: int) -> None:
    """Run the job in the background (or inline in tests). Never raises to the caller."""
    if _inline():
        process_job(db, job_id)
        return
    _pool().submit(_run_in_thread, job_id, tenant_id)


def _claim(db: Session, job_id: int) -> bool:
    res = db.execute(
        update(HomeSafetyAIJob)
        .where(HomeSafetyAIJob.id == job_id, HomeSafetyAIJob.status == "queued")
        .values(
            status="running",
            progress_stage="preparing",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()
    return bool(res.rowcount)


def _run_in_thread(job_id: int, tenant_id: int) -> None:
    from app.core.database import SessionLocal

    with _lock_for(tenant_id):
        db = SessionLocal()
        try:
            process_job(db, job_id)
        except Exception:
            log.exception("AI render worker crashed on job %s", job_id)
        finally:
            db.close()


def process_job(db: Session, job_id: int) -> None:
    """Claim and render one queued job, committing each stage. Safe to call twice."""
    from app.livewell.ai_visualization_service import HomeSafetyAIVisualizationService as Svc
    from app.models.document import Document
    from app.models.user import User

    if not _claim(db, job_id):
        return
    job = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.id == job_id).first()
    if job is None:
        return
    try:
        creator_id = None
        for e in job.event_log or []:
            if isinstance(e, dict) and e.get("event") == "job_created":
                creator_id = (e.get("detail") or {}).get("created_by_user_id")
                break
        user = db.query(User).filter(User.id == creator_id).first() if creator_id else None
        doc = db.query(Document).filter(Document.id == job.source_document_id).first()
        if user is None or doc is None:
            raise RuntimeError("creator or source photo missing")
        ctx = Svc._load_job_context(db, user)

        def on_stage(_name: str) -> None:
            db.commit()  # the UI polls this row

        Svc._render(db, ctx, job, doc, on_stage=on_stage)
        db.refresh(job, attribute_names=["review_status"])
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.id == job_id).first()
        if job is not None:
            job.status = "failed"
            job.progress_stage = "failed"
            job.error_code = "WORKER_ERROR"
            job.error_message = f"Preview could not be made ({type(exc).__name__})."
            job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
        log.exception("AI render failed for job %s", job_id)


def recover_pending() -> int:
    """Start-up: re-run recent queued/running jobs, fail stale ones. Returns re-queued count."""
    if _inline():
        return 0
    from app.core.database import SessionLocal

    db = SessionLocal()
    requeued = 0
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - STALE_AFTER
        rows = (
            db.query(HomeSafetyAIJob)
            .filter(HomeSafetyAIJob.status.in_(("queued", "running")))
            .all()
        )
        todo: list[tuple[int, int]] = []
        for job in rows:
            if (job.created_at or cutoff) < cutoff:
                job.status = "failed"
                job.progress_stage = "failed"
                job.error_code = "INTERRUPTED"
                job.error_message = "Interrupted by a server restart. Generate again."
                continue
            job.status = "queued"
            job.progress_stage = "queued"
            todo.append((job.id, job.tenant_id))
        db.commit()
        for job_id, tenant_id in todo:
            _pool().submit(_run_in_thread, job_id, tenant_id)
            requeued += 1
    except Exception:
        log.exception("AI render recovery failed")
    finally:
        db.close()
    return requeued
