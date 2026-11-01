from dataclasses import dataclass
from enum import Enum

from workforceos_core.notifications import WhatsAppTemplateMessage


@dataclass(frozen=True)
class WhatsAppDocumentTemplate(WhatsAppTemplateMessage):
    """Template whose header is a document (PDF) fetched by WhatsApp from a public URL."""

    header_document_url: str = ""
    header_filename: str = "document.pdf"


class DeliveryStatus(str, Enum):
    """Persisted on monitoring_alerts.status."""

    LOGGED = "LOGGED"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    detail: str | None = None

    @property
    def success(self) -> bool:
        return self.status in {DeliveryStatus.SENT, DeliveryStatus.LOGGED}


@dataclass(frozen=True)
class NotificationRecipient:
    role: str
    email: str | None = None
    phone: str | None = None


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return None
    if len(digits) == 10:
        return f"91{digits}"
    if digits.startswith("91") and len(digits) >= 12:
        return digits
    return digits
