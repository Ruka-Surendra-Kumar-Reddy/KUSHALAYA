"""Team targets: KPI, target, achieved and % for the month, per person."""

from datetime import datetime, timedelta, timezone

from app.core.pipeline_constants import ACTIVITY_STAGE_CHANGE
from app.livewell import sales_targets as st
from app.models.customer_plan import CustomerPlan
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.user import User

URL = "/api/v1/sales/targets"


def _me(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).json()


def _row(report, user_id):
    person = next(p for p in report["people"] if p["user_id"] == user_id)
    return {k["key"]: k for k in person["kpis"]}


def _lead(db, tid, owner_id, created):
    lead = ElderProspect(tenant_id=tid, first_name="Asha", last_name="Rao", owner_user_id=owner_id, stage="NEW")
    db.add(lead)
    db.commit()
    lead.created_at = created
    db.commit()
    return lead


def _move(db, tid, lead, to, when, by):
    act = PipelineActivity(tenant_id=tid, elder_prospect_id=lead.id, activity_type=ACTIVITY_STAGE_CHANGE,
                           body=f"-> {to}", metadata_={"from": "NEW", "to": to}, created_by_user_id=by)
    db.add(act)
    db.commit()
    act.created_at = when
    db.commit()


def test_counts_this_month_for_the_lead_owner(client, db, seed_tenant, admin_headers):
    me = _me(client, admin_headers)
    tid = me["tenant_id"]
    month = st.current_month()
    start, _ = st.month_bounds(month)
    in_month = start + timedelta(days=1, hours=5)
    last_month = start - timedelta(days=3)

    a = _lead(db, tid, me["id"], in_month)
    b = _lead(db, tid, me["id"], in_month)
    _lead(db, tid, me["id"], last_month)  # older: not counted
    _move(db, tid, a, "ASSESSMENT_SCHEDULED", in_month, me["id"])
    _move(db, tid, a, "ASSESSMENT_SCHEDULED", in_month + timedelta(hours=1), me["id"])  # same lead twice: once
    _move(db, tid, a, "ASSESSMENT_DONE", in_month, None)
    _move(db, tid, b, "WON", in_month, me["id"])
    elder = Elder(tenant_id=tid, first_name="Asha", last_name="Rao")
    db.add(elder)
    db.commit()
    for amount, status in ((550000, "active"), (99900, "cancelled")):
        plan = CustomerPlan(tenant_id=tid, elder_id=elder.id, prospect_id=b.id, plan_id="assurance", billing_cycle="annual",
                            start_date=start.date(), end_date=start.date(), amount_paise=amount, status=status)
        db.add(plan)
        db.commit()
        plan.created_at = in_month
        db.commit()

    res = client.put(URL, headers=admin_headers, json={"month": month, "user_id": me["id"],
                                                        "targets": {"leads": 4, "won": 2, "revenue_paise": 1100000}})
    assert res.status_code == 200, res.text
    row = _row(client.get(URL, headers=admin_headers).json(), me["id"])
    assert row["leads"]["achieved"] == 2 and row["leads"]["target"] == 4 and row["leads"]["percent"] == 50
    assert row["assessments_booked"]["achieved"] == 1 and row["assessments_booked"]["target"] is None
    assert row["assessments_done"]["achieved"] == 1
    assert row["won"]["achieved"] == 1 and row["won"]["percent"] == 50
    assert row["revenue_paise"]["achieved"] == 550000 and row["revenue_paise"]["percent"] == 50


def test_targets_carry_forward_and_staff_see_only_themselves(client, db, seed_tenant, admin_headers, auth_headers):
    me = _me(client, admin_headers)
    manager = _me(client, auth_headers)
    client.put(URL, headers=admin_headers, json={"month": "2026-10", "user_id": manager["id"], "targets": {"leads": 10}})
    nov = client.get(URL + "?month=2026-11", headers=admin_headers).json()
    assert _row(nov, manager["id"])["leads"]["target"] == 10  # carried forward

    own = client.get(URL + "?month=2026-11", headers=auth_headers).json()
    assert [p["user_id"] for p in own["people"]] == [manager["id"]]
    assert client.put(URL, headers=auth_headers, json={"month": "2026-11", "user_id": me["id"], "targets": {}}).status_code == 403


def test_bad_month_and_other_tenant_rejected(client, db, seed_tenant, admin_headers):
    assert client.get(URL + "?month=2026-13", headers=admin_headers).status_code in (400, 422)
    assert client.put(URL, headers=admin_headers, json={"month": "2026-11", "user_id": 999999, "targets": {}}).status_code in (400, 422)
