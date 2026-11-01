"""Activity log mode filtering for session timeline."""

from app.services.session_activity_service import SessionActivityService


def test_standard_skips_successful_get_hydration(monkeypatch):
    monkeypatch.setenv("ACTIVITY_LOG_MODE", "standard")
    from app.core.config import settings

    settings.ACTIVITY_LOG_MODE = "standard"

    assert (
        SessionActivityService.should_log_api_call(
            method="GET",
            path="/api/v1/home-safety/assessments/hsa-1",
            status_code=200,
        )
        is False
    )
    assert (
        SessionActivityService.should_log_api_call(
            method="GET",
            path="/api/v1/auth/me",
            status_code=200,
        )
        is False
    )


def test_standard_keeps_mutations_and_errors(monkeypatch):
    from app.core.config import settings

    settings.ACTIVITY_LOG_MODE = "standard"

    assert (
        SessionActivityService.should_log_api_call(
            method="PUT",
            path="/api/v1/home-safety/assessments/hsa-1",
            status_code=200,
        )
        is True
    )
    assert (
        SessionActivityService.should_log_api_call(
            method="GET",
            path="/api/v1/home-safety/assessments/hsa-1",
            status_code=400,
        )
        is True
    )


def test_verbose_logs_gets(monkeypatch):
    from app.core.config import settings

    settings.ACTIVITY_LOG_MODE = "verbose"

    assert (
        SessionActivityService.should_log_api_call(
            method="GET",
            path="/api/v1/auth/me",
            status_code=200,
        )
        is True
    )
