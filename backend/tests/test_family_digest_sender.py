"""Family digest delivery job — uses the log providers."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import app.models  # noqa: F401

from app.core.rbac import ELDER_PORTAL
from app.core.security import hash_password
from app.livewell import family_digest_sender as fds
from app.livewell.family_care_hub import FamilyCareHubService
from app.models.elder import Elder
from app.models.user import User
from app.services.notifications import clear_provider_cache

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _log_providers():
    from app.core.config import settings

    settings.NOTIFICATION_EMAIL_PROVIDER = "log"
    settings.NOTIFICATION_WHATSAPP_PROVIDER = "log"
    clear_provider_cache()
    yield
    clear_provider_cache()


def _household(db, seed_tenant, *, phone="9876543210", prefs=None):
    tenant = seed_tenant["tenant"]
    elder = Elder(
        tenant_id=tenant.id,
        first_name="Lakshmi",
        last_name="Digest",
        status="ACTIVE",
        emergency_contact_phone=phone,
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    user = User(
        email=f"family.digest.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Family",
        last_name="Digest",
        role=ELDER_PORTAL,
        tenant_id=tenant.id,
        elder_id=elder.id,
        portal_relationship="daughter",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if prefs:
        FamilyCareHubService.update_prefs(db, user, prefs)
        db.refresh(elder)
    return elder, user


def _prefs(elder):
    return (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {}).get("prefs", {})


def test_latest_send_slot_daily_and_weekly():
    # Wednesday 2026-09-30 10:00 IST
    now = datetime(2026, 9, 30, 10, 0, tzinfo=IST)
    daily = fds.latest_send_slot("daily", "Asia/Kolkata", now)
    assert daily.astimezone(IST) == datetime(2026, 9, 30, 8, 0, tzinfo=IST)
    weekly = fds.latest_send_slot("weekly", "Asia/Kolkata", now)
    assert weekly.astimezone(IST) == datetime(2026, 9, 28, 8, 0, tzinfo=IST)  # Monday

    # Before 08:00 local the slot is the previous day.
    early = datetime(2026, 9, 30, 7, 30, tzinfo=IST)
    assert fds.latest_send_slot("daily", "Asia/Kolkata", early).astimezone(IST) == datetime(
        2026, 9, 29, 8, 0, tzinfo=IST
    )
    # Unknown timezone falls back to Asia/Kolkata rather than failing the batch.
    assert fds.latest_send_slot("daily", "Mars/Olympus", now) == daily


def test_digest_is_due_rules():
    now = datetime(2026, 9, 30, 10, 0, tzinfo=IST)
    base = {"digest_enabled": True, "digest_channel": "whatsapp", "digest_cadence": "daily", "digest_timezone": "Asia/Kolkata"}
    assert fds.digest_is_due(base, now)
    assert not fds.digest_is_due({**base, "digest_enabled": False}, now)
    assert not fds.digest_is_due({**base, "digest_channel": "none"}, now)
    sent_today = datetime(2026, 9, 30, 8, 5, tzinfo=IST).isoformat()
    assert not fds.digest_is_due({**base, fds.LAST_SENT_KEY: sent_today}, now)
    sent_yesterday = datetime(2026, 9, 29, 8, 5, tzinfo=IST).isoformat()
    assert fds.digest_is_due({**base, fds.LAST_SENT_KEY: sent_yesterday}, now)
    # Weekly, sent this Monday already → not due on Wednesday.
    monday = datetime(2026, 9, 28, 8, 10, tzinfo=IST).isoformat()
    assert not fds.digest_is_due({**base, "digest_cadence": "weekly", fds.LAST_SENT_KEY: monday}, now)


def test_daily_whatsapp_digest_sent_once_per_slot(db, seed_tenant):
    elder, user = _household(
        db, seed_tenant, prefs={"digest_cadence": "daily", "digest_channel": "whatsapp"}
    )
    now = datetime(2026, 9, 30, 10, 0, tzinfo=IST).astimezone(timezone.utc)

    result = fds.run_family_digest_send(db, tenant_id=elder.tenant_id, now=now)
    assert result["digests_due"] >= 1
    mine = [d for d in result["deliveries"] if d["elder_id"] == elder.id]
    assert len(mine) == 1
    assert mine[0]["status"] == "LOGGED"
    assert mine[0]["channel"] == "whatsapp"
    assert mine[0]["recipients"] == ["919876543210"]

    db.refresh(elder)
    prefs = _prefs(elder)
    assert prefs[fds.LAST_SENT_KEY] == now.isoformat()
    assert prefs[fds.LAST_RESULT_KEY]["status"] == "LOGGED"
    assert prefs[fds.LAST_RESULT_KEY]["recipients"] == ["919876543210"]
    # Original preferences survive the write.
    assert prefs["digest_cadence"] == "daily"
    assert FamilyCareHubService.get_prefs(db, user)["digest_cadence"] == "daily"

    # Same slot again → nothing more sent (idempotent).
    again = fds.run_family_digest_send(db, tenant_id=elder.tenant_id, now=now + timedelta(hours=1))
    assert not [d for d in again["deliveries"] if d["elder_id"] == elder.id]

    # Next day's slot → sent again.
    tomorrow = now + timedelta(days=1)
    third = fds.run_family_digest_send(db, tenant_id=elder.tenant_id, now=tomorrow)
    assert [d for d in third["deliveries"] if d["elder_id"] == elder.id]


def test_whatsapp_without_phone_falls_back_to_family_email(db, seed_tenant):
    elder, user = _household(
        db, seed_tenant, phone=None, prefs={"digest_cadence": "daily", "digest_channel": "whatsapp"}
    )
    now = datetime(2026, 9, 30, 10, 0, tzinfo=IST).astimezone(timezone.utc)
    delivery = fds.send_digest_for_elder(db, elder, now=now)
    assert delivery is not None
    assert delivery.channel == "email"
    assert delivery.status == "LOGGED"
    assert delivery.recipients == [user.email]


def test_email_channel_and_weekly_not_due_midweek(db, seed_tenant):
    elder, user = _household(
        db, seed_tenant, prefs={"digest_cadence": "weekly", "digest_channel": "email"}
    )
    monday = datetime(2026, 9, 28, 9, 0, tzinfo=IST).astimezone(timezone.utc)
    delivery = fds.send_digest_for_elder(db, elder, now=monday)
    assert delivery is not None and delivery.channel == "email"
    assert delivery.recipients == [user.email]

    wednesday = datetime(2026, 9, 30, 9, 0, tzinfo=IST).astimezone(timezone.utc)
    db.refresh(elder)
    assert fds.send_digest_for_elder(db, elder, now=wednesday) is None


def test_disabled_digest_never_sends(db, seed_tenant):
    elder, _ = _household(db, seed_tenant, prefs={"digest_enabled": False, "digest_cadence": "daily"})
    now = datetime(2026, 9, 30, 10, 0, tzinfo=IST).astimezone(timezone.utc)
    assert fds.send_digest_for_elder(db, elder, now=now) is None


def test_job_handler_registered():
    import app.jobs.handlers as handlers
    from workforceos_core.jobs.registry import known_job_types

    assert handlers.JOB_FAMILY_DIGEST_SEND in known_job_types()
