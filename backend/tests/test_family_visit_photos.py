"""Family visit reports carry the caregiver's visit photos — only this family's elder's."""
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.photo_service import HomeSafetyPhotoService
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.user import User

F = "/api/v1/home-safety/family"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _family(db, tenant_id, tag):
    elder = Elder(tenant_id=tenant_id, first_name=f"Senior{tag}", last_name="Pics", status="ACTIVE")
    db.add(elder)
    db.flush()
    user = User(email=f"family.{tag}.pics@test.example", password_hash=hash_password("testpass123"),
                first_name=f"Fam{tag}", last_name="Pics", role="ELDER_PORTAL", tenant_id=tenant_id,
                elder_id=elder.id)
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _photo(db, staff, elder, caption):
    return HomeSafetyPhotoService.upload(db, staff, file_name="p.jpg", content=JPEG, content_type="image/jpeg",
                                         caption=caption, assessment_id=None, prospect_id=None, elder_id=elder.id)


def _done_job(db, elder, photo_ids=()):
    when = datetime.now(timezone.utc) - timedelta(days=1)
    job = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Home visit",
                  status="completed", scheduled_at=when, completed_at=when,
                  report={"checks": {}, "photo_ids": list(photo_ids)})
    db.add(job)
    db.commit()
    return job


def test_family_sees_own_visit_photos_and_never_another_familys(client, db, seed_tenant):
    tid = seed_tenant["elder"].tenant_id
    staff = db.query(User).filter(User.email == "admin@test.example").first()
    ua, ea = _family(db, tid, "a")
    ub, eb = _family(db, tid, "b")
    mine = _photo(db, staff, ea, "Grab rail fitted")
    plain = _photo(db, staff, ea, None)
    theirs = _photo(db, staff, eb, "B's kitchen")

    # A tampered report that also points at family B's photo must not leak it.
    job = _done_job(db, ea, [mine.id, plain.id, theirs.id])

    ha, hb = _login(client, ua.email), _login(client, ub.email)
    v = client.get(f"{F}/visits/job-{job.id}", headers=ha)
    assert v.status_code == 200, v.text
    body = v.json()
    assert [p["id"] for p in body["photos"]] == [mine.id, plain.id]
    assert body["photos"][0]["caption"] == "Grab rail fitted"
    assert body["photos"][1]["caption"] == ""  # default upload label is not a caption
    assert body["photos"][0]["taken_at"]
    assert body["photos"][0]["url"] == f"{F}/photos/{mine.id}/image"
    assert body["photo_ids"] == [mine.id, plain.id]

    img = client.get(f"{F}/photos/{mine.id}/image", headers=ha)
    assert img.status_code == 200 and img.content == JPEG
    assert client.get(f"{F}/photos/{theirs.id}/image", headers=ha).status_code == 404

    # Family B can't open A's visit report or A's photo.
    assert client.get(f"{F}/visits/job-{job.id}", headers=hb).status_code == 404
    assert client.get(f"{F}/photos/{mine.id}/image", headers=hb).status_code == 404
    # Signed out: no access at all.
    assert client.get(f"{F}/photos/{mine.id}/image").status_code in (401, 403)


def test_visit_without_photos_has_empty_list(client, db, seed_tenant):
    ua, ea = _family(db, seed_tenant["elder"].tenant_id, "c")
    job = _done_job(db, ea)
    v = client.get(f"{F}/visits/job-{job.id}", headers=_login(client, ua.email))
    assert v.status_code == 200, v.text
    assert v.json()["photos"] == [] and v.json()["photo_urls"] == []


# --- updates feed + hide from family ----------------------------------------------

P = "/api/v1/home-safety/photos"


def _feed_visit(client, headers, job):
    r = client.get(f"{F}/care-feed", headers=headers)
    assert r.status_code == 200, r.text
    return next(i for i in r.json() if i["id"] == f"visit-job-{job.id}")


def test_feed_visit_carries_own_photos_only_max_four(client, db, seed_tenant):
    tid = seed_tenant["elder"].tenant_id
    staff = db.query(User).filter(User.email == "admin@test.example").first()
    ua, ea = _family(db, tid, "d")
    ub, eb = _family(db, tid, "e")
    mine = [_photo(db, staff, ea, f"Room {n}") for n in range(5)]
    theirs = _photo(db, staff, eb, "B's room")
    job = _done_job(db, ea, [*(p.id for p in mine), theirs.id])

    item = _feed_visit(client, _login(client, ua.email), job)
    assert [p["id"] for p in item["photos"]] == [p.id for p in mine[:4]]
    assert item["photo_count"] == 5
    assert item["photos"][0]["url"] == f"{F}/photos/{mine[0].id}/image"
    # Family B never sees A's visit in its feed.
    rb = client.get(f"{F}/care-feed", headers=_login(client, ub.email)).json()
    assert all(i["id"] != f"visit-job-{job.id}" for i in rb)


def test_hidden_photo_not_listed_and_not_fetchable(client, db, seed_tenant, admin_headers):
    tid = seed_tenant["elder"].tenant_id
    staff = db.query(User).filter(User.email == "admin@test.example").first()
    ua, ea = _family(db, tid, "f")
    shown = _photo(db, staff, ea, "Shown")
    hidden = _photo(db, staff, ea, "Internal")
    job = _done_job(db, ea, [shown.id, hidden.id])
    ha = _login(client, ua.email)

    r = client.patch(f"{P}/{hidden.id}/family-visibility", json={"family_hidden": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["family_hidden"] is True
    assert client.get(f"{P}/{hidden.id}/family-visibility", headers=admin_headers).json()["family_hidden"] is True

    body = client.get(f"{F}/visits/job-{job.id}", headers=ha).json()
    assert [p["id"] for p in body["photos"]] == [shown.id]
    assert body["photo_ids"] == [shown.id]
    assert [p["id"] for p in _feed_visit(client, ha, job)["photos"]] == [shown.id]
    assert client.get(f"{F}/photos/{hidden.id}/image", headers=ha).status_code == 404
    # Staff still see it.
    assert client.get(f"{P}/{hidden.id}/image", headers=admin_headers).status_code == 200

    # Show it again → back for the family.
    r = client.patch(f"{P}/{hidden.id}/family-visibility", json={"family_hidden": False}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["family_hidden"] is False
    assert client.get(f"{F}/photos/{hidden.id}/image", headers=ha).status_code == 200


def test_only_care_team_of_same_tenant_can_toggle(client, db, seed_tenant):
    from app.models.tenant import Tenant

    tid = seed_tenant["elder"].tenant_id
    staff = db.query(User).filter(User.email == "admin@test.example").first()
    ua, ea = _family(db, tid, "g")
    photo = _photo(db, staff, ea, "Hall")
    other = Tenant(name="Other Pics Org", email="otherpics@test.example", phone="1", address="x", city="y", state="z")
    db.add(other)
    db.flush()
    outsider = User(email="admin.otherpics@test.example", password_hash=hash_password("testpass123"),
                    first_name="O", last_name="Admin", role="TENANT_ADMIN", tenant_id=other.id)
    db.add(outsider)
    db.commit()
    url = f"{P}/{photo.id}/family-visibility"

    assert client.patch(url, json={"family_hidden": True}, headers=_login(client, ua.email)).status_code == 403
    assert client.patch(url, json={"family_hidden": True}, headers=_login(client, "viewer@test.example")).status_code == 403
    assert client.patch(url, json={"family_hidden": True}, headers=_login(client, outsider.email)).status_code == 404
    assert client.patch(url, json={"family_hidden": True}).status_code in (401, 403)
    # Nothing changed: the family still gets the photo.
    assert client.get(f"{F}/photos/{photo.id}/image", headers=_login(client, ua.email)).status_code == 200
    # A care manager toggles photos of clients on their own team.
    manager = db.query(User).filter(User.email == "manager@test.example").first()
    ea.manager_user_id = manager.id
    db.commit()
    assert client.patch(url, json={"family_hidden": True},
                        headers=_login(client, manager.email)).status_code == 200
