"""KushAlaya care plans — the one source of truth (owner's pricing sheet, 27 Oct 2026).

Prices include GST and are integer paise. Paying monthly costs more than the
annual price on purpose; monthly billing is offered on every plan. Keep in step with
frontend/lib/care-plan-catalog.ts (tests check they match).
"""

from __future__ import annotations

PLANS: list[dict] = [
    {
        "id": "assurance",
        "name": "KushAlaya Assurance",
        "tag": "Annual plan",
        "annual_paise": 55_000_00,
        "monthly_paise": 6_000_00,
        "visits_per_year": 8,
        "summary": "Ideal for emergency support only",
        "inclusions": [
            "8 care-manager visits a year",
        ],
    },
    {
        "id": "total-care",
        "name": "KushAlaya Total Care",
        "tag": "Annual plan",
        "annual_paise": 95_000_00,
        "monthly_paise": 9_900_00,
        "visits_per_year": 30,
        "summary": "Baseline protection",
        "inclusions": [
            "30 care-manager visits a year",
        ],
    },
    {
        "id": "privilege",
        "name": "KushAlaya Privilege",
        "tag": "Most popular",
        "annual_paise": 1_25_000_00,
        "monthly_paise": 13_500_00,
        "visits_per_year": 50,
        "summary": "Ongoing partnership",
        "popular": True,
        "inclusions": [
            "50 care-manager visits a year (about 1 a week)",
            "Complimentary SOS watch with family alerts",
        ],
    },
    {
        "id": "signature",
        "name": "KushAlaya Signature",
        "tag": "Premium",
        "annual_paise": 1_60_000_00,
        "monthly_paise": 17_500_00,
        "visits_per_year": 70,
        "summary": "Ultra high-touch",
        "inclusions": [
            "70 care-manager visits a year",
            "Complimentary SOS watch with family alerts",
            "Privilege kit: BP monitor, glucose meter, pulse oximeter",
            "Weekly BP, glucose, pulse and SpO2 tracking",
        ],
    },
]

# What every annual plan includes; each plan's "inclusions" are only what differs.
EVERY_PLAN_INCLUDES: list[str] = [
    "Care-manager visits — the number depends on the plan",
    "Emergency visits always free — never counted against your visits",
    "Emergency coordination",
    "Free KushAlaya assessment with any annual plan",
    "Family portal: visit reports with photos, message your care manager, rapid family alerts, live care-manager location, WhatsApp digest",
    "Doctor and errand accompaniment",
    "Utilities, groceries and repairs coordination",
    "Partner services coordinated by us: home caregivers, physiotherapy, nursing and recovery support",
    "Personalised recommendations and request follow-ups",
    "Digital health and service records",
    "Regular family care summaries",
]

# Pay as you go (no subscription): a 4-hour priority visit plus a one-time registration.
SINGLE_VISIT = {"id": "single-visit", "name": "Single priority visit", "price_paise": 3_400_00, "registration_paise": 100_00, "hours": 4}
# KushCare Discovery home assessment: free (owner, 27 Oct 2026). The ₹100
# registration applies only to SINGLE_VISIT.
HOME_ASSESSMENT = {"id": "home-assessment", "name": "KushCare Discovery home assessment", "price_paise": 0}

BILLING_CYCLES = ("yearly", "monthly")


def plan(plan_id: str) -> dict | None:
    return next((p for p in PLANS if p["id"] == plan_id), None)


def price_paise(plan_id: str, cycle: str) -> int | None:
    """Price for one billing period, or None when that cycle isn't offered."""
    p = plan(plan_id)
    if p is None or cycle not in BILLING_CYCLES:
        return None
    return p["annual_paise"] if cycle == "yearly" else p["monthly_paise"]
