"""Admin / Manager / Caregiver: managers see only their own team."""

from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _setup(client, db, seed_tenant):
    tenant = seed_tenant["tenant"]
    manager = seed_tenant["manager"]
    other = User(
        email="other.manager@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Other",
        last_name="Manager",
        role="CARE_MANAGER",
        tenant_id=tenant.id,
    )
    db.add(other)
    db.commit()
    admin = _login(client, "admin@test.example")

    res = client.post(
        "/api/v1/team/caregivers",
        json={
            "first_name": "Sita",
            "last_name": "Rao",
            "email": "sita.cg@test.example",
            "password": "carepass123",
            "manager_user_id": manager.id,
        },
        headers=admin,
    )
    assert res.status_code == 201, res.text
    cg = res.json()
    assert cg["login_email"] == "sita.cg@test.example"
    assert cg["manager_user_id"] == manager.id

    team_client = seed_tenant["elder"]
    db.add(
        Assignment(
            tenant_id=tenant.id,
            elder_id=team_client.id,
            caregiver_id=cg["id"],
            status="ACTIVE",
            match_score=90.0,
        )
    )
    outside = Elder(tenant_id=tenant.id, first_name="Out", last_name="Side", care_level="Low")
    db.add(outside)
    db.commit()
    return admin, cg, team_client, outside


def test_manager_sees_only_team_clients(client, db, seed_tenant):
    admin, cg, team_client, outside = _setup(client, db, seed_tenant)
    mgr = _login(client, "manager@test.example")

    ids = {e["id"] for e in client.get("/api/v1/elders", headers=mgr).json()}
    assert team_client.id in ids
    assert outside.id not in ids
    assert client.get(f"/api/v1/elders/{outside.id}", headers=mgr).status_code == 404

    admin_ids = {e["id"] for e in client.get("/api/v1/elders", headers=admin).json()}
    assert {team_client.id, outside.id} <= admin_ids

    other = _login(client, "other.manager@test.example")
    assert team_client.id not in {e["id"] for e in client.get("/api/v1/elders", headers=other).json()}


def test_manager_sees_only_their_caregivers(client, db, seed_tenant):
    _, cg, _, _ = _setup(client, db, seed_tenant)
    mgr = _login(client, "manager@test.example")
    other = _login(client, "other.manager@test.example")
    assert cg["id"] in [c["id"] for c in client.get("/api/v1/team/caregivers", headers=mgr).json()]
    assert client.get("/api/v1/team/caregivers", headers=other).json() == []


def test_admin_moves_client_to_manager(client, db, seed_tenant):
    admin, _, _, outside = _setup(client, db, seed_tenant)
    other_id = db.query(User).filter(User.email == "other.manager@test.example").one().id
    res = client.put(
        f"/api/v1/team/clients/{outside.id}/manager",
        json={"manager_user_id": other_id},
        headers=admin,
    )
    assert res.status_code == 200
    other = _login(client, "other.manager@test.example")
    assert outside.id in {e["id"] for e in client.get("/api/v1/elders", headers=other).json()}


def test_manager_creates_caregivers_in_own_team_only(client, db, seed_tenant):
    # Same rule as POST /caregivers: a manager's new caregiver joins their own team.
    mgr = _login(client, "manager@test.example")
    res = client.post(
        "/api/v1/team/caregivers",
        json={"first_name": "X", "email": "x.cg@test.example", "password": "carepass123"},
        headers=mgr,
    )
    assert res.status_code == 201
    assert res.json()["manager_user_id"] == seed_tenant["manager"].id
    viewer = _login(client, "viewer@test.example")
    res = client.post("/api/v1/team/caregivers", json={"first_name": "Y"}, headers=viewer)
    assert res.status_code == 403


def test_new_caregiver_can_sign_in(client, db, seed_tenant):
    _setup(client, db, seed_tenant)
    headers = _login(client, "sita.cg@test.example", "carepass123")
    assert client.get("/api/v1/caregiver-portal/me", headers=headers).status_code == 200


def test_caregiver_without_login(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    res = client.post("/api/v1/team/caregivers", json={"first_name": "Raju", "last_name": "K"}, headers=admin)
    assert res.status_code == 201, res.text
    assert res.json()["login_email"] is None
