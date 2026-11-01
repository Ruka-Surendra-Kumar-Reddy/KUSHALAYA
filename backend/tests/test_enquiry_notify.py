"""Website enquiries reach admins and care managers by email and on the dashboard."""

from app.livewell import email_notifications as en


def test_enquiry_emails_team_and_shows_on_dashboard(client, db, seed_tenant, auth_headers, monkeypatch):
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((list(to), title, body)))
    res = client.post("/api/v1/home-safety/enquiries", json={
        "name": "Priya Sharma", "phone": "+91 98765 43210", "area": "Kukatpally",
        "notes": "Mother lives alone, had a fall last month", "kind": "care-check"})
    assert res.status_code == 200, res.text
    assert sent, "team should be emailed"
    to, title, body = sent[0]
    assert "admin@test.example" in to and "manager@test.example" in to
    assert title == "New enquiry: Priya Sharma" and "98765" in body and "KA-" in body

    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    enq = attn["enquiries"]
    assert enq and enq[0]["name"] == "Priya Sharma" and attn["counts"]["enquiries"] >= 1
    r = client.patch(f"/api/v1/prospects/elders/{enq[0]['id']}/stage", json={"stage": "CONTACTED"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert not any(e["id"] == enq[0]["id"] for e in attn["enquiries"])
