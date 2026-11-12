"""AI room hazard check — provider mocked, no real API calls."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.livewell import ai_hazard_provider as hp
from app.livewell.ai_hazard_provider import (
    HazardProviderError,
    HazardResult,
    box_from_yxyx,
    parse_hazard_payload,
    strip_image_metadata,
)
from app.models.ai_hazard_check import AiHazardFeedback
from app.models.ai_usage import AiUsageEvent
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

GPS_TAG = 0x8825


def _jpeg_with_gps(color=(200, 180, 160)) -> bytes:
    im = Image.new("RGB", (64, 48), color)
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[GPS_TAG] = {1: "N", 2: (17.0, 24.0, 0.0), 3: "E", 4: (78.0, 29.0, 0.0)}
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


CANNED = {
    "hazards": [
        {"code": "no_toilet_grab_bar", "confidence": 92, "box_2d": [300, 100, 700, 400], "evidence": "Toilet, bare wall"},
        {"code": "slippery_bathroom_floor", "confidence": 0.7, "box_2d": [800, 0, 1000, 1000]},
        {"code": "no_shower_chair", "confidence": 40},
        {"code": "made_up_hazard", "confidence": 99},
        {"code": "loose_wires", "confidence": 88, "box_2d": "bad"},
    ],
    "notes": "Water heater visible",
}


class MockProvider:
    def __init__(self, payload=None, fail: str | None = None):
        self.calls: list[bytes] = []
        self.payload = payload if payload is not None else CANNED
        self.fail = fail

    def name(self):
        return "mock"

    def model_version(self):
        return "mock-vision-1"

    def is_configured(self):
        return True

    def detect(self, image_jpeg: bytes, hazards: list[dict]) -> HazardResult:
        self.calls.append(image_jpeg)
        if self.fail:
            raise HazardProviderError(self.fail)
        found, rejected, notes = parse_hazard_payload(self.payload, [h["code"] for h in hazards])
        return HazardResult(provider="mock", model="mock-vision-1", hazards=found, notes=notes, rejected_codes=rejected)


@pytest.fixture
def mock_provider():
    p = MockProvider()
    hp.set_hazard_provider_for_tests(p)
    yield p
    hp.set_hazard_provider_for_tests(None)


def _headers(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _draft_assessment(db, seed_tenant, assessment_id="ASM-HZ-1"):
    rec = HomeSafetyAssessmentRecord(
        assessment_id=assessment_id,
        tenant_id=seed_tenant["tenant"].id,
        status="draft",
        elder_id=seed_tenant["elder"].id,
        payload={"id": assessment_id, "ratings": {}, "itemNotes": {}},
    )
    db.add(rec)
    db.commit()
    return rec


def _upload(client, headers, elder_id, content, assessment_id=None, room="bathroom"):
    data = {"elder_id": str(elder_id), "room_type": room, "caption": "Bathroom"}
    if assessment_id:
        data["assessment_id"] = assessment_id
    res = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath.jpg", io.BytesIO(content), "image/jpeg")},
        data=data,
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _start(client, headers, doc_id, **extra):
    return client.post(
        "/api/v1/home-safety/ai/hazard-checks",
        headers=headers,
        json={"document_id": doc_id, "room_type": "bathroom", **extra},
    )


# --- pure validation -------------------------------------------------------------


def test_schema_validation_rejects_unknown_codes():
    found, rejected, notes = parse_hazard_payload(CANNED, ["no_toilet_grab_bar", "slippery_bathroom_floor", "no_shower_chair"])
    codes = [f.code for f in found]
    assert "made_up_hazard" in rejected and "made_up_hazard" not in codes
    assert "loose_wires" in rejected  # allowed elsewhere, not in this room's list
    assert codes[0] == "no_toilet_grab_bar" and found[0].confidence == 92
    assert next(f for f in found if f.code == "slippery_bathroom_floor").confidence == 70
    assert notes == "Water heater visible"
    with pytest.raises(HazardProviderError):
        parse_hazard_payload(["not", "an", "object"], ["x"])
    with pytest.raises(HazardProviderError):
        parse_hazard_payload({"hazards": "nope"}, ["x"])


def test_bounding_boxes_validated():
    assert box_from_yxyx([300, 100, 700, 400]) == [0.1, 0.3, 0.3, 0.4]
    assert box_from_yxyx([800, 0, 1000, 1000]) == [0.0, 0.8, 1.0, 0.2]
    assert box_from_yxyx([0, 0, 1000, 1000]) is None  # whole frame is not a location
    assert box_from_yxyx([500, 500, 400, 600]) is None  # inverted
    assert box_from_yxyx([0, 0, 2000, 10]) is None  # off the grid
    assert box_from_yxyx("bad") is None
    assert box_from_yxyx([1, 2, 3]) is None


def test_exif_and_gps_stripped():
    raw = _jpeg_with_gps()
    with Image.open(io.BytesIO(raw)) as im:
        assert GPS_TAG in im.getexif()
    clean = strip_image_metadata(raw)
    with Image.open(io.BytesIO(clean)) as im:
        assert len(im.getexif()) == 0
        assert im.size == (64, 48)
    assert b"Exif" not in clean and b"PhoneMaker" not in clean


# --- API flow --------------------------------------------------------------------


def test_check_runs_in_background_and_applies_nothing(db, client, seed_tenant, mock_provider):
    headers = _headers(client, "admin@test.example")
    rec = _draft_assessment(db, seed_tenant)
    doc_id = _upload(client, headers, seed_tenant["elder"].id, _jpeg_with_gps(), assessment_id="ASM-HZ-1")

    res = _start(client, headers, doc_id, assessment_id="ASM-HZ-1")
    assert res.status_code == 200, res.text
    check_id = res.json()["id"]
    assert res.json()["status"] in ("queued", "running", "succeeded")

    body = client.get(f"/api/v1/home-safety/ai/hazard-checks/{check_id}", headers=headers).json()
    assert body["status"] == "succeeded" and body["stage"] == "Done"
    by_code = {h["code"]: h for h in body["hazards"]}
    # loose_wires is an any-room hazard; made_up_hazard is not ours and is dropped.
    assert set(by_code) == {"no_toilet_grab_bar", "slippery_bathroom_floor", "no_shower_chair", "loose_wires"}
    assert by_code["loose_wires"]["box"] is None  # malformed box -> listed without a box
    assert all(h["decision"] == "pending" for h in body["hazards"])  # nothing auto-applied
    top = by_code["no_toilet_grab_bar"]
    assert top["band"] == "high" and top["severity"] == "urgent" and top["severity_label"] == "Urgent"
    assert top["box"] == [0.1, 0.3, 0.3, 0.4]
    assert top["rubric_item_id"] == "home_safety_toilet_grab_bar_installed"
    assert top["question"]
    assert any(p["product_code"] for p in top["products"])
    assert all(p["price_with_gst_paise"] is None or p["price_with_gst_paise"] >= p["price_paise"] for p in top["products"])
    assert by_code["slippery_bathroom_floor"]["band"] == "check"
    assert by_code["no_shower_chair"]["band"] == "low"

    # The image sent out had no EXIF / GPS.
    assert len(mock_provider.calls) == 1
    assert b"PhoneMaker" not in mock_provider.calls[0]

    db.refresh(rec)
    assert rec.payload.get("ratings") == {}

    usage = db.query(AiUsageEvent).filter(AiUsageEvent.feature == "hazard_check").all()
    assert len(usage) == 1 and usage[0].cache_hit is False


def test_confirm_writes_rating_with_attribution_and_reject_is_stored(db, client, seed_tenant, mock_provider):
    headers = _headers(client, "admin@test.example")
    rec = _draft_assessment(db, seed_tenant, "ASM-HZ-2")
    doc_id = _upload(client, headers, seed_tenant["elder"].id, _jpeg_with_gps(), assessment_id="ASM-HZ-2")
    check = _start(client, headers, doc_id, assessment_id="ASM-HZ-2").json()
    body = client.get(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}", headers=headers).json()
    n_grab = next(h["n"] for h in body["hazards"] if h["code"] == "no_toilet_grab_bar")
    n_floor = next(h["n"] for h in body["hazards"] if h["code"] == "slippery_bathroom_floor")

    ok = client.post(
        f"/api/v1/home-safety/ai/hazard-checks/{check['id']}/hazards/{n_grab}",
        headers=headers,
        json={"decision": "confirm"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["applied_to_assessment"] is True
    db.refresh(rec)
    assert rec.payload["ratings"]["home_safety_toilet_grab_bar_installed"] == "unsafe"
    assert rec.payload["itemNotes"]["home_safety_toilet_grab_bar_installed"] == "AI-checked, confirmed by Test Admin"
    assert rec.payload["aiHazardSources"]["home_safety_toilet_grab_bar_installed"]["check_id"] == check["id"]

    no = client.post(
        f"/api/v1/home-safety/ai/hazard-checks/{check['id']}/hazards/{n_floor}",
        headers=headers,
        json={"decision": "reject"},
    )
    assert no.status_code == 200
    fb = {(f.hazard_code, f.decision) for f in db.query(AiHazardFeedback).all()}
    assert ("no_toilet_grab_bar", "accepted") in fb
    assert ("slippery_bathroom_floor", "rejected") in fb
    db.refresh(rec)
    assert "home_safety_anti_slip_flooring" not in rec.payload["ratings"]

    listed = client.get("/api/v1/home-safety/ai/hazard-checks?assessment_id=ASM-HZ-2", headers=headers).json()
    assert listed["summary"]["total_confirmed"] == 1
    assert listed["summary"]["rooms"][0] == {"room": "bathroom", "label": "Bathroom", "hazards": 1, "urgent": 1}

    # Viewers read, never decide.
    vh = _headers(client, "viewer@test.example")
    assert client.get(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}", headers=vh).status_code == 200
    denied = client.post(
        f"/api/v1/home-safety/ai/hazard-checks/{check['id']}/hazards/{n_floor}", headers=vh, json={"decision": "confirm"}
    )
    assert denied.status_code == 403


def test_family_sees_confirmed_only(db, client, seed_tenant, mock_provider):
    from app.core.security import hash_password
    from app.livewell.family_elder_access import ensure_family_elder_link
    from app.models.user import User

    headers = _headers(client, "admin@test.example")
    elder = seed_tenant["elder"]
    doc_id = _upload(client, headers, elder.id, _jpeg_with_gps())
    check = _start(client, headers, doc_id).json()
    body = client.get(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}", headers=headers).json()
    n = next(h["n"] for h in body["hazards"] if h["code"] == "no_toilet_grab_bar")
    client.post(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}/hazards/{n}", headers=headers, json={"decision": "confirm"})

    fam = User(
        email="hz.family@test.example", password_hash=hash_password("testpass123"), first_name="Fam",
        last_name="Ily", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id,
    )
    db.add(fam)
    db.flush()
    ensure_family_elder_link(db, fam, elder)
    db.commit()
    fh = _headers(client, "hz.family@test.example")
    fam_url = "/api/v1/home-safety/family/room-hazards"
    share_url = f"/api/v1/home-safety/ai/hazard-checks/{check['id']}/share"
    # Room checks are internal until a care manager shares them.
    assert client.get(fam_url, headers=fh).json()["total"] == 0
    shared = client.post(share_url, headers=headers, json={"shared": True})
    assert shared.status_code == 200 and shared.json()["shared_with_family_at"]
    res = client.get(fam_url, headers=fh)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 1
    item = data["hazards"][0]
    assert item["label"] == "No grab bar next to the toilet" and item["room_label"] == "Bathroom"
    assert set(item) == {"room_label", "label", "severity_label", "suggestion"}  # no confidence/boxes/names
    # Families cannot use the staff API, or share.
    assert client.get(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}", headers=fh).status_code == 403
    assert client.post(share_url, headers=fh, json={"shared": True}).status_code == 403
    # Un-sharing hides it again; History lists it with the client's name.
    assert client.post(share_url, headers=headers, json={"shared": False}).json()["shared_with_family_at"] is None
    assert client.get(fam_url, headers=fh).json()["total"] == 0
    recent = client.get("/api/v1/home-safety/ai/hazard-checks?recent=true", headers=headers).json()["checks"]
    assert any(c["id"] == check["id"] and c["elder_name"] for c in recent)


def test_cache_by_image_hash(db, client, seed_tenant, mock_provider):
    headers = _headers(client, "admin@test.example")
    img = _jpeg_with_gps((10, 20, 30))
    doc1 = _upload(client, headers, seed_tenant["elder"].id, img)
    first = _start(client, headers, doc1).json()
    again = _start(client, headers, doc1).json()
    assert again["id"] == first["id"]
    doc2 = _upload(client, headers, seed_tenant["elder"].id, img)
    copy = _start(client, headers, doc2).json()
    assert copy["id"] != first["id"] and copy["cache_hit"] is True and copy["status"] == "succeeded"
    assert all(h["decision"] == "pending" for h in copy["hazards"])
    assert len(mock_provider.calls) == 1
    hits = db.query(AiUsageEvent).filter(AiUsageEvent.cache_hit.is_(True)).count()
    assert hits == 1


def test_daily_cap(db, client, seed_tenant, mock_provider):
    tenant = seed_tenant["tenant"]
    tenant.workflow_config = {**(tenant.workflow_config or {}), "home_safety_ai": {"settings": {"hazard_check_daily_cap": 1}}}
    db.commit()
    headers = _headers(client, "admin@test.example")
    doc1 = _upload(client, headers, seed_tenant["elder"].id, _jpeg_with_gps((1, 2, 3)))
    assert _start(client, headers, doc1).status_code == 200
    doc2 = _upload(client, headers, seed_tenant["elder"].id, _jpeg_with_gps((90, 80, 70)))
    capped = _start(client, headers, doc2)
    assert capped.status_code == 429
    assert "limit" in capped.text
    assert len(mock_provider.calls) == 1


def test_team_scope_and_roles(db, client, seed_tenant, mock_provider):
    admin = _headers(client, "admin@test.example")
    other = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Not", last_name="Mine", care_level="Low")
    db.add(other)
    db.commit()
    doc_other = _upload(client, admin, other.id, _jpeg_with_gps((5, 5, 5)))
    doc_mine = _upload(client, admin, seed_tenant["elder"].id, _jpeg_with_gps((6, 6, 6)))

    mgr = _headers(client, "manager@test.example")
    assert _start(client, mgr, doc_other).status_code == 404
    assert client.get(f"/api/v1/home-safety/ai/hazard-checks?elder_id={other.id}", headers=mgr).status_code == 404
    assert _start(client, mgr, doc_mine).status_code == 200

    viewer = _headers(client, "viewer@test.example")
    assert _start(client, viewer, doc_mine).status_code == 403


def test_provider_failure_is_graceful_and_retryable(db, client, seed_tenant):
    failing = MockProvider(fail="The AI service is busy right now. Please try again in a minute.")
    hp.set_hazard_provider_for_tests(failing)
    try:
        headers = _headers(client, "admin@test.example")
        doc = _upload(client, headers, seed_tenant["elder"].id, _jpeg_with_gps((7, 7, 7)))
        check = _start(client, headers, doc).json()
        body = client.get(f"/api/v1/home-safety/ai/hazard-checks/{check['id']}", headers=headers).json()
        assert body["status"] == "failed" and "busy" in body["error_message"]
        hp.set_hazard_provider_for_tests(MockProvider())
        retry = _start(client, headers, doc).json()
        done = client.get(f"/api/v1/home-safety/ai/hazard-checks/{retry['id']}", headers=headers).json()
        assert done["status"] == "succeeded"
    finally:
        hp.set_hazard_provider_for_tests(None)


def test_gemini_model_fallback_on_404(monkeypatch):
    import httpx

    seen: list[str] = []

    class FakeResp:
        def __init__(self, status, payload=None):
            self.status_code = status
            self._payload = payload or {}

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            assert "key=" not in url  # key never in the URL
            seen.append(url)
            if "gone-model" in url:
                return FakeResp(404)
            text = '{"hazards":[{"code":"loose_rug","confidence":90,"box_2d":[100,100,300,300]}]}'
            return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(hp.settings, "AI_VISION_MODEL", "gone-model")
    monkeypatch.setattr(hp.settings, "AI_VISION_MODEL_FALLBACKS", "backup-model")
    monkeypatch.setattr(hp, "_working_model", None)
    prov = hp.GeminiHazardProvider(api_key="test-key")
    res = prov.detect(b"jpeg", [{"code": "loose_rug", "label": "Loose rug"}])
    assert res.model == "backup-model"
    assert [h.code for h in res.hazards] == ["loose_rug"]
    assert len(seen) == 2
    monkeypatch.setattr(hp, "_working_model", None)
