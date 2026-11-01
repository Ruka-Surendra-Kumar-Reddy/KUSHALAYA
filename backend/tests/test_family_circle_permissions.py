"""Family circle: primary member runs invites/removals; staff can unlink."""

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.tenant import Tenant
from app.models.user import User


def _login(client, email, password="testpass123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _headers(client, email, password="testpass123"):
    res = _login(client, email, password)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag, *, link=True):
    elder = Elder(tenant_id=tenant_id, first_name=f"Elder{tag}", last_name="Circle", status="ACTIVE")
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.circle@test.example",
        password_hash=hash_password("testpass123"),
        first_name=f"Primary{tag}",
        last_name="Member",
        role="ELDER_PORTAL",
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    if link:
        ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


INVITE = {
    "email": "sibling.circle@test.example",
    "password": "longenough8",
    "first_name": "Sib",
    "last_name": "Ling",
    "portal_relationship": "daughter",
}


def test_primary_invites_and_removes_non_primary_cannot(db, client, seed_tenant):
    primary, elder = _family(db, seed_tenant["tenant"].id, "a")
    ph = _headers(client, primary.email)

    circle = client.get("/api/v1/home-safety/family/circle", headers=ph).json()
    assert circle == [
        {
            "id": primary.id,
            "email": primary.email,
            "first_name": "Primarya",
            "last_name": "Member",
            "portal_relationship": "family",
            "is_you": True,
            "is_primary": True,
        }
    ]

    short = client.post(
        "/api/v1/home-safety/family/circle/invite", headers=ph, json={**INVITE, "password": "short7c"}
    )
    assert short.status_code == 400
    assert "8 characters" in short.json()["detail"]

    invited = client.post("/api/v1/home-safety/family/circle/invite", headers=ph, json=INVITE)
    assert invited.status_code == 200, invited.text
    member_id = invited.json()["id"]
    assert invited.json()["is_primary"] is False

    link = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == member_id, FamilyElderLink.elder_id == elder.id)
        .one()
    )
    assert link.invited_by_user_id == primary.id
    assert link.is_primary is False

    circle = client.get("/api/v1/home-safety/family/circle", headers=ph).json()
    by_id = {m["id"]: m for m in circle}
    assert by_id[primary.id]["is_primary"] is True
    assert by_id[member_id]["is_primary"] is False

    # The invited member can see the circle but cannot invite or remove.
    mh = _headers(client, INVITE["email"], INVITE["password"])
    assert client.get("/api/v1/home-safety/family/circle", headers=mh).status_code == 200
    denied = client.post(
        "/api/v1/home-safety/family/circle/invite",
        headers=mh,
        json={**INVITE, "email": "third.circle@test.example"},
    )
    assert denied.status_code == 403
    assert client.delete(f"/api/v1/home-safety/family/circle/{primary.id}", headers=mh).status_code == 403

    # The primary cannot remove themselves, but can remove the member.
    assert client.delete(f"/api/v1/home-safety/family/circle/{primary.id}", headers=ph).status_code == 400
    removed = client.delete(f"/api/v1/home-safety/family/circle/{member_id}", headers=ph)
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed"] is True
    assert [m["id"] for m in client.get("/api/v1/home-safety/family/circle", headers=ph).json()] == [primary.id]
    assert (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == member_id, FamilyElderLink.elder_id == elder.id)
        .first()
        is None
    )
    # Nothing left to see -> the login is switched off rather than left dangling.
    db.expire_all()
    member = db.query(User).filter(User.id == member_id).one()
    assert member.status == "INACTIVE"
    assert member.elder_id is None
    assert _login(client, INVITE["email"], INVITE["password"]).status_code != 200
    # Removing again is a 404, not a crash.
    assert client.delete(f"/api/v1/home-safety/family/circle/{member_id}", headers=ph).status_code == 404


def test_legacy_household_without_link_rows_still_has_a_primary(db, client, seed_tenant):
    user, elder = _family(db, seed_tenant["tenant"].id, "legacy", link=False)
    h = _headers(client, user.email)
    circle = client.get("/api/v1/home-safety/family/circle", headers=h).json()
    assert circle[0]["is_primary"] is True
    res = client.post("/api/v1/home-safety/family/circle/invite", headers=h, json={**INVITE, "email": "legacy.invite@test.example"})
    assert res.status_code == 200, res.text


def test_staff_unlink_family_user(db, client, seed_tenant):
    primary, elder = _family(db, seed_tenant["tenant"].id, "staff")
    ph = _headers(client, primary.email)
    invited = client.post(
        "/api/v1/home-safety/family/circle/invite",
        headers=ph,
        json={**INVITE, "email": "unlink.me@test.example"},
    )
    assert invited.status_code == 200, invited.text
    member_id = invited.json()["id"]
    link = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == member_id, FamilyElderLink.elder_id == elder.id)
        .one()
    )

    other = Tenant(name="Elsewhere", email="elsewhere@test.example", phone="1", address="x", city="y", state="z")
    db.add(other)
    db.flush()
    other_admin = User(
        email="elsewhere.admin@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Else",
        last_name="Where",
        role="TENANT_ADMIN",
        tenant_id=other.id,
    )
    db.add(other_admin)
    db.commit()
    assert (
        client.delete(f"/api/v1/home-safety/care/family-links/{link.id}", headers=_headers(client, other_admin.email)).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/home-safety/care/family-links/{link.id}", headers=_headers(client, seed_tenant["viewer"].email)).status_code
        == 403
    )

    staff = _headers(client, seed_tenant["manager"].email)
    res = client.delete(f"/api/v1/home-safety/care/family-links/{link.id}", headers=staff)
    assert res.status_code == 200, res.text
    assert res.json() == {"link_id": link.id, "user_id": member_id, "elder_id": elder.id, "removed": True}
    assert client.delete(f"/api/v1/home-safety/care/family-links/{link.id}", headers=staff).status_code == 404
    assert [m["id"] for m in client.get("/api/v1/home-safety/family/circle", headers=ph).json()] == [primary.id]


def test_removing_primary_via_staff_hands_over_to_next_member(db, client, seed_tenant):
    primary, elder = _family(db, seed_tenant["tenant"].id, "handover")
    ph = _headers(client, primary.email)
    invited = client.post(
        "/api/v1/home-safety/family/circle/invite",
        headers=ph,
        json={**INVITE, "email": "next.primary@test.example"},
    )
    member_id = invited.json()["id"]
    primary_link = (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == primary.id, FamilyElderLink.elder_id == elder.id)
        .one()
    )
    staff = _headers(client, seed_tenant["manager"].email)
    assert client.delete(f"/api/v1/home-safety/care/family-links/{primary_link.id}", headers=staff).status_code == 200
    nh = _headers(client, "next.primary@test.example", INVITE["password"])
    circle = client.get("/api/v1/home-safety/family/circle", headers=nh).json()
    assert [(m["id"], m["is_primary"]) for m in circle] == [(member_id, True)]
