"""Durable background job ledger — model from workforceos-core."""

from app.core.database import Base
from app.models.mixins import TimestampMixin
from workforceos_core.jobs.constants import (
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    TERMINAL_STATUSES,
)
from workforceos_core.jobs.model import background_job_model

BackgroundJob = background_job_model(Base, TimestampMixin)

__all__ = [
    "BackgroundJob",
    "STATUS_CANCELLED",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_SUCCEEDED",
    "TERMINAL_STATUSES",
]
