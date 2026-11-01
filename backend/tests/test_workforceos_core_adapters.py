"""Vertical adapters are registered in workforceos-core; this deploy uses defaults."""

from types import SimpleNamespace

from workforceos_core.adapters.care_plans import get_care_plan_adapter
from workforceos_core.adapters.customer_portal import (
    DefaultCustomerPortalAdapter,
    get_customer_portal_adapter,
)
from workforceos_core.adapters.family_portal import get_family_portal_adapter
from workforceos_core.adapters.visit_execution import get_visit_execution_adapter
from workforceos_core.adapters.visit_notifications import get_visit_notification_adapter

from app.core.verticals import ELDER_CARE, LIVEWELL360


def test_livewell_adapters_resolve_to_core_defaults():
    assert isinstance(get_customer_portal_adapter(LIVEWELL360), DefaultCustomerPortalAdapter)
    family = get_family_portal_adapter(LIVEWELL360)
    assert family.portal_enabled(SimpleNamespace(vertical=LIVEWELL360)) in (True, False)
    plans = get_care_plan_adapter(LIVEWELL360)
    assert isinstance(plans.templates_payload(), dict)
    visits = get_visit_execution_adapter(LIVEWELL360)
    assert isinstance(visits.checklist_items(), list)
    notify = get_visit_notification_adapter(LIVEWELL360)
    assert notify is not None


def test_elder_care_adapters_still_resolve():
    assert get_customer_portal_adapter(ELDER_CARE).portal_label() == "customer"
    assert get_family_portal_adapter(ELDER_CARE) is not None
    assert get_care_plan_adapter(ELDER_CARE) is not None
    assert get_visit_execution_adapter(ELDER_CARE) is not None
    assert get_visit_notification_adapter(ELDER_CARE) is not None
