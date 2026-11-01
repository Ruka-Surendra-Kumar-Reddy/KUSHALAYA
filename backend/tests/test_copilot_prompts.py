from app.core.copilot_prompts import PACKS, get_copilot_pack
from app.core.verticals import ELDER_CARE, HOUSEKEEPING, LIVEWELL360, DEFAULT_VERTICAL


def test_elder_care_pack_mentions_vertical():
    pack = get_copilot_pack(ELDER_CARE)
    assert "Elder Care" in pack.system_prompt
    assert pack.suggested_questions
    assert pack.executive_questions
    assert "bench" in " ".join(pack.executive_questions).lower()


def test_housekeeping_uses_generic_pack():
    pack = get_copilot_pack(HOUSEKEEPING)
    assert pack.system_prompt == PACKS["HOUSEKEEPING"].system_prompt
    assert len(pack.suggested_questions) >= 4


def test_unknown_vertical_falls_back_to_default():
    pack = get_copilot_pack("NOT_A_VERTICAL")
    assert pack == PACKS[DEFAULT_VERTICAL] or pack.system_prompt == PACKS[DEFAULT_VERTICAL].system_prompt


def test_livewell_falls_back_or_has_pack():
    pack = get_copilot_pack(LIVEWELL360)
    assert pack.suggested_questions
    assert pack.executive_questions
