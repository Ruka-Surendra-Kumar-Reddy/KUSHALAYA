"""Round-5 family audit: one urgent list, noted changes on visit lines, one status word."""

from types import SimpleNamespace

from app.livewell import kushlife
from app.livewell.family_service import _critical_findings, align_plan_urgency
from app.livewell.family_status import build_family_status, status_words

LINKS = {
    "LW-HS-BTH-001": {"id": "LW-HS-BTH-001", "finding": "Unsafe toilet transfer", "rubricItemIds": ["toilet_bar"]},
    "LW-HS-BTH-002": {"id": "LW-HS-BTH-002", "finding": "Unsafe shower entry", "rubricItemIds": ["shower_bar"]},
    "LW-HS-ENT-001": {
        "id": "LW-HS-ENT-001",
        "finding": "Uneven walkway",
        "rubricItemIds": ["pathway"],
        "riskDescription": "Make the path level.",
        "recommendedSolutions": ["Level the path"],
        "scoreImprovement": 4,
    },
}


def _item(id_, priority):
    return {"id": id_, "title": id_, "priority": priority, "actions": [], "score_gain": 5, "status": "open"}


def test_plan_urgent_is_the_critical_findings():
    items = [_item("LW-HS-BTH-002", "critical"), _item("LW-HS-BTH-001", "high")]
    critical = [
        {"id": "toilet_bar", "label": "Toilet grab bar installed", "area": "Home Safety"},
        {"id": "pathway", "label": "Pathway level and clear", "area": "Home Safety"},
        {"id": "rugs", "label": "Loose rugs secured or removed", "area": "Home Safety"},
    ]
    out = align_plan_urgency(items, critical, LINKS)
    by_id = {r["id"]: r for r in out}
    # Fixes a critical finding -> Urgent; "critical" in the library but no critical finding -> Important.
    assert by_id["LW-HS-BTH-001"]["priority"] == "critical"
    assert by_id["LW-HS-BTH-002"]["priority"] == "high"
    # Uncovered critical findings get their own plan items (from the library, else the label).
    assert by_id["LW-HS-ENT-001"]["priority"] == "critical"
    assert by_id["LW-HS-ENT-001"]["actions"] == ["Level the path"]
    assert by_id["finding-rugs"]["title"] == "Loose rugs secured or removed"
    assert sum(1 for r in out if r["priority"] == "critical") == len(critical)
    assert [r["priority"] for r in out][:3] == ["critical"] * 3


def test_critical_findings_only_when_capped():
    score = {"capped_by_critical_item": True, "critical_findings": [{"id": "a", "label": "X installed", "category": "1. Home Safety"}]}
    assert _critical_findings(score) == [{"id": "a", "label": "X installed", "area": "Home Safety"}]
    assert _critical_findings({**score, "capped_by_critical_item": False}) == []


def test_record_changes_match_the_status_words():
    rec = {
        "checks": {k: {"status": "ok", "chips": [], "note": ""} for k in kushlife.CHECKS},
        "sleep": "poorly",
        "appetite": "less",
    }
    assert kushlife.record_changes(rec) == ["Slept poorly", "Ate less"]
    assert kushlife.noted_text(kushlife.record_changes(rec)) == "slept poorly, ate less"
    assert kushlife.record_changes(None) == []


def test_visit_summary_says_what_was_noted():
    from app.livewell.care_jobs import _family_summary

    rec = {"checks": {k: {"status": "ok", "chips": [], "note": ""} for k in kushlife.CHECKS}, "sleep": "poorly"}
    job = SimpleNamespace(report={"checks": {k: "ok" for k in kushlife.CHECKS}, "kushlife": rec}, tasks="")
    assert _family_summary(job).endswith("· noted: slept poorly")
    job.report["kushlife"] = {**rec, "sleep": None}
    assert "noted" not in _family_summary(job)


def test_one_status_word():
    assert status_words("Small changes noted") == "Well · small changes noted"
    assert status_words("All good") == "Well"
    assert status_words("Watching closely") == "Watching closely"
    s = build_family_status(
        word="Small changes noted",
        level=None,
        checks={"safe": "ok"},
        changes=["Slept poorly"],
        last_visit_at=None,
        mobility_sheet=None,
        mobility_checkin=None,
    )
    assert s["status_text"] == "Well · small changes noted"
