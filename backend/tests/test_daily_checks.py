"""Timer checks: missed visits and the daily "assessments to book" email."""

from datetime import datetime, timedelta, timezone

from app.livewell import daily_checks, email_notifications
from app.models.care_job import CareJob


def test_missed_visit_and_reassessment_digest(db, seed_tenant, monkeypatch):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    now = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)  # 11:30 India time
    old = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Care visit",
                  status="scheduled", scheduled_at=now - timedelta(hours=4))
    soon = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Care visit",
                   status="scheduled", scheduled_at=now - timedelta(hours=1))
    db.add_all([old, soon])
    db.commit()

    sent = []
    monkeypatch.setattr(email_notifications, "send",
                        lambda to, title, body, *, family, background=True: sent.append((list(to), title, family)))

    assert daily_checks.mark_missed_visits(db, now=now) == [old.id]
    db.refresh(old), db.refresh(soon)
    assert old.status == "missed" and soon.status == "scheduled"
    staff = [s for s in sent if not s[2]]
    assert staff and seed_tenant["manager"].email in staff[0][0] and staff[0][1].startswith("Missed")

    # No assessment on record yet -> on the list. Once a day only.
    sent.clear()
    assert daily_checks.send_reassessment_digests(db, now=now) == [elder.tenant_id]
    assert any("assessment" in t for _to, t, _f in sent)
    sent.clear()
    assert daily_checks.send_reassessment_digests(db, now=now + timedelta(hours=2)) == []
    assert sent == []
    # Before 08:00 India time nothing goes out.
    assert daily_checks.send_reassessment_digests(db, now=now + timedelta(days=1) - timedelta(hours=4)) == []
