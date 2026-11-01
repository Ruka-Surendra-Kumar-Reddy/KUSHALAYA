"""Phase 2E family portal: no self-notices, care team contact setting, Home payload."""

from app.core.security import hash_password
from app.livewell.family_care_hub import FamilyCareHubService, _hub, _save_hub
from app.livewell.document_types import LW_FAMILY_MEDICAL
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(client, db, seed_tenant, email="p2e.family@test.example"):
    elder = db.query(Elder).filter(Elder.tenant_id == seed_tenant["tenant"].id).first()
    user = User(
        email=email,
        password_hash=hash_password("testpass123"),
        first_name="Asha",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return _login(client, email), user, elder


def test_no_self_notice_alerts(client, db, seed_tenant):
    _, user, elder = _family(client, db, seed_tenant)
    FamilyCareHubService.send_message(db, user, "Hello team")
    FamilyCareHubService.upload_document(
        db,
        user,
        file_name="note.pdf",
        content=b"%PDF-1.4 test",
        content_type="application/pdf",
        document_type=LW_FAMILY_MEDICAL,
    )
    titles = [a["title"] for a in FamilyCareHubService.list_alerts(db, user)]
    assert "Message sent to your care team" not in titles
    assert "Document shared by family" not in titles
    assert FamilyCareHubService.unread_alert_count(elder) == 0


def test_old_self_notices_hidden_and_read_alerts_kept(client, db, seed_tenant):
    _, user, elder = _family(client, db, seed_tenant, email="p2e.old@test.example")
    hub = _hub(elder)
    hub["alerts"] = [
        {"id": "a1", "title": "Message sent to your care team", "body": "", "created_at": "2026-10-01T00:00:00+00:00"},
        {"id": "a2", "title": "Fall risk noted", "body": "x", "severity": "warning", "read_at": "2026-10-02T00:00:00+00:00",
         "created_at": "2026-10-01T00:00:00+00:00"},
    ]
    _save_hub(db, elder, hub)
    rows = FamilyCareHubService.list_alerts(db, user)
    assert [r["id"] for r in rows] == ["a2"]  # read alert stays for "Past alerts"
    assert FamilyCareHubService.unread_alert_count(elder) == 0


def test_care_team_contact_setting_admin_only(client, db, seed_tenant, auth_headers):
    res = client.get("/api/v1/team/care-team-contact", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["is_default"] is True
    assert body["phone_tel"] == "+918309500488"
    assert body["whatsapp_link"] == "https://wa.me/918309500488"
    assert [e["number"] for e in body["emergency"]] == ["112", "108"]

    # Managers cannot change it.
    res = client.put("/api/v1/team/care-team-contact", json={"phone": "+91 90000 00001"}, headers=auth_headers)
    assert res.status_code == 403

    admin = _login(client, "admin@test.example")
    res = client.put(
        "/api/v1/team/care-team-contact",
        json={"phone": "+91 90000 00001", "whatsapp": "+91 90000 00002"},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    assert res.json()["phone_tel"] == "+919000000001"
    assert res.json()["whatsapp_link"] == "https://wa.me/919000000002"
    assert res.json()["is_default"] is False

    bad = client.put("/api/v1/team/care-team-contact", json={"phone": "call me"}, headers=admin)
    assert bad.status_code == 400

    # Families see it on Home.
    headers, _, _ = _family(client, db, seed_tenant, email="p2e.dash@test.example")
    dash = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    data = dash.json()
    assert data["care_team_contact"]["phone"] == "+919000000001"
    assert data["care_team_contact"]["whatsapp_link"] == "https://wa.me/919000000002"
    assert isinstance(data["needs_you"], list)
    assert "last_visit" in data


def test_needs_you_shows_open_sos(client, db, seed_tenant):
    headers, user, _ = _family(client, db, seed_tenant, email="p2e.sos@test.example")
    FamilyCareHubService.raise_sos(db, user, "Test")
    data = client.get("/api/v1/home-safety/family/dashboard", headers=headers).json()
    kinds = {n["kind"] for n in data["needs_you"]}
    assert "sos" in kinds


def test_needs_you_lists_quote_waiting(client, db, seed_tenant):
    from app.models.commerce import Order

    headers, _, elder = _family(client, db, seed_tenant, email="p2e.quote@test.example")
    db.add(Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="quoted", lines=[],
                 subtotal_paise=100000, total_paise=118000,
                 quoted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)))
    db.commit()
    data = client.get("/api/v1/home-safety/family/dashboard", headers=headers).json()
    quotes = [n for n in data["needs_you"] if n["kind"] == "quote"]
    assert quotes and quotes[0]["href"].endswith("/services#quotes")
    assert "incl. GST" in quotes[0]["title"]


def test_care_team_contact_normalises_and_keeps_whatsapp(client, db, seed_tenant):
    from app.livewell.care_team_contact import _clean

    assert _clean("09876543210") == "+919876543210"
    assert _clean("98765 43210") == "+919876543210"
    assert _clean("+971 50 123 4567") == "+971501234567"
    for bad in ("12345", "+1234567890123456"):
        try:
            _clean(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)

    admin = _login(client, "admin@test.example")
    client.put("/api/v1/team/care-team-contact",
               json={"phone": "9000000001", "whatsapp": "9000000002"}, headers=admin)
    res = client.put("/api/v1/team/care-team-contact", json={"phone": "9000000003"}, headers=admin)
    assert res.status_code == 200, res.text
    assert res.json()["phone"] == "+919000000003"
    assert res.json()["whatsapp"] == "+919000000002"


def test_info_rows_are_updates_and_self_notices_per_member(client, db, seed_tenant):
    _, user, elder = _family(client, db, seed_tenant, email="p2e.info@test.example")
    _, sibling, _ = _family(client, db, seed_tenant, email="p2e.sib@test.example")
    FamilyCareHubService._push_alert(db, elder, title="Visit done", body="ok", severity="info")
    FamilyCareHubService._push_alert(db, elder, title="Fall risk", body="x", severity="warning")
    FamilyCareHubService._push_alert(
        db, elder, title="Request received", body="x", severity="info", actor_email=user.email
    )
    titles = [a["title"] for a in FamilyCareHubService.list_alerts(db, user)]
    assert titles == ["Fall risk"]
    assert FamilyCareHubService.unread_alert_count(elder, user) == 1
    feed = {i["title"]: i["kind"] for i in FamilyCareHubService.care_feed(db, user)}
    assert feed.get("Visit done") == "update" and "Request received" not in feed
    sib_feed = {i["title"] for i in FamilyCareHubService.care_feed(db, sibling)}
    assert "Request received" in sib_feed

    # SOS: the sender does not get the echo; a sibling does (critical never hidden).
    sos = FamilyCareHubService.raise_sos(db, user, "Help")
    from app.livewell import incident_service, sos_siren

    assert not any(a["severity"] == "critical" for a in FamilyCareHubService.list_alerts(db, sibling))
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    sos_siren.confirm(db, row.id, seed_tenant["manager"])
    sos_siren.notify_family(db, row.id, seed_tenant["manager"])  # care team first (29 Oct)
    assert not any(a["severity"] == "critical" for a in FamilyCareHubService.list_alerts(db, user))
    assert any(a["severity"] == "critical" for a in FamilyCareHubService.list_alerts(db, sibling))
