import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
_telemetry_ready = False


def setup_telemetry() -> bool:
    """Configure Azure Monitor OpenTelemetry when a connection string is set."""
    global _telemetry_ready

    if _telemetry_ready:
        return True

    conn = (settings.APPLICATIONINSIGHTS_CONNECTION_STRING or "").strip()
    if not conn or not settings.ENABLE_TELEMETRY:
        logger.info("Application Insights disabled (no connection string)")
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        configure_azure_monitor(
            connection_string=conn,
            logger_name="WorkforceOS",
        )
        SQLAlchemyInstrumentor().instrument()
        _telemetry_ready = True
        logger.info("Application Insights telemetry enabled")
        return True
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry not installed; skipping App Insights"
        )
        return False
    except Exception as exc:
        logger.error("Failed to configure Application Insights: %s", exc)
        return False


def instrument_fastapi(app) -> None:
    if not _telemetry_ready:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("FastAPI instrumentation skipped: %s", exc)
