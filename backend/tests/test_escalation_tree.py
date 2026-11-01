"""SOS escalation tree set from Settings: minutes per step and extra people."""

from app.livewell import incident_service as inc


def _admin(client):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_escalation_tree_round_trip(client, db, seed_tenant):
    admin = _admin(client)
    tree = client.get("/api/v1/team/escalation", headers=admin).json()
    assert tree["ack_minutes"] == 5 and tree["level2_emails"] == []

    res = client.put("/api/v1/team/escalation", headers=admin, json={
        "ack_minutes": 3, "level2_minutes": 8, "level3_minutes": 15,
        "level1_phones": ["98765 43210"], "level2_emails": ["owner@kushalaya.example", "junk"],
        "level2_phones": ["+44 7700 900123", "12"],
    })
    assert res.status_code == 200, res.text
    tree = res.json()
    assert (tree["ack_minutes"], tree["level2_minutes"], tree["level3_minutes"]) == (3, 8, 15)
    assert tree["level1_phones"] == ["+919876543210"]
    assert tree["level2_emails"] == ["owner@kushalaya.example"]
    assert tree["level2_phones"] == ["+447700900123"]
    tid = seed_tenant["tenant"].id
    assert inc.escalation_policy(db, tid)["ack_minutes"] == 3
    assert inc.escalation_contacts(db, tid)["level2_emails"] == ["owner@kushalaya.example"]
