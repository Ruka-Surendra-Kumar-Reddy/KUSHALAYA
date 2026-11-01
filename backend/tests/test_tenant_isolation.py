from app.core.security import hash_password
from app.models.elder import Elder as ElderModel
from app.models.tenant import Tenant as TenantModel
from app.models.user import User as UserModel


def test_user_cannot_read_other_tenant_elder(client, db, seed_tenant):
    other = TenantModel(
        name="Other Agency",
        email="other@test.example",
        phone="+1-555-0200",
        address="2 Other St",
        city="Elsewhere",
        state="OT",
    )
    db.add(other)
    db.flush()
    other_elder = ElderModel(
        tenant_id=other.id,
        first_name="Private",
        last_name="Elder",
    )
    db.add(other_elder)
    other_user = UserModel(
        email="othermgr@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Other",
        last_name="Mgr",
        role="CARE_MANAGER",
        tenant_id=other.id,
    )
    db.add(other_user)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    res = client.get(f"/api/v1/elders/{other_elder.id}", headers=headers)
    assert res.status_code == 403
