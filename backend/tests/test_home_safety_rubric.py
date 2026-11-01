from app.livewell.rubric import SAFETY_CATEGORIES, safety_grade, total_score


def test_full_pass_scores_100():
    ratings = {
        item["id"]: "pass"
        for cat in SAFETY_CATEGORIES
        for item in cat["items"]
    }
    assert total_score(ratings) == 100
    assert safety_grade(100)["grade"] == "Platinum"


def test_fail_grade():
    assert safety_grade(55)["grade"] == "Red"
