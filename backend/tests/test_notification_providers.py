import app.models  # noqa: F401

from app.services.notifications.alert_email import format_mac, render_iot_alert_email
from app.services.notifications.factory import (
    clear_provider_cache,
    get_email_provider,
    get_sms_provider,
    get_whatsapp_provider,
)
from app.services.notifications.log_providers import LogEmailProvider, LogSmsProvider
from app.services.notifications.ses_email import SesEmailProvider
from app.services.notifications.smtp_email import SmtpEmailProvider
from app.services.notifications.msg91_sms import Msg91SmsProvider
from app.services.notifications.twilio_messaging import TwilioSmsProvider, TwilioWhatsAppProvider, to_e164
from app.services.notifications.telegram_bot import send_telegram_message
from app.services.notifications.types import DeliveryStatus, normalize_phone


def test_normalize_phone_india_10_digit():
    assert normalize_phone("9876543210") == "919876543210"


def test_log_email_provider():
    result = LogEmailProvider().send("a@b.com", "Subj", "Body")
    assert result.status == DeliveryStatus.LOGGED
    assert result.success


def test_iot_alert_email_card_includes_fields():
    text, html = render_iot_alert_email(
        title="SOS from wearable",
        severity="critical",
        client_name="Lakshmi",
        event_label="Wearable SOS",
        device_label="Lakshmi band",
        hub_id="gw-poc-1",
        mac_address="c3:00:00:98:f3:f8",
        incident_id="dsos_test",
    )
    assert "Time:" in text
    assert "MAC address: C3:00:00:98:F3:F8" in text
    assert "Lakshmi" in html
    assert "gw-poc-1" in html
    assert "C3:00:00:98:F3:F8" in html
    assert "SOS ALERT" in html
    assert "<table" in html
    assert format_mac("c3000098f3f8") == "C3:00:00:98:F3:F8"


def test_factory_defaults_to_log():
    from app.core.config import settings

    settings.NOTIFICATION_EMAIL_PROVIDER = "log"
    settings.NOTIFICATION_SMS_PROVIDER = "log"
    clear_provider_cache()
    assert isinstance(get_email_provider(), LogEmailProvider)
    assert isinstance(get_sms_provider(), LogSmsProvider)


def test_factory_ses_without_credentials_fails(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_EMAIL_PROVIDER", "ses")
    clear_provider_cache()
    from app.core.config import settings

    settings.NOTIFICATION_EMAIL_PROVIDER = "ses"
    settings.SES_FROM_EMAIL = ""
    clear_provider_cache()
    provider = get_email_provider()
    assert isinstance(provider, SesEmailProvider)
    result = provider.send("test@example.com", "S", "B")
    assert result.status == DeliveryStatus.FAILED


def test_factory_smtp_without_credentials_fails():
    from app.core.config import settings

    settings.NOTIFICATION_EMAIL_PROVIDER = "smtp"
    settings.SMTP_USERNAME = ""
    settings.SMTP_PASSWORD = ""
    settings.SMTP_FROM_EMAIL = ""
    clear_provider_cache()
    provider = get_email_provider()
    assert isinstance(provider, SmtpEmailProvider)
    result = provider.send("test@example.com", "S", "B")
    assert result.status == DeliveryStatus.FAILED


def test_factory_gmail_alias_uses_smtp():
    from app.core.config import settings

    settings.NOTIFICATION_EMAIL_PROVIDER = "gmail"
    clear_provider_cache()
    assert isinstance(get_email_provider(), SmtpEmailProvider)


def test_factory_msg91_without_key_fails(monkeypatch):
    from app.core.config import settings

    settings.NOTIFICATION_SMS_PROVIDER = "msg91"
    settings.MSG91_AUTH_KEY = ""
    clear_provider_cache()
    provider = get_sms_provider()
    assert isinstance(provider, Msg91SmsProvider)
    result = provider.send("919876543210", "Alert")
    assert result.status == DeliveryStatus.FAILED


def test_twilio_e164_india():
    assert to_e164("9876543210") == "+919876543210"
    assert to_e164("+919876543210") == "+919876543210"


def test_factory_twilio_without_credentials_fails():
    from app.core.config import settings

    settings.NOTIFICATION_SMS_PROVIDER = "twilio"
    settings.NOTIFICATION_WHATSAPP_PROVIDER = "twilio"
    settings.TWILIO_ACCOUNT_SID = ""
    settings.TWILIO_AUTH_TOKEN = ""
    settings.TWILIO_SMS_FROM = "+15005550006"
    clear_provider_cache()
    sms = get_sms_provider()
    wa = get_whatsapp_provider()
    assert isinstance(sms, TwilioSmsProvider)
    assert isinstance(wa, TwilioWhatsAppProvider)
    assert sms.send("+919876543210", "Alert").status == DeliveryStatus.FAILED
    assert wa.send_text("+919876543210", "Alert").status == DeliveryStatus.FAILED


def test_telegram_without_token_fails():
    from app.core.config import settings

    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_ID = "123"
    result = send_telegram_message("hello")
    assert result.status == DeliveryStatus.FAILED
