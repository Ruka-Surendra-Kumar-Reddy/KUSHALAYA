"""Create / touch / log user sessions for assessor & family activity tracking."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.rbac import CAREGIVER, ELDER_PORTAL
from app.models.user import User
from app.models.user_session import UserSession, UserSessionEvent

logger = logging.getLogger(__name__)

SESSION_HEADER = "X-Session-ID"
ACTIVITY_INTENT_HEADER = "X-Activity-Intent"

# A user session that sees no activity for this long is closed at its last
# event and further activity opens a new session, so a tab left open for a
# week does not report as a week-long session.
SESSION_IDLE_SPLIT = timedelta(minutes=30)

# The per-tenant system session (background jobs, IoT) never logs out; it is
# rolled over once per UTC day so its duration is at most one day.
SYSTEM_SESSION_MAX_AGE = timedelta(days=1)

SYSTEM_ACTOR = "system"

_SKIP_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
    "/db-test",
    "/favicon",
)

# Successful GETs under these prefixes are skipped in standard mode (hydration noise).
_STANDARD_SKIP_GET_PREFIXES = (
    "/api/v1/auth/me",
    "/api/v1/auth/refresh",
    "/api/v1/home-safety/rubric",
    "/api/v1/home-safety/catalog",
    "/api/v1/home-safety/solutions",
    "/api/v1/home-safety/pricing",
    "/api/v1/home-safety/suppliers",
    "/api/v1/home-safety/master-data",
    "/api/v1/home-safety/assessments",
    "/api/v1/home-safety/signed-docs",
    "/api/v1/home-safety/ai/visualization-jobs",
    "/api/v1/home-safety/recommendation-chat/conversations",
    "/api/v1/elders",
    "/api/v1/prospects",
    "/api/v1/tenants",
    "/api/v1/users",
    "/api/v1/documents",
)

# Friendly labels for common LiveWell / ops API paths.
_PATH_LABELS: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"^/api/v1/auth/login$"), "Logged in", None),
    (re.compile(r"^/api/v1/auth/me$"), "Loaded profile", None),
    (re.compile(r"^/api/v1/auth/refresh$"), "Refreshed session", None),
    (re.compile(r"^/api/v1/auth/logout$"), "Logged out", None),
    (
        re.compile(r"^/api/v1/home-safety/assessments/?$"),
        "Listed assessments",
        "assessment",
    ),
    (
        re.compile(r"^/api/v1/home-safety/assessments/([^/]+)$"),
        "Opened / saved assessment",
        "assessment",
    ),
    (
        re.compile(r"^/api/v1/home-safety/photos$"),
        "Uploaded room photo",
        "photo",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai/analyze$"),
        "Sent photo(s) to AI vision",
        "vision",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai/visualization-jobs/generate-for-photo$"),
        "Sent photo to AI visualization",
        "ai",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai/visualization-jobs$"),
        "Created AI visualization job",
        "ai",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai/visualization-jobs/upload-concept$"),
        "Uploaded concept photo",
        "ai",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai/visualization-jobs/([^/]+)/review$"),
        "Reviewed AI visualization",
        "ai",
    ),
    (
        re.compile(r"^/api/v1/home-safety/family/"),
        "Family portal API",
        "family",
    ),
    (
        re.compile(r"^/api/v1/home-safety/visits"),
        "Visits",
        "visit",
    ),
    (
        re.compile(r"^/api/v1/home-safety/ai"),
        "AI visualization",
        "ai",
    ),
    (
        re.compile(r"^/api/v1/documents"),
        "Documents",
        "document",
    ),
    (re.compile(r"^/api/v1/iot/register-kit$"), "Registered IoT kit", "iot"),
    (re.compile(r"^/api/v1/iot/devices/mac$"), "Updated IoT band MAC", "iot"),
    (re.compile(r"^/api/v1/iot/devices/\d+$"), "Removed IoT band", "iot"),
    (re.compile(r"^/api/v1/iot/devices$"), "Registered IoT band", "iot"),
    (re.compile(r"^/api/v1/iot/hubs/\d+$"), "Removed IoT hub", "iot"),
    (re.compile(r"^/api/v1/iot/hubs$"), "Registered IoT hub", "iot"),
    (re.compile(r"^/api/v1/iot/events$"), "IoT event ingest", "iot"),
]


def actor_type_for_role(role: str) -> str:
    if role == ELDER_PORTAL:
        return "family"
    if role == CAREGIVER:
        return "assessor"
    return "staff"


def activity_log_mode() -> str:
    from app.core.config import settings

    mode = (settings.ACTIVITY_LOG_MODE or "standard").strip().lower()
    if mode in {"verbose", "full", "debug"}:
        return "verbose"
    return "standard"


def is_verbose_activity_log() -> bool:
    return activity_log_mode() == "verbose"


def activity_intent_from_request(request: Request | None) -> str:
    if request is None:
        return ""
    return (request.headers.get(ACTIVITY_INTENT_HEADER) or "").strip().lower()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes even for DateTime(timezone=True)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def session_should_split(session: UserSession, now: datetime) -> bool:
    """True when activity at `now` belongs to a fresh session, not this one."""
    if session.ended_at is not None:
        return True
    if session.actor_type == SYSTEM_ACTOR:
        started = _as_utc(session.started_at)
        if started is None:
            return False
        return started.date() != now.date() or (now - started) >= SYSTEM_SESSION_MAX_AGE
    last_seen = _as_utc(session.last_seen_at) or _as_utc(session.started_at)
    if last_seen is None:
        return False
    return (now - last_seen) > SESSION_IDLE_SPLIT


def _client_meta(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ua = (request.headers.get("user-agent") or "")[:512] or None
    from app.services.login_throttle import client_ip

    ip = client_ip(request)
    return ua, (None if ip == "unknown" else ip)


def summarize_api_call(method: str, path: str) -> tuple[str, str | None, str | None]:
    """Return (action label, entity_type, entity_id)."""
    clean = path.split("?")[0]
    for pattern, label, entity_type in _PATH_LABELS:
        m = pattern.match(clean)
        if m:
            entity_id = m.group(1) if m.lastindex else None
            verb = method.upper()
            if verb == "GET" and "Opened / saved" in label:
                label = "Opened assessment"
            elif verb in ("PUT", "POST", "PATCH") and "Opened / saved" in label:
                label = "Saved assessment"
            elif verb == "DELETE" and entity_type == "assessment":
                label = "Deleted assessment"
            return label, entity_type, entity_id
    short = clean
    if len(short) > 80:
        short = short[:77] + "…"
    return f"{method.upper()} {short}", None, None


class SessionActivityService:
    @staticmethod
    def start_session(
        db: Session,
        user: User,
        *,
        request: Request | None = None,
    ) -> UserSession:
        now = _utcnow()
        ua, ip = _client_meta(request)
        name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
        row = UserSession(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            user_id=user.id,
            actor_type=actor_type_for_role(user.role),
            user_email=user.email,
            user_name=name or user.email,
            user_role=user.role,
            started_at=now,
            last_seen_at=now,
            user_agent=ua,
            ip_address=ip,
            event_count=0,
        )
        db.add(row)
        db.flush()
        SessionActivityService.record_event(
            db,
            session_id=row.id,
            tenant_id=user.tenant_id,
            event_kind="action",
            action="Session started",
            summary=f"{row.actor_type} session for {row.user_email}",
            commit=False,
        )
        return row

    @staticmethod
    def latest_in_family(db: Session, session_id: str) -> UserSession | None:
        """Newest session in the chain rooted at `session_id` (the id the client
        holds). Falls back to the row itself when nothing continued it."""
        sid = (session_id or "").strip()
        if not sid:
            return None
        return (
            db.query(UserSession)
            .filter(or_(UserSession.id == sid, UserSession.root_session_id == sid))
            .order_by(UserSession.started_at.desc())
            .first()
        )

    @staticmethod
    def _close_session(db: Session, row: UserSession, *, at: datetime, reason: str) -> None:
        if row.ended_at is not None:
            return
        row.ended_at = at
        ended_event = UserSessionEvent(
            session_id=row.id,
            tenant_id=row.tenant_id,
            occurred_at=at,
            event_kind="action",
            action="Session ended",
            summary=reason,
        )
        db.add(ended_event)
        row.event_count = int(row.event_count or 0) + 1

    @staticmethod
    def _continue_session(db: Session, previous: UserSession, *, now: datetime) -> UserSession:
        """Open a successor that the client's existing X-Session-ID still resolves to."""
        root_id = previous.root_session_id or previous.id
        row = UserSession(
            id=str(uuid.uuid4()),
            tenant_id=previous.tenant_id,
            user_id=previous.user_id,
            actor_type=previous.actor_type,
            user_email=previous.user_email,
            user_name=previous.user_name,
            user_role=previous.user_role,
            started_at=now,
            last_seen_at=now,
            user_agent=previous.user_agent,
            ip_address=previous.ip_address,
            event_count=1,
            root_session_id=root_id,
        )
        db.add(row)
        db.flush()
        db.add(
            UserSessionEvent(
                session_id=row.id,
                tenant_id=row.tenant_id,
                occurred_at=now,
                event_kind="action",
                action="Session started",
                summary=f"{row.actor_type} session for {row.user_email} (continued)",
                meta={"continued_from": previous.id, "root_session_id": root_id},
            )
        )
        return row

    @staticmethod
    def resolve_live_session(
        db: Session, session_id: str, *, now: datetime | None = None
    ) -> UserSession | None:
        """Session that activity at `now` should be recorded on.

        Ended sessions are never re-opened: activity after logout, after
        SESSION_IDLE_SPLIT of silence, or on a system session from a previous
        day closes the old row (at its last event) and opens a successor.
        """
        now = now or _utcnow()
        session = SessionActivityService.latest_in_family(db, session_id)
        if not session:
            return None
        if not session_should_split(session, now):
            return session
        if session.ended_at is None:
            close_at = _as_utc(session.last_seen_at) or now
            reason = (
                "Rolled over: system session is closed daily"
                if session.actor_type == SYSTEM_ACTOR
                else f"Idle for more than {int(SESSION_IDLE_SPLIT.total_seconds() // 60)} minutes"
            )
            SessionActivityService._close_session(db, session, at=close_at, reason=reason)
        return SessionActivityService._continue_session(db, session, now=now)

    @staticmethod
    def end_session(db: Session, session_id: str, user_id: int | None = None) -> None:
        row = SessionActivityService.latest_in_family(db, session_id)
        if not row or row.ended_at:
            return
        if user_id is not None and row.user_id != user_id:
            return
        now = _utcnow()
        row.last_seen_at = now
        SessionActivityService._close_session(db, row, at=now, reason="Logged out")
        db.commit()

    @staticmethod
    def record_event(
        db: Session,
        *,
        session_id: str,
        tenant_id: int | None,
        event_kind: str = "api_call",
        action: str,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
        request_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        summary: str | None = None,
        meta: dict | None = None,
        commit: bool = True,
    ) -> UserSessionEvent | None:
        now = _utcnow()
        session = SessionActivityService.resolve_live_session(db, session_id, now=now)
        if not session:
            return None

        event = UserSessionEvent(
            session_id=session.id,
            tenant_id=tenant_id if tenant_id is not None else session.tenant_id,
            occurred_at=now,
            event_kind=event_kind,
            action=action[:120],
            method=method,
            path=(path[:512] if path else None),
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            meta=meta,
        )
        db.add(event)
        session.last_seen_at = now
        session.event_count = int(session.event_count or 0) + 1
        if commit:
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("session_event_commit_failed session=%s", session_id)
                return None
        return event

    @staticmethod
    def record_user_action(
        db: Session,
        *,
        request: Request | None,
        user: User | None = None,
        action: str,
        summary: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        meta: dict | None = None,
        commit: bool = False,
    ) -> UserSessionEvent | None:
        """
        Record a named business action on the caller's session (X-Session-ID).
        Safe no-op when the header is missing. Does not commit by default so
        the route's existing transaction can include the event.
        """
        session_id = SessionActivityService.session_id_from_request(request)
        if not session_id:
            return None
        tenant_id = user.tenant_id if user is not None else None
        return SessionActivityService.record_event(
            db,
            session_id=session_id,
            tenant_id=tenant_id,
            event_kind="action",
            action=action[:120],
            summary=summary,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            meta=meta,
            commit=commit,
        )

    @staticmethod
    def session_id_from_request(request: Request | None) -> str:
        if request is None:
            return ""
        return (request.headers.get(SESSION_HEADER) or "").strip()

    @staticmethod
    def resolve_session_for_user(
        db: Session,
        *,
        session_id: str | None = None,
        user_id: int | None = None,
    ) -> str | None:
        """Prefer explicit session id; else latest open session for the user."""
        sid = (session_id or "").strip()
        if sid:
            row = SessionActivityService.latest_in_family(db, sid)
            if row:
                return row.id
        if user_id is None:
            return None
        row = (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id, UserSession.ended_at.is_(None))
            .order_by(UserSession.started_at.desc())
            .first()
        )
        return row.id if row else None

    @staticmethod
    def record_ai_or_system_event(
        db: Session,
        *,
        action: str,
        summary: str | None = None,
        event_kind: str = "ai_result",
        session_id: str | None = None,
        user_id: int | None = None,
        tenant_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        meta: dict | None = None,
        commit: bool = False,
    ) -> UserSessionEvent | None:
        """
        Record an AI return or important system event onto the originating session.
        Falls back to the user's latest open session when session_id is missing.
        """
        sid = SessionActivityService.resolve_session_for_user(
            db, session_id=session_id, user_id=user_id
        )
        if not sid:
            return None
        kind = event_kind if event_kind in {"ai_result", "system"} else "system"
        return SessionActivityService.record_event(
            db,
            session_id=sid,
            tenant_id=tenant_id,
            event_kind=kind,
            action=action[:120],
            summary=summary,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            meta=meta,
            commit=commit,
        )

    @staticmethod
    def ensure_system_session(db: Session, *, tenant_id: int) -> UserSession | None:
        """Stable per-tenant session for background / system events."""
        existing = (
            db.query(UserSession)
            .filter(
                UserSession.tenant_id == tenant_id,
                UserSession.actor_type == SYSTEM_ACTOR,
                UserSession.ended_at.is_(None),
            )
            .order_by(UserSession.started_at.desc())
            .first()
        )
        if existing:
            now = _utcnow()
            if not session_should_split(existing, now):
                return existing
            # Close yesterday's system session at its last event and open today's
            # as its continuation, so events still addressed to the old id land
            # on the live row instead of forking a third session.
            SessionActivityService._close_session(
                db,
                existing,
                at=_as_utc(existing.last_seen_at) or now,
                reason="Rolled over: system session is closed daily",
            )
            successor = SessionActivityService._continue_session(db, existing, now=now)
            db.flush()
            return successor
        admin = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.role.in_(["TENANT_ADMIN", "CARE_MANAGER", "SYSTEM_ADMIN"]))
            .order_by(User.id)
            .first()
        )
        if not admin:
            return None
        now = _utcnow()
        row = UserSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=admin.id,
            actor_type=SYSTEM_ACTOR,
            user_email="system@livewell.local",
            user_name="LiveWell360 System",
            user_role="SYSTEM",
            started_at=now,
            last_seen_at=now,
            event_count=0,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def should_skip_path(path: str) -> bool:
        if not path:
            return True
        if path.startswith(_SKIP_PATH_PREFIXES):
            return True
        # Avoid noise while viewing the activity UI itself
        if path.startswith("/api/v1/activity"):
            return True
        return False

    @staticmethod
    def should_log_api_call(*, method: str, path: str, status_code: int) -> bool:
        """
        standard: mutations + errors only (skip successful hydration GETs).
        verbose: every API call that is not on the skip list.
        """
        if SessionActivityService.should_skip_path(path):
            return False
        if is_verbose_activity_log():
            return True
        method_u = method.upper()
        if status_code >= 400:
            return True
        if method_u in {"POST", "PUT", "PATCH", "DELETE"}:
            return True
        # Successful GET — skip known hydration paths in standard mode
        clean = path.split("?")[0]
        for prefix in _STANDARD_SKIP_GET_PREFIXES:
            if clean == prefix or clean.startswith(prefix + "/"):
                return False
        # Other successful GETs also skipped in standard (keep timeline focused)
        return False

    @staticmethod
    def log_api_call_from_request(
        *,
        session_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str | None,
    ) -> None:
        """Best-effort write using a fresh DB session (safe from middleware)."""
        if not SessionActivityService.should_log_api_call(
            method=method, path=path, status_code=status_code
        ):
            return
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            action, entity_type, entity_id = summarize_api_call(method, path)
            SessionActivityService.record_event(
                db,
                session_id=session_id,
                tenant_id=None,
                event_kind="api_call",
                action=action,
                method=method.upper(),
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=f"{method.upper()} {path} → {status_code}",
                commit=True,
            )
        except Exception:
            logger.exception("session_api_log_failed session=%s path=%s", session_id, path)
        finally:
            db.close()

    @staticmethod
    def list_sessions(
        db: Session,
        *,
        tenant_id: int | None,
        actor_type: str | None = None,
        user_id: int | None = None,
        user_ids: set[int] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UserSession]:
        q = db.query(UserSession)
        if user_ids is not None:
            q = q.filter(UserSession.user_id.in_(user_ids or {-1}))
        if tenant_id is not None:
            q = q.filter(UserSession.tenant_id == tenant_id)
        if actor_type:
            q = q.filter(UserSession.actor_type == actor_type)
        if user_id is not None:
            q = q.filter(UserSession.user_id == user_id)
        return (
            q.order_by(UserSession.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_session(db: Session, session_id: str, tenant_id: int | None) -> UserSession | None:
        q = db.query(UserSession).filter(UserSession.id == session_id)
        if tenant_id is not None:
            q = q.filter(UserSession.tenant_id == tenant_id)
        return q.first()

    @staticmethod
    def list_events(
        db: Session,
        session_id: str,
        *,
        limit: int = 200,
    ) -> list[UserSessionEvent]:
        return (
            db.query(UserSessionEvent)
            .filter(UserSessionEvent.session_id == session_id)
            .order_by(UserSessionEvent.occurred_at.asc())
            .limit(limit)
            .all()
        )
