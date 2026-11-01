"""AI room preview: async jobs, caps, cache reuse, privacy, QA retry, family view, scope.

Stub / fake providers only — no real AI calls.
"""

import io

import pytest
from PIL import Image

from app.core.security import hash_password
from app.livewell import ai_preview_qa, ai_render_queue
from app.livewell.ai_config_service import DEFAULT_SETTINGS
from app.livewell.ai_provider import AIImageJobResult, LocalStubProvider
from app.livewell.ai_room_preview import has_exif, room_similarity, strip_exif
from app.models.elder import Elder
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User

PRODUCTS = ["BTH-002", "BTH-009"]


def _room_jpeg(seed: int = 0, gps: bool = True) -> bytes:
    img = Image.new("RGB", (320, 240), (200, 190, 170))
    px = img.load()
    for x in range(320):
        for y in range(240):
            if (x // 40 + y // 40 + seed) % 2:
                px[x, y] = (120, 140, 150)
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    if gps:
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N"
        gps_ifd[2] = (17.0, 24.0, 0.0)
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


def _noise() -> bytes:
    import random

    rnd = random.Random(7)
    img = Image.new("RGB", (320, 240))
    img.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(320 * 240)])
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def setup(db, client, seed_tenant):
    elder = seed_tenant["elder"]
    rec = HomeSafetyAssessmentRecord(
        assessment_id="ASM-PREV-1",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        status="completed",
        payload={"ratings": {"home_safety_toilet_grab_bar_installed": "unsafe"}, "photos": []},
    )
    db.add(rec)
    db.commit()
    admin = _login(client, "admin@test.example")
    photos = []
    for i in range(3):
        up = client.post(
            "/api/v1/home-safety/photos",
            headers=admin,
            files={"file": (f"bath{i}.jpg", io.BytesIO(_room_jpeg(i)), "image/jpeg")},
            data={"elder_id": str(elder.id), "assessment_id": "ASM-PREV-1", "room_type": "bathroom"},
        )
        assert up.status_code == 200, up.text
        photos.append(up.json()["id"])
    return {"admin": admin, "photos": photos, "elder": elder, "seed": seed_tenant}


@pytest.fixture
def qa_all_present(monkeypatch):
    def fake(image, names, before=None):
        return {
            "items": [
                {"n": i, "product": n, "present": True, "confidence": 0.9, "box_2d": [100, 200, 400, 500]}
                for i, n in enumerate(names, start=1)
            ]
        }

    monkeypatch.setattr(ai_preview_qa, "_call_gemini", fake)


def _create(client, headers, photo, tier="comfort", products=PRODUCTS, force=False):
    return client.post(
        "/api/v1/home-safety/ai/preview/jobs",
        headers=headers,
        json={
            "assessment_id": "ASM-PREV-1",
            "source_document_id": photo,
            "room_type": "bathroom",
            "package_level": tier,
            "product_codes": products,
            "force": force,
        },
    )


def test_strip_exif_removes_gps_and_similarity_behaves():
    raw = _room_jpeg()
    assert has_exif(raw)
    clean = strip_exif(raw)
    assert not has_exif(clean)
    assert room_similarity(raw, raw) >= 0.99
    assert room_similarity(raw, _noise()) < 0.5  # below the 0.55 default threshold


def test_async_job_lifecycle(db, client, setup, monkeypatch, qa_all_present):
    queued: list[int] = []
    monkeypatch.setattr(ai_render_queue, "_inline", lambda: False)
    monkeypatch.setattr(ai_render_queue, "_pool", lambda: type("P", (), {"submit": lambda self, fn, jid, tid: queued.append(jid)})())
    sent: list[bytes] = []
    orig = LocalStubProvider.submit_render

    def spy(self, request, *, source_image_bytes, extra=None):
        sent.append(source_image_bytes)
        return orig(self, request, source_image_bytes=source_image_bytes, extra=extra)

    monkeypatch.setattr(LocalStubProvider, "submit_render", spy)

    r = _create(client, setup["admin"], setup["photos"][0])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued" and body["progress"]["stage"] == "queued"
    assert body["progress"]["running"] is True
    assert len(queued) == 1 and not sent  # request returned before any render

    ai_render_queue.process_job(db, queued[0])
    ai_render_queue.process_job(db, queued[0])  # second call is a no-op (already claimed)

    got = client.get(f"/api/v1/home-safety/ai/preview/jobs/{body['ai_job_id']}", headers=setup["admin"]).json()
    assert got["status"] == "needs_review"
    assert got["progress"]["stage"] == "done" and got["progress"]["percent"] == 100
    assert got["render_attempts"] == 1 and len(sent) == 1
    assert got["similarity_score"] >= 0.9
    assert not has_exif(sent[0])  # only clean pixels left the server
    assert [m["n"] for m in got["markers"]] == [1, 2] and got["markers"][0]["x"] == 0.2
    # Paise math: price + 18% GST per item, total = sum.
    for it in got["items"]:
        assert it["gst_paise"] == it["price_paise"] * 1800 // 10000
        assert it["price_with_gst_paise"] == it["price_paise"] + it["gst_paise"]
    assert got["total_paise"] == sum(i["price_with_gst_paise"] for i in got["items"])
    assert [i["product_code"] for i in got["items"]] == PRODUCTS
    img = client.get(got["after_url"], headers=setup["admin"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    pdf = client.get(f"/api/v1/home-safety/ai/preview/jobs/{got['ai_job_id']}/pdf", headers=setup["admin"])
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_auto_retry_when_room_changed_and_item_missing(db, client, setup, monkeypatch):
    calls = {"n": 0}
    clean_room = strip_exif(_room_jpeg(0))

    def fake_submit(self, request, *, source_image_bytes, extra=None):
        calls["n"] += 1
        img = _noise() if calls["n"] == 1 else source_image_bytes
        return AIImageJobResult(status="completed", generated_image_bytes=img, generated_content_type="image/png", is_stub=True)

    qa_calls = {"n": 0}

    def fake_qa(image, names, before=None):
        qa_calls["n"] += 1
        present = qa_calls["n"] > 1
        return {"items": [{"n": i, "present": present or i == 1, "confidence": 0.9} for i in range(1, len(names) + 1)]}

    monkeypatch.setattr(LocalStubProvider, "submit_render", fake_submit)
    monkeypatch.setattr(ai_preview_qa, "_call_gemini", fake_qa)
    r = _create(client, setup["admin"], setup["photos"][0])
    assert r.status_code == 200, r.text
    job = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.public_id == r.json()["ai_job_id"]).first()
    assert job.render_attempts == 2
    events = [e["event"] for e in job.event_log]
    assert "auto_retry" in events
    retry = next(e for e in job.event_log if e["event"] == "auto_retry")["detail"]
    assert retry["room_changed"] is True and retry["missing"] == ["Anti-slip Strips"] or retry["missing"]
    assert "MUST be clearly visible" in job.prompt_text and "floor tile colour" in job.prompt_text
    assert job.similarity_score >= 0.9
    assert room_similarity(clean_room, clean_room) >= 0.99


def test_approve_blocked_when_product_missing(db, client, setup, monkeypatch):
    monkeypatch.setattr(
        ai_preview_qa, "_call_gemini",
        lambda image, names, before=None: {"items": [{"n": 1, "present": True, "confidence": 0.9}, {"n": 2, "present": False, "confidence": 0.1}]},
    )
    r = _create(client, setup["admin"], setup["photos"][0]).json()
    assert r["missing"] and r["items"][1]["shown"] is False
    ap = client.post(f"/api/v1/home-safety/ai/preview/jobs/{r['ai_job_id']}/review", headers=setup["admin"], json={"action": "approve"})
    assert ap.status_code == 400 and "Not shown" in ap.text


def test_caps_enforced_including_regenerate_and_single_create(db, client, setup, monkeypatch, qa_all_present):
    monkeypatch.setitem(DEFAULT_SETTINGS, "max_regenerations_per_tier", 1)
    monkeypatch.setitem(DEFAULT_SETTINGS, "max_images_per_assessment", 2)
    a = setup["admin"]
    first = _create(client, a, setup["photos"][0]).json()
    regen = client.post(f"/api/v1/home-safety/ai/preview/jobs/{first['ai_job_id']}/review", headers=a, json={"action": "regenerate"})
    assert regen.status_code == 200, regen.text
    assert regen.json()["regenerated_from"] == first["ai_job_id"]
    again = client.post(f"/api/v1/home-safety/ai/preview/jobs/{regen.json()['ai_job_id']}/review", headers=a, json={"action": "regenerate"})
    assert again.status_code == 400 and "regenerations" in again.text
    # Forced new render of the same tier counts as a regeneration too.
    forced = _create(client, a, setup["photos"][0], products=["BTH-002"], force=True)
    assert forced.status_code == 400
    # Photo cap (2 photos) on the preview path and the legacy single-create path.
    assert _create(client, a, setup["photos"][1]).status_code == 200
    assert _create(client, a, setup["photos"][2]).status_code == 400
    legacy = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=a,
        json={"assessment_id": "ASM-PREV-1", "room_type": "bathroom", "package_level": "essential",
              "source_document_id": setup["photos"][2], "approved_solution_ids": []},
    )
    assert legacy.status_code == 400


def test_daily_cap(db, client, setup, monkeypatch, qa_all_present):
    monkeypatch.setitem(DEFAULT_SETTINGS, "daily_render_cap", 1)
    assert _create(client, setup["admin"], setup["photos"][0]).status_code == 200
    r = _create(client, setup["admin"], setup["photos"][1])
    assert r.status_code == 429


def test_identical_request_reuses_result(db, client, setup, qa_all_present):
    a = _create(client, setup["admin"], setup["photos"][0]).json()
    b = _create(client, setup["admin"], setup["photos"][0]).json()
    assert b["cache_hit"] is True and b["ai_job_id"] == a["ai_job_id"]
    from app.models.ai_usage import AiUsageEvent

    hits = db.query(AiUsageEvent).filter(AiUsageEvent.feature == "room_preview", AiUsageEvent.cache_hit.is_(True)).count()
    assert hits == 1
    c = _create(client, setup["admin"], setup["photos"][0], products=["BTH-002"]).json()
    assert c["cache_hit"] is False and c["ai_job_id"] != a["ai_job_id"]


def test_context_preselects_room_products(db, client, setup):
    r = client.get("/api/v1/home-safety/ai/preview/context?elder_id=%d" % setup["elder"].id, headers=setup["admin"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assessment_id"] == "ASM-PREV-1"
    assert {p["document_id"] for p in body["photos"]} == set(setup["photos"])
    rec = body["recommended"]["bathroom"]
    assert rec and all(c.split("-")[0] not in ("SVC", "HM") for c in rec)
    assert any(c.startswith("BTH-") for c in rec)
    assert body["catalog"] and "cost_paise" not in body["catalog"][0]


def test_family_sees_only_approved_and_requests_fixes_once(db, client, setup, qa_all_present):
    elder = setup["elder"]
    fam = User(email="famprev@test.example", password_hash=hash_password("testpass123"), first_name="Fam",
               last_name="P", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(fam)
    db.commit()
    fh = _login(client, fam.email)
    job = _create(client, setup["admin"], setup["photos"][0]).json()
    # Pretend the image came from the real provider (families never see stub images).
    row = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.public_id == job["ai_job_id"]).first()
    row.provider = "fal_kontext"
    from app.models.document import Document

    doc = db.get(Document, row.generated_document_id)
    doc.ocr_extracted_json = {**doc.ocr_extracted_json, "is_stub": False}
    db.commit()

    assert client.get("/api/v1/home-safety/family/ai-previews", headers=fh).json() == []
    ap = client.post(f"/api/v1/home-safety/ai/preview/jobs/{job['ai_job_id']}/review", headers=setup["admin"], json={"action": "approve"})
    assert ap.status_code == 200, ap.text
    listed = client.get("/api/v1/home-safety/family/ai-previews", headers=fh)
    assert listed.status_code == 200, listed.text
    [v] = listed.json()
    assert [i["product_code"] for i in v["items"]] == PRODUCTS
    assert "price_paise" not in v["items"][0]
    req = client.post(f"/api/v1/home-safety/family/ai-previews/{v['id']}/request", headers=fh, json={})
    assert req.status_code == 200, req.text
    body = req.json()
    assert [i["product_code"] for i in body["items"]] == PRODUCTS
    assert body["product_code"] == "BTH-002,BTH-009"
    all_reqs = client.get("/api/v1/home-safety/family/service-requests", headers=fh).json()
    assert len(all_reqs) == 1
    pdf = client.get(f"/api/v1/home-safety/family/ai-previews/{v['id']}/pdf", headers=fh)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_team_scope_and_viewer_read_only(db, client, setup, qa_all_present):
    seed = setup["seed"]
    a = setup["admin"]
    job = _create(client, a, setup["photos"][0]).json()
    viewer = _login(client, "viewer@test.example")
    assert client.get(f"/api/v1/home-safety/ai/preview/jobs/{job['ai_job_id']}", headers=viewer).status_code == 200
    assert _create(client, viewer, setup["photos"][1]).status_code == 403
    assert client.post(f"/api/v1/home-safety/ai/preview/jobs/{job['ai_job_id']}/review", headers=viewer,
                       json={"action": "approve"}).status_code == 403
    assert client.get("/api/v1/home-safety/ai/preview/usage", headers=viewer).status_code == 403

    manager = _login(client, "manager@test.example")
    assert client.get(f"/api/v1/home-safety/ai/preview/jobs/{job['ai_job_id']}", headers=manager).status_code == 200
    # Move the client out of the manager's team: the job disappears for them.
    elder = db.get(Elder, seed["elder"].id)
    elder.manager_user_id = None
    db.commit()
    assert client.get(f"/api/v1/home-safety/ai/preview/jobs/{job['ai_job_id']}", headers=manager).status_code == 404
    assert _create(client, manager, setup["photos"][1]).status_code == 404
    assert client.get("/api/v1/home-safety/ai/preview/jobs?assessment_id=ASM-PREV-1", headers=manager).json() == []

    usage = client.get("/api/v1/home-safety/ai/preview/usage", headers=a).json()
    rp = next(f for f in usage["features"] if f["feature"] == "room_preview")
    assert rp["calls"] >= 2  # one render + one product check (shared ai_usage_events)
    assert {f["feature"] for f in usage["features"]} >= {"room_preview", "hazard_check"}
    # Stub render is free; the (mocked) Gemini product check is estimated.
    assert usage["estimated_cost_paise"] == rp["estimated_cost_paise"] == 10


def test_mock_gpu_router_admin_only(client, setup):
    viewer = _login(client, "viewer@test.example")
    manager = _login(client, "manager@test.example")
    assert client.get("/api/v1/home-safety/ai/gpu/v1/jobs/x", headers=viewer).status_code == 403
    assert client.get("/api/v1/home-safety/ai/gpu/v1/jobs/x", headers=manager).status_code == 403
    assert client.get("/api/v1/home-safety/ai/gpu/v1/jobs/x", headers=setup["admin"]).status_code == 404


def test_room_change_retries_and_blocks_approval(db, client, setup, monkeypatch):
    """A render that adds e.g. a second toilet is retried with a corrective prompt and cannot be approved."""
    seen = {"before": None}

    def fake_qa(image, names, before=None):
        seen["before"] = before
        return {
            "items": [{"n": i, "present": True, "confidence": 0.9} for i in range(1, len(names) + 1)],
            "changes": ["A second toilet was added"],
        }

    monkeypatch.setattr(ai_preview_qa, "_call_gemini", fake_qa)
    r = _create(client, setup["admin"], setup["photos"][0]).json()
    assert seen["before"], "the original photo must be sent for the before/after comparison"
    assert r["changes"] == ["A second toilet was added"] and r["room_changed"] is True
    job = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.public_id == r["ai_job_id"]).first()
    assert job.render_attempts == 2
    assert "A second toilet was added" in job.prompt_text
    ap = client.post(f"/api/v1/home-safety/ai/preview/jobs/{r['ai_job_id']}/review", headers=setup["admin"], json={"action": "approve"})
    assert ap.status_code == 400 and "changed the room" in ap.text


def test_qa_changes_cleaned_and_only_with_before(monkeypatch):
    raw = {"items": [{"n": 1, "present": True, "confidence": 0.9}], "changes": ["  extra   toilet ", {"description": "sink removed"}, "", "extra toilet"]}
    monkeypatch.setattr(ai_preview_qa, "_call_gemini", lambda image, names, before=None: raw)
    with_before = ai_preview_qa.check_products(b"after", ["Grab bar"], before=b"before")
    assert with_before["changes"] == ["extra toilet", "sink removed"]
    assert ai_preview_qa.check_products(b"after", ["Grab bar"])["changes"] == []
