"""Batch B+C ops fixes: leave clash in Needs attention + Visits badge, completed-this-week
counts jobs, future check-in refused, awaiting reply, one rule for the enquiry badge."""

from datetime import datetime, timedelta, timezone

import pytest
from workforceos_core.exceptions import WorkforceHTTPError as HTTPException

from app.livewell import care_jobs
from app.livewell.dashboard_attention import IST, attention, nav_counts
from app.models.care_job import CareJob
from app.models.elder_prospect import ElderProspect
from app.models.leave_request import LeaveRequest


def _job(db, seed, *, at, status="scheduled", caregiver=True, completed_at=None):
    e = seed["elder"]
    j = CareJob(
        tenant_id=e.tenant_id,
        elder_id=e.id,
        caregiver_id=seed["caregiver"].id if caregiver else None,
        kind="care_visit",
        title="Visit",
        scheduled_at=at,
        status=status,
        completed_at=completed_at,
    )
    db.add(j)
    db.commit()
    return j


def test_leave_clash_shows_in_attention_and_visits_badge(db, seed_tenant):
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).astimezone(IST)
    job = _job(db, seed_tenant, at=tomorrow.replace(hour=10, minute=0).astimezone(timezone.utc))
    manager = seed_tenant["manager"]
    before = nav_counts(db, manager)["nav"]["schedule"]
    db.add(
        LeaveRequest(
            tenant_id=seed_tenant["tenant"].id,
            caregiver_id=seed_tenant["caregiver"].id,
            leave_type="ANNUAL",
            start_date=tomorrow.date(),
            end_date=tomorrow.date(),
            status="APPROVED",
        )
    )
    db.commit()

    data = attention(db, manager)
    assert [c["job_id"] for c in data["cover"]] == [job.id]
    assert data["counts"]["cover"] == 1
    counts = nav_counts(db, manager)
    assert counts["cover"] == 1
    assert counts["nav"]["schedule"] == before + 1

    # Reassigned (or pending leave only) → no longer needs cover.
    job.caregiver_id = None
    db.commit()
    assert attention(db, manager)["cover"] == []


def test_completed_this_week_counts_care_jobs(db, seed_tenant):
    now = datetime.now(timezone.utc)
    _job(db, seed_tenant, at=now - timedelta(minutes=90), status="completed", completed_at=now - timedelta(minutes=30))
    # Completed last week: not counted.
    _job(db, seed_tenant, at=now - timedelta(days=9), status="completed", completed_at=now - timedelta(days=9))
    assert attention(db, seed_tenant["admin"])["counts"]["visits_this_week"] == 1


def test_check_in_refused_more_than_12h_early(db, seed_tenant):
    now = datetime.now(timezone.utc)
    far = _job(db, seed_tenant, at=now + timedelta(days=2))
    with pytest.raises(HTTPException) as err:
        care_jobs.caregiver_set_status(db, seed_tenant["manager"], far.id, "checked_in")
    assert err.value.status_code == 400
    assert "12 hours" in str(err.value.detail)
    with pytest.raises(HTTPException):
        care_jobs.update_job(db, seed_tenant["admin"], far.id, {"status": "checked_in"})

    soon = _job(db, seed_tenant, at=now + timedelta(hours=2))
    out = care_jobs.caregiver_set_status(db, seed_tenant["manager"], soon.id, "checked_in")
    assert out["status"] == "checked_in"


def test_read_family_message_without_reply_is_awaiting(db, seed_tenant):
    e = seed_tenant["elder"]
    now = datetime.now(timezone.utc)
    e.custom_attributes = {
        **(e.custom_attributes or {}),
        "safe_home": {
            "family_hub": {
                "messages": [
                    {"id": "m1", "body": "Question: is the physio coming?", "sender_role": "family",
                     "created_at": (now - timedelta(hours=2)).isoformat()},
                ],
                # Read after the message: nothing unread, but still no reply.
                "staff_read_at": now.isoformat(),
            }
        },
    }
    db.commit()
    data = attention(db, seed_tenant["manager"])
    assert [m["elder_id"] for m in data["messages"]] == [e.id]
    assert data["messages"][0]["unread_count"] == 0
    assert nav_counts(db, seed_tenant["manager"])["awaiting_reply"] == 1

    # A team reply after it clears it.
    hub = dict(e.custom_attributes["safe_home"]["family_hub"])
    hub["messages"] = hub["messages"] + [
        {"id": "m2", "body": "Yes, at 4 pm.", "sender_role": "team", "created_at": now.isoformat()}
    ]
    e.custom_attributes = {**e.custom_attributes, "safe_home": {"family_hub": hub}}
    db.commit()
    assert attention(db, seed_tenant["manager"])["messages"] == []
    assert nav_counts(db, seed_tenant["manager"])["awaiting_reply"] == 0


def test_enquiry_badge_matches_new_list_rule(db, seed_tenant):
    tid = seed_tenant["tenant"].id
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=45)
    db.add_all(
        [
            ElderProspect(tenant_id=tid, first_name="New", last_name="Web", stage="NEW", status="OPEN",
                          source="website:contact"),
            # Older than 30 days but still New on the list: the badge counts it too.
            ElderProspect(tenant_id=tid, first_name="Old", last_name="New", stage="NEW", status="OPEN",
                          source="Phone call", created_at=old),
            ElderProspect(tenant_id=tid, first_name="Called", last_name="Back", stage="CONTACTED", status="OPEN"),
        ]
    )
    db.commit()
    listed_new = (
        db.query(ElderProspect)
        .filter(ElderProspect.tenant_id == tid, ElderProspect.status == "OPEN", ElderProspect.stage == "NEW")
        .count()
    )
    counts = nav_counts(db, seed_tenant["admin"])
    assert counts["enquiries"] == listed_new == 2
    assert counts["nav"]["enquiries"] == 2
    assert len(attention(db, seed_tenant["admin"])["enquiries"]) == 2
