"""Checkr webhook updates US workforce compliance."""

from app.models.us_workforce_compliance import USWorkforceCompliance


def test_checkr_webhook_updates_compliance(db, client, seed_tenant):
    caregiver_id = seed_tenant["caregiver"].id
    tenant_id = seed_tenant["tenant"].id

    row = USWorkforceCompliance(
        caregiver_id=caregiver_id,
        tenant_id=tenant_id,
        background_check_status="PENDING",
        background_check_provider_ref="cand_test_abc123",
    )
    db.add(row)
    db.commit()

    res = client.post(
        "/api/v1/webhooks/checkr",
        json={
            "type": "report.completed",
            "data": {
                "object": {
                    "id": "cand_test_abc123",
                    "status": "clear",
                }
            },
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated"] is True
    assert body["background_check_status"] == "VERIFIED"

    db.refresh(row)
    assert row.background_check_status == "VERIFIED"
