"""SOS alarm pushes to the KushAlaya Android apps (Firebase Cloud Messaging, HTTP v1).

The apps ring like an alarm clock when they get a ``type=sos`` data message, even
when closed, locked, on silent or on do-not-disturb (see mobile/README.md). This
module sends that message to the phones of exactly the people who got a siren row
(``app.livewell.sos_siren``).

Configuration (server env, never in code):

* ``FCM_SERVICE_ACCOUNT_FILE`` — path to the Firebase service-account JSON, or
* ``FCM_SERVICE_ACCOUNT_JSON`` — the same JSON inline.
* ``FCM_PROJECT_ID`` — optional; defaults to ``project_id`` in the JSON.

Not configured: nothing is sent and nothing errors; the web siren works as before.
Sending happens on a background thread so an SOS is never slowed by Google.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.push_device import PushDevice

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
APPS = ("ops", "family")
# The alarm is pointless once the person has had a minute or two to answer it.
SOS_TTL = "300s"

_token_cache: dict[str, Any] = {"token": None, "exp": 0.0}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _env(name: str) -> str:
    """Process env first, then backend/.env (pydantic settings do not export to os.environ)."""
    from app.core.config import settings

    return (os.environ.get(name) or str(getattr(settings, name, "") or "")).strip()


def service_account() -> dict | None:
    raw = _env("FCM_SERVICE_ACCOUNT_JSON")
    path = _env("FCM_SERVICE_ACCOUNT_FILE")
    try:
        if raw:
            data = json.loads(raw)
        elif path and os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            return None
    except (OSError, ValueError):
        logger.warning("fcm_service_account_unreadable")
        return None
    if not isinstance(data, dict) or not data.get("private_key") or not data.get("client_email"):
        return None
    return data


def is_configured() -> bool:
    return service_account() is not None


def _project_id(sa: dict) -> str:
    return _env("FCM_PROJECT_ID") or str(sa.get("project_id") or "")


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


def register(db: Session, user, token: str, *, app: str = "ops", platform: str = "android") -> PushDevice:
    """Upsert by token: the phone now rings for this user only."""
    token = token.strip()
    now = datetime.now(timezone.utc)
    row = db.query(PushDevice).filter(PushDevice.token == token).first()
    if row is None:
        row = PushDevice(token=token)
        db.add(row)
    row.user_id = user.id
    row.tenant_id = user.tenant_id
    row.app = app if app in APPS else "ops"
    row.platform = (platform or "android")[:16]
    row.last_seen_at = now
    db.commit()
    db.refresh(row)
    return row


def unregister(db: Session, user, token: str) -> bool:
    row = db.query(PushDevice).filter(PushDevice.token == token.strip(), PushDevice.user_id == user.id).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def tokens_for(db: Session, user_ids: set[int] | list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    ids = list(user_ids)
    if not ids:
        return out
    for uid, token in db.query(PushDevice.user_id, PushDevice.token).filter(PushDevice.user_id.in_(ids)).all():
        out.setdefault(uid, []).append(token)
    return out


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


def sos_message(token: str, item: dict, *, reason: str) -> dict:
    """A data-only, high-priority message. Data-only so the app's own service always
    runs (a ``notification`` block would be shown by the system, without the alarm)."""
    who = item.get("elder_name") or "Client"
    data = {
        "type": "sos",
        "reason": reason,
        "alert_id": str(item.get("id") or ""),
        "incident_id": str(item.get("incident_id") or ""),
        "title": f"{item.get('title') or 'SOS'} — {who}",
        "elder_name": str(who),
        "pressed_by": str(item.get("pressed_by") or ""),
        "audience": str(item.get("audience") or ""),
        "verify": "1" if item.get("verify") else "0",
        "escalated": "1" if item.get("escalated") else "0",
        "call_label": str((item.get("call") or {}).get("label") or ""),
        "call_phone": str((item.get("call") or {}).get("phone") or ""),
    }
    return {"message": {"token": token, "data": data, "android": {"priority": "HIGH", "ttl": SOS_TTL}}}


def notify_sos(db: Session, incident_id: int, user_ids: set[int], *, reason: str) -> int:
    """Push the SOS to every phone of these users (their unacknowledged siren rows).

    Returns the number of messages queued. Never raises: the siren rows and the web
    siren are the source of truth; the push only makes the phone ring sooner/louder.
    """
    if not user_ids or not is_configured():
        return 0
    try:
        from app.livewell import sos_siren
        from app.models.elder import Elder
        from app.models.incident import Incident
        from app.models.sos_siren import SosSirenAlert

        devices = tokens_for(db, user_ids)
        if not devices:
            return 0
        row = db.get(Incident, incident_id)
        elder = db.get(Elder, row.elder_id) if row else None
        if row is None or elder is None:
            return 0
        alerts = (
            db.query(SosSirenAlert)
            .filter(
                SosSirenAlert.incident_id == incident_id,
                SosSirenAlert.user_id.in_(list(devices)),
                SosSirenAlert.acknowledged_at.is_(None),
            )
            .all()
        )
        messages = []
        for alert in alerts:
            item = sos_siren.serialize(db, alert, row, elder)
            messages += [sos_message(t, item, reason=reason) for t in devices.get(alert.user_id, [])]
        if messages:
            _deliver(messages)
        return len(messages)
    except Exception:  # noqa: BLE001
        logger.exception("fcm_sos_prepare_failed incident=%s", incident_id)
        return 0


# ---------------------------------------------------------------------------
# Transport (FCM HTTP v1)
# ---------------------------------------------------------------------------


def _deliver(messages: list[dict]) -> None:
    """Send on a daemon thread. Tests replace this."""
    threading.Thread(target=send_all, args=(messages,), name="fcm-sos", daemon=True).start()


def _access_token(sa: dict) -> str:
    with _lock:
        if _token_cache["token"] and _token_cache["exp"] - 60 > time.time():
            return _token_cache["token"]
        import httpx
        from jose import jwt

        now = int(time.time())
        assertion = jwt.encode(
            {
                "iss": sa["client_email"],
                "scope": FCM_SCOPE,
                "aud": sa.get("token_uri") or TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            sa["private_key"],
            algorithm="RS256",
            headers={"kid": sa.get("private_key_id")} if sa.get("private_key_id") else None,
        )
        res = httpx.post(
            sa.get("token_uri") or TOKEN_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            timeout=10,
        )
        res.raise_for_status()
        body = res.json()
        _token_cache["token"] = body["access_token"]
        _token_cache["exp"] = time.time() + int(body.get("expires_in") or 3600)
        return _token_cache["token"]


def send_all(messages: list[dict]) -> list[str]:
    """Send each message; drop tokens FCM says are dead. Returns the dead tokens."""
    sa = service_account()
    if not sa or not messages:
        return []
    dead: list[str] = []
    try:
        import httpx

        url = SEND_URL.format(project=_project_id(sa))
        headers = {"Authorization": f"Bearer {_access_token(sa)}"}
        with httpx.Client(timeout=10) as client:
            for msg in messages:
                try:
                    res = client.post(url, json=msg, headers=headers)
                except httpx.HTTPError:
                    logger.warning("fcm_send_network_error")
                    continue
                if res.status_code == 200:
                    continue
                text = res.text or ""
                if res.status_code == 404 or "UNREGISTERED" in text:
                    dead.append(msg["message"]["token"])
                else:
                    logger.warning("fcm_send_failed status=%s body=%s", res.status_code, text[:300])
    except Exception:  # noqa: BLE001
        logger.exception("fcm_send_all_failed")
    if dead:
        _drop_tokens(dead)
    return dead


def _drop_tokens(tokens: list[str]) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        db.query(PushDevice).filter(PushDevice.token.in_(tokens)).delete(synchronize_session=False)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("fcm_drop_tokens_failed")
    finally:
        db.close()
