"""Brute-force throttling for sign-in and password-reset requests.

Stored in the ``auth_attempts`` table so every uvicorn worker sees the same counts
(production runs ``--workers 2``).

- Per email: 5 failed sign-ins within 15 minutes locks that email for 15 minutes
  after the last failure. Unknown emails are counted the same way, so the response
  never reveals whether an account exists. A successful sign-in clears the count.
- Per client IP: 30 failed sign-ins within 15 minutes blocks that IP for 15 minutes.
- Password-reset requests: 5 per hour per email.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.auth_attempt import AuthAttempt

log = logging.getLogger("app.auth.throttle")

LOGIN_EMAIL = "login_email"
LOGIN_IP = "login_ip"
RESET_EMAIL = "reset_email"

EMAIL_MAX_FAILS = 5
IP_MAX_FAILS = 30
LOCK_WINDOW = timedelta(minutes=15)
RESET_MAX = 5
RESET_WINDOW = timedelta(hours=1)

LOGIN_BLOCKED_MESSAGE = (
    "Too many sign-in attempts. Try again in 15 minutes, or reset your password."
)
RESET_BLOCKED_MESSAGE = "Too many password reset requests. Try again in an hour."

# Only the local nginx may tell us the real client address.
_TRUSTED_PROXIES = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def norm_email(email: str | None) -> str:
    return (email or "").strip().lower()[:320]


def client_ip(request: Request | None) -> str:
    """Peer address, or the address nginx saw when the peer is the local nginx.

    nginx sets ``X-Real-IP $remote_addr`` (overwritten, not client-controlled) and
    appends to ``X-Forwarded-For``; the client can forge the leading XFF entries, so
    we use X-Real-IP and fall back to the last XFF entry (the one nginx added).
    """
    if request is None:
        return "unknown"
    peer = request.client.host if request.client else ""
    if peer in _TRUSTED_PROXIES:
        real = (request.headers.get("x-real-ip") or "").strip()
        if real:
            return real[:64]
        fwd = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
        if fwd:
            return fwd[-1][:64]
    return (peer or "unknown")[:64]


def _lock_remaining(db: Session, kind: str, key: str, limit: int, window: timedelta) -> int:
    """Seconds left on a lock, 0 if not locked.

    Locked when the ``limit`` most recent attempts all fall within ``window``; the
    lock lasts ``window`` from the latest of them.
    """
    if not key:
        return 0
    rows = (
        db.query(AuthAttempt.created_at)
        .filter(AuthAttempt.kind == kind, AuthAttempt.key == key)
        .order_by(AuthAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
    if len(rows) < limit:
        return 0
    newest, oldest = rows[0][0], rows[-1][0]
    if newest - oldest > window:
        return 0
    remaining = (newest + window - _now()).total_seconds()
    return math.ceil(remaining) if remaining > 0 else 0


def _record(db: Session, kind: str, key: str) -> None:
    if not key:
        return
    db.add(AuthAttempt(kind=kind, key=key, created_at=_now()))
    # Occasionally drop rows nobody will look at again.
    if random.random() < 0.02:
        db.query(AuthAttempt).filter(AuthAttempt.created_at < _now() - timedelta(days=1)).delete(
            synchronize_session=False
        )
    db.commit()


def _too_many(message: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=message,
        headers={"Retry-After": str(max(1, retry_after))},
    )


def check_login_allowed(db: Session, email: str, request: Request | None) -> None:
    """Raise 429 if this email or client IP is locked. Call before checking the password."""
    ident = norm_email(email)
    ip = client_ip(request)
    wait = _lock_remaining(db, LOGIN_EMAIL, ident, EMAIL_MAX_FAILS, LOCK_WINDOW)
    scope = "email"
    if not wait:
        wait = _lock_remaining(db, LOGIN_IP, ip, IP_MAX_FAILS, LOCK_WINDOW)
        scope = "ip"
    if wait:
        log.warning("login_blocked scope=%s email=%s ip=%s retry_after=%s", scope, ident, ip, wait)
        raise _too_many(LOGIN_BLOCKED_MESSAGE, wait)


def record_login_failure(db: Session, email: str, request: Request | None) -> None:
    try:
        _record(db, LOGIN_EMAIL, norm_email(email))
        _record(db, LOGIN_IP, client_ip(request))
    except Exception:  # never let throttling bookkeeping break sign-in
        db.rollback()
        log.exception("login_failure_record_failed")


def record_login_success(db: Session, email: str) -> None:
    ident = norm_email(email)
    if not ident:
        return
    try:
        db.query(AuthAttempt).filter(
            AuthAttempt.kind == LOGIN_EMAIL, AuthAttempt.key == ident
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("login_success_reset_failed")


def check_and_record_reset_request(db: Session, email: str, request: Request | None) -> None:
    """5 reset requests per hour per email (same for unknown addresses)."""
    ident = norm_email(email)
    since = _now() - RESET_WINDOW
    count = (
        db.query(AuthAttempt)
        .filter(
            AuthAttempt.kind == RESET_EMAIL,
            AuthAttempt.key == ident,
            AuthAttempt.created_at >= since,
        )
        .count()
    )
    if count >= RESET_MAX:
        oldest = (
            db.query(AuthAttempt.created_at)
            .filter(
                AuthAttempt.kind == RESET_EMAIL,
                AuthAttempt.key == ident,
                AuthAttempt.created_at >= since,
            )
            .order_by(AuthAttempt.created_at.asc())
            .first()
        )
        wait = math.ceil((oldest[0] + RESET_WINDOW - _now()).total_seconds()) if oldest else 3600
        log.warning("reset_blocked email=%s ip=%s retry_after=%s", ident, client_ip(request), wait)
        raise _too_many(RESET_BLOCKED_MESSAGE, wait)
    _record(db, RESET_EMAIL, ident)
