from datetime import datetime, timezone

from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.dashboard_service import HomeSafetyDashboardService


def test_ops_summary_counts_clients_assessments_visits_catalog(db, seed_tenant):
    admin = seed_tenant["admin"]
    elder = seed_tenant["elder"]

    HomeSafetyAssessmentService.upsert_assessment(
        db,
        admin,
        {
            "id": "hs-dash-draft",
            "status": "draft",
            "clientFirstName": "A",
            "clientLastName": "B",
            "ratings": {},
            "itemNotes": {},
            "photos": [],
        },
    )
    HomeSafetyAssessmentService.upsert_assessment(
        db,
        admin,
        {
            "id": "hs-dash-done",
            "status": "completed",
            "completedAt": "2026-06-25T13:00:00+00:00",
            "clientFirstName": "C",
            "clientLastName": "D",
            "ratings": {},
            "itemNotes": {},
            "photos": [],
        },
    )

    today = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    elder.custom_attributes = {
        **(elder.custom_attributes or {}),
        "safe_home": {
            "visits": [
                {"id": "v-today", "visited_at": today, "visit_type": "Wellness visit"},
                {
                    "id": "v-old",
                    "visited_at": "2026-01-01T12:00:00+00:00",
                    "visit_type": "Wellness visit",
                },
            ]
        },
    }
    db.add(elder)
    db.commit()

    summary = HomeSafetyDashboardService.summary(db, admin)
    assert summary["clients"] >= 1
    assert summary["assessments_open"] >= 1
    assert summary["assessments_total"] >= 2
    assert summary["visits_today"] >= 1
    assert summary["visits_total"] >= 2
    assert summary["catalog_items"] >= 0
