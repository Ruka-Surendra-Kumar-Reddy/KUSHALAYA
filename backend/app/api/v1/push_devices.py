"""Android app push tokens: the app's web page registers the phone after sign-in
and unregisters it on sign-out. Used for the SOS alarm (app/livewell/push.py)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.livewell import push
from app.models.user import User

router = APIRouter(prefix="/push", tags=["Push devices"])


class DeviceBody(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    app: Literal["ops", "family"] = "ops"
    platform: Literal["android", "ios"] = "android"


class TokenBody(BaseModel):
    token: str = Field(min_length=1, max_length=512)


@router.post("/devices")
def register_device(body: DeviceBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = push.register(db, current_user, body.token, app=body.app, platform=body.platform)
    return {"ok": True, "id": row.id, "push_configured": push.is_configured()}


@router.post("/devices/unregister")
def unregister_device(body: TokenBody, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"ok": True, "removed": push.unregister(db, current_user, body.token)}
