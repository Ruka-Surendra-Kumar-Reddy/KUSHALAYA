"""Enqueue recurring background jobs — run from systemd timer on the VM."""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
import app.jobs.handlers  # noqa: F401 — register handlers + configure jobs
from app.jobs.handlers import (
    JOB_ATTENDANCE_SCAN,
    JOB_CARE_DAILY_CHECKS,
    JOB_FAMILY_DIGEST_SEND,
    JOB_INCIDENT_ESCALATION_SCAN,
    JOB_WORKFLOW_SCAN,
)
from app.models.tenant import Tenant
from app.services.background_job_service import BackgroundJobService

logger = logging.getLogger(__name__)


def _enqueue(db, *, job_type: str, dedupe_key: str, payload: dict | None = None, tenant_id: int | None = None):
    """Queue a job unless one of the same kind is already waiting or running.

    ``background_jobs.dedupe_key`` is unique across all rows (finished ones too),
    so each run gets a timestamped key; the pending check does the de-duplication.
    """
    from datetime import datetime, timezone

    from app.models.background_job import BackgroundJob

    waiting = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.dedupe_key.like(f"{dedupe_key}%"), BackgroundJob.status.in_(("PENDING", "RUNNING")))
        .first()
    )
    if waiting:
        return waiting
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return BackgroundJobService.enqueue(
        db, job_type=job_type, payload=payload or {}, tenant_id=tenant_id, dedupe_key=f"{dedupe_key}@{stamp}"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = SessionLocal()
    try:
        from sqlalchemy import inspect

        tables = set(inspect(db.get_bind()).get_table_names())
        # The shared staffing scans need tables this product's database may not have
        # (caregiver certifications, attendance). Skip them rather than fail every tick.
        staffing = {"caregiver_certifications", "attendance_records"} <= tables
        tenants = db.query(Tenant).order_by(Tenant.id).all() if staffing else []
        for tenant in tenants:
            job = _enqueue(
                db,
                job_type=JOB_WORKFLOW_SCAN,
                payload={"tenant_id": tenant.id},
                tenant_id=tenant.id,
                dedupe_key=f"workflow.scan:{tenant.id}",
            )
            logger.info("workflow scan queued tenant=%s job=%s", tenant.id, job.id)

        if staffing:
            att = _enqueue(
                db,
                job_type=JOB_ATTENDANCE_SCAN,
                payload={},
                dedupe_key="attendance.scan_exceptions:all",
            )
            logger.info("attendance scan queued job=%s", att.id)

        # SOS escalation must run every 2 minutes: the ack deadline is 5 min, so
        # a coarser tick would let level 1 slip by minutes. The dedupe key keeps
        # one pending scan at a time however often the timer fires.
        esc = _enqueue(
            db,
            job_type=JOB_INCIDENT_ESCALATION_SCAN,
            payload={},
            dedupe_key="incident.escalation_scan:all",
        )
        logger.info("incident escalation scan queued job=%s", esc.id)

        # Family digests: the handler decides per household whether the local
        # 08:00 slot (daily, or Monday for weekly) has passed since the last
        # send, so enqueueing on every timer tick is safe — it needs to run at
        # least hourly for the send hour to be honoured within the hour.
        digest = _enqueue(
            db,
            job_type=JOB_FAMILY_DIGEST_SEND,
            payload={},
            dedupe_key="family.digest_send:all",
        )
        logger.info("family digest send queued job=%s", digest.id)
        care = _enqueue(
            db,
            job_type=JOB_CARE_DAILY_CHECKS,
            payload={},
            dedupe_key="care.daily_checks:all",
        )
        logger.info("care daily checks queued job=%s", care.id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
