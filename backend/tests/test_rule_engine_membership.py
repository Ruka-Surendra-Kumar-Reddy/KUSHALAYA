"""Multi-factor membership decision table."""

from app.livewell.rule_engine_defaults import recommend_membership, risk_band_for_score


def test_high_score_alone_with_mild_cognitive_is_assisted():
    assert (
        recommend_membership(
            independence_score=88,
            lives_alone=True,
            cognitive_risk="mild",
        )
        == "mbr_assisted"
    )


def test_high_score_without_clinical_flags_is_independent():
    assert (
        recommend_membership(
            independence_score=88,
            lives_alone=False,
            family_abroad=False,
            cognitive_risk=None,
        )
        == "mbr_independent"
    )


def test_family_abroad_wins_nri():
    assert (
        recommend_membership(
            independence_score=88,
            family_abroad=True,
            lives_alone=True,
            cognitive_risk="mild",
        )
        == "mbr_nri"
    )


def test_risk_band_critical():
    band = risk_band_for_score(35)
    assert band["band"] == "critical"
