"""Email (SMTP, e.g. Zoho Mail) and SMS (MSG91) connections set from Settings.

Stored platform-wide in ``app_global_settings`` (keys ``channel.email`` and
``channel.sms``). The password / auth key is encrypted with a key derived from
SECRET_KEY and is never returned by the API. When a channel is saved and turned
on it wins over the .env values; when it is off, the .env setup is used as before.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

KEYS = {"email": "channel.email", "sms": "channel.sms"}
SECRET_FIELD = {"email": "password", "sms": "auth_key"}
FIELDS = {
    "email": ("host", "port", "username", "from_email", "from_name"),
    "sms": ("sender_id", "template_id", "route"),
}
DEFAULTS = {
    "email": {"host": "smtp.zoho.in", "port": 587, "username": "", "from_email": "", "from_name": "KushAlaya"},
    "sms": {"sender_id": "", "template_id": "", "route": "4"},
}
_TTL = 30.0
_cache: dict[str, tuple[float, dict | None]] = {}


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"channel-config:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        logger.warning("channel_config_secret_unreadable (SECRET_KEY changed?)")
        return ""


def _session():
    from app.core.database import SessionLocal, engine
    from app.models.app_global_setting import AppGlobalSetting

    AppGlobalSetting.__table__.create(bind=engine, checkfirst=True)
    return SessionLocal()


def _read_raw(kind: str, db=None) -> dict:
    from app.models.app_global_setting import AppGlobalSetting

    own = db is None
    db = db or _session()
    try:
        row = db.get(AppGlobalSetting, KEYS[kind])
        return dict(row.value) if row and isinstance(row.value, dict) else {}
    finally:
        if own:
            db.close()


def active(kind: str) -> dict | None:
    """The saved, switched-on connection with its secret decrypted — or None. Cached briefly."""
    hit = _cache.get(kind)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    cfg: dict | None = None
    try:
        raw = _read_raw(kind)
        if raw.get("enabled") and raw.get("secret"):
            secret = _decrypt(raw["secret"])
            if secret:
                cfg = {**DEFAULTS[kind], **{k: raw.get(k) for k in FIELDS[kind] if raw.get(k) not in (None, "")}}
                cfg[SECRET_FIELD[kind]] = secret
    except Exception:
        logger.exception("channel_config_read_failed kind=%s", kind)
    _cache[kind] = (time.monotonic(), cfg)
    return cfg


def public_view(kind: str, db=None) -> dict:
    """What Settings shows: every field except the secret, plus whether one is saved."""
    raw = _read_raw(kind, db)
    out = {**DEFAULTS[kind], **{k: raw[k] for k in FIELDS[kind] if k in raw}}
    out["enabled"] = bool(raw.get("enabled"))
    out["secret_set"] = bool(raw.get("secret"))
    out["updated_by"] = raw.get("updated_by") or ""
    out["env_configured"] = _env_configured(kind)
    return out


def _env_configured(kind: str) -> bool:
    if kind == "email":
        return (settings.NOTIFICATION_EMAIL_PROVIDER or "log").lower() not in {"", "log"} and bool(
            settings.SMTP_USERNAME and settings.SMTP_PASSWORD
        )
    return (settings.NOTIFICATION_SMS_PROVIDER or "log").lower() == "msg91" and bool(settings.MSG91_AUTH_KEY)


def save(kind: str, body: dict, *, by: str, db=None) -> dict:
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.app_global_setting import AppGlobalSetting

    own = db is None
    if own:
        db = _session()
    else:
        AppGlobalSetting.__table__.create(bind=db.get_bind(), checkfirst=True)
    try:
        row = db.get(AppGlobalSetting, KEYS[kind])
        raw = dict(row.value) if row and isinstance(row.value, dict) else {}
        for k in FIELDS[kind]:
            if k in body and body[k] is not None:
                v = body[k]
                raw[k] = int(v) if k == "port" else str(v).strip()[:200]
        secret = str(body.get(SECRET_FIELD[kind]) or "").strip()
        if kind == "email":
            secret = secret.replace(" ", "")  # app passwords are shown in groups
        if secret:
            raw["secret"] = _encrypt(secret)
        if body.get("clear_secret"):
            raw.pop("secret", None)
        if "enabled" in body:
            raw["enabled"] = bool(body["enabled"])
        raw["updated_by"] = by
        if row is None:
            row = AppGlobalSetting(key=KEYS[kind], value=raw)
            db.add(row)
        else:
            row.value = raw
            flag_modified(row, "value")
        db.commit()
    finally:
        if own:
            db.close()
    _cache.pop(kind, None)
    return public_view(kind, None if own else db)


def clear_cache() -> None:
    _cache.clear()
