"""Safe Home family app API."""

from app.core.security import hash_password
from app.models.elder import Elder
from app.models.user import User


def test_family_dashboard_elder_portal(db, client, seed_tenant):
    elder = db.query(Elder).first()
    user = User(
        email="family.safehome@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Family",
        last_name="Member",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    res = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert elder.first_name in data["senior_name"]
    assert data["safety"]["max_total"] == 100

    res_alerts = client.get("/api/v1/home-safety/family/alerts", headers=headers)
    assert res_alerts.status_code == 200
    assert isinstance(res_alerts.json(), list)
