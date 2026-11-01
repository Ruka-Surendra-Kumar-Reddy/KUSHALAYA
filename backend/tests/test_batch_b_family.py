"""Batch B family fixes: plain device alerts, no invented preferred time,
notice date guards, cancelled quotes not awaiting approval."""

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell import care_jobs
from app.livewell.family_alert_text import sanitize_family_alert
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.iot_ingest_service import IotIngestService
from app.models.care_job import CareJob
from app.models.user import User


def _family(db, elder, email="famb@test.example"):
    u = User(email=email, password_hash=hash_password("testpass123"), first_name="Fam",
             last_name="B", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(u)
    db.commit()
    return u


def _hub(elder):
    return (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})


def test_device_alert_text_is_plain_for_family(db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder)
    out = IotIngestService.raise_device_event(
        db, event_type="DEVICE_OFFLINE", elder_id=elder.id, device_id="b7-demo",
        hub_id="mg7-1", mac_address="aa:bb:cc:dd:ee:ff", source="mqtt",
    )
    assert "mac=" in out["note"]  # staff copy keeps the codes
    db.refresh(elder)
    alert = _hub(elder)["alerts"][0]
    for code in ("mac=", "device=", "hub=", "aa:bb", "b7-demo", "mg7-1", "BLE"):
        assert code not in alert["body"] and code not in alert["title"]
    assert "alert band hasn't checked in" in alert["body"] and elder.first_name in alert["body"]
    inc = FamilyCareHubService.list_incidents(db, fam)[0]
    assert "mac=" not in inc["note"]


def test_old_device_alert_rows_are_sanitised_on_the_way_out(db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder, "famb2@test.example")
    FamilyCareHubService._push_alert(
        db, elder, title="Wearable not heard — B7 3F2A",
        body="Wearable offline · B7 3F2A · device=b7 · hub=mg7 · mac=AA:BB:CC:DD:EE:FF — No BLE advertisements",
        severity="warning",
    )
    row = FamilyCareHubService.list_alerts(db, fam)[0]
    assert "mac=" not in row["body"] and "AA:BB" not in row["body"] and "3F2A" not in row["title"]
    assert row["title"] == "Alert band not checking in"
    # Unrelated text is left alone.
    assert sanitize_family_alert("Message sent", "hello") == ("Message sent", "hello")


def test_request_without_time_is_not_given_one(db, seed_tenant):
    from app.livewell.family_service_requests import FamilyServiceRequestService as S

    fam = _family(db, seed_tenant["elder"], "famb3@test.example")
    req = S.create_for_family(db, fam, service_type="haircut_grooming", preferred_at=None, notes="")
    assert req["preferred_at"] is None
    assert S.list_for_family(db, fam)[0]["preferred_at"] is None


def test_cancelled_quote_is_not_awaiting_approval(db, seed_tenant):
    from app.livewell.family_service_requests import FamilyServiceRequestService as S

    elder = seed_tenant["elder"]
    fam = _family(db, elder, "famb4@test.example")
    req = S.create_for_family(db, fam, service_type="haircut_grooming", preferred_at=None, notes="")
    quoted = S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="requested", quoted_amount_minor=50000)
    assert quoted["payment_status"] == "awaiting_approval"
    S.cancel_for_family(db, fam, req["id"])
    row = next(r for r in S.list_for_family(db, fam) if r["id"] == req["id"])
    assert row["status"] == "cancelled" and row["payment_status"] != "awaiting_approval"


def test_notice_date_guards():
    now = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    assert care_jobs._in_past(now - timedelta(minutes=1), now)
    assert not care_jobs._in_past(now + timedelta(hours=1), now)
    assert care_jobs._on_the_way_notice_ok(now + timedelta(hours=2), now)
    assert not care_jobs._on_the_way_notice_ok(now + timedelta(hours=3, minutes=1), now)
    assert care_jobs._on_the_way_notice_ok(now - timedelta(hours=1), now)


def test_past_visit_gets_no_scheduled_notice(db, seed_tenant, monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(care_jobs, "_notify_family", lambda db, elder, title, body, event="visit": sent.append(title))
    elder = seed_tenant["elder"]
    past = (datetime.now(timezone.utc) - timedelta(days=2))
    care_jobs.create_job(db, seed_tenant["manager"], {"elder_id": elder.id, "kind": "visit", "scheduled_at": past, "force": True})
    assert not any("scheduled" in t for t in sent)
    future = (datetime.now(timezone.utc) + timedelta(days=2))
    care_jobs.create_job(db, seed_tenant["manager"], {"elder_id": elder.id, "kind": "visit", "scheduled_at": future, "force": True})
    assert any("scheduled" in t for t in sent)


def test_public_care_team_contact_needs_no_login(client):
    res = client.get("/api/v1/home-safety/family/public/care-team-contact")
    assert res.status_code == 200
    body = res.json()
    assert body["phone_tel"].startswith("+") and body["whatsapp_link"].startswith("https://wa.me/")


def test_family_summary_drops_pathway():
    from app.livewell.family_alert_text import clean_family_summary

    s = "Independence Score 62/100 (Moderate). Suggested pathway: Premium Care. Top priorities: Grab bars."
    out = clean_family_summary(s)
    assert "pathway" not in out.lower() and "Top priorities: Grab bars." in out
    assert "Independence" not in out and "Safety Score 62/100" in out
    assert clean_family_summary("LiveWell360 Independence Score™ 72/100.").endswith("Safety Score 72/100.")
    brief = "Update for Amma\nIndependence Score: 62/100\nPathway: Premium Care · ECM recommended\nPriorities: x"
    assert "Pathway" not in clean_family_summary(brief)
