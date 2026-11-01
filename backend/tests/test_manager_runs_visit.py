"""Caregivers don't use an app: the care manager runs the visit from the ops portal."""
from tests.assess_client import confirm_client


from datetime import datetime, timedelta, timezone

from app.models.elder import Elder


def _job(client, headers, elder_id, cg_id, kind="visit"):
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    res = client.post("/api/v1/jobs", json={"elder_id": elder_id, "kind": kind, "scheduled_at": when,
                                            "caregiver_id": cg_id}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_manager_runs_visit_with_report(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _job(client, auth_headers, elder.id, cg.id)
    for step in ("on_the_way", "checked_in"):
        res = client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": step}, headers=auth_headers)
        assert res.status_code == 200, res.text
    done = client.post(f"/api/v1/jobs/{job['id']}/report",
                       json={"checks": {"safe": "ok", "steady": "ok", "settled": "concern", "connected": "ok"}, "note": "Low appetite today"}, headers=auth_headers)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed" and body["caregiver_name"]  # caregiver still recorded


def test_manager_does_assessment(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _job(client, auth_headers, elder.id, cg.id, kind="assessment")
    client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "checked_in"}, headers=auth_headers)
    form = client.get(f"/api/v1/jobs/{job['id']}/assessment", headers=auth_headers).json()
    ratings = {i["id"]: "excellent" for c in form["categories"] for i in c["items"]}
    confirm_client(client, auth_headers, job["id"])
    res = client.put(f"/api/v1/jobs/{job['id']}/assessment", json={"ratings": ratings, "complete": True},
                     headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["job"]["status"] == "completed"


def test_manager_cannot_run_other_teams_job(client, db, seed_tenant):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    admin = {"Authorization": f"Bearer {res.json()['access_token']}"}
    outside = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="Side", status="ACTIVE")
    db.add(outside)
    db.commit()
    job = _job(client, admin, outside.id, None)
    mgr = client.post("/api/v1/auth/login", json={"email": "manager@test.example", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {mgr.json()['access_token']}"}
    res = client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "checked_in"}, headers=headers)
    assert res.status_code == 404


def test_reassessment_remembers_questions_that_do_not_apply(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _job(client, auth_headers, elder.id, cg.id, kind="assessment")
    form = client.get(f"/api/v1/jobs/{job['id']}/assessment", headers=auth_headers).json()
    ids = [i["id"] for c in form["categories"] for i in c["items"]]
    ratings = {i: "excellent" for i in ids}
    ratings[ids[0]] = "na"  # e.g. no stairs in this home
    confirm_client(client, auth_headers, job["id"])
    client.put(f"/api/v1/jobs/{job['id']}/assessment", json={"ratings": ratings, "complete": True}, headers=auth_headers)

    again = _job(client, auth_headers, elder.id, cg.id, kind="assessment")
    form2 = client.get(f"/api/v1/jobs/{again['id']}/assessment", headers=auth_headers).json()
    assert form2["skip_for_home"] == [ids[0]]
    assert form2["ratings"] == {ids[0]: "na"}


def test_log_past_visit_saves_completed_report(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    when = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    res = client.post("/api/v1/jobs/log-past", headers=auth_headers, json={
        "elder_id": elder.id, "caregiver_id": cg.id, "visited_at": when,
        "checks": {"safe": "ok", "steady": "concern", "settled": "ok", "connected": "ok"}, "note": "Unsteady on the stairs",
    })
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["status"] == "completed" and job["report"]["checks"]["steady"] == "concern"
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    bad = client.post("/api/v1/jobs/log-past", headers=auth_headers,
                      json={"elder_id": elder.id, "visited_at": future})
    assert bad.status_code == 400


def test_assessment_keeps_tapped_option_labels_and_admin_options(client, seed_tenant, auth_headers, admin_headers):
    """Rubric editor options reach the form; the tapped option's words are kept for the report."""
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    rubric = {"categories": [{"id": "bath", "title": "Bathroom", "items": [
        {"id": "q1", "label": "Grab bar", "maxPoints": 2, "ask": "Is there a grab bar?",
         "options": [{"label": "Yes, firm", "rating": "excellent"}, {"label": "Towel rail", "rating": "unsafe"},
                     {"label": "No bar", "rating": "unsafe"}]},
        {"id": "q2", "label": "Lighting", "maxPoints": 1},
    ]}]}
    assert client.put("/api/v1/home-safety/rubric", json=rubric, headers=admin_headers).status_code == 200
    job = _job(client, auth_headers, elder.id, cg.id, kind="assessment")
    form = client.get(f"/api/v1/jobs/{job['id']}/assessment", headers=auth_headers).json()
    q1 = next(i for c in form["categories"] for i in c["items"] if i["id"] == "q1")
    assert q1["ask"] == "Is there a grab bar?" and [o["label"] for o in q1["options"]][1] == "Towel rail"
    labels = {"q1": "  Towel rail  ", "q2": "", "ghost": "Not answered"}
    res = client.put(f"/api/v1/jobs/{job['id']}/assessment",
                     json={"ratings": {"q1": "unsafe", "q2": "excellent"}, "answer_labels": labels},
                     headers=auth_headers)
    assert res.status_code == 200, res.text
    again = client.get(f"/api/v1/jobs/{job['id']}/assessment", headers=auth_headers).json()
    # Trimmed, only for answered questions, empty dropped; ratings (and so the score) unchanged.
    assert again["answer_labels"] == {"q1": "Towel rail"}
    assert again["ratings"] == {"q1": "unsafe", "q2": "excellent"}
