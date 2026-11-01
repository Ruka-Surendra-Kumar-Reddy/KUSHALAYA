import logging

from app.services.notifications.base import EmailProvider, SmsProvider, WhatsAppProvider
from app.services.notifications.types import (
    DeliveryResult,
    DeliveryStatus,
    WhatsAppTemplateMessage,
)

logger = logging.getLogger(__name__)


class LogEmailProvider(EmailProvider):
    """Default: audit-only until NOTIFICATION_EMAIL_PROVIDER=ses."""

    def send(self, to: str, subject: str, body: str, html: str | None = None) -> DeliveryResult:
        logger.info(
            "notification_email_logged to=%s subject=%s body=%s",
            to,
            subject,
            body[:200],
        )
        return DeliveryResult(
            status=DeliveryStatus.LOGGED,
            detail="Email provider is log-only (set NOTIFICATION_EMAIL_PROVIDER=ses)",
        )


class LogSmsProvider(SmsProvider):
    """Default: audit-only until NOTIFICATION_SMS_PROVIDER=msg91."""

    def send(self, to: str, body: str) -> DeliveryResult:
        logger.info(
            "notification_sms_logged to=%s body=%s",
            to,
            body[:200],
        )
        return DeliveryResult(
            status=DeliveryStatus.LOGGED,
            detail="SMS provider is log-only (set NOTIFICATION_SMS_PROVIDER=msg91)",
        )


class LogWhatsAppProvider(WhatsAppProvider):
    """Default: audit-only until NOTIFICATION_WHATSAPP_PROVIDER=meta."""

    def send_template(self, to: str, message: WhatsAppTemplateMessage) -> DeliveryResult:
        logger.info(
            "notification_whatsapp_logged to=%s template=%s params=%s",
            to,
            message.template_name,
            message.body_params,
        )
        return DeliveryResult(
            status=DeliveryStatus.LOGGED,
            detail=(
                "WhatsApp provider is log-only "
                "(set NOTIFICATION_WHATSAPP_PROVIDER=meta when BSP credentials are ready)"
            ),
        )
