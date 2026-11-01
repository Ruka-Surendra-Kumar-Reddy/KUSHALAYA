"""Customer portal adapters live in workforceos-core; this app uses the defaults."""

from types import SimpleNamespace

from workforceos_core.adapters.customer_portal import (
    DefaultCustomerPortalAdapter,
    get_customer_portal_adapter,
)
from workforceos_core.exceptions import WorkforceHTTPError

from app.core.verticals import ELDER_CARE, HOUSEKEEPING, LIVEWELL360, has_feature
import pytest


def test_adapter_registry_uses_default_for_livewell():
    adapter = get_customer_portal_adapter(LIVEWELL360)
    assert isinstance(adapter, DefaultCustomerPortalAdapter)
    assert adapter.portal_label() == "customer"


def test_adapter_registry_uses_default_for_elder_care():
    adapter = get_customer_portal_adapter(ELDER_CARE)
    assert isinstance(adapter, DefaultCustomerPortalAdapter)


@pytest.mark.parametrize(
    "vertical,expected",
    [
        (ELDER_CARE, has_feature(ELDER_CARE, "customer_portal_billing")),
        (LIVEWELL360, has_feature(LIVEWELL360, "customer_portal_billing")),
        (HOUSEKEEPING, has_feature(HOUSEKEEPING, "customer_portal_billing")),
        ("SECURITY", has_feature("SECURITY", "customer_portal_billing")),
    ],
)
def test_default_adapter_billing_follows_vertical_feature(vertical, expected):
    adapter = DefaultCustomerPortalAdapter()
    tenant = SimpleNamespace(vertical=vertical, name="Test")
    assert adapter.billing_enabled(tenant) is expected


def test_assert_billing_enabled_raises_when_feature_off():
    adapter = DefaultCustomerPortalAdapter()
    tenant = SimpleNamespace(vertical="SECURITY", name="Guard Co")
    if adapter.billing_enabled(tenant):
        pytest.skip("SECURITY pack enables portal billing")
    with pytest.raises(WorkforceHTTPError) as exc:
        adapter.assert_billing_enabled(tenant)
    assert exc.value.status_code == 400


def test_client_ids_for_user_prefers_customer_id():
    adapter = DefaultCustomerPortalAdapter()
    user = SimpleNamespace(customer_id=42, elder_id=7)
    assert adapter.client_ids_for_user(None, user) == [42]


def test_client_ids_for_user_falls_back_to_elder_id():
    adapter = DefaultCustomerPortalAdapter()
    user = SimpleNamespace(customer_id=None, elder_id=9)
    assert adapter.client_ids_for_user(None, user) == [9]


def test_client_ids_empty_when_unlinked():
    adapter = DefaultCustomerPortalAdapter()
    user = SimpleNamespace(customer_id=None, elder_id=None)
    assert adapter.client_ids_for_user(None, user) == []
