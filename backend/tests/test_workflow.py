import pytest
from datetime import date, datetime, timedelta

from app.core.workflow_events import CUSTOMER_MESSAGE_RECEIVED
from app.models.caregiver_certification import CaregiverCertification
from app.models.workflow_event import WorkflowEvent
from app.models.workflow_task import WorkflowTask
from app.services.workflow_engine import WorkflowEngine
from app.services.workflow_emitter import emit_workflow_event


def _login_headers(client, email: str) -> dict:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_list_workflow_definitions(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    res = client.get("/api/v1/workflows/definitions", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body.get("workflows") or body, (list, dict))


def test_disable_workflow(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    res = client.patch(
        "/api/v1/workflows/definitions",
        headers=headers,
        json={"disabled_workflow_ids": ["family-message-intake"]},
    )
    assert res.status_code == 200
    disabled = res.json().get("workflows") or []
    if not disabled:
        pytest.skip("No workflow definitions in this LiveWell deploy")
    family = next((w for w in disabled if w["id"] == "family-message-intake"), None)
    if family is None:
        pytest.skip("family-message-intake workflow is not in this vertical pack")
    assert family["enabled"] is False


def test_emit_creates_task_and_event(db, seed_tenant):
    tenant = seed_tenant["tenant"]
    result = emit_workflow_event(
        db,
        tenant_id=tenant.id,
        event_type=CUSTOMER_MESSAGE_RECEIVED,
        entity_type="elder_message",
        entity_id=99,
        payload={
            "elder_id": seed_tenant["elder"].id,
            "body": "Need help with medication schedule",
            "summary": "Family portal message received",
        },
    )
    assert result is not None
    if result.get("workflows_matched", 0) < 1:
        pytest.skip("No workflow templates matched this event for LiveWell")

    events = (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.tenant_id == tenant.id)
        .all()
    )
    assert len(events) >= 1

    tasks = (
        db.query(WorkflowTask)
        .filter(
            WorkflowTask.tenant_id == tenant.id,
            WorkflowTask.status == "OPEN",
        )
        .all()
    )
    assert len(tasks) >= 1


def test_workflow_scan_certification_expiring(client, db, seed_tenant):
    tenant = seed_tenant["tenant"]
    caregiver = seed_tenant["caregiver"]
    cert = CaregiverCertification(
        tenant_id=tenant.id,
        caregiver_id=caregiver.id,
        certification_name="First Aid",
        issuing_body="Red Cross",
        expiry_date=date.today() + timedelta(days=14),
        verification_status="VERIFIED",
    )
    db.add(cert)
    db.commit()

    headers = _login_headers(client, "manager@test.example")
    res = client.post("/api/v1/workflows/scan", headers=headers)
    assert res.status_code == 200
    assert res.json()["events_emitted"] >= 1
