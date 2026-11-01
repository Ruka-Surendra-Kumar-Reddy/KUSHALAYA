"""Session telemetry: ended sessions stay ended, idle gaps split, system rolls daily."""

from datetime import datetime, timedelta, timezone

import app.models  # noqa: F401

from app.models.user_session import UserSession, UserSessionEvent
from app.services import session_activity_service as sas
from app.services.session_activity_service import (
    SESSION_IDLE_SPLIT,
    SessionActivityService,
    session_should_split,
)


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_activity_after_logout_opens_new_session_not_reopen(db, seed_tenant):
    manager = seed_tenant["manager"]
    first = SessionActivityService.start_session(db, manager)
    db.commit()
    SessionActivityService.end_session(db, first.id, user_id=manager.id)
    db.refresh(first)
    assert first.ended_at is not None
    ended_at = first.ended_at

    # Client still sends the old X-Session-ID.
    event = SessionActivityService.record_event(
        db, session_id=first.id, tenant_id=manager.tenant_id, action="Saved assessment"
    )
    assert event is not None
    assert event.session_id != first.id

    db.refresh(first)
    assert first.ended_at == ended_at  # never re-opened

    successor = db.query(UserSession).filter(UserSession.id == event.session_id).one()
    assert successor.root_session_id == first.id
    assert successor.ended_at is None
    assert successor.user_id == manager.id

    # And a further event lands on the same successor, not a third session.
    again = SessionActivityService.record_event(
        db, session_id=first.id, tenant_id=manager.tenant_id, action="Uploaded room photo"
    )
    assert again.session_id == successor.id
    assert db.query(UserSession).filter(UserSession.user_id == manager.id).count() == 2

    # Logout with the original header id closes the live successor.
    SessionActivityService.end_session(db, first.id, user_id=manager.id)
    db.refresh(successor)
    assert successor.ended_at is not None


def test_idle_gap_splits_session_at_last_seen(db, seed_tenant, monkeypatch):
    manager = seed_tenant["manager"]
    session = SessionActivityService.start_session(db, manager)
    db.commit()

    base = _utc(session.started_at)
    later = base + SESSION_IDLE_SPLIT + timedelta(minutes=5)
    monkeypatch.setattr(sas, "_utcnow", lambda: later)

    event = SessionActivityService.record_event(
        db, session_id=session.id, tenant_id=manager.tenant_id, action="Opened assessment"
    )
    db.refresh(session)
    assert session.ended_at is not None
    # Closed at its last activity, so the old session's duration is not inflated by the gap.
    assert _utc(session.ended_at) == _utc(session.last_seen_at)
    assert _utc(session.ended_at) - base < SESSION_IDLE_SPLIT

    successor = db.query(UserSession).filter(UserSession.id == event.session_id).one()
    assert successor.id != session.id
    assert successor.root_session_id == session.id
    assert _utc(successor.started_at) == later

    ended_events = (
        db.query(UserSessionEvent)
        .filter(UserSessionEvent.session_id == session.id, UserSessionEvent.action == "Session ended")
        .all()
    )
    assert len(ended_events) == 1
    assert "Idle" in (ended_events[0].summary or "")


def test_short_gap_keeps_same_session(db, seed_tenant, monkeypatch):
    manager = seed_tenant["manager"]
    session = SessionActivityService.start_session(db, manager)
    db.commit()
    soon = _utc(session.started_at) + timedelta(minutes=10)
    monkeypatch.setattr(sas, "_utcnow", lambda: soon)
    event = SessionActivityService.record_event(
        db, session_id=session.id, tenant_id=manager.tenant_id, action="Saved assessment"
    )
    assert event.session_id == session.id
    db.refresh(session)
    assert session.ended_at is None


def test_system_session_rolls_over_daily(db, seed_tenant, monkeypatch):
    tenant = seed_tenant["tenant"]
    day1 = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sas, "_utcnow", lambda: day1)
    first = SessionActivityService.ensure_system_session(db, tenant_id=tenant.id)
    assert first is not None
    db.commit()

    # Same day, hours later: same session (no idle split for system sessions).
    same_day = day1 + timedelta(hours=9)
    monkeypatch.setattr(sas, "_utcnow", lambda: same_day)
    assert not session_should_split(first, same_day)
    again = SessionActivityService.ensure_system_session(db, tenant_id=tenant.id)
    assert again.id == first.id
    SessionActivityService.record_ai_or_system_event(
        db, action="Workflow scan completed", session_id=first.id, event_kind="system", commit=True
    )

    # Next day: yesterday's session is closed at its last event, a new one opens.
    day2 = day1 + timedelta(days=1)
    monkeypatch.setattr(sas, "_utcnow", lambda: day2)
    rolled = SessionActivityService.ensure_system_session(db, tenant_id=tenant.id)
    db.commit()
    assert rolled.id != first.id
    db.refresh(first)
    assert first.ended_at is not None
    assert _utc(first.ended_at) == _utc(first.last_seen_at)
    assert _utc(first.ended_at) - _utc(first.started_at) <= timedelta(days=1)

    # Events addressed to yesterday's id also land on today's session.
    ev = SessionActivityService.record_ai_or_system_event(
        db, action="Attendance scan completed", session_id=first.id, event_kind="system", commit=True
    )
    assert ev.session_id == rolled.id


def test_session_should_split_rules():
    now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    user = UserSession(
        id="u", user_id=1, actor_type="staff", user_email="a@b", user_role="VIEWER",
        started_at=now - timedelta(hours=2), last_seen_at=now - timedelta(minutes=29),
    )
    assert not session_should_split(user, now)
    user.last_seen_at = now - timedelta(minutes=31)
    assert session_should_split(user, now)
    user.last_seen_at = now
    user.ended_at = now
    assert session_should_split(user, now)

    system = UserSession(
        id="s", user_id=1, actor_type="system", user_email="s@b", user_role="SYSTEM",
        started_at=now - timedelta(hours=11), last_seen_at=now - timedelta(hours=5),
    )
    assert not session_should_split(system, now)  # same UTC day, long gap is fine
    system.started_at = now - timedelta(hours=13)  # yesterday 23:00
    assert session_should_split(system, now)
