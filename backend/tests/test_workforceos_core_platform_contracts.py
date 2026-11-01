"""Ensure backend platform shims match workforceos-core contracts."""

from workforceos_core.workflow.events import ATTENDANCE_ALERT, CLEANING_JOB_REQUESTED
from workforceos_core.workflow.templates import templates_for_vertical


def test_workflow_events_reexport():
    from app.core.workflow_events import ATTENDANCE_ALERT as app_event

    assert app_event == ATTENDANCE_ALERT


def test_workflow_templates_reexport():
    from app.core.workflow_templates import templates_for_vertical as app_templates

    assert len(app_templates("ELDER_CARE")) == len(templates_for_vertical("ELDER_CARE"))


def test_platform_modules_reexport():
    from app.core.platform_modules import list_platform_modules

    assert any(m["id"] == "copilot" for m in list_platform_modules())


def test_responses_use_core_errors():
    from app.core.responses import raise_not_found
    from workforceos_core.exceptions import WorkforceHTTPError
    import pytest

    with pytest.raises(WorkforceHTTPError) as exc:
        raise_not_found("x")
    assert exc.value.status_code == 404
