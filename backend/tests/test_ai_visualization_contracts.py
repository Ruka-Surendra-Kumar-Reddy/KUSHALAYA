"""AI visualization interface contracts A/B/D/E + local stub Contract E path."""

from datetime import datetime, timezone

from app.livewell.ai_contracts import (
    build_assessment_output,
    build_contract_bundle,
    build_recommendation_set,
    build_render_job_request,
    build_visualization_plan,
    map_room_type,
)
from app.livewell.ai_provider import LocalStubProvider, get_ai_provider
from app.schemas.ai_visualization_contracts import (
    ApprovalStatus,
    RoomType,
    VisualizationMode,
)


def test_map_room_type_aliases():
    assert map_room_type("bathroom") == RoomType.BATHROOM
    assert map_room_type("entry") == RoomType.ENTRANCE
    assert map_room_type("living") == RoomType.LIVING_ROOM


def test_contract_a_b_d_e_bundle():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    bundle = build_contract_bundle(
        assessment_id="KAA-2026-00125",
        elder_id="ELD-0081",
        assessor_id="USR-0182",
        room_type="bathroom",
        photo_id="PHOTO-001",
        download_url="https://signed.example/photo",
        approved_solution_ids=["SH-BATH-GRAB"],
        modification_labels=["Wall-mounted grab bars"],
        source_image_bytes=png,
        independence_score=62,
        domain_scores={"HOME_SAFETY": 48, "MOBILITY": 55},
        package_level="essential",
        prompt_text="test prompt",
        rule_config_version="2026.07.3",
        job_id="JOB-RENDER-5001",
    )
    assert bundle.assessment.independence_score == 62
    assert bundle.assessment.rooms[0].room_type == RoomType.BATHROOM
    assert bundle.recommendations.recommendation_set_id.startswith("RECSET-")
    assert bundle.plan.visualization_plan_id.startswith("VPLAN-")
    assert all(
        i.approval_status == ApprovalStatus.APPROVED_FOR_VISUALIZATION
        for i in bundle.plan.render_items
    )
    assert bundle.render_request is not None
    assert bundle.render_request.job_id == "JOB-RENDER-5001"
    assert bundle.render_request.render_items[0].operation == VisualizationMode.INSERT_OBJECT
    assert bundle.render_request.source_image.sha256


def test_plan_rejects_when_no_approved_items():
    assessment = build_assessment_output(
        assessment_id="A1",
        elder_id="E1",
        room_type="bathroom",
        photo_ids=["P1"],
        finding_codes=["NO_SHOWER_SUPPORT"],
    )
    recs = build_recommendation_set(
        assessment=assessment,
        approved_solution_ids=["X"],
    )
    plan = build_visualization_plan(
        assessment=assessment,
        recommendations=recs,
        source_photo_id="P1",
        auto_approve=False,
    )
    assert plan.approved_items() == []
    try:
        build_render_job_request(plan=plan, download_url="https://x")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "UNSAFE_OR_UNSUPPORTED_PLAN" in str(exc)


def test_local_stub_consumes_contract_e():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    bundle = build_contract_bundle(
        assessment_id="A1",
        elder_id=1,
        assessor_id=2,
        room_type="bathroom",
        photo_id="12",
        download_url="/api/v1/home-safety/photos/12/image",
        approved_solution_ids=["GRAB_BAR"],
        modification_labels=["Grab bar"],
        source_image_bytes=png,
        package_level="essential",
    )
    result = LocalStubProvider().submit_render(
        bundle.render_request,
        source_image_bytes=png,
    )
    assert result.status == "completed"
    assert result.is_stub is True
    assert result.render_accepted is not None
    assert result.render_accepted.status.value == "QUEUED"
    assert result.render_callback is not None
    assert result.render_callback.status.value == "SUCCEEDED"
    assert result.render_callback.outputs[0].candidate_id == "CAND-01"
    assert result.generated_image_bytes


def test_get_ai_provider_defaults_to_local_stub():
    assert get_ai_provider({}).name() == "local_stub"


def test_mock_gpu_contract_e_endpoint(db, client, seed_tenant):
    from app.models.user import User

    admin = db.query(User).filter(User.email == "admin@test.example").first()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    bundle = build_contract_bundle(
        assessment_id="A-GPU",
        elder_id=1,
        assessor_id=2,
        room_type="bathroom",
        photo_id="99",
        download_url="https://signed.example/x",
        approved_solution_ids=["GRAB"],
        modification_labels=["Grab bar"],
        package_level="essential",
        job_id="JOB-RENDER-API-1",
    )
    res = client.post(
        "/api/v1/home-safety/ai/gpu/v1/visualizations",
        headers={**headers, "Idempotency-Key": "idem-1"},
        json=bundle.render_request.model_dump(mode="json"),
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["job_id"] == "JOB-RENDER-API-1"
    assert body["status"] == "QUEUED"

    status = client.get(
        "/api/v1/home-safety/ai/gpu/v1/jobs/JOB-RENDER-API-1",
        headers=headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["result"]["status"] == "SUCCEEDED"

    # Idempotent replay returns original acceptance.
    again = client.post(
        "/api/v1/home-safety/ai/gpu/v1/visualizations",
        headers={**headers, "Idempotency-Key": "idem-1"},
        json=bundle.render_request.model_dump(mode="json"),
    )
    assert again.status_code == 202
    assert again.json()["job_id"] == "JOB-RENDER-API-1"

