"""Six-monthly reassessment: due 182 days after the last completed assessment."""

from datetime import datetime, timedelta, timezone

from app.models.home_safety_assessment import HomeSafetyAssessmentRecord


def _attention(client, headers):
    res = client.get("/api/v1/home-safety/dashboard/attention", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["reassessments"]


def test_first_then_six_monthly(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    due = _attention(client, auth_headers)
    assert due and due[0]["needs_first"] and due[0]["elder_id"] == elder.id

    done = datetime.now(timezone.utc) - timedelta(days=170)  # due in ~12 days
    db.add(HomeSafetyAssessmentRecord(
        tenant_id=elder.tenant_id, assessment_id="hsa-test-6m", status="completed", elder_id=elder.id,
        payload={"id": "hsa-test-6m"}, completed_at=done.replace(tzinfo=None)))
    db.commit()
    due = _attention(client, auth_headers)
    assert due[0]["label"] == "6-monthly reassessment" and not due[0]["overdue"]

    when = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    client.post("/api/v1/jobs", json={"elder_id": elder.id, "kind": "assessment", "scheduled_at": when},
                headers=auth_headers)
    assert _attention(client, auth_headers) == []  # booked -> no longer waiting

    prof = client.get(f"/api/v1/home-safety/clients/{elder.id}/profile", headers=auth_headers).json()
    assert prof["reassessment"]["due_at"] and prof["reassessment"]["booked_job_id"]
