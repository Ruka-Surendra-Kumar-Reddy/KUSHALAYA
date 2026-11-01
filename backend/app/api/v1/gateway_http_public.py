"""Minew gateway HTTP upload — no login, the secret link is the key.

``/api/v1/home-safety/gateway/{token}``: mounted under the Safe Home prefix so
nginx already routes it. Minew G1 / MG3 gateways cannot add custom headers, so
the per-gateway token sits in the URL path. One token per gateway; regenerate it
from Wearables to cut a gateway off.

POST: the gateway's JSON scan batch (bare array, or wrapped in a dict).
GET:  a quick "is this link right?" check an installer can open in a browser.
"""

from __future__ import annotations

import gzip
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell.iot_gateway_http import process_gateway_upload
from app.livewell.iot_registry_service import IotRegistryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/home-safety/gateway", tags=["Safe Home — Gateway HTTP"])

MAX_BODY_BYTES = 2 * 1024 * 1024


def _hub_or_404(db: Session, token: str):
    hub = IotRegistryService.find_hub_by_token(db, token[:120])
    if hub is None:
        raise HTTPException(status_code=404, detail="Unknown gateway link")
    return hub


def _decode_body(raw: bytes, encoding: str | None):
    if (encoding or "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Some firmware sends one JSON object per line.
    rows = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.extend(item if isinstance(item, list) else [item])
    if not rows:
        raise HTTPException(status_code=400, detail="Body is not JSON")
    return rows


@router.get("/{token}")
def gateway_check(token: str, db: Session = Depends(get_db)):
    hub = _hub_or_404(db, token)
    return {"ok": True, "gateway": hub.label, "message": "Link is correct. Set the gateway to POST JSON here."}


async def _raw_body(request: Request) -> bytes:
    return await request.body()


@router.post("/{token}")
def gateway_upload(
    token: str,
    request: Request,
    raw: bytes = Depends(_raw_body),
    db: Session = Depends(get_db),
):
    # Sync handler (runs in the threadpool): the DB work must not block the event loop.
    hub = _hub_or_404(db, token)
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Batch too large")
    try:
        payload = _decode_body(raw, request.headers.get("content-encoding"))
    except (OSError, EOFError):
        raise HTTPException(status_code=400, detail="Bad gzip body") from None
    summary = process_gateway_upload(db, hub, payload)
    return {"ok": True, **{k: summary[k] for k in ("heard", "registered")}, "events": len(summary["events"])}
