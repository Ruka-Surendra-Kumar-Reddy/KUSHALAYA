"""LiveWell360 rule-engine tables (spreadsheet sheets 19–28).

Stored under tenant workflow_config key livewell_rule_engine after Master Data approve.
Decision-table evaluators use these lists when present; otherwise fall back to defaults below.
"""

from __future__ import annotations

from typing import Any

# Severity / risk ordinals for multi-factor matching (blank rule = ignore).
_RISK_RANK = {
    "": 0,
    "none": 0,
    "no": 0,
    "low": 1,
    "mild": 1,
    "yes": 1,
    "moderate": 2,
    "med": 2,
    "medium": 2,
    "high": 3,
    "severe": 3,
    "critical": 4,
}


def _rank(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    return _RISK_RANK.get(str(value).strip().lower(), 0)


def risk_meets_minimum(actual: Any, required: Any) -> bool:
    """True if rule has no required level, or actual rank >= required rank."""
    if required is None or str(required).strip() == "":
        return True
    return _rank(actual) >= _rank(required)


# ---------------------------------------------------------------------------
# 19_MembershipRules — score + family + clinical complexity
# ---------------------------------------------------------------------------
DEFAULT_MEMBERSHIP_RULES: list[dict] = [
    {
        "id": "mbr_rule_nri",
        "min_independence_score": 0,
        "max_independence_score": 100,
        "lives_alone": None,
        "family_abroad": True,
        "mobility_risk": None,
        "cognitive_risk": None,
        "health_complexity": None,
        "recommended_membership_id": "mbr_nri",
        "priority": 5,
    },
    {
        "id": "mbr_rule_alone_cognitive",
        "min_independence_score": 0,
        "max_independence_score": 100,
        "lives_alone": True,
        "family_abroad": None,
        "mobility_risk": None,
        "cognitive_risk": "mild",
        "health_complexity": None,
        "recommended_membership_id": "mbr_assisted",
        "priority": 6,
        "notes": "High Independence Score but lives alone + cognitive risk → not Independent",
    },
    {
        "id": "mbr_rule_cognitive_moderate",
        "min_independence_score": 0,
        "max_independence_score": 100,
        "lives_alone": None,
        "family_abroad": None,
        "mobility_risk": None,
        "cognitive_risk": "moderate",
        "health_complexity": None,
        "recommended_membership_id": "mbr_assisted",
        "priority": 7,
    },
    {
        "id": "mbr_rule_critical",
        "min_independence_score": 0,
        "max_independence_score": 39,
        "lives_alone": None,
        "family_abroad": False,
        "mobility_risk": None,
        "cognitive_risk": None,
        "health_complexity": None,
        "recommended_membership_id": "mbr_premium",
        "priority": 8,
    },
    {
        "id": "mbr_rule_independent",
        "min_independence_score": 75,
        "max_independence_score": 100,
        "lives_alone": None,
        "family_abroad": False,
        "mobility_risk": None,
        "cognitive_risk": "none",
        "health_complexity": None,
        "recommended_membership_id": "mbr_independent",
        "priority": 10,
    },
    {
        "id": "mbr_rule_assisted",
        "min_independence_score": 60,
        "max_independence_score": 74,
        "lives_alone": None,
        "family_abroad": None,
        "mobility_risk": None,
        "cognitive_risk": None,
        "health_complexity": None,
        "recommended_membership_id": "mbr_assisted",
        "priority": 20,
    },
    {
        "id": "mbr_rule_premium",
        "min_independence_score": 0,
        "max_independence_score": 59,
        "lives_alone": None,
        "family_abroad": None,
        "mobility_risk": None,
        "cognitive_risk": None,
        "health_complexity": None,
        "recommended_membership_id": "mbr_premium",
        "priority": 30,
    },
]

# ---------------------------------------------------------------------------
# 20_EcmRules
# ---------------------------------------------------------------------------
DEFAULT_ECM_RULES: list[dict] = [
    {
        "id": "ecm_critical_score",
        "condition": "independence_score < 40",
        "assignment_required": True,
        "visit_frequency": "twice_weekly",
        "escalation_level": "critical",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_low_score",
        "condition": "independence_score < 60",
        "assignment_required": True,
        "visit_frequency": "weekly",
        "escalation_level": "high",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_lives_alone_moderate",
        "condition": "lives_alone == true AND independence_score < 75",
        "assignment_required": True,
        "visit_frequency": "biweekly",
        "escalation_level": "medium",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_nri",
        "condition": "family_abroad == true",
        "assignment_required": True,
        "visit_frequency": "weekly",
        "escalation_level": "high",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_family_preference",
        "condition": "family_requests_ecm == true",
        "assignment_required": True,
        "visit_frequency": "as_agreed",
        "escalation_level": "medium",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_cognitive",
        "condition": "cognitive_risk >= mild",
        "assignment_required": True,
        "visit_frequency": "weekly",
        "escalation_level": "high",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_repeat_emergency",
        "condition": "emergency_calls_90d >= 2",
        "assignment_required": True,
        "visit_frequency": "weekly",
        "escalation_level": "high",
        "action": "assign_ecm",
    },
    {
        "id": "ecm_home_deterioration",
        "condition": "home_condition_drop > 15",
        "assignment_required": True,
        "visit_frequency": "biweekly",
        "escalation_level": "medium",
        "action": "schedule_reassessment",
    },
    {
        "id": "ecm_family_inactive",
        "condition": "family_contact_days > 90",
        "assignment_required": True,
        "visit_frequency": "monthly",
        "escalation_level": "medium",
        "action": "ecm_monthly_call",
    },
    {
        "id": "ecm_missed_visit",
        "condition": "missed_wellness_visit == true",
        "assignment_required": True,
        "visit_frequency": "as_scheduled",
        "escalation_level": "medium",
        "action": "reschedule_within_48h",
    },
]

# ---------------------------------------------------------------------------
# 21_AssessmentFindings — starter catalog (grow by domain)
# ---------------------------------------------------------------------------
DEFAULT_ASSESSMENT_FINDINGS: list[dict] = [
    {"id": "fnd_bath_no_grab_bar", "domain": "Bathroom", "question_id": "home_safety_toilet_grab_bar_installed", "answer": "unsafe", "severity": "high", "label": "Missing grab bar"},
    {"id": "fnd_bath_poor_lighting", "domain": "Bathroom", "question_id": "", "answer": "", "severity": "medium", "label": "Poor bathroom lighting"},
    {"id": "fnd_bath_slippery", "domain": "Bathroom", "question_id": "home_safety_anti_slip_flooring", "answer": "unsafe", "severity": "high", "label": "Slippery floor"},
    {"id": "fnd_bath_high_step", "domain": "Bathroom", "question_id": "", "answer": "", "severity": "high", "label": "High shower step"},
    {"id": "fnd_bath_toilet_height", "domain": "Bathroom", "question_id": "home_safety_toilet_height_appropriate", "answer": "unsafe", "severity": "medium", "label": "Unsafe toilet height"},
    {"id": "fnd_bath_no_pull_cord", "domain": "Bathroom", "question_id": "", "answer": "", "severity": "high", "label": "No emergency pull cord"},
    {"id": "fnd_bath_loose_mat", "domain": "Bathroom", "question_id": "", "answer": "", "severity": "medium", "label": "Loose bath mat"},
    {"id": "fnd_bath_scald", "domain": "Bathroom", "question_id": "home_safety_hot_water_scald_risk_controlled", "answer": "unsafe", "severity": "high", "label": "Hot water scald risk"},
    {"id": "fnd_entry_no_zero_step", "domain": "Entry", "question_id": "home_safety_zero_step_or_ramped_main_entry", "answer": "unsafe", "severity": "high", "label": "No accessible main entry"},
    {"id": "fnd_home_loose_rugs", "domain": "Home", "question_id": "home_safety_loose_rugs_secured_or_removed", "answer": "unsafe", "severity": "high", "label": "Loose rugs / trip mats"},
    {"id": "fnd_home_smoke_co", "domain": "Home", "question_id": "home_safety_smoke_and_co_detectors_on_each_level", "answer": "unsafe", "severity": "critical", "label": "Missing smoke or CO detectors"},
    {"id": "fnd_kit_stove_gas", "domain": "Kitchen", "question_id": "home_safety_stove_gas_safety_controls", "answer": "unsafe", "severity": "high", "label": "Stove / gas safety concern"},
    {"id": "fnd_bed_height", "domain": "Bedroom", "question_id": "", "answer": "", "severity": "medium", "label": "Unsafe bed height"},
    {"id": "fnd_bed_night_light", "domain": "Bedroom", "question_id": "home_safety_bedroom_night_lighting", "answer": "unsafe", "severity": "medium", "label": "Poor night lighting"},
    {"id": "fnd_bed_clutter", "domain": "Bedroom", "question_id": "", "answer": "", "severity": "medium", "label": "Clutter / trip hazard"},
    {"id": "fnd_bed_no_rail", "domain": "Bedroom", "question_id": "", "answer": "", "severity": "medium", "label": "No bed rail"},
    {"id": "fnd_hc_med_compliance", "domain": "Health", "question_id": "health_wellness_medications_reconciled", "answer": "unsafe", "severity": "high", "label": "Poor medication compliance"},
    {"id": "fnd_hc_med_sedation", "domain": "Health", "question_id": "health_wellness_meds_checked_for_dizziness_sedation", "answer": "unsafe", "severity": "high", "label": "Sedating / dizziness meds risk"},
    {"id": "fnd_hc_fall_history", "domain": "Health", "question_id": "health_wellness_no_falls_in_the_past_year", "answer": "unsafe", "severity": "high", "label": "Fall in past year"},
    {"id": "fnd_hc_unsteady", "domain": "Health", "question_id": "health_wellness_steady_when_walking", "answer": "unsafe", "severity": "high", "label": "Unsteady gait"},
    {"id": "fnd_hc_fall_fear", "domain": "Health", "question_id": "health_wellness_not_worried_about_falling", "answer": "unsafe", "severity": "medium", "label": "Fear of falling"},
    {"id": "fnd_hc_weight_loss", "domain": "Health", "question_id": "", "answer": "", "severity": "medium", "label": "Recent weight loss"},
    {"id": "fnd_hc_hearing", "domain": "Health", "question_id": "", "answer": "", "severity": "medium", "label": "Hearing difficulty"},
    {"id": "fnd_hc_vision", "domain": "Health", "question_id": "", "answer": "", "severity": "medium", "label": "Vision risk"},
    {"id": "fnd_hc_chronic", "domain": "Health", "question_id": "", "answer": "", "severity": "high", "label": "Multiple chronic conditions"},
    {"id": "fnd_hc_cognitive", "domain": "Health", "question_id": "", "answer": "", "severity": "high", "label": "Cognitive concern"},
    {"id": "fnd_home_electrical", "domain": "Home", "question_id": "home_condition_electrical_outlets_wiring_safe", "answer": "unsafe", "severity": "high", "label": "Electrical hazard"},
    {"id": "fnd_home_water_leak", "domain": "Home", "question_id": "", "answer": "", "severity": "medium", "label": "Water leak"},
    {"id": "fnd_home_security", "domain": "Home", "question_id": "", "answer": "", "severity": "medium", "label": "Security risk"},
    {"id": "fnd_emg_no_plan", "domain": "Emergency", "question_id": "", "answer": "", "severity": "high", "label": "No emergency plan"},
    {"id": "fnd_fam_isolation", "domain": "Family", "question_id": "", "answer": "", "severity": "medium", "label": "Social isolation"},
    {"id": "fnd_fam_no_directive", "domain": "Family", "question_id": "family_support_advance_directive_decision_maker_known", "answer": "unsafe", "severity": "high", "label": "No advance directive / decision-maker"},
]

# ---------------------------------------------------------------------------
# 25_RiskRules — Independence Score™ bands (Finding/Risk engine)
# ---------------------------------------------------------------------------
DEFAULT_RISK_RULES: list[dict] = [
    {"id": "risk_excellent", "min_independence_score": 90, "max_independence_score": 100, "band": "excellent", "label": "Fully independent", "escalation_level": "none"},
    {"id": "risk_good", "min_independence_score": 75, "max_independence_score": 89, "band": "good", "label": "Minor improvements recommended", "escalation_level": "low"},
    {"id": "risk_moderate", "min_independence_score": 60, "max_independence_score": 74, "band": "moderate", "label": "Several improvements recommended", "escalation_level": "medium"},
    {"id": "risk_high", "min_independence_score": 40, "max_independence_score": 59, "band": "high", "label": "Comprehensive intervention recommended", "escalation_level": "high"},
    {"id": "risk_critical", "min_independence_score": 0, "max_independence_score": 39, "band": "critical", "label": "Immediate safety and care coordination required", "escalation_level": "critical"},
]

# ---------------------------------------------------------------------------
# 26_QuoteRules — configurable commercial discounts
# ---------------------------------------------------------------------------
DEFAULT_QUOTE_RULES: list[dict] = [
    {"id": "quote_bundle", "discount_type": "bundle", "condition": "product_count >= 3", "percent": 10, "priority": 20, "enabled": True, "campaign_code": ""},
    {"id": "quote_senior", "discount_type": "senior_citizen", "condition": "resident_age >= 60", "percent": 5, "priority": 30, "enabled": True, "campaign_code": ""},
    {"id": "quote_nri", "discount_type": "nri_campaign", "condition": "family_abroad == true", "percent": 0, "priority": 10, "enabled": True, "campaign_code": "NRI_POM"},
    {"id": "quote_referral", "discount_type": "referral", "condition": "referral_code != ''", "percent": 5, "priority": 40, "enabled": True, "campaign_code": ""},
    {"id": "quote_festival", "discount_type": "festival", "condition": "campaign_active == festival", "percent": 8, "priority": 15, "enabled": False, "campaign_code": "FESTIVAL"},
    {"id": "quote_apartment_bulk", "discount_type": "apartment_bulk", "condition": "units_in_order >= 5", "percent": 12, "priority": 25, "enabled": False, "campaign_code": "BULK"},
    {"id": "quote_corporate", "discount_type": "corporate_partnership", "condition": "partner_id != ''", "percent": 10, "priority": 25, "enabled": False, "campaign_code": ""},
]

# ---------------------------------------------------------------------------
# 27_NotificationRules — ops vs customer audiences
# ---------------------------------------------------------------------------
DEFAULT_NOTIFICATION_RULES: list[dict] = [
    {"id": "ntf_ecm_assigned_ops", "audience": "ops", "channel": "email", "event": "ecm_assigned", "template_id": "ops_ecm_assigned", "enabled": True},
    {"id": "ntf_installer_ops", "audience": "ops", "channel": "whatsapp", "event": "install_scheduled", "template_id": "ops_notify_installer", "enabled": True},
    {"id": "ntf_vendor_ops", "audience": "ops", "channel": "email", "event": "po_created", "template_id": "ops_notify_vendor", "enabled": True},
    {"id": "ntf_assessment_done_customer", "audience": "customer", "channel": "whatsapp", "event": "assessment_completed", "template_id": "cust_assessment_complete", "enabled": True},
    {"id": "ntf_quote_ready_customer", "audience": "customer", "channel": "whatsapp", "event": "quote_ready", "template_id": "cust_quote_ready", "enabled": True},
    {"id": "ntf_critical_family", "audience": "customer", "channel": "sms", "event": "risk_band_critical", "template_id": "cust_critical_alert", "enabled": True},
]

# ---------------------------------------------------------------------------
# 28_FollowUpRules — event-driven journey
# ---------------------------------------------------------------------------
DEFAULT_FOLLOWUP_RULES: list[dict] = [
    {"id": "fu_install_csat", "trigger_event": "grab_bar_installed", "delay_days": 7, "action_type": "satisfaction_survey", "template_id": "survey_install_7d", "enabled": True},
    {"id": "fu_assessment_quote", "trigger_event": "assessment_completed", "delay_days": 30, "action_type": "check_quote_status", "template_id": "ops_quote_chase", "enabled": True},
    {"id": "fu_premium_wellness", "trigger_event": "membership_premium_active", "delay_days": 30, "action_type": "schedule_wellness_visit", "template_id": "visit_monthly_wellness", "enabled": True, "repeat": "monthly"},
    {"id": "fu_critical_call", "trigger_event": "risk_band_critical", "delay_days": 0, "action_type": "ops_call_within_24h", "template_id": "ops_critical_call", "enabled": True},
]


def default_rule_engine_payload() -> dict:
    return {
        "membership_rules": DEFAULT_MEMBERSHIP_RULES,
        "ecm_rules": DEFAULT_ECM_RULES,
        "assessment_findings": DEFAULT_ASSESSMENT_FINDINGS,
        "risk_rules": DEFAULT_RISK_RULES,
        "quote_rules": DEFAULT_QUOTE_RULES,
        "notification_rules": DEFAULT_NOTIFICATION_RULES,
        "followup_rules": DEFAULT_FOLLOWUP_RULES,
        "rule_master": [],
        "rule_conditions": [],
        "rule_actions": [],
    }


def recommend_membership(
    *,
    independence_score: int,
    lives_alone: bool = False,
    family_abroad: bool = False,
    mobility_risk: str | bool | None = None,
    cognitive_risk: str | bool | None = None,
    health_complexity: str | bool | None = None,
    rules: list[dict] | None = None,
) -> str:
    """Return membership package id. Lower priority number wins among matches."""
    table = rules if rules is not None else DEFAULT_MEMBERSHIP_RULES
    candidates: list[tuple[int, str]] = []
    for rule in table:
        lo = int(rule.get("min_independence_score", 0))
        hi = int(rule.get("max_independence_score", 100))
        if not (lo <= independence_score <= hi):
            continue
        fa = rule.get("family_abroad")
        if fa is True and not family_abroad:
            continue
        if fa is False and family_abroad:
            continue
        la = rule.get("lives_alone")
        if la is True and not lives_alone:
            continue
        if la is False and lives_alone:
            continue
        # cognitive_risk on rule = "none" means require no cognitive risk
        cog_req = rule.get("cognitive_risk")
        if cog_req is not None and str(cog_req).strip() != "":
            if str(cog_req).strip().lower() in ("none", "no"):
                if _rank(cognitive_risk) > 0:
                    continue
            elif not risk_meets_minimum(cognitive_risk, cog_req):
                continue
        if not risk_meets_minimum(mobility_risk, rule.get("mobility_risk")):
            continue
        if not risk_meets_minimum(health_complexity, rule.get("health_complexity")):
            continue
        mid = str(rule.get("recommended_membership_id") or "").strip()
        if not mid:
            continue
        candidates.append((int(rule.get("priority", 100)), mid))
    if not candidates:
        return "mbr_assisted"
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def ecm_recommended(
    *,
    independence_score: int,
    lives_alone: bool = False,
    family_abroad: bool = False,
    family_requests_ecm: bool = False,
    cognitive_risk: str | bool | None = None,
    rules: list[dict] | None = None,
) -> bool:
    """Boolean ECM assign flag from simple signals (full condition parser later)."""
    if independence_score < 60:
        return True
    if lives_alone and independence_score < 75:
        return True
    if family_abroad:
        return True
    if family_requests_ecm:
        return True
    if _rank(cognitive_risk) >= _rank("mild"):
        return True
    # Prefer configured assignment_required rows when a simple evaluator isn't used yet
    if rules:
        for rule in rules:
            if not rule.get("assignment_required", True):
                continue
            cond = str(rule.get("condition") or "")
            if "independence_score < 40" in cond and independence_score < 40:
                return True
            if "cognitive_risk" in cond and _rank(cognitive_risk) >= _rank("mild"):
                return True
    return False


# Display names for membership ids (mirrors frontend MEMBERSHIP_LABELS).
MEMBERSHIP_LABELS: dict[str, str] = {
    "mbr_independent": "Independent Living",
    "mbr_assisted": "Assisted Living at Home",
    "mbr_premium": "Premium Care",
    "mbr_nri": "NRI Family Peace of Mind",
}

# Band ordinal — lower is better. Used for the critical-item cap.
_BAND_ORDER = {"excellent": 0, "good": 1, "moderate": 2, "high": 3, "critical": 4}

# Grade / label vocabulary shared with the frontend LWA_INDEPENDENCE_BANDS.
BAND_DISPLAY: dict[str, tuple[str, str]] = {
    "excellent": ("Excellent", "Fully independent"),
    "good": ("Good", "Minor improvements recommended"),
    "moderate": ("Moderate Risk", "Several improvements recommended"),
    "high": ("High Risk", "Comprehensive intervention recommended"),
    "critical": ("Critical", "Immediate safety and care coordination required"),
}


def risk_band_for_score(
    independence_score: int,
    rules: list[dict] | None = None,
    *,
    critical_unsafe: bool = False,
) -> dict:
    """Independence band for a 0-100 score.

    ``critical_unsafe`` — a rubric item on the ``critical`` scale rated unsafe sets
    ``capped_by_critical_item`` so critical findings are listed first; the band still
    follows the number (owner, 28 Oct). Mirrors frontend safetyGradeFromScore.
    """
    table = rules if rules is not None else DEFAULT_RISK_RULES
    found: dict | None = None
    for rule in table:
        lo = int(rule.get("min_independence_score", 0))
        hi = int(rule.get("max_independence_score", 100))
        if lo <= independence_score <= hi:
            found = rule
            break
    if found is None:
        found = {
            "id": "risk_unknown",
            "band": "unknown",
            "label": "Unknown",
            "escalation_level": "medium",
        }
    if critical_unsafe:
        # Band follows the number (owner, 28 Oct); the flag still lists critical items.
        return {**found, "capped_by_critical_item": True}
    return found
