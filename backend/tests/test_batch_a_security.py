"""Batch A security/privacy fixes: spoof-proof client IP, PIN-check limit,
no staff notes to families, scoped activity log, single-senior invites,
tenantless family accounts refused."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.user import User
from app.services.session_activity_service import SessionActivityService, _client_meta


def _req(peer: str, headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 1234),
        }
    )


def _headers(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _user(db, email, role, tenant_id, **kw):
    u = User(
        email=email,
        password_hash=hash_password("testpass123"),
        first_name="T",
        last_name="U",
        role=role,
        tenant_id=tenant_id,
        **kw,
    )
    db.add(u)
    db.flush()
    return u


# --- 1. client IP ----------------------------------------------------------------


def test_forged_xff_ignored_for_enquiry_limit(client, seed_tenant):
    body = {"name": "Spoofer", "phone": "9000000000", "area": "Somewhere"}
    codes = []
    for i in range(6):
        res = client.post(
            "/api/v1/home-safety/enquiries",
            json=body,
            headers={"X-Forwarded-For": f"10.0.0.{i}, 1.2.3.4"},
        )
        codes.append(res.status_code)
    # A fresh forged address per request must not reset the per-IP limit (5/hour).
    assert codes[:5] == [200] * 5, codes
    assert codes[5] == 429


def test_session_ip_ignores_forged_xff():
    _ua, ip = _client_meta(_req("203.0.113.9", {"X-Forwarded-For": "6.6.6.6", "User-Agent": "x"}))
    assert ip == "203.0.113.9"
    # From the local nginx, X-Real-IP is trusted; a forged leading XFF entry is not.
    _ua, ip = _client_meta(
        _req("127.0.0.1", {"X-Forwarded-For": "6.6.6.6, 198.51.100.7", "X-Real-IP": "198.51.100.7"})
    )
    assert ip == "198.51.100.7"
    _ua, ip = _client_meta(_req("127.0.0.1", {"X-Forwarded-For": "6.6.6.6, 198.51.100.8"}))
    assert ip == "198.51.100.8"


# --- 2. PIN checker limit --------------------------------------------------------


def test_pincode_check_rate_limited(client, seed_tenant, monkeypatch):
    from app.api.v1 import public_enquiries as pe

    monkeypatch.setattr(pe, "_pincode_hits", {})
    monkeypatch.setattr(pe, "PINCODE_CHECK_LIMIT", 3)
    codes = [client.get("/api/v1/home-safety/enquiries/pincode/500001").status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3] == 429


# --- 3. no staff notes to families -----------------------------------------------


def test_family_visual_schema_has_no_review_notes():
    from app.schemas.home_safety_family import FamilyApprovedVisualResponse

    assert "review_notes" not in FamilyApprovedVisualResponse.model_fields


# --- 4. activity log -------------------------------------------------------------


def test_activity_log_scoped_for_manager(db, client, seed_tenant):
    tid = seed_tenant["tenant"].id
    manager = seed_tenant["manager"]
    team_elder = seed_tenant["elder"]
    other_elder = Elder(tenant_id=tid, first_name="Other", last_name="Client", status="ACTIVE")
    db.add(other_elder)
    db.flush()
    cg_user = _user(db, "cg.batcha@test.example", "CAREGIVER", tid, caregiver_id=seed_tenant["caregiver"].id)
    fam_in = _user(db, "fam.in.batcha@test.example", "ELDER_PORTAL", tid, elder_id=team_elder.id)
    fam_out = _user(db, "fam.out.batcha@test.example", "ELDER_PORTAL", tid, elder_id=other_elder.id)
    outsider = _user(db, "staff.out.batcha@test.example", "CARE_MANAGER", tid)
    rows = {}
    for u in (manager, cg_user, fam_in, fam_out, outsider):
        rows[u.id] = SessionActivityService.start_session(
            db, u, request=_req("203.0.113.5", {"User-Agent": "SecretBrowser/1"})
        )
    db.commit()

    mh = _headers(client, manager.email)
    res = client.get("/api/v1/activity/sessions?limit=100", headers=mh)
    assert res.status_code == 200, res.text
    seen = {r["user_id"] for r in res.json()}
    assert {manager.id, cg_user.id, fam_in.id} <= seen
    assert fam_out.id not in seen and outsider.id not in seen
    assert all(r["ip_address"] is None and r["user_agent"] is None for r in res.json())

    detail = client.get(f"/api/v1/activity/sessions/{rows[fam_in.id].id}", headers=mh)
    assert detail.status_code == 200
    d = detail.json()
    assert d["ip_address"] is None and d["user_agent"] is None
    assert all(e["meta"] is None and e["path"] is None for e in d["events"])
    hidden = client.get(f"/api/v1/activity/sessions/{rows[outsider.id].id}", headers=mh)
    assert hidden.status_code == 404

    ah = _headers(client, seed_tenant["admin"].email)
    res = client.get("/api/v1/activity/sessions?limit=100", headers=ah)
    seen = {r["user_id"]: r for r in res.json()}
    assert {manager.id, cg_user.id, fam_in.id, fam_out.id, outsider.id} <= set(seen)
    assert seen[outsider.id]["ip_address"] == "203.0.113.5"
    assert seen[outsider.id]["user_agent"] == "SecretBrowser/1"


def test_activity_log_viewer_refused(client, seed_tenant):
    vh = _headers(client, seed_tenant["viewer"].email)
    assert client.get("/api/v1/activity/sessions", headers=vh).status_code == 403


# --- 5. invites are for the selected senior only ---------------------------------

INVITE = {
    "email": "sib.batcha@test.example",
    "password": "longenough8",
    "first_name": "Sib",
    "last_name": "Ling",
    "portal_relationship": "daughter",
}


def _household(db, tid):
    a = Elder(tenant_id=tid, first_name="Mum", last_name="A", status="ACTIVE")
    b = Elder(tenant_id=tid, first_name="Dad", last_name="B", status="ACTIVE")
    db.add_all([a, b])
    db.flush()
    primary = _user(db, "primary.batcha@test.example", "ELDER_PORTAL", tid, elder_id=a.id)
    ensure_family_elder_link(db, primary, a)
    ensure_family_elder_link(db, primary, b)
    db.commit()
    return primary, a, b


def test_invite_links_only_selected_senior(db, client, seed_tenant):
    primary, a, b = _household(db, seed_tenant["tenant"].id)
    ph = _headers(client, primary.email)
    res = client.post("/api/v1/home-safety/family/circle/invite", headers=ph, json={**INVITE, "elder_id": b.id})
    assert res.status_code == 200, res.text
    links = db.query(FamilyElderLink).filter(FamilyElderLink.user_id == res.json()["id"]).all()
    assert [l.elder_id for l in links] == [b.id]


def test_invite_refused_for_non_primary_or_unlinked(db, client, seed_tenant):
    primary, a, b = _household(db, seed_tenant["tenant"].id)
    # b's primary is someone else; the inviter is only an ordinary member there.
    other = _user(db, "other.primary.batcha@test.example", "ELDER_PORTAL", seed_tenant["tenant"].id, elder_id=b.id)
    for link in db.query(FamilyElderLink).filter(FamilyElderLink.elder_id == b.id).all():
        link.is_primary = False
    ensure_family_elder_link(db, other, b).is_primary = True
    db.commit()
    ph = _headers(client, primary.email)
    res = client.post("/api/v1/home-safety/family/circle/invite", headers=ph, json={**INVITE, "elder_id": b.id})
    assert res.status_code == 403
    stranger = Elder(tenant_id=seed_tenant["tenant"].id, first_name="X", last_name="Y", status="ACTIVE")
    db.add(stranger)
    db.commit()
    res = client.post(
        "/api/v1/home-safety/family/circle/invite", headers=ph, json={**INVITE, "elder_id": stranger.id}
    )
    assert res.status_code == 403


# --- 6. tenantless family accounts -----------------------------------------------


def test_tenantless_elder_portal_user_refused(db, seed_tenant):
    from app.core.rbac import require_elder_portal
    from app.livewell.family_elder_access import _same_tenant

    u = User(email="nt@test.example", role="ELDER_PORTAL", tenant_id=None, elder_id=seed_tenant["elder"].id)
    with pytest.raises(HTTPException) as exc:
        require_elder_portal(u)
    assert exc.value.status_code == 403
    assert _same_tenant(u, seed_tenant["elder"]) is False
