"""The backend and frontend plan catalogs must agree: ids, prices (paise) and visits."""

import re
from pathlib import Path

from app.livewell import care_plan_catalog as catalog

TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "care-plan-catalog.ts"


def _num(text: str) -> int | None:
    text = text.strip()
    return None if text == "null" else int(text.replace("_", ""))


def _ts_plans() -> list[dict]:
    src = TS.read_text(encoding="utf-8")
    body = src.split("CARE_PLAN_CATALOG", 1)[1]
    out = []
    for m in re.finditer(
        r'id:\s*"([^"]+)".*?annualPaise:\s*([\d_]+).*?monthlyPaise:\s*([\d_]+|null).*?visitsPerYear:\s*(\d+)',
        body,
        re.S,
    ):
        out.append({"id": m[1], "annual_paise": _num(m[2]), "monthly_paise": _num(m[3]), "visits_per_year": int(m[4])})
    return out


def test_frontend_and_backend_catalogs_match():
    ts = _ts_plans()
    py = [{k: p[k] for k in ("id", "annual_paise", "monthly_paise", "visits_per_year")} for p in catalog.PLANS]
    assert len(ts) == 4
    assert ts == py


def test_single_visit_and_assessment_match():
    src = TS.read_text(encoding="utf-8")
    single = re.search(
        r"SINGLE_VISIT = \{.*?pricePaise:\s*([\d_]+),\s*registrationPaise:\s*([\d_]+),\s*hours:\s*(\d+)", src, re.S
    )
    assessment = re.search(r"HOME_ASSESSMENT = \{.*?pricePaise:\s*([\d_]+)", src, re.S)
    assert _num(single[1]) == catalog.SINGLE_VISIT["price_paise"] == 340_000
    assert _num(single[2]) == catalog.SINGLE_VISIT["registration_paise"] == 10_000
    assert int(single[3]) == catalog.SINGLE_VISIT["hours"]
    assert _num(assessment[1]) == catalog.HOME_ASSESSMENT["price_paise"] == 0


def test_every_plan_includes_match():
    src = TS.read_text(encoding="utf-8")
    block = src.split("EVERY_PLAN_INCLUDES", 1)[1].split("];", 1)[0]
    ts = re.findall(r'^\s*"([^"]*)",?\s*$', block, re.M)
    assert ts == catalog.EVERY_PLAN_INCLUDES and len(ts) > 5


def test_plan_inclusions_match():
    src = TS.read_text(encoding="utf-8").split("CARE_PLAN_CATALOG", 1)[1].split("EVERY_PLAN_INCLUDES", 1)[0]
    blocks = re.findall(r"inclusions:\s*\[(.*?)\]", src, re.S)
    ts = [re.findall(r'"([^"]*)"', b) for b in blocks]
    assert ts == [p["inclusions"] for p in catalog.PLANS]


def test_prices_are_integer_paise():
    for p in catalog.PLANS:
        assert isinstance(p["annual_paise"], int)
        assert p["monthly_paise"] is None or isinstance(p["monthly_paise"], int)
