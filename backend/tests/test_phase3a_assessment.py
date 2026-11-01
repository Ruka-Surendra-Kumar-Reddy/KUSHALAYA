"""Phase 3A: hidden / visit questions, score history and critical findings for families."""

from unittest.mock import patch

from app.livewell import scoring
from app.livewell.family_publish import publish_assessment_to_family
from app.livewell.rubric_service import normalize_rubric

RUBRIC = [
    {
        "id": "bath",
        "title": "Bathroom",
        "sectionNumber": 1,
        "items": [
            {"id": "b1", "label": "Grab bar by the toilet", "maxPoints": 10, "scoringScale": "critical"},
            {"id": "b2", "label": "Old mat question", "maxPoints": 10, "hidden": True},
            {"id": "b3", "label": "Night light", "maxPoints": 10, "visitQuestion": True},
        ],
    }
]


def test_normalize_keeps_hidden_and_visit_flags_and_order():
    out = normalize_rubric(RUBRIC)["categories"][0]["items"]
    assert [i["id"] for i in out] == ["b1", "b2", "b3"]
    assert out[1]["hidden"] is True
    assert out[2]["visitQuestion"] is True
    assert "hidden" not in out[0] and "visitQuestion" not in out[0]
    # Help text survives a save.
    saved = normalize_rubric([{**RUBRIC[0], "items": [{"id": "x", "label": "Q", "help": "Look under the sink"}]}])
    assert saved["categories"][0]["items"][0]["help"] == "Look under the sink"


def test_hidden_unanswered_is_left_out_of_the_score():
    cats = normalize_rubric(RUBRIC)["categories"]
    # New assessment: b2 hidden and not asked -> denominator is b1 + b3 only.
    res = scoring.score_assessment({"ratings": {"b1": "excellent", "b3": "excellent"}}, cats)
    assert res["independence_score"] == 100
    assert res["max"] == 20


def test_hidden_question_still_counts_on_old_assessment():
    cats = normalize_rubric(RUBRIC)["categories"]
    res = scoring.score_assessment({"ratings": {"b1": "excellent", "b2": "unsafe", "b3": "excellent"}}, cats)
    assert res["max"] == 30
    assert res["independence_score"] == 67


def test_caregiver_questions_skip_hidden_unless_answered(db, seed_tenant):
    from app.livewell.field_assessment import _questions
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, seed_tenant["elder"].tenant_id)
    with patch("app.livewell.field_assessment.effective_rubric", return_value=(normalize_rubric(RUBRIC)["categories"], "tenant")):
        fresh = [i["id"] for c in _questions(db, tenant.id) for i in c["items"]]
        old = [i["id"] for c in _questions(db, tenant.id, {"b2": "unsafe"}) for i in c["items"]]
        visit = {i["id"]: i["visit_question"] for c in _questions(db, tenant.id) for i in c["items"]}
    assert fresh == ["b1", "b3"]
    assert old == ["b1", "b2", "b3"]
    assert visit == {"b1": False, "b3": True}


def _payload(aid: str, elder_id: int, score: int, critical: list[dict]) -> dict:
    return {
        "id": aid,
        "status": "completed",
        "completedAt": "2026-10-01T10:00:00+00:00",
        "ratings": {},
        "residentProfile": {},
        "elderId": elder_id,
        "independenceScore": score,
        "criticalFindings": critical,
    }


def test_critical_findings_notify_family_once_and_history_kept(db, seed_tenant):
    elder = seed_tenant["elder"]
    crit = [{"id": "b1", "label": "Grab bar by the toilet", "category": "Bathroom"}]
    with patch("app.livewell.family_notify.notify_family") as notify:
        publish_assessment_to_family(db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=_payload("p3a-1", elder.id, 55, crit))
        # Re-publishing the same assessment does not send it again.
        publish_assessment_to_family(db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=_payload("p3a-1", elder.id, 55, crit))
        # A later assessment without critical findings sends nothing.
        publish_assessment_to_family(db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=_payload("p3a-2", elder.id, 81, []))
    db.commit()
    assert notify.call_count == 1
    args, kwargs = notify.call_args
    assert args[2] == "Urgent safety fixes found"
    assert "Grab bar by the toilet" in args[3]
    assert kwargs["event"] == "safety"

    db.refresh(elder)
    hist = elder.custom_attributes["safe_home"]["score_history"]
    assert [h["total"] for h in hist][-2:] == [55, 81]


def test_critical_notice_reaches_family_alerts(db, seed_tenant):
    elder = seed_tenant["elder"]
    crit = [{"id": "b1", "label": "Grab bar by the toilet", "category": "Bathroom"}]
    publish_assessment_to_family(db, elder_id=elder.id, tenant_id=elder.tenant_id, payload=_payload("p3a-3", elder.id, 50, crit))
    db.commit()
    db.refresh(elder)
    from app.livewell.family_care_hub import _hub

    titles = [a["title"] for a in _hub(elder)["alerts"]]
    assert "Urgent safety fixes found" in titles


def test_finding_problem_wording():
    from app.livewell.family_alert_text import finding_problem

    assert finding_problem("Toilet grab bar installed") == "No toilet grab bar"
    assert finding_problem("Night lights fitted") == "No night lights"
    assert finding_problem("SOS button available") == "No SOS button"
    assert finding_problem("Pathway level and clear") == "Uneven or cluttered pathway"
    assert finding_problem("Bed transfer support") == "Hard to get in and out of bed"
    assert finding_problem("Grab bar") == "Grab bar — needs fixing"
