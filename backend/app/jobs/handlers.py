"""Registered background job handlers — platform scans for this vertical."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.background_jobs import ensure_background_jobs_configured
from app.models.tenant import Tenant
from app.services.attendance_service import AttendanceService
from app.services.workflow_scan_service import WorkflowScanService
from workforceos_core.jobs.constants import JOB_ATTENDANCE_SCAN, JOB_WORKFLOW_SCAN
from workforceos_core.jobs.registry import register_job_handler

# Vertical-local job type: escalates unacknowledged SOS / wearable incidents.
# Defined here (not in workforceos_core) because the shared package is not this
# product's to change; the registry only needs the string.
JOB_INCIDENT_ESCALATION_SCAN = "incident.escalation_scan"

# Vertical-local job type: delivers the family care digest (daily / weekly per
# household preference) via WhatsApp or email. Enqueued hourly; each run sends
# only the digests whose local send slot has passed since their last send.
JOB_FAMILY_DIGEST_SEND = "family.digest_send"

# Vertical-local: missed visits and the daily "assessments to book" email.
JOB_CARE_DAILY_CHECKS = "care.daily_checks"

__all__ = [
    "JOB_ATTENDANCE_SCAN",
    "JOB_CARE_DAILY_CHECKS",
    "JOB_FAMILY_DIGEST_SEND",
    "JOB_INCIDENT_ESCALATION_SCAN",
    "JOB_WORKFLOW_SCAN",
]


def _workflow_scan(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.session_activity_service import SessionActivityService

    tenant_id = payload.get("tenant_id")
    if tenant_id is not None:
        result = WorkflowScanService.scan_tenant(db, int(tenant_id))
        sys_session = SessionActivityService.ensure_system_session(db, tenant_id=int(tenant_id))
        if sys_session:
            SessionActivityService.record_ai_or_system_event(
                db,
                action="Workflow scan completed",
                summary=(
                    f"Emitted {result.get('events_emitted', 0)} workflow event(s)"
                ),
                event_kind="system",
                session_id=sys_session.id,
                user_id=sys_session.user_id,
                tenant_id=int(tenant_id),
                meta=result if isinstance(result, dict) else None,
                commit=True,
            )
        return result

    results = []
    for tenant in db.query(Tenant).order_by(Tenant.id).all():
        r = WorkflowScanService.scan_tenant(db, tenant.id)
        results.append(r)
        sys_session = SessionActivityService.ensure_system_session(db, tenant_id=tenant.id)
        if sys_session:
            SessionActivityService.record_ai_or_system_event(
                db,
                action="Workflow scan completed",
                summary=f"Emitted {r.get('events_emitted', 0)} workflow event(s)",
                event_kind="system",
                session_id=sys_session.id,
                user_id=sys_session.user_id,
                tenant_id=tenant.id,
                meta=r if isinstance(r, dict) else None,
                commit=True,
            )
    return {
        "tenants_scanned": len(results),
        "events_emitted": sum(r.get("events_emitted", 0) for r in results),
        "results": results,
    }


def _attendance_scan(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.models.user import User
    from app.services.session_activity_service import SessionActivityService

    tenant_id = payload.get("tenant_id")
    tenants = []
    if tenant_id is not None:
        tenants = [int(tenant_id)]
    else:
        tenants = [t.id for t in db.query(Tenant).order_by(Tenant.id).all()]

    results = []
    for tid in tenants:
        admin = (
            db.query(User)
            .filter(User.role == "TENANT_ADMIN", User.tenant_id == tid)
            .order_by(User.id)
            .first()
        )
        if not admin:
            results.append({"tenant_id": tid, "skipped": "no_tenant_admin"})
            continue
        scan = AttendanceService.scan_missed_arrivals(db, admin)
        results.append({"tenant_id": tid, **scan})
        sys_session = SessionActivityService.ensure_system_session(db, tenant_id=tid)
        if sys_session:
            SessionActivityService.record_ai_or_system_event(
                db,
                action="Attendance scan completed",
                summary=f"Missed-arrival scan for tenant {tid}",
                event_kind="system",
                session_id=sys_session.id,
                user_id=sys_session.user_id,
                tenant_id=tid,
                meta=scan if isinstance(scan, dict) else None,
                commit=True,
            )
    return {"tenants_scanned": len(tenants), "results": results}


def _incident_escalation_scan(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Walk open, unacknowledged incidents and escalate the ones past a deadline.

    Payload: ``{"tenant_id": n}`` scopes the scan; empty payload scans everyone.
    See ``incident_service.escalation_policy`` for the ladder (5 / 10 / 20 min).
    """
    from app.livewell import incident_service

    tenant_id = payload.get("tenant_id")
    return incident_service.run_escalation_scan(
        db,
        tenant_id=int(tenant_id) if tenant_id is not None else None,
    )


def _family_digest_send(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Send due family care digests. Payload ``{"tenant_id": n}`` scopes the run."""
    from app.livewell.family_digest_sender import run_family_digest_send
    from app.services.session_activity_service import SessionActivityService

    tenant_id = payload.get("tenant_id")
    result = run_family_digest_send(
        db,
        tenant_id=int(tenant_id) if tenant_id is not None else None,
    )
    touched = sorted({int(d["tenant_id"]) for d in result.get("deliveries", [])})
    for tid in touched:
        sys_session = SessionActivityService.ensure_system_session(db, tenant_id=tid)
        if not sys_session:
            continue
        rows = [d for d in result["deliveries"] if int(d["tenant_id"]) == tid]
        SessionActivityService.record_ai_or_system_event(
            db,
            action="Family digest send completed",
            summary=f"{len(rows)} digest(s) processed for tenant {tid}",
            event_kind="system",
            session_id=sys_session.id,
            user_id=sys_session.user_id,
            tenant_id=tid,
            meta={"deliveries": rows},
            commit=True,
        )
    return result


register_job_handler(JOB_WORKFLOW_SCAN, _workflow_scan)
register_job_handler(JOB_ATTENDANCE_SCAN, _attendance_scan)
register_job_handler(JOB_INCIDENT_ESCALATION_SCAN, _incident_escalation_scan)
register_job_handler(JOB_FAMILY_DIGEST_SEND, _family_digest_send)


def _care_daily_checks(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.livewell.daily_checks import run

    return run(db)


register_job_handler(JOB_CARE_DAILY_CHECKS, _care_daily_checks)

ensure_background_jobs_configured()
