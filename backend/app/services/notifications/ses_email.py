import logging

from app.core.config import settings
from app.services.notifications.base import EmailProvider
from app.services.notifications.types import DeliveryResult, DeliveryStatus

logger = logging.getLogger(__name__)


class SesEmailProvider(EmailProvider):
    """Amazon SES. Requires boto3 and verified SES_FROM_EMAIL."""

    def send(self, to: str, subject: str, body: str, html: str | None = None) -> DeliveryResult:
        if not settings.SES_FROM_EMAIL:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="SES_FROM_EMAIL is not configured",
            )
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="AWS credentials are not configured",
            )

        try:
            import boto3
        except ImportError:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="boto3 is not installed (pip install boto3)",
            )

        try:
            client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            client.send_email(
                Source=settings.SES_FROM_EMAIL,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body, "Charset": "UTF-8"},
                        **(
                            {"Html": {"Data": html, "Charset": "UTF-8"}}
                            if html
                            else {}
                        ),
                    },
                },
            )
            logger.info("ses_email_sent to=%s", to)
            return DeliveryResult(status=DeliveryStatus.SENT)
        except Exception as exc:
            logger.exception("ses_email_failed to=%s", to)
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail=str(exc)[:500],
            )
