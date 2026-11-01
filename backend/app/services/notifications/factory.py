from functools import lru_cache

from app.core.config import settings
from app.services.notifications.base import EmailProvider, SmsProvider, WhatsAppProvider
from app.services.notifications.log_providers import (
    LogEmailProvider,
    LogSmsProvider,
    LogWhatsAppProvider,
)
from app.services.notifications.meta_whatsapp_stub import MetaWhatsAppStubProvider
from app.services.notifications.msg91_sms import Msg91SmsProvider
from app.services.notifications.msg91_whatsapp import Msg91WhatsAppProvider
from app.services.notifications.ses_email import SesEmailProvider
from app.services.notifications.smtp_email import SmtpEmailProvider
from app.services.notifications.twilio_messaging import TwilioSmsProvider, TwilioWhatsAppProvider

_EMAIL_PROVIDERS: dict[str, type[EmailProvider]] = {
    "log": LogEmailProvider,
    "ses": SesEmailProvider,
    "smtp": SmtpEmailProvider,
    "gmail": SmtpEmailProvider,
}

_SMS_PROVIDERS: dict[str, type[SmsProvider]] = {
    "log": LogSmsProvider,
    "msg91": Msg91SmsProvider,
    "twilio": TwilioSmsProvider,
}

_WHATSAPP_PROVIDERS: dict[str, type[WhatsAppProvider]] = {
    "log": LogWhatsAppProvider,
    "meta": MetaWhatsAppStubProvider,
    "msg91": Msg91WhatsAppProvider,
    "twilio": TwilioWhatsAppProvider,
}


def register_email_provider(name: str, cls: type[EmailProvider]) -> None:
    """Register a custom email provider at startup if needed."""
    _EMAIL_PROVIDERS[name.lower()] = cls


def register_sms_provider(name: str, cls: type[SmsProvider]) -> None:
    """Register a custom SMS provider at startup if needed."""
    _SMS_PROVIDERS[name.lower()] = cls


def register_whatsapp_provider(name: str, cls: type[WhatsAppProvider]) -> None:
    """Register a custom WhatsApp BSP provider at startup if needed."""
    _WHATSAPP_PROVIDERS[name.lower()] = cls


@lru_cache
def _env_email_provider() -> EmailProvider:
    name = (settings.NOTIFICATION_EMAIL_PROVIDER or "log").lower()
    cls = _EMAIL_PROVIDERS.get(name, LogEmailProvider)
    return cls()


@lru_cache
def _env_sms_provider() -> SmsProvider:
    name = (settings.NOTIFICATION_SMS_PROVIDER or "log").lower()
    cls = _SMS_PROVIDERS.get(name, LogSmsProvider)
    return cls()


def get_email_provider() -> EmailProvider:
    """The connection saved in Settings (when switched on) wins over .env."""
    from app.services.notifications import channel_config

    cfg = channel_config.active("email")
    return SmtpEmailProvider(cfg) if cfg else _env_email_provider()


def get_sms_provider() -> SmsProvider:
    from app.services.notifications import channel_config

    cfg = channel_config.active("sms")
    return Msg91SmsProvider(cfg) if cfg else _env_sms_provider()


@lru_cache
def get_whatsapp_provider() -> WhatsAppProvider:
    name = (settings.NOTIFICATION_WHATSAPP_PROVIDER or "log").lower()
    cls = _WHATSAPP_PROVIDERS.get(name, LogWhatsAppProvider)
    return cls()


def clear_provider_cache() -> None:
    """For tests when settings change."""
    from app.services.notifications import channel_config

    _env_email_provider.cache_clear()
    _env_sms_provider.cache_clear()
    channel_config.clear_cache()
    get_whatsapp_provider.cache_clear()
