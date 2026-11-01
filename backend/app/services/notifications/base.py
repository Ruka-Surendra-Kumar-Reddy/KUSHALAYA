from abc import ABC, abstractmethod

from app.services.notifications.types import DeliveryResult, DeliveryStatus, WhatsAppTemplateMessage


class EmailProvider(ABC):
    """Plug in SES (or another provider) by subclassing and registering in factory."""

    @abstractmethod
    def send(self, to: str, subject: str, body: str, html: str | None = None) -> DeliveryResult:
        ...


class SmsProvider(ABC):
    """Plug in MSG91 (or another provider) by subclassing and registering in factory."""

    @abstractmethod
    def send(self, to: str, body: str) -> DeliveryResult:
        ...


class WhatsAppProvider(ABC):
    """Plug in Meta Cloud API, Twilio, or a BSP by subclassing and registering in factory."""

    @abstractmethod
    def send_template(self, to: str, message: WhatsAppTemplateMessage) -> DeliveryResult:
        ...

    def send_text(self, to: str, body: str) -> DeliveryResult:
        return DeliveryResult(
            status=DeliveryStatus.FAILED,
            detail="WhatsApp free-text is not supported on this provider",
        )
