"""Session policy: no sign-out for inactivity (owner, 2026-10-26).

There is no idle limit and no absolute session limit for anyone (staff, family,
caregivers). A session that is in use keeps refreshing: each refresh hands out
a new sliding refresh token, so only normal token expiry (an unused refresh
token running out) or an explicit sign-out ends it.

Older agencies may still have ``tenant.workflow_config["security"]`` idle
minutes saved from Settings -> Security; they are ignored.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def policy_for(db: Session, user) -> dict:
    """``{"idle_minutes": None, "absolute_hours": 0}``: no idle or absolute limit."""
    return {"idle_minutes": None, "absolute_hours": 0}


def refresh_rejection(payload: dict, policy: dict, access_minutes: int, now: float | None = None) -> str | None:
    """Never refuse a valid refresh token for inactivity or session age."""
    return None
