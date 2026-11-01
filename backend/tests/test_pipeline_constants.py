from app.core.pipeline_constants import (
    ACTIVITY_CALL,
    ACTIVITY_EMAIL,
    ACTIVITY_FOLLOW_UP,
    ACTIVITY_NOTE,
    ACTIVITY_OWNER_CHANGE,
    ACTIVITY_STAGE_CHANGE,
    ACTIVITY_VISIT,
    CAREGIVER_PROSPECT_STAGES,
    ELDER_PROSPECT_STAGES,
    PROSPECT_STATUS_LOST,
    PROSPECT_STATUS_OPEN,
    PROSPECT_STATUS_WON,
)


def test_elder_prospect_funnel_order():
    assert ELDER_PROSPECT_STAGES[0] == "NEW"
    assert ELDER_PROSPECT_STAGES[-2] == "WON"
    assert ELDER_PROSPECT_STAGES[-1] == "LOST"
    assert "ASSESSMENT_DONE" in ELDER_PROSPECT_STAGES
    assert "PROPOSAL_SENT" in ELDER_PROSPECT_STAGES


def test_caregiver_prospect_funnel_order():
    assert CAREGIVER_PROSPECT_STAGES[0] == "APPLIED"
    assert "HIRED" in CAREGIVER_PROSPECT_STAGES
    assert "REJECTED" in CAREGIVER_PROSPECT_STAGES
    assert "VERIFICATION" in CAREGIVER_PROSPECT_STAGES


def test_prospect_status_constants():
    assert {PROSPECT_STATUS_OPEN, PROSPECT_STATUS_WON, PROSPECT_STATUS_LOST} == {
        "OPEN",
        "WON",
        "LOST",
    }


def test_activity_types_are_unique():
    types = [
        ACTIVITY_NOTE,
        ACTIVITY_CALL,
        ACTIVITY_EMAIL,
        ACTIVITY_VISIT,
        ACTIVITY_STAGE_CHANGE,
        ACTIVITY_FOLLOW_UP,
        ACTIVITY_OWNER_CHANGE,
    ]
    assert len(types) == len(set(types))
