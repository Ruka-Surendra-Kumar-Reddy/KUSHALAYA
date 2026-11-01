"""AI visualization jobs — local stub works without GPU provider."""

import pytest
from io import BytesIO

from app.livewell.ai_config_service import normalize_ai_config
from app.livewell.ai_defaults import DEFAULT_AI_CONFIG
from app.livewell.ai_prompt_builder import build_prompt_bundle
from app.livewell.ai_provider import AIImageJobPayload, LocalStubProvider, get_ai_provider
from app.livewell.ai_stub_image import build_local_stub_concept
from app.models.user import User


def test_normalize_ai_config_defaults():
    cfg = normalize_ai_config({})
    assert len(cfg["tiers"]) == 3
    assert cfg["tiers"][0]["id"] == "essential"
    assert any(t["room_type"] == "bathroom" for t in cfg["prompt_templates"])
    assert cfg["settings"]["default_provider"] == "local_stub"


def test_get_ai_provider_defaults_to_local_stub():
    provider = get_ai_provider({})
    assert provider.name() == "local_stub"
    assert provider.is_configured() is True


def test_build_prompt_bundle_replaces_modifications():
    solutions = {
        "solutions": [
            {
                "id": "SH-BATH-GRAB",
                "finding": "Install grab bars",
                "recommendedSolutions": ["Wall-mounted grab bars"],
            }
        ]
    }
    # Empty package_solutions so tier filter falls back to approved IDs.
    cfg = {
        **DEFAULT_AI_CONFIG,
        "package_solutions": [],
    }
    bundle = build_prompt_bundle(
        cfg,
        room_type="bathroom",
        package_level="essential",
        approved_solution_ids=["SH-BATH-GRAB"],
        solutions_lib=solutions,
    )
    assert "Wall-mounted grab bars" in bundle["prompt_text"]
    assert "{approved_modifications}" not in bundle["prompt_text"]
    assert bundle["workflow_name"] == "bathroom_essential_v1"


def test_local_stub_builds_concept_png():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out, ctype, _used_board = build_local_stub_concept(
        png,
        room_type="bathroom",
        package_level="essential",
        modifications=["Wall-mounted grab bars"],
        width=512,
        height=512,
    )
    assert ctype == "image/png"
    assert out[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(out) > len(png)


def test_local_stub_provider_completes_without_gpu():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = LocalStubProvider().generate_image(
        AIImageJobPayload(
            ai_job_id="AIJ-TEST",
            assessment_id="ASM-1",
            room_type="bathroom",
            package_level="essential",
            original_image_url="/x",
            prompt="test",
            negative_prompt="",
            workflow="bathroom_essential_v1",
            model_name="stub",
            extra={
                "source_image_bytes": png,
                "modification_labels": ["Grab bar"],
            },
        )
    )
    assert result.status == "completed"
    assert result.is_stub is True
    assert result.generated_image_bytes
    assert result.generated_image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_create_visualization_job_local_stub(db, client, seed_tenant):
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath.png", BytesIO(png), "image/png")},
        data={
            "elder_id": str(elder_id),
            "assessment_id": "ASM-TEST-1",
            "caption": "Main bathroom",
            "room_type": "bathroom",
        },
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    res = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=headers,
        json={
            "assessment_id": "ASM-TEST-1",
            "room_type": "bathroom",
            "package_level": "essential",
            "source_document_id": doc_id,
            "approved_solution_ids": ["SH-TEST"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "needs_review"
    assert body["job"]["provider"] == "local_stub"
    assert body["job"]["generated_image_url"]
    assert body["job"]["generated_document_id"]
    assert body["job"]["prompt_text"]
    assert body["job"]["visualization_plan_id"]
    assert body["job"]["recommendation_set_id"]
    assert body["job"]["render_job_id"]
    assert body["job"]["current_phase"] in ("review", "needs_review", "render")
    assert body["job"]["phase_snapshot"]
    assert body["job"]["phase_snapshot"]["assessment"]["assessment_id"] == "ASM-TEST-1"
    assert body["job"]["phase_snapshot"]["analysis"]["status"] == "skipped"

    img = client.get(body["job"]["generated_image_url"], headers=headers)
    assert img.status_code == 200, img.text
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

    listed = client.get(
        "/api/v1/home-safety/ai/visualization-jobs?assessment_id=ASM-TEST-1",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_delete_photo_removes_ai_jobs(db, client, seed_tenant):
    """Deleting a source photo must succeed even when AI jobs reference it."""
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath-del.png", BytesIO(png), "image/png")},
        data={
            "elder_id": str(elder_id),
            "assessment_id": "ASM-DEL-1",
            "room_type": "bathroom",
        },
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    created = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=headers,
        json={
            "assessment_id": "ASM-DEL-1",
            "room_type": "bathroom",
            "package_level": "essential",
            "source_document_id": doc_id,
            "approved_solution_ids": [],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["job"]["generated_document_id"]

    deleted = client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"

    listed = client.get(
        "/api/v1/home-safety/ai/visualization-jobs?assessment_id=ASM-DEL-1",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []


def test_generate_for_photo_creates_three_tiers(db, client, seed_tenant):
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath2.png", BytesIO(png), "image/png")},
        data={"elder_id": str(elder_id), "assessment_id": "ASM-BATCH", "room_type": "bathroom"},
    )
    doc_id = upload.json()["id"]

    res = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/generate-for-photo",
        headers=headers,
        json={
            "assessment_id": "ASM-BATCH",
            "source_document_id": doc_id,
            "room_type": "bathroom",
            "approved_solution_ids": [],
        },
    )
    assert res.status_code == 200, res.text
    jobs = res.json()
    assert len(jobs) == 3
    levels = {j["package_level"] for j in jobs}
    assert levels == {"essential", "comfort", "premium"}
    assert all(j["status"] == "needs_review" for j in jobs)
    assert all(j["generated_image_url"] for j in jobs)


def test_generate_for_photo_replaces_duplicate_tier(db, client, seed_tenant):
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath3.png", BytesIO(png), "image/png")},
        data={"elder_id": str(elder_id), "assessment_id": "ASM-REPLACE", "room_type": "bathroom"},
    )
    doc_id = upload.json()["id"]
    payload = {
        "assessment_id": "ASM-REPLACE",
        "source_document_id": doc_id,
        "room_type": "bathroom",
        "approved_solution_ids": [],
    }

    first = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/generate-for-photo",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert len(first.json()) == 3

    second = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/generate-for-photo",
        headers=headers,
        json={**payload, "only_missing": True},
    )
    assert second.status_code == 200, second.text
    assert len(second.json()) == 0

    third = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/generate-for-photo",
        headers=headers,
        json={**payload, "tiers": ["essential"], "only_missing": False},
    )
    assert third.status_code == 200, third.text
    assert len(third.json()) == 1
    assert third.json()[0]["package_level"] == "essential"
    essential_id = next(
        j["ai_job_id"] for j in first.json() if j["package_level"] == "essential"
    )
    assert third.json()[0]["ai_job_id"] == essential_id

    forced = client.post(
        "/api/v1/home-safety/ai/visualization-jobs/generate-for-photo",
        headers=headers,
        json={
            **payload,
            "tiers": ["essential"],
            "only_missing": False,
            "force": True,
        },
    )
    assert forced.status_code == 200, forced.text
    assert len(forced.json()) == 1
    assert forced.json()[0]["cache_hit"] is False
    assert forced.json()[0]["ai_job_id"] != essential_id
    assert forced.json()[0]["status"] == "needs_review"

    listed = client.get(
        "/api/v1/home-safety/ai/visualization-jobs?assessment_id=ASM-REPLACE",
        headers=headers,
    )
    assert listed.status_code == 200
    jobs = listed.json()
    assert len(jobs) == 3
    levels = [j["package_level"] for j in jobs]
    assert sorted(levels) == ["comfort", "essential", "premium"]


def test_create_visualization_job_reuses_contract_e_cache(db, client, seed_tenant):
    admin = db.query(User).filter(User.email == "admin@test.example").first()
    elder_id = seed_tenant["elder"].id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = client.post(
        "/api/v1/home-safety/photos",
        headers=headers,
        files={"file": ("bath-cache.png", BytesIO(png), "image/png")},
        data={
            "elder_id": str(elder_id),
            "assessment_id": "ASM-CACHE-E",
            "room_type": "bathroom",
        },
    )
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]
    payload = {
        "assessment_id": "ASM-CACHE-E",
        "room_type": "bathroom",
        "package_level": "essential",
        "source_document_id": doc_id,
        "approved_solution_ids": ["SH-A", "SH-B"],
    }

    first = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["cache_hit"] is False
    job_id = first.json()["ai_job_id"]

    second = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=headers,
        json=payload,
    )
    assert second.status_code == 200, second.text
    assert second.json()["ai_job_id"] == job_id

    # Different solutions → cache miss
    third = client.post(
        "/api/v1/home-safety/ai/visualization-jobs",
        headers=headers,
        json={**payload, "approved_solution_ids": ["SH-A"]},
    )
    assert third.status_code == 200, third.text
    assert third.json()["cache_hit"] is False
    assert third.json()["ai_job_id"] != job_id

    # Regenerate always bypasses cache
    regen = client.post(
        f"/api/v1/home-safety/ai/visualization-jobs/{third.json()['ai_job_id']}/review",
        headers=headers,
        json={"action": "regenerate"},
    )
    assert regen.status_code == 200, regen.text
    assert regen.json()["cache_hit"] is False
    assert regen.json()["ai_job_id"] != third.json()["ai_job_id"]
    assert regen.json()["status"] == "needs_review"
