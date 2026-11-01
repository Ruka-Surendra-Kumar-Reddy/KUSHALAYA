"""Operations board (lead stages + history) and customer plans (pending -> authorize -> paid)."""

from datetime import date

from app.livewell import care_plan_catalog as catalog
from app.livewell.public_enquiry_service import PublicEnquiryService
from app.livewell.sales_pipeline import add_months


def _lead(client, headers, name="Asha Rao"):
    res = client.post(
        "/api/v1/sales/leads",
        headers=headers,
        json={"name": name, "source": "Phone call", "phone": "9876543210"},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _move(client, headers, lead_id, **body):
    return client.post(f"/api/v1/sales/leads/{lead_id}/move", headers=headers, json=body)


def test_add_months_clamps_month_end():
    assert add_months(date(2026, 10, 26), 12) == date(2027, 10, 26)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_website_enquiry_lands_in_new(db, client, seed_tenant, auth_headers):
    PublicEnquiryService.create(
        db, name="Web Visitor", phone="9876500000", email=None, area=None, services=None,
        visit_frequency=None, products=None, notes=None, kind="care-check",
    )
    leads = client.get("/api/v1/sales/leads", headers=auth_headers).json()
    hit = next(x for x in leads if x["name"] == "Web Visitor")
    assert hit["stage"] == "NEW"
    assert hit["source"].startswith("website")


def test_stage_moves_keep_history(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    assert lead["stage"] == "NEW"
    for to in ("ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE", "FOLLOW_UP_1", "FOLLOW_UP_2"):
        res = _move(client, auth_headers, lead["id"], to=to, comment=f"now {to}")
        assert res.status_code == 200, res.text
        assert res.json()["stage"] == to
    hist = client.get(f"/api/v1/sales/leads/{lead['id']}/history", headers=auth_headers).json()
    moves = [h for h in hist if h["to"]]
    assert moves[0]["from"] == "FOLLOW_UP_1" and moves[0]["to"] == "FOLLOW_UP_2"
    assert moves[0]["comment"] == "now FOLLOW_UP_2"
    assert moves[0]["by"] == "Test Manager"
    assert moves[0]["to_label"] == "Follow-up 2"
    # Moving back is allowed; an unknown stage is not.
    assert _move(client, auth_headers, lead["id"], to="NEW").status_code == 200
    assert _move(client, auth_headers, lead["id"], to="PROPOSAL_SENT").status_code == 422


def test_lost_needs_a_comment(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    assert _move(client, auth_headers, lead["id"], to="LOST").status_code == 422
    assert _move(client, auth_headers, lead["id"], to="LOST", comment="  ").status_code == 422
    res = _move(client, auth_headers, lead["id"], to="LOST", comment="Chose another provider")
    assert res.status_code == 200
    assert res.json()["stage"] == "LOST" and res.json()["status"] == "LOST"
    assert res.json()["lost_reason"] == "Chose another provider"
    # Reopen from Lost.
    again = _move(client, auth_headers, lead["id"], to="FOLLOW_UP_1", comment="Called back")
    assert again.json()["stage"] == "FOLLOW_UP_1" and again.json()["status"] == "OPEN"


def test_won_needs_plan_and_cycle(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    assert _move(client, auth_headers, lead["id"], to="WON").status_code == 422
    assert _move(client, auth_headers, lead["id"], to="WON", plan_id="privilege").status_code == 422
    assert _move(client, auth_headers, lead["id"], to="WON", plan_id="gold", billing_cycle="yearly").status_code == 422
    assert _move(client, auth_headers, lead["id"], to="WON", plan_id="assurance", billing_cycle="weekly").status_code == 422
    # Nothing was created by the failed attempts.
    leads = client.get("/api/v1/sales/leads", headers=auth_headers).json()
    assert next(x for x in leads if x["id"] == lead["id"])["stage"] == "NEW"


def test_won_creates_client_and_pending_plan(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers, name="Meena Iyer")
    res = _move(
        client, auth_headers, lead["id"],
        to="WON", plan_id="total-care", billing_cycle="monthly", start_date="2026-11-01", comment="Signed",
    )
    assert res.status_code == 200, res.text
    out = res.json()
    plan = out["customer_plan"]
    assert out["stage"] == "WON" and out["converted_elder_id"]
    assert plan["status"] == "pending_approval" and plan["payment_status"] == "unpaid"
    assert plan["amount_paise"] == catalog.price_paise("total-care", "monthly") == 9_900_00
    assert plan["start_date"] == "2026-11-01" and plan["end_date"] == "2026-12-01"
    # The lead and its history stay on the board.
    hist = client.get(f"/api/v1/sales/leads/{lead['id']}/history", headers=auth_headers).json()
    assert hist[0]["to"] == "WON" and hist[0]["comment"] == "Signed"
    # A won lead can't be moved again.
    assert _move(client, auth_headers, lead["id"], to="LOST", comment="x").status_code == 400
    # The client shows in Customers with the plan in the approval queue.
    cust = client.get("/api/v1/sales/customers", headers=auth_headers).json()
    row = next(c for c in cust["customers"] if c["elder_id"] == out["converted_elder_id"])
    assert row["status"] == "pending_approval" and row["name"] == "Meena Iyer"
    assert any(p["id"] == plan["id"] for p in cust["pending"])


def test_won_yearly_defaults_to_today(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    plan = _move(client, auth_headers, lead["id"], to="WON", plan_id="assurance", billing_cycle="yearly").json()["customer_plan"]
    today = date.today()
    assert plan["start_date"] == today.isoformat()
    assert plan["end_date"] == add_months(today, 12).isoformat()
    assert plan["amount_paise"] == 55_000_00


def test_won_assurance_monthly(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    res = _move(client, auth_headers, lead["id"], to="WON", plan_id="assurance", billing_cycle="monthly")
    assert res.status_code == 200, res.text
    assert res.json()["customer_plan"]["amount_paise"] == 6_000_00


def test_assign_authorize_and_mark_paid(client, seed_tenant, auth_headers, admin_headers):
    elder_id = seed_tenant["elder"].id
    cust = client.get("/api/v1/sales/customers", headers=auth_headers).json()
    assert next(c for c in cust["customers"] if c["elder_id"] == elder_id)["status"] == "none"

    assert client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                       json={"plan_id": "assurance", "billing_cycle": "weekly"}).status_code == 422
    res = client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                      json={"plan_id": "signature", "billing_cycle": "yearly"})
    assert res.status_code == 201, res.text
    plan = res.json()
    assert plan["amount_paise"] == 1_60_000_00 and plan["status"] == "pending_approval"
    # Only one plan can wait for approval at a time.
    assert client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                       json={"plan_id": "privilege", "billing_cycle": "yearly"}).status_code == 400

    # Authorize is an admin step and needs a payment mode.
    assert client.post(f"/api/v1/sales/plans/{plan['id']}/authorize", headers=auth_headers,
                       json={"payment_mode": "upi", "paid": False}).status_code == 403
    assert client.post(f"/api/v1/sales/plans/{plan['id']}/authorize", headers=admin_headers,
                       json={"payment_mode": "barter", "paid": False}).status_code == 422
    auth = client.post(f"/api/v1/sales/plans/{plan['id']}/authorize", headers=admin_headers,
                       json={"payment_mode": "upi", "paid": False})
    assert auth.status_code == 200
    assert auth.json()["status"] == "active" and auth.json()["payment_status"] == "unpaid"
    assert auth.json()["authorized_by_name"] == "Test Admin"
    assert client.post(f"/api/v1/sales/plans/{plan['id']}/authorize", headers=admin_headers,
                       json={"payment_mode": "upi"}).status_code == 400

    paid = client.post(f"/api/v1/sales/plans/{plan['id']}/mark-paid", headers=auth_headers, json={})
    assert paid.status_code == 200
    assert paid.json()["payment_status"] == "paid" and paid.json()["payment_mode"] == "upi"
    assert client.post(f"/api/v1/sales/plans/{plan['id']}/mark-paid", headers=auth_headers, json={}).status_code == 400

    detail = client.get(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers).json()
    assert detail["current"]["id"] == plan["id"] and detail["current"]["status"] == "active"
    assert detail["paid_paise"] == 1_60_000_00
    assert detail["customer_id"] == f"KC-{elder_id:06d}"


def test_authorize_paid_at_once(client, seed_tenant, auth_headers, admin_headers):
    elder_id = seed_tenant["elder"].id
    plan = client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                       json={"plan_id": "privilege", "billing_cycle": "monthly", "start_date": "2026-01-31"}).json()
    assert plan["end_date"] == "2026-02-28" and plan["amount_paise"] == 13_500_00
    res = client.post(f"/api/v1/sales/plans/{plan['id']}/authorize", headers=admin_headers,
                      json={"payment_mode": "cash", "paid": True})
    assert res.json()["payment_status"] == "paid" and res.json()["paid_at"]
    # The end date has passed, so the active plan reads as expired.
    assert res.json()["status"] == "expired"


def test_viewer_cannot_change_anything(client, seed_tenant):
    login = client.post("/api/v1/auth/login", json={"email": "viewer@test.example", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/sales/customers", headers=headers).status_code == 200
    assert client.post("/api/v1/sales/leads", headers=headers, json={"name": "X", "phone": "9876543210"}).status_code == 403
    elder_id = seed_tenant["elder"].id
    assert client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=headers,
                       json={"plan_id": "privilege", "billing_cycle": "yearly"}).status_code == 403


def test_city_from_address():
    from app.livewell.sales_pipeline import city_from_address

    assert city_from_address("Flat 2, Banjara Hills, Hyderabad, Telangana 500034") == "Hyderabad"
    assert city_from_address("Plot 5, Gachibowli, Hyderabad - 500032, India") == "Hyderabad"
    assert city_from_address("") is None and city_from_address("500034") is None


def test_lead_list_has_stage_since_and_last_comment(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    _move(client, auth_headers, lead["id"], to="FOLLOW_UP_1", comment="Call on Monday")
    row = next(x for x in client.get("/api/v1/sales/leads", headers=auth_headers).json() if x["id"] == lead["id"])
    assert row["last_comment"] == "Call on Monday"
    assert row["stage_since"]


def test_customer_columns_and_dashboard_counts(db, client, seed_tenant, auth_headers, admin_headers):
    elder = seed_tenant["elder"]
    elder.address = "12 Road No 3, Banjara Hills, Hyderabad, Telangana 500034"
    db.commit()
    before = client.get("/api/v1/sales/dashboard-counts", headers=auth_headers).json()
    lead = _lead(client, auth_headers, name="Count Me")
    _move(client, auth_headers, lead["id"], to="ASSESSMENT_SCHEDULED")
    lost = _lead(client, auth_headers, name="Gone")
    _move(client, auth_headers, lost["id"], to="LOST", comment="No budget")
    client.post(f"/api/v1/sales/customers/{elder.id}/plans", headers=auth_headers,
                json={"plan_id": "privilege", "billing_cycle": "yearly"})
    after = client.get("/api/v1/sales/dashboard-counts", headers=auth_headers).json()
    assert after["leads"]["ASSESSMENT_SCHEDULED"] == before["leads"]["ASSESSMENT_SCHEDULED"] + 1
    assert after["lost_this_month"] == before["lost_this_month"] + 1
    assert after["pending_approval"] == before["pending_approval"] + 1
    assert after["unpaid_plans"] == before["unpaid_plans"] + 1
    assert after["active_clients"] >= 1
    row = next(c for c in client.get("/api/v1/sales/customers", headers=auth_headers).json()["customers"] if c["elder_id"] == elder.id)
    assert row["city"] == "Hyderabad"
    assert row["device_linked"] is False
    assert "referred_by" in row


def test_lead_list_date_range_and_funnel_counts(db, client, seed_tenant, auth_headers):
    from datetime import datetime, timedelta

    from app.models.elder_prospect import ElderProspect

    old = _lead(client, auth_headers, name="Old Lead")
    new = _lead(client, auth_headers, name="New Lead")
    lost = _lead(client, auth_headers, name="Lost Lead")
    _move(client, auth_headers, lost["id"], to="LOST", comment="Too costly")
    row = db.get(ElderProspect, old["id"])
    row.created_at = datetime.utcnow() - timedelta(days=40)
    db.commit()

    since = (datetime.utcnow() - timedelta(days=30)).isoformat()
    res = client.get("/api/v1/sales/leads", headers=auth_headers, params={"from": since})
    assert res.status_code == 200, res.text
    ids = {x["id"] for x in res.json()}
    assert new["id"] in ids and lost["id"] in ids and old["id"] not in ids
    # `to` is exclusive and bounds the other side.
    upto = client.get("/api/v1/sales/leads", headers=auth_headers, params={"to": since}).json()
    assert {x["id"] for x in upto} >= {old["id"]} and new["id"] not in {x["id"] for x in upto}
    # Every lead is in exactly one stage: the per-stage counts add up to the list.
    rows = client.get("/api/v1/sales/leads", headers=auth_headers, params={"all": "true"}).json()
    counts: dict[str, int] = {}
    for x in rows:
        counts[x["stage"]] = counts.get(x["stage"], 0) + 1
    assert sum(counts.values()) == len(rows)
    assert counts.get("LOST", 0) >= 1


def test_lead_comment_adds_history(client, seed_tenant, auth_headers):
    lead = _lead(client, auth_headers)
    assert client.post(f"/api/v1/sales/leads/{lead['id']}/comment", headers=auth_headers, json={"comment": " "}).status_code == 422
    res = client.post(f"/api/v1/sales/leads/{lead['id']}/comment", headers=auth_headers, json={"comment": "Son will call back"})
    assert res.status_code == 201, res.text
    hist = client.get(f"/api/v1/sales/leads/{lead['id']}/history", headers=auth_headers).json()
    assert hist[0]["body"] == "Son will call back" and hist[0]["to"] is None
    row = next(x for x in client.get("/api/v1/sales/leads", headers=auth_headers).json() if x["id"] == lead["id"])
    assert row["last_comment"] == "Son will call back" and row["stage"] == "NEW"


def test_won_emails_admins_that_a_plan_waits(client, seed_tenant, auth_headers, monkeypatch):
    """Owner report 2026-10-29: Won showed "pending approval" but no admin was told."""
    from app.livewell import email_notifications

    sent = []
    monkeypatch.setattr(email_notifications, "email_staff", lambda db, elder, event, title, body, **kw: sent.append((event, title, body, kw)))
    lead = _lead(client, auth_headers, name="Kamala Devi")
    res = _move(client, auth_headers, lead["id"], to="WON", plan_id="total-care", billing_cycle="monthly", start_date="2026-11-01")
    assert res.status_code == 200, res.text
    assert len(sent) == 1
    event, title, body, kw = sent[0]
    assert event == "approval" and "Plan to approve" in title and "Kamala" in title
    assert "₹9,900" in body and kw["path"].endswith("?tab=plan")
