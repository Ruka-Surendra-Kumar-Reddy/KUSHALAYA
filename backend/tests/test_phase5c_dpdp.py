"""Phase 5C (#104 DPDP, #105 backup status)."""

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell import privacy
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.audit_log import AuditLog
from app.models.commerce import Order
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.privacy import PrivacyConsent, PrivacyDataRequest
from app.models.user import User

P = "/api/v1/home-safety/family/privacy"
A = "/api/v1/home-safety/privacy"


def _headers(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag):
    elder = Elder(
        tenant_id=tenant_id, first_name=f"Senior{tag}", last_name="Dp", status="ACTIVE",
        phone="+919999900000", address=f"{tag} Road, Hyderabad", medical_conditions="BP",
        custom_attributes={"language_preference": "Telugu", "staff_internal_note": "difficult son"},
    )
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.dpdp@test.example", password_hash=hash_password("testpass123"),
        first_name=f"Fam{tag}", last_name="Dp", role="ELDER_PORTAL", tenant_id=tenant_id, elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


def _order(db, elder, note="staff only"):
    o = Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="PAID",
              lines=[{"name": "Grab bar", "qty": 1, "price_paise": 150000, "cost_paise": 90000}],
              subtotal_paise=150000, cost_paise=90000, discount_paise=0, discount_reason="",
              gst_bp=1800, gst_paise=27000, total_paise=177000, note=note, family_note="Thanks", paid_paise=177000)
    db.add(o)
    db.commit()
    return o


def _consent_body(elder, marketing=False):
    return {
        "purposes": {"care_delivery": True, "health_data": True, "location_sharing": True, "marketing": marketing},
        "elders": [{"elder_id": elder.id, "purposes": {"care_delivery": True}, "consented_by_name": "Fam son",
                    "relationship": "son"}],
    }


def test_consent_recorded_and_reasked_on_version_change(client, db, seed_tenant, monkeypatch):
    user, elder = _family(db, seed_tenant["tenant"].id, "c1")
    h = _headers(client, user.email)
    st = client.get(f"{P}/consent", headers=h).json()
    assert st["needs_consent"] is True and st["elders"][0]["needs_consent"] is True

    # Care delivery cannot be refused.
    bad = client.post(f"{P}/consent", headers=h, json={"purposes": {"care_delivery": False}})
    assert bad.status_code == 400

    res = client.post(f"{P}/consent", headers=h, json=_consent_body(elder))
    assert res.status_code == 200, res.text
    st = res.json()
    assert st["needs_consent"] is False
    assert st["consent"]["purposes"]["marketing"] is False  # off by default
    assert st["consent"]["notice_version"] == privacy.NOTICE_VERSION
    erow = db.query(PrivacyConsent).filter_by(subject="elder", elder_id=elder.id).one()
    assert erow.consented_by_name == "Fam son" and erow.relationship == "son"
    assert db.query(AuditLog).filter_by(action="privacy.consent", user_id=user.id).count() == 2

    # Marketing omitted -> stays off.
    client.post(f"{P}/consent", headers=h, json={"purposes": {"care_delivery": True}})
    assert privacy.marketing_opted_in(db, user) is False

    monkeypatch.setattr(privacy, "NOTICE_VERSION", "2099-01-01")
    st = client.get(f"{P}/consent", headers=h).json()
    assert st["needs_consent"] is True and st["notice_version"] == "2099-01-01"


def test_export_only_own_household_no_staff_fields(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "e1")
    other, other_elder = _family(db, tid, "e2")
    _order(db, elder)
    _order(db, other_elder)
    h = _headers(client, user.email)
    res = client.get(f"{P}/export", headers=h)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert {"my-data.json", "clients.csv", "orders.csv", "account.csv"} <= names
    data = json.loads(zf.read("my-data.json"))
    blob = json.dumps(data)
    assert [c["id"] for c in data["clients"]] == [elder.id]
    assert all(o["elder_id"] == elder.id for o in data["orders"]) and len(data["orders"]) == 1
    assert other_elder.first_name not in blob and other.email not in blob
    assert "password" not in blob and "cost_paise" not in blob and "staff only" not in blob
    assert "staff_internal_note" not in blob and "difficult son" not in blob
    assert data["clients"][0]["details"]["language_preference"] == "Telugu"
    assert db.query(AuditLog).filter_by(action="privacy.export", user_id=user.id).count() == 1


def test_delete_request_flow_anonymises_and_keeps_financial(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "d1")
    order = _order(db, elder)
    h = _headers(client, user.email)
    res = client.post(f"{P}/delete-request", headers=h, json={"scope": "household", "reason": "moving"})
    assert res.status_code == 200, res.text
    rid = res.json()["id"]
    assert client.post(f"{P}/delete-request", headers=h, json={}).status_code == 409

    # Staff who are not admins cannot review.
    mh = _headers(client, "manager@test.example")
    assert client.get(f"{A}/requests", headers=mh).status_code == 403
    assert client.post(f"{A}/requests/{rid}/approve", headers=mh, json={}).status_code == 403
    assert client.get(f"{A}/requests", headers=h).status_code == 403

    ah = _headers(client, "admin@test.example")
    rows = client.get(f"{A}/requests", headers=ah).json()
    assert any(r["id"] == rid and r["status"] == "PENDING" for r in rows)
    done = client.post(f"{A}/requests/{rid}/approve", headers=ah, json={"note": "ok"})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"

    db.expire_all()
    e = db.get(Elder, elder.id)
    assert e.first_name == "Deleted" and e.phone is None and e.address is None and e.medical_conditions is None
    u = db.get(User, user.id)
    assert u.email.endswith("@deleted.invalid") and u.status == "INACTIVE" and u.elder_id is None
    assert db.query(FamilyElderLink).filter_by(elder_id=elder.id).count() == 0
    kept = db.get(Order, order.id)
    assert kept is not None and kept.total_paise == 177000 and kept.elder_id == elder.id
    assert client.post("/api/v1/auth/login", json={"email": user.email, "password": "testpass123"}).status_code != 200
    actions = {a.action for a in db.query(AuditLog).filter(AuditLog.entity_type == "privacy_request",
                                                           AuditLog.entity_id == rid)}
    assert {"privacy.delete_requested", "privacy.delete_approved"} <= actions
    # Can't approve twice.
    assert client.post(f"{A}/requests/{rid}/approve", headers=ah, json={}).status_code == 409


def test_reject_and_account_scope_and_secondary_member(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "r1")
    helper = User(email="helper.r1.dpdp@test.example", password_hash=hash_password("testpass123"),
                  first_name="Helper", last_name="Dp", role="ELDER_PORTAL", tenant_id=tid, elder_id=elder.id)
    db.add(helper)
    db.flush()
    ensure_family_elder_link(db, helper, elder)
    db.commit()
    hh = _headers(client, helper.email)
    assert client.post(f"{P}/delete-request", headers=hh, json={"scope": "household"}).status_code == 403
    rid = client.post(f"{P}/delete-request", headers=hh, json={"scope": "account"}).json()["id"]
    ah = _headers(client, "admin@test.example")
    rej = client.post(f"{A}/requests/{rid}/reject", headers=ah, json={"note": "call first"})
    assert rej.json()["status"] == "REJECTED"
    assert db.query(AuditLog).filter_by(action="privacy.delete_rejected", entity_id=rid).count() == 1

    rid2 = client.post(f"{P}/delete-request", headers=hh, json={"scope": "account"}).json()["id"]
    client.post(f"{A}/requests/{rid2}/approve", headers=ah, json={})
    db.expire_all()
    assert db.get(Elder, elder.id).first_name == "Senior" + "r1"  # client untouched
    assert db.get(User, helper.id).status == "INACTIVE"
    assert db.get(PrivacyDataRequest, rid2).status == "COMPLETED"


def test_backup_status_admin_only(client, db, seed_tenant, tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    monkeypatch.setenv("BACKUP_STATUS_FILE", str(status_file))
    ah = _headers(client, "admin@test.example")
    mh = _headers(client, "manager@test.example")
    assert client.get(f"{A}/backup-status", headers=mh).status_code == 403
    assert client.get(f"{A}/backup-status").status_code in (401, 403)
    assert client.get(f"{A}/backup-status", headers=ah).json()["configured"] is False

    now = datetime.now(timezone.utc)
    status_file.write_text(json.dumps({"last_status": "ok", "last_success_at": now.isoformat(),
                                       "last_attempt_at": now.isoformat(), "remote": "oci:kushalaya-backups"}))
    body = client.get(f"{A}/backup-status", headers=ah).json()
    assert body["ok"] is True and body["stale"] is False

    old = (now - timedelta(days=3)).isoformat()
    status_file.write_text(json.dumps({"last_status": "ok", "last_success_at": old}))
    assert client.get(f"{A}/backup-status", headers=ah).json()["ok"] is False


def test_public_notice_has_version_and_grievance_officer(client):
    body = client.get(f"{A}/notice").json()
    assert body["version"] == privacy.NOTICE_VERSION
    assert body["grievance_officer"]["email"]
    assert [p for p in body["purposes"] if p["key"] == "marketing"][0]["default"] is False


# --- audit fixes: erasure covers every personal table; export shows only the requester's rows ---


def _job(db, elder, cg_id=None):
    from app.models.care_job import CareJob

    job = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=cg_id, kind="visit", title="Visit",
                  status="completed", scheduled_at=datetime.now(timezone.utc) - timedelta(days=1))
    db.add(job)
    db.flush()
    return job


def test_household_erasure_covers_voice_letters_reports_feedback_consents(client, db, seed_tenant):
    from datetime import date

    import pytest

    from app.core.storage import get_storage
    from app.models.care_job_live_location import CareJobLiveLocation
    from app.models.family_contact import FamilyQuestion
    from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
    from app.models.incident_report import IncidentReport
    from app.models.kushlife_quality import KushLifeMonthly, NpsResponse, VisitRating, VisitVoiceNote

    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "x1")
    job = _job(db, elder, seed_tenant["caregiver"].id)
    key, _ = get_storage().save(tid, "elder", elder.id, "voice-note-x.webm", b"\x1aE\xdf\xa3voice", "audio/webm")
    db.add(VisitVoiceNote(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, storage_key=key,
                          mime_type="audio/webm", size_bytes=9, share_with_family=True))
    db.add(KushLifeMonthly(tenant_id=tid, elder_id=elder.id, month_start=date(2026, 9, 1), status="approved",
                           text="Amma walked daily", draft_text="Amma walked daily"))
    db.add(IncidentReport(tenant_id=tid, elder_id=elder.id, kind="fall", occurred_at=datetime.now(timezone.utc),
                          location="Bathroom at 12 Banjara Hills", what_happened="Slipped near tub",
                          witnesses="Neighbour Ravi", family_summary="Minor bruise"))
    db.add(VisitRating(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, user_id=user.id, rating=2,
                       comment="Caregiver late, my mother cried"))
    db.add(NpsResponse(tenant_id=tid, elder_id=elder.id, user_id=user.id, score=3, reason="Too costly for my father"))
    db.add(FamilyQuestion(tenant_id=tid, elder_id=elder.id, asker_user_id=user.id, kind="call_me",
                          body="Call about BP", call_window="Evening"))
    db.add(PrivacyConsent(tenant_id=tid, user_id=user.id, elder_id=elder.id, subject="elder",
                          notice_version=privacy.NOTICE_VERSION, purposes={"care_delivery": True},
                          consented_by_name="Ravi Kumar (son)", relationship="son"))
    db.add(CareJobLiveLocation(job_id=job.id, tenant_id=tid, latitude=17.41, longitude=78.44,
                               updated_at=datetime.now(timezone.utc)))
    db.add(HomeSafetyAssessmentRecord(assessment_id="HSA-X1", tenant_id=tid, elder_id=elder.id, status="completed",
                                      payload={"client_name": "Senior x1", "address": "12 Banjara Hills"},
                                      history=[{"by": "Fam"}], versions=[{"payload": {"name": "x"}}]))
    db.commit()

    h = _headers(client, user.email)
    rid = client.post(f"{P}/delete-request", headers=h, json={"scope": "household"}).json()["id"]
    done = client.post(f"{A}/requests/{rid}/approve", headers=_headers(client, "admin@test.example"), json={})
    assert done.status_code == 200, done.text
    db.expire_all()

    assert db.query(VisitVoiceNote).filter_by(elder_id=elder.id).count() == 0
    with pytest.raises(Exception):
        get_storage().read(key)
    assert db.query(KushLifeMonthly).filter_by(elder_id=elder.id).count() == 0
    rep = db.query(IncidentReport).filter_by(elder_id=elder.id).one()  # kept for counts, text gone
    assert rep.kind == "fall" and rep.location == "" and "Slipped" not in rep.what_happened
    assert rep.witnesses == "" and rep.family_summary == ""
    assert db.query(VisitRating).filter_by(elder_id=elder.id).one().comment == ""
    assert db.query(NpsResponse).filter_by(elder_id=elder.id).one().reason == ""
    q = db.query(FamilyQuestion).filter_by(elder_id=elder.id).one()
    assert q.body is None and q.call_window is None
    consents = db.query(PrivacyConsent).filter_by(elder_id=elder.id).all()
    assert consents and all("Ravi" not in c.consented_by_name and c.relationship is None for c in consents)
    assert db.query(CareJobLiveLocation).filter_by(job_id=job.id).count() == 0
    a = db.query(HomeSafetyAssessmentRecord).filter_by(assessment_id="HSA-X1").one()
    assert "Banjara" not in json.dumps(a.payload) and not a.history and not a.versions


def test_export_scoped_to_requester_and_includes_invoices_feedback_letters_voice(client, db, seed_tenant):
    from datetime import date

    from app.models.family_contact import FamilyContact, FamilyQuestion
    from app.models.kushlife_quality import KushLifeMonthly, NpsResponse, VisitRating, VisitVoiceNote
    from app.models.tax_invoice import TaxInvoice

    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "x2")
    sibling = User(email="sibling.x2.dpdp@test.example", password_hash=hash_password("testpass123"),
                   first_name="Sib", last_name="Dp", role="ELDER_PORTAL", tenant_id=tid, elder_id=elder.id)
    db.add(sibling)
    db.flush()
    db.query(FamilyContact).filter_by(elder_id=elder.id).delete()
    db.add(FamilyContact(tenant_id=tid, elder_id=elder.id, user_id=user.id, name="Me", email="me.x2@example.com",
                         phone="+911111111111"))
    db.add(FamilyContact(tenant_id=tid, elder_id=elder.id, user_id=sibling.id, name="Sib Dp",
                         email="sib.secret@example.com", phone="+912222222222"))
    db.add(FamilyQuestion(tenant_id=tid, elder_id=elder.id, asker_user_id=user.id, kind="ask", body="My question",
                          reply="Staff answer"))
    db.add(FamilyQuestion(tenant_id=tid, elder_id=elder.id, asker_user_id=sibling.id, kind="ask",
                          body="Sibling private question"))
    job = _job(db, elder)
    db.add(VisitRating(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, user_id=user.id, rating=5, comment="Great"))
    db.add(VisitRating(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, user_id=sibling.id, rating=1,
                       comment="Sibling complaint"))
    db.add(NpsResponse(tenant_id=tid, elder_id=elder.id, user_id=user.id, score=9, reason="Mine"))
    db.add(KushLifeMonthly(tenant_id=tid, elder_id=elder.id, month_start=date(2026, 8, 1), status="approved",
                           text="Approved letter"))
    db.add(KushLifeMonthly(tenant_id=tid, elder_id=elder.id, month_start=date(2026, 9, 1), status="draft",
                           text="Draft letter"))
    db.add(VisitVoiceNote(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, storage_key="k/shared.webm",
                          share_with_family=True))
    db.add(VisitVoiceNote(tenant_id=tid, elder_id=elder.id, care_job_id=job.id, storage_key="k/private.webm",
                          share_with_family=False))
    db.add(TaxInvoice(tenant_id=tid, elder_id=elder.id, number="KA/26-27/00009", fy=2026, seq=9,
                      issued_at=datetime.now(timezone.utc), source_type="order", source_id="x2", total_paise=1180))
    db.commit()

    res = client.get(f"{P}/export", headers=_headers(client, user.email))
    assert res.status_code == 200, res.text
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    data = json.loads(zf.read("my-data.json"))
    blob = json.dumps(data)
    mine = [c for c in data["family_contacts"] if c.get("email")]
    assert [c["email"] for c in mine] == ["me.x2@example.com"]
    assert any(c.get("name") == "Sib Dp" for c in data["family_contacts"])
    assert "sib.secret@example.com" not in blob and "+912222222222" not in blob
    assert [q["body"] for q in data["questions"]] == ["My question"] and data["questions"][0]["reply"] == "Staff answer"
    assert "Sibling private question" not in blob and "Sibling complaint" not in blob
    assert [r["comment"] for r in data["visit_ratings"]] == ["Great"]
    assert [n["reason"] for n in data["nps_responses"]] == ["Mine"]
    assert [m["text"] for m in data["monthly_letters"]] == ["Approved letter"]
    assert len(data["voice_notes"]) == 1 and data["voice_notes"][0]["download_url"].endswith("/audio")
    assert "storage_key" not in blob
    assert data["tax_invoices"][0]["number"] == "KA/26-27/00009"
    assert data["tax_invoices"][0]["pdf_url"].endswith("/pdf")
    assert {"tax_invoices.csv", "visit_ratings.csv", "voice_notes.csv"} <= set(zf.namelist())


def test_export_csv_escapes_formulas(db, seed_tenant):
    tid = seed_tenant["tenant"].id
    user, elder = _family(db, tid, "x3")
    elder.first_name = "@SUM(1)"
    db.commit()
    raw, _ = privacy.export_zip(db, user)
    text = zipfile.ZipFile(io.BytesIO(raw)).read("clients.csv").decode("utf-8")
    assert "'@SUM(1)" in text and ",@SUM" not in text


def test_csv_safe_rules():
    from app.core.csv_safe import csv_safe

    assert csv_safe("=1+2") == "'=1+2"
    assert csv_safe("+91 98") == "'+91 98"
    assert csv_safe("-cmd") == "'-cmd"
    assert csv_safe("@x") == "'@x"
    assert csv_safe("\tx") == "'\tx"
    assert csv_safe("\rx") == "'\rx"
    assert csv_safe("-3068.00") == "-3068.00"  # money stays numeric
    assert csv_safe("Ravi") == "Ravi" and csv_safe(5) == 5 and csv_safe(None) is None
