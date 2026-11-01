"""Visit report, know-them card, and the spotted → fixed hazard loop."""

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _cg(client, db, seed_tenant):
    cg = seed_tenant["caregiver"]
    db.add(User(email="rep.cg@test.example", password_hash=hash_password("testpass123"), first_name="Raju",
                last_name="K", role="CAREGIVER", tenant_id=cg.tenant_id, caregiver_id=cg.id))
    db.commit()
    return _login(client, "rep.cg@test.example")


def _job(client, headers, elder_id, cg_id, kind="visit", **extra):
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    res = client.post("/api/v1/jobs", json={"elder_id": elder_id, "kind": kind, "scheduled_at": when,
                                            "caregiver_id": cg_id, **extra}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_know_them_card_reaches_caregiver(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    res = client.put(f"/api/v1/team/clients/{elder.id}/know-them",
                     json={"approach": "Morning person; talk about the garden", "avoid": "Don't mention money"},
                     headers=auth_headers)
    assert res.status_code == 200, res.text
    _job(client, auth_headers, elder.id, cg.id)
    field = _cg(client, db, seed_tenant)
    jobs = client.get("/api/v1/caregiver-portal/jobs", headers=field).json()
    assert jobs[0]["know_them"]["approach"].startswith("Morning person")


def test_report_hazard_order_install_fixed(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    admin = _login(client, "admin@test.example")
    products = client.get("/api/v1/products", headers=admin).json()
    grab = next(p for p in products if p["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{grab['id']}", json={"cost_paise": 100000}, headers=admin)

    visit = _job(client, auth_headers, elder.id, cg.id)
    field = _cg(client, db, seed_tenant)
    client.post(f"/api/v1/caregiver-portal/jobs/{visit['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)
    done = client.post(f"/api/v1/caregiver-portal/jobs/{visit['id']}/report", json={"latitude": 17.4, "longitude": 78.4, 
        "checks": {"safe": "concern", "steady": "ok", "settled": "ok", "connected": "ok"}, "note": "Slipped near the toilet but fine",
        "hazard": {"note": "No grab bar by the toilet", "product_id": grab["id"]}}, headers=field)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["report"]["checks"]["safe"] == "concern"

    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    hz = attn["hazards"][0]
    assert hz["product_name"] == "Fixed grab bar"

    order = client.post("/api/v1/orders", json={"elder_id": elder.id, "lines": [{"product_id": grab["id"]}]},
                        headers=auth_headers).json()
    client.post(f"/api/v1/team/clients/{elder.id}/hazards/{hz['id']}",
                json={"status": "ordered", "order_id": order["id"]}, headers=auth_headers)
    install = _job(client, auth_headers, elder.id, cg.id, kind="install", request_id=f"order-{order['id']}")
    client.post(f"/api/v1/caregiver-portal/jobs/{install['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)
    client.post(f"/api/v1/caregiver-portal/jobs/{install['id']}/report", json={"latitude": 17.4, "longitude": 78.4, "checks": {"safe": "ok", "steady": "ok", "settled": "ok", "connected": "ok"}, "note": "Installed"},
                headers=field)

    hazards = client.get(f"/api/v1/team/clients/{elder.id}/hazards", headers=auth_headers).json()
    assert hazards[0]["status"] == "fixed"
    orders = client.get(f"/api/v1/orders?elder_id={elder.id}", headers=auth_headers).json()
    assert orders[0]["status"] == "completed"

    db.add(User(email="rep.fam@test.example", password_hash=hash_password("testpass123"), first_name="F",
                last_name="A", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id))
    db.commit()
    fam = _login(client, "rep.fam@test.example")
    fh = client.get("/api/v1/home-safety/family/hazards", headers=fam).json()
    assert fh[0]["status"] == "fixed"
    sched = client.get("/api/v1/home-safety/family/schedule", headers=fam).json()
    assert any("KushLife check" in v["summary"] for v in sched["recent"])
