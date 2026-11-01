from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import raise_bad_request
from app.services.checkr_webhook_service import CheckrWebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/checkr")
async def checkr_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_checkr_signature: str | None = Header(default=None, alias="X-Checkr-Signature"),
):
    if not CheckrWebhookService.verify_secret(x_checkr_signature):
        raise_bad_request("Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise_bad_request("Invalid JSON body")

    if not isinstance(payload, dict):
        raise_bad_request("Payload must be a JSON object")

    return CheckrWebhookService.process_payload(db, payload)
