import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.services.notifications.base import EmailProvider
from app.services.notifications.types import DeliveryResult, DeliveryStatus

logger = logging.getLogger(__name__)


class SmtpEmailProvider(EmailProvider):
    """Gmail (or any SMTP) via username + app password. STARTTLS on port 587 by default."""

    def __init__(self, cfg: dict | None = None):
        # cfg comes from Settings → Email & SMS (channel_config); otherwise .env.
        self.cfg = cfg

    def send(self, to: str, subject: str, body: str, html: str | None = None) -> DeliveryResult:
        c = self.cfg
        if c:
            user, password = str(c.get("username") or "").strip(), str(c.get("password") or "").replace(" ", "")
            host, port = str(c.get("host") or "smtp.zoho.in").strip(), int(c.get("port") or 587)
            from_email = str(c.get("from_email") or user).strip()
            from_name = str(c.get("from_name") or "KushAlaya").strip()
        else:
            user = (settings.SMTP_USERNAME or "").strip()
            # Gmail shows app passwords as 4 groups; SMTP accepts them with or without spaces.
            password = (settings.SMTP_PASSWORD or "").replace(" ", "").strip()
            host = (settings.SMTP_HOST or "smtp.gmail.com").strip()
            port = int(settings.SMTP_PORT or 587)
            from_email = (settings.SMTP_FROM_EMAIL or user).strip()
            from_name = (settings.SMTP_FROM_NAME or "LiveWell360").strip()

        if not user or not password or not from_email:
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail="SMTP_USERNAME / SMTP_PASSWORD / SMTP_FROM_EMAIL are not configured",
            )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = to
        if settings.EMAIL_REPLY_TO:
            msg["Reply-To"] = settings.EMAIL_REPLY_TO
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")

        try:
            if port == 465:  # implicit SSL (Zoho also offers this)
                with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                    smtp.login(user, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=20) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                    smtp.login(user, password)
                    smtp.send_message(msg)
            logger.info("smtp_email_sent to=%s", to)
            return DeliveryResult(status=DeliveryStatus.SENT)
        except Exception as exc:
            logger.exception("smtp_email_failed to=%s", to)
            return DeliveryResult(
                status=DeliveryStatus.FAILED,
                detail=str(exc)[:500],
            )
