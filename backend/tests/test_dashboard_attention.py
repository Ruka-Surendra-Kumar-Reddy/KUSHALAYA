"""Dashboard attention feed: requests, messages, alerts, today's visits — team scoped."""

from datetime import datetime, timezone

from app.models.elder import Elder


def test_attention_lists_open_requests_and_today(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    now = datetime.now(timezone.utc).isoformat()
    elder.custom_attributes = {
        **(elder.custom_attributes or {}),
        "safe_home": {
            "service_requests": [
                {"id": "r1", "service_type": "nurse_pt", "status": "requested", "notes": "Physio", "created_at": now},
                {"id": "r2", "service_type": "home_repair", "status": "done", "created_at": now},
            ],
            "visits": [{"id": "v1", "visit_type": "Wellness visit", "visited_at": now, "status": "scheduled"}],
        },
    }
    outside = Elder(
        tenant_id=elder.tenant_id,
        first_name="Not",
        last_name="Mine",
        status="ACTIVE",
        custom_attributes={"safe_home": {"service_requests": [{"id": "x", "status": "requested"}]}},
    )
    db.add(outside)
    db.commit()

    res = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [r["id"] for r in body["requests"]] == ["r1"]  # manager: own team only, open only
    assert [v["id"] for v in body["today"]] == ["v1"]
    assert body["counts"]["open_requests"] == 1
