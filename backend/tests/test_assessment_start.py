"""Start / continue an assessment from the office — for a client or a lead (assessment_start.py)."""
from tests.assess_client import confirm_client


from datetime import datetime, timedelta, timezone

from app.models.care_job import CareJob
from app.models.elder import Elder


def _lead(client, headers, name="Ravi Kumar"):
    res = client.post(
        "/api/v1/sales/leads", headers=headers, json={"name": name, "source": "Phone call", "phone": "9876500011"}
    )
    assert res.status_code == 201, res.text
    return res.json()


def _start(client, headers, **body):
    res = client.post("/api/v1/jobs/start-assessment", headers=headers, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _all_answers(client, headers, job_id):
    form = client.get(f"/api/v1/jobs/{job_id}/assessment", headers=headers).json()
    return {i["id"]: "excellent" for c in form["categories"] for i in c["items"]}


def test_lead_assessment_creates_hidden_record_and_follows_to_won(client, db, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    out = _start(client, auth_headers, lead_id=lead["id"])
    assert out["resumed"] is False
    job = db.get(CareJob, out["job_id"])
    elder = db.get(Elder, job.elder_id)
    # Hidden until Won: not a client, not in the client list, the lead is not "converted".
    assert elder.status == "INACTIVE" and elder.custom_attributes["lead_id"] == lead["id"]
    assert all(e["id"] != elder.id for e in client.get("/api/v1/elders", headers=auth_headers).json())
    leads = client.get("/api/v1/sales/leads", headers=auth_headers).json()
    row = next(x for x in leads if x["id"] == lead["id"])
    assert row["converted_elder_id"] is None
    assert row["stage"] == "ASSESSMENT_SCHEDULED"  # moved automatically
    # Office-started: no "scheduled" notice, and the missed-visit timer leaves it alone.
    assert job.assessment_id == f"field-job-{job.id}"
    hub = (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})
    assert not any("scheduled" in (a.get("title") or "") for a in hub.get("alerts", []))

    # Draft save needs neither every answer nor a location.
    draft = client.put(f"/api/v1/jobs/{job.id}/assessment", headers=auth_headers, json={"ratings": {}})
    assert draft.status_code == 200 and draft.json()["status"] == "draft"

    # Submit -> lead moves to "Assessment done".
    ratings = _all_answers(client, auth_headers, job.id)
    confirm_client(client, auth_headers, job.id)
    done = client.put(
        f"/api/v1/jobs/{job.id}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True}
    )
    assert done.status_code == 200, done.text
    leads = client.get("/api/v1/sales/leads", headers=auth_headers).json()
    assert next(x for x in leads if x["id"] == lead["id"])["stage"] == "ASSESSMENT_DONE"

    # Won: the same record becomes the client, so the assessment stays linked.
    won = client.post(
        f"/api/v1/sales/leads/{lead['id']}/move",
        headers=auth_headers,
        json={"to": "WON", "plan_id": "assurance", "billing_cycle": "monthly"},
    )
    assert won.status_code == 200, won.text
    assert won.json()["converted_elder_id"] == elder.id
    db.refresh(elder)
    assert elder.status == "ACTIVE" and "lead_id" not in elder.custom_attributes
    jobs = client.get(f"/api/v1/jobs?elder_id={elder.id}", headers=auth_headers).json()
    assert jobs[0]["status"] == "completed" and jobs[0]["assessment_id"]


def test_continue_the_draft_instead_of_a_second_one(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    first = _start(client, auth_headers, elder_id=elder.id)
    client.put(
        f"/api/v1/jobs/{first['job_id']}/assessment", headers=auth_headers, json={"ratings": {"x": "na"}}
    )
    check = client.get(f"/api/v1/jobs/assessment-draft?elder_id={elder.id}", headers=auth_headers).json()
    assert check["draft"]["job_id"] == first["job_id"]
    again = _start(client, auth_headers, elder_id=elder.id)
    assert again == {"job_id": first["job_id"], "resumed": True, "elder_id": elder.id}
    fresh = _start(client, auth_headers, elder_id=elder.id, new=True)
    assert fresh["job_id"] != first["job_id"] and fresh["resumed"] is False


def test_draft_record_without_open_job_is_picked_up(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    first = _start(client, auth_headers, elder_id=elder.id)
    client.put(
        f"/api/v1/jobs/{first['job_id']}/assessment", headers=auth_headers, json={"ratings": {"a": "unsafe"}}
    )
    db.get(CareJob, first["job_id"]).status = "cancelled"
    db.commit()
    again = _start(client, auth_headers, elder_id=elder.id)
    assert again["resumed"] is True and again["job_id"] != first["job_id"]
    form = client.get(f"/api/v1/jobs/{again['job_id']}/assessment", headers=auth_headers).json()
    assert form["ratings"].get("a") == "unsafe"


def test_targets_list_clients_and_open_leads(client, db, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers, name="Lakshmi Devi")
    rows = client.get("/api/v1/jobs/assessment-targets", headers=auth_headers).json()
    kinds = {r["key"]: r for r in rows}
    assert f"client:{seed_tenant['elder'].id}" in kinds
    assert kinds[f"lead:{lead['id']}"]["kind"] == "lead"
    _start(client, auth_headers, lead_id=lead["id"])
    rows = client.get("/api/v1/jobs/assessment-targets", headers=auth_headers).json()
    hit = next(r for r in rows if r["key"] == f"lead:{lead['id']}")
    assert hit["draft"] and hit["draft"]["job_id"]
    # The hidden record is not listed as a client.
    assert sum(1 for r in rows if r["name"] == "Lakshmi Devi") == 1


def test_lost_lead_cannot_start(client, db, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    client.post(f"/api/v1/sales/leads/{lead['id']}/move", headers=auth_headers, json={"to": "LOST", "comment": "No"})
    res = client.post("/api/v1/jobs/start-assessment", headers=auth_headers, json={"lead_id": lead["id"]})
    assert res.status_code == 400


def test_missed_timer_skips_assessment_in_progress(db, seed_tenant):
    from app.livewell.daily_checks import mark_missed_visits

    elder = seed_tenant["elder"]
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    started = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="assessment", scheduled_at=old,
                      status="scheduled", assessment_id="field-job-x")
    untouched = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="assessment", scheduled_at=old,
                        status="scheduled")
    db.add_all([started, untouched])
    db.commit()
    missed = mark_missed_visits(db)
    assert untouched.id in missed and started.id not in missed


def test_start_new_discards_old_office_drafts(client, db, seed_tenant, auth_headers):
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    elder = seed_tenant["elder"]
    first = _start(client, auth_headers, elder_id=elder.id)
    client.put(f"/api/v1/jobs/{first['job_id']}/assessment", headers=auth_headers, json={"ratings": {"a": "unsafe"}})
    old_aid = db.get(CareJob, first["job_id"]).assessment_id
    fresh = _start(client, auth_headers, elder_id=elder.id, new=True)
    db.expire_all()
    assert db.get(CareJob, first["job_id"]).status == "cancelled"
    rec = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == old_aid).one()
    assert rec.status == "discarded"
    listed = {a.get("id") for a in client.get("/api/v1/home-safety/assessments", headers=auth_headers).json()}
    assert old_aid not in listed
    # Finish the new one: the old draft does not come back as "continue".
    ratings = _all_answers(client, auth_headers, fresh["job_id"])
    confirm_client(client, auth_headers, fresh["job_id"])
    res = client.put(f"/api/v1/jobs/{fresh['job_id']}/assessment", headers=auth_headers,
                     json={"ratings": ratings, "complete": True})
    assert res.status_code == 200, res.text
    check = client.get(f"/api/v1/jobs/assessment-draft?elder_id={elder.id}", headers=auth_headers).json()
    assert check["draft"] is None


def test_submit_builds_the_family_improvement_plan(client, db, seed_tenant, auth_headers):
    from app.livewell.solution_service import DEFAULT_SOLUTIONS
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    elder = seed_tenant["elder"]
    job = _start(client, auth_headers, elder_id=elder.id)["job_id"]
    ratings = _all_answers(client, auth_headers, job)
    fixable = [rid for s in DEFAULT_SOLUTIONS["solutions"] for rid in s.get("rubricItemIds") or [] if rid in ratings]
    assert fixable
    for rid in fixable[:3]:
        ratings[rid] = "unsafe"
    confirm_client(client, auth_headers, job)
    res = client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True})
    assert res.status_code == 200, res.text
    aid = db.get(CareJob, job).assessment_id
    plan = db.query(HomeSafetyAssessmentRecord).filter(
        HomeSafetyAssessmentRecord.assessment_id == aid).one().payload["familyImprovementPlan"]
    assert plan["items"] and plan["finding_count"] >= 1
    assert plan["projected_score"] >= plan["current_score"]
    assert all(i["status"] == "open" and i["title"] for i in plan["items"])
    staff_view = client.get(f"/api/v1/home-safety/care/elders/{elder.id}/improvement-plan", headers=auth_headers)
    assert staff_view.status_code == 200, staff_view.text
    assert staff_view.json()["items"], "family plan should be published"


def test_step1_client_details_and_location(client, db, seed_tenant, auth_headers):
    from tests.assess_client import CLIENT

    lead = _lead(client, auth_headers, name="Kamala Devi")
    job = _start(client, auth_headers, lead_id=lead["id"])["job_id"]
    form = client.get(f"/api/v1/jobs/{job}/assessment", headers=auth_headers).json()
    info = form["client"]
    assert info["is_lead"] is True and info["confirmed"] is False
    assert info["details"]["emergency_contact_phone"].replace(" ", "").endswith("9876500011") and "pincode" in info["missing"]

    ratings = _all_answers(client, auth_headers, job)
    blocked = client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True})
    assert blocked.status_code == 400 and "step 1" in blocked.text

    url = f"/api/v1/jobs/{job}/assessment/client"
    bad = client.put(url, headers=auth_headers, json={"details": {**CLIENT, "pincode": "12"}, "location": {"mode": "manual"}})
    assert bad.status_code == 400 and "PIN" in bad.text
    no_loc = client.put(url, headers=auth_headers, json={"details": CLIENT, "location": {"mode": "auto"}})
    assert no_loc.status_code == 400
    ok = client.put(url, headers=auth_headers, json={"details": CLIENT, "location": {"mode": "manual"}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["confirmed"] is True and ok.json()["missing"] == []
    assert ok.json()["location"]["mode"] == "manual"

    done = client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True})
    assert done.status_code == 200, done.text
    again = client.get(f"/api/v1/jobs/{job}/assessment", headers=auth_headers).json()["client"]
    assert again["details"]["city"] == "Hyderabad" and again["details"]["date_of_birth"] == "1948-05-01"


def test_assessment_board_buckets(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    lead = _lead(client, auth_headers, name="Board Lead")
    sched = _start(client, auth_headers, lead_id=lead["id"])["job_id"]
    prog = _start(client, auth_headers, elder_id=elder.id)["job_id"]
    client.put(f"/api/v1/jobs/{prog}/assessment", headers=auth_headers, json={"ratings": {"x": "na"}})
    rows = {r["job_id"]: r for r in client.get("/api/v1/jobs/assessment-board", headers=auth_headers).json()}
    assert rows[sched]["status"] == "scheduled" and rows[sched]["is_lead"] is True
    assert rows[prog]["status"] == "in_progress" and rows[prog]["answered"] == 1

    ratings = _all_answers(client, auth_headers, prog)
    confirm_client(client, auth_headers, prog)
    client.put(f"/api/v1/jobs/{prog}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True})
    rows = {r["job_id"]: r for r in client.get("/api/v1/jobs/assessment-board", headers=auth_headers).json()}
    done = rows[prog]
    assert done["status"] == "completed" and done["score"] is not None and done["completed_at"]
    assert done["area"] == "Uppal, Hyderabad" and done["assessment_id"]


def test_assessment_goes_to_a_care_manager(client, db, seed_tenant, auth_headers):
    elder, mgr = seed_tenant["elder"], seed_tenant["manager"]
    elder.manager_user_id = mgr.id
    db.commit()
    res = client.post("/api/v1/jobs", headers=auth_headers, json={
        "elder_id": elder.id, "kind": "assessment", "scheduled_at": "2030-01-05T10:00:00+05:30"})
    assert res.status_code in (200, 201), res.text
    job = res.json()
    assert job["assignee_user_id"] == mgr.id and job["assignee_name"]  # the client's own care manager
    # A caregiver is not a care manager.
    bad = client.patch(f"/api/v1/jobs/{job['id']}", headers=auth_headers,
                       json={"assignee_user_id": seed_tenant["caregiver"].user_id if hasattr(seed_tenant["caregiver"], "user_id") and seed_tenant["caregiver"].user_id else 999999})
    assert bad.status_code == 400
    board = {r["job_id"]: r for r in client.get("/api/v1/jobs/assessment-board", headers=auth_headers).json()}
    assert board[job["id"]]["care_manager_id"] == mgr.id
    # Started from the office: assigned to whoever starts it.
    started = _start(client, auth_headers, elder_id=elder.id, new=True)
    assert db.get(CareJob, started["job_id"]).assignee_user_id is not None


def test_missed_assessment_can_be_cancelled(client, db, seed_tenant, auth_headers):
    job_id = _start(client, auth_headers, elder_id=seed_tenant["elder"].id, new=True)["job_id"]
    db.get(CareJob, job_id).status = "missed"
    db.commit()
    res = client.patch(f"/api/v1/jobs/{job_id}", headers=auth_headers, json={"status": "cancelled"})
    assert res.status_code == 200, res.text
    rows = {r["job_id"] for r in client.get("/api/v1/jobs/assessment-board", headers=auth_headers).json()}
    assert job_id not in rows


def test_step1_date_of_birth_is_optional(client, db, seed_tenant, auth_headers):
    from tests.assess_client import CLIENT

    job = _start(client, auth_headers, elder_id=seed_tenant["elder"].id, new=True)["job_id"]
    body = {"details": {**CLIENT, "date_of_birth": ""}, "location": {"mode": "manual"}}
    res = client.put(f"/api/v1/jobs/{job}/assessment/client", headers=auth_headers, json=body)
    assert res.status_code == 200, res.text
    assert "date_of_birth" not in res.json()["missing"]


def test_step1_lead_prefills_contact_person_and_beneficiaries(client, db, seed_tenant, auth_headers):
    from tests.assess_client import CLIENT

    lead = _lead(client, auth_headers, name="Ravi Son")  # the enquirer
    job = _start(client, auth_headers, lead_id=lead["id"])["job_id"]
    info = client.get(f"/api/v1/jobs/{job}/assessment", headers=auth_headers).json()["client"]
    d = info["details"]
    assert d["emergency_contact_name"] == "Ravi Son" and d["emergency_contact_phone"]
    assert d["first_name"] == "" and d["phone"] == ""  # the beneficiary is someone else
    assert "phone" not in info["missing"]

    body = {
        "details": {**CLIENT, "phone": "", "contact_relation": "son"},
        "location": {"mode": "manual"},
        "beneficiaries": [{"name": "Sita Rao", "relation": "spouse", "gender": "female"}, {}],
    }
    res = client.put(f"/api/v1/jobs/{job}/assessment/client", headers=auth_headers, json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["beneficiaries"] == [{"name": "Sita Rao", "gender": "female", "date_of_birth": "", "relation": "spouse", "phone": ""}]
    assert out["details"]["contact_relation"] == "son"
    bad = client.put(f"/api/v1/jobs/{job}/assessment/client", headers=auth_headers,
                     json={**body, "beneficiaries": [{"relation": "spouse"}]})
    assert bad.status_code == 400


def test_history_text_is_parsed_not_split_into_characters(client, db, seed_tenant, auth_headers):
    """A history stored as JSON text must stay a list of entries, never grow per save."""
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

    job = _start(client, auth_headers, elder_id=seed_tenant["elder"].id, new=True)["job_id"]
    client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": {"x": "na"}})
    aid = db.get(CareJob, job).assessment_id
    rec = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).one()
    rec.history = '["[", "\\"", "x"]'  # the corrupted shape found on live
    db.commit()
    for _ in range(3):  # draft saves leave history alone
        assert client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": {"x": "na"}}).status_code == 200
    db.expire_all()
    assert len(str(db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).one().history)) < 40
    ratings = _all_answers(client, auth_headers, job)
    confirm_client(client, auth_headers, job)
    assert client.put(f"/api/v1/jobs/{job}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True}).status_code == 200
    db.expire_all()
    hist = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).one().history
    import json as _json
    parsed = _json.loads(hist) if isinstance(hist, str) else hist
    assert parsed == []  # junk dropped on completion, not multiplied


def test_details_on_file_count_as_confirmed(client, db, seed_tenant, auth_headers):
    """A reassessment of a client whose details + home location are on file skips step 1."""
    elder = seed_tenant["elder"]
    first = _start(client, auth_headers, elder_id=elder.id, new=True)["job_id"]
    confirm_client(client, auth_headers, first)  # saves details + location for the client
    again = _start(client, auth_headers, elder_id=elder.id, new=True)["job_id"]
    info = client.get(f"/api/v1/jobs/{again}/assessment", headers=auth_headers).json()["client"]
    assert info["confirmed"] is True
    ratings = _all_answers(client, auth_headers, again)
    res = client.put(f"/api/v1/jobs/{again}/assessment", headers=auth_headers, json={"ratings": ratings, "complete": True})
    assert res.status_code == 200, res.text


def test_book_assessment_for_a_new_lead_schedules_job_and_moves_lead(client, db, seed_tenant, auth_headers):
    """A new lead on a call asks for a visit in 3 days: book it, the card moves to "Assessment booked"."""
    lead = _lead(client, auth_headers, name="Sita Rao")
    when = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
    res = client.post(
        "/api/v1/jobs/book-assessment",
        headers=auth_headers,
        json={"lead_id": lead["id"], "scheduled_at": when.isoformat()},
    )
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["stage"] == "ASSESSMENT_SCHEDULED"
    job = db.get(CareJob, out["job"]["id"])
    assert job.kind == "assessment" and job.status == "scheduled"
    sched = job.scheduled_at if job.scheduled_at.tzinfo else job.scheduled_at.replace(tzinfo=timezone.utc)
    assert sched == when
    elder = db.get(Elder, job.elder_id)
    assert elder.custom_attributes["lead_id"] == lead["id"] and elder.status == "INACTIVE"
    row = next(x for x in client.get("/api/v1/sales/leads", headers=auth_headers).json() if x["id"] == lead["id"])
    assert row["stage"] == "ASSESSMENT_SCHEDULED"
    hist = client.get(f"/api/v1/sales/leads/{lead['id']}/history", headers=auth_headers).json()
    assert "Assessment booked for" in hist[0]["body"]
    # "Start assessment now" later continues this booked job instead of making a second one.
    assert _start(client, auth_headers, lead_id=lead["id"])["job_id"] == job.id


def test_lead_times_are_sent_as_utc(client, db, seed_tenant, auth_headers):
    """Naive DB times go out with an offset, so the browser shows 07:11 UTC as 12:41 IST."""
    lead = _lead(client, auth_headers)
    created = datetime.fromisoformat(lead["created_at"])
    assert created.utcoffset() == timedelta(0)
    hist = client.get(f"/api/v1/sales/leads/{lead['id']}/history", headers=auth_headers).json()
    assert datetime.fromisoformat(hist[0]["at"]).utcoffset() == timedelta(0)
