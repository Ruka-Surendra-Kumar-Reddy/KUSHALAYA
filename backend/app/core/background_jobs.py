"""Wire workforceos_core.jobs to this vertical app's ORM and RBAC."""

from __future__ import annotations

from app.core.config import settings
from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.background_job import BackgroundJob
from workforceos_core.jobs.deps import BackgroundJobDeps, configure_background_jobs
from workforceos_core.jobs.payload import parse_payload
from workforceos_core.jobs.registry import known_job_types, run_handler

_configured = False


def ensure_background_jobs_configured() -> None:
    global _configured
    if _configured:
        return
    configure_background_jobs(
        BackgroundJobDeps(
            job_model=BackgroundJob,
            resolve_tenant_id=resolve_tenant_id,
            assert_tenant_access=assert_tenant_access,
            raise_bad_request=raise_bad_request,
            raise_not_found=raise_not_found,
            database_url=lambda: settings.DATABASE_URL or "",
            run_handler=run_handler,
            parse_payload=parse_payload,
            known_job_types=known_job_types,
        ),
    )
    _configured = True
