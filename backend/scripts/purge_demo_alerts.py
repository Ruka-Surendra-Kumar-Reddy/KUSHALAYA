"""Data fix: collapse duplicate "wearable offline" alerts in a family hub.

A gateway that flaps raises DEVICE_OFFLINE repeatedly, and every raise pushes
another alert onto ``elder.custom_attributes.safe_home.family_hub.alerts``.
The demo elder ended up with the same "Wearable not heard" card dozens of
times. This keeps the newest alert of each identical (title, body) pair and
drops the rest. Other alert kinds are never touched.

Idempotent: a second run finds nothing to remove.

Usage (from backend/, with the venv active):
    python -m scripts.purge_demo_alerts --tenant-id 1                 # dry run, all elders
    python -m scripts.purge_demo_alerts --tenant-id 1 --elder-id 12   # dry run, one elder
    python -m scripts.purge_demo_alerts --tenant-id 1 --apply         # write changes
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.models.elder import Elder

DEVICE_OFFLINE_KIND = "device_offline"
# Titles pushed by IotIngestService for DEVICE_OFFLINE (brand-rewritten at runtime,
# so match on the phrase, not the whole string).
DEVICE_OFFLINE_TITLE_MARKERS = ("wearable not heard", "wearable offline", "alert band not checking in")


def _parse_dt(value) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _hub_of(elder: Elder) -> tuple[dict, dict, dict]:
    attrs = dict(elder.custom_attributes or {})
    block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
    hub = dict(block.get("family_hub") or {}) if isinstance(block.get("family_hub"), dict) else {}
    return attrs, block, hub


def is_device_offline_alert(alert: dict, incident_kinds: dict[str, str]) -> bool:
    if not isinstance(alert, dict):
        return False
    incident_id = str(alert.get("incident_id") or "")
    if incident_id and incident_kinds.get(incident_id) == DEVICE_OFFLINE_KIND:
        return True
    if str(alert.get("kind") or "").lower() == DEVICE_OFFLINE_KIND:
        return True
    title = str(alert.get("title") or "").lower()
    return any(marker in title for marker in DEVICE_OFFLINE_TITLE_MARKERS)


def dedupe_device_offline_alerts(alerts: list, incident_kinds: dict[str, str]) -> tuple[list, int]:
    """Return (kept alerts in original order, removed count).

    Among device-offline alerts with the same title and body, the newest by
    ``created_at`` survives. Everything else is kept as-is.
    """
    newest_per_key: dict[tuple[str, str], tuple[datetime, int]] = {}
    for idx, alert in enumerate(alerts):
        if not is_device_offline_alert(alert, incident_kinds):
            continue
        key = (str(alert.get("title") or ""), str(alert.get("body") or ""))
        when = _parse_dt(alert.get("created_at"))
        current = newest_per_key.get(key)
        # Ties keep the earlier list position (the list is newest-first).
        if current is None or when > current[0]:
            newest_per_key[key] = (when, idx)

    keep_idx = {idx for _, idx in newest_per_key.values()}
    kept: list = []
    removed = 0
    for idx, alert in enumerate(alerts):
        if is_device_offline_alert(alert, incident_kinds) and idx not in keep_idx:
            removed += 1
            continue
        kept.append(alert)
    return kept, removed


def purge_elder(db: Session, elder: Elder, *, apply: bool) -> dict:
    attrs, block, hub = _hub_of(elder)
    alerts = list(hub.get("alerts") or []) if isinstance(hub.get("alerts"), list) else []
    incidents = list(hub.get("incidents") or []) if isinstance(hub.get("incidents"), list) else []
    incident_kinds = {
        str(i.get("id")): str(i.get("kind") or "").lower()
        for i in incidents
        if isinstance(i, dict) and i.get("id")
    }
    offline_before = sum(1 for a in alerts if is_device_offline_alert(a, incident_kinds))
    kept, removed = dedupe_device_offline_alerts(alerts, incident_kinds)
    if apply and removed:
        hub["alerts"] = kept
        block["family_hub"] = hub
        attrs["safe_home"] = block
        elder.custom_attributes = attrs
        flag_modified(elder, "custom_attributes")
    return {
        "elder_id": elder.id,
        "name": f"{elder.first_name} {elder.last_name}".strip(),
        "alerts_before": len(alerts),
        "device_offline_before": offline_before,
        "removed": removed,
        "alerts_after": len(kept),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--elder-id", type=int, default=None)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        q = db.query(Elder).filter(Elder.tenant_id == args.tenant_id)
        if args.elder_id is not None:
            q = q.filter(Elder.id == args.elder_id)
        elders = q.order_by(Elder.id).all()
        if not elders:
            print("No matching elders.")
            return 1

        total_removed = 0
        for elder in elders:
            report = purge_elder(db, elder, apply=args.apply)
            total_removed += report["removed"]
            print(
                f"elder #{report['elder_id']} {report['name']}: "
                f"{report['alerts_before']} alert(s), "
                f"{report['device_offline_before']} device-offline, "
                f"{report['removed']} duplicate(s) "
                + ("removed" if args.apply else "would be removed")
                + f", {report['alerts_after']} remain"
            )

        if args.apply:
            db.commit()
            print(f"Applied: {total_removed} alert(s) removed across {len(elders)} elder(s).")
        else:
            print(f"Dry run: {total_removed} alert(s) would be removed. Re-run with --apply.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
