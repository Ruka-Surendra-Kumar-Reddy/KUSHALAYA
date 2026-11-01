"""scripts/purge_demo_alerts — duplicate device-offline alert cleanup."""

from scripts.purge_demo_alerts import dedupe_device_offline_alerts, purge_elder


def _alert(i, title="Wearable not heard — Lakshmi band", body="offline", incident_id=None, **extra):
    row = {
        "id": f"fal_{i}",
        "title": title,
        "body": body,
        "severity": "warning",
        "read_at": None,
        "created_at": f"2026-09-{10 + i:02d}T08:00:00+00:00",
    }
    if incident_id:
        row["incident_id"] = incident_id
    row.update(extra)
    return row


def test_dedupe_keeps_newest_of_each_duplicate_and_other_alerts():
    alerts = [
        _alert(5),  # newest duplicate — kept
        _alert(4, title="Message sent", body="hello"),  # unrelated — kept
        _alert(3),
        _alert(2, title="Possible fall from wearable", incident_id="dfall_1"),  # different kind — kept
        _alert(1),
        _alert(0, body="different body"),  # different pair — kept
    ]
    kept, removed = dedupe_device_offline_alerts(alerts, {"dfall_1": "possible_fall"})
    assert removed == 2
    assert [a["id"] for a in kept] == ["fal_5", "fal_4", "fal_2", "fal_0"]
    # Idempotent.
    kept2, removed2 = dedupe_device_offline_alerts(kept, {"dfall_1": "possible_fall"})
    assert removed2 == 0 and kept2 == kept


def test_incident_kind_identifies_offline_alert_with_custom_title():
    alerts = [
        _alert(2, title="Custom title", incident_id="doff_a"),
        _alert(1, title="Custom title", incident_id="doff_b"),
    ]
    kept, removed = dedupe_device_offline_alerts(alerts, {"doff_a": "device_offline", "doff_b": "device_offline"})
    assert removed == 1
    assert kept[0]["id"] == "fal_2"


def test_purge_elder_dry_run_then_apply(db, seed_tenant):
    from sqlalchemy.orm.attributes import flag_modified

    elder = seed_tenant["elder"]
    attrs = dict(elder.custom_attributes or {})
    attrs["safe_home"] = {"family_hub": {"alerts": [_alert(3), _alert(2), _alert(1)], "incidents": []}}
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()

    dry = purge_elder(db, elder, apply=False)
    assert dry["removed"] == 2 and dry["alerts_after"] == 1
    db.commit()
    db.refresh(elder)
    assert len(elder.custom_attributes["safe_home"]["family_hub"]["alerts"]) == 3

    applied = purge_elder(db, elder, apply=True)
    db.commit()
    db.refresh(elder)
    assert applied["removed"] == 2
    remaining = elder.custom_attributes["safe_home"]["family_hub"]["alerts"]
    assert [a["id"] for a in remaining] == ["fal_3"]

    again = purge_elder(db, elder, apply=True)
    assert again["removed"] == 0
