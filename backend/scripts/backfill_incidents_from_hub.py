"""One-off: create care_incidents rows from the legacy family_hub JSON incidents.

Idempotent — an incident whose ``legacy_id`` already exists is skipped. Also
collapses duplicate *open* ``device_offline`` alerts/incidents in the JSON
(keeps the newest per elder), which is where the "99 identical alerts" came from.

Run from backend/ with the app's environment (DATABASE_URL etc.):

    .venv/Scripts/python.exe scripts/backfill_incidents_from_hub.py            # dry run
    .venv/Scripts/python.exe scripts/backfill_incidents_from_hub.py --apply    # write

Never run against production without a DB backup and a dry run first.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

import app.models  # noqa: F401,E402 — register tables
from app.core.database import SessionLocal  # noqa: E402
from app.models.elder import Elder  # noqa: E402
from app.models.incident import COLLAPSE_KINDS, Incident, IncidentEvent  # noqa: E402

LEGACY_KIND_MAP = {
    "possible_fall": "fall",
    "immobility": "immobility",
    "device_offline": "device_offline",
    "battery_low": "battery_low",
}
JSON_KIND_FOR_DB = {"device_offline": "device_offline", "battery_low": "battery_low"}


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            dt = datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _db_kind(row: dict) -> str:
    kind = str(row.get("kind") or "sos").lower()
    if kind == "sos":
        created_by = str(row.get("created_by") or "")
        legacy = str(row.get("id") or "")
        if created_by.startswith("iot:") or legacy.startswith("dsos"):
            return "sos_button"
        return "family_sos"
    return LEGACY_KIND_MAP.get(kind, "other")


def _severity(kind: str) -> str:
    return "critical" if kind in ("sos_button", "family_sos") else "warning"


def _source(row: dict, kind: str) -> str:
    if kind == "family_sos":
        return "family"
    return "device" if str(row.get("created_by") or "").startswith("iot:") or row.get("mac_address") else "staff"


def backfill(db: Session, *, apply: bool) -> dict[str, int]:
    counts = {
        "elders_scanned": 0,
        "incidents_seen": 0,
        "incidents_created": 0,
        "incidents_skipped_existing": 0,
        "json_offline_incidents_collapsed": 0,
        "json_offline_alerts_collapsed": 0,
    }
    existing = {
        (elder_id, legacy)
        for elder_id, legacy in db.query(Incident.elder_id, Incident.legacy_id).filter(Incident.legacy_id.isnot(None))
    }
    for elder in db.query(Elder).order_by(Elder.id).all():
        attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
        sh = attrs.get("safe_home") if isinstance(attrs.get("safe_home"), dict) else None
        hub = sh.get("family_hub") if sh and isinstance(sh.get("family_hub"), dict) else None
        if not hub:
            continue
        counts["elders_scanned"] += 1
        incidents = [i for i in (hub.get("incidents") or []) if isinstance(i, dict)]
        alerts = [a for a in (hub.get("alerts") or []) if isinstance(a, dict)]

        # --- collapse duplicate open offline/battery rows in the JSON (keep newest) ---
        incidents.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        kept: list[dict] = []
        seen_open_kind: set[str] = set()
        dropped_ids: set[str] = set()
        for row in incidents:
            kind = str(row.get("kind") or "").lower()
            is_open = str(row.get("status") or "open").lower() not in ("resolved", "closed")
            if kind in JSON_KIND_FOR_DB and is_open:
                if kind in seen_open_kind:
                    dropped_ids.add(str(row.get("id")))
                    counts["json_offline_incidents_collapsed"] += 1
                    continue
                seen_open_kind.add(kind)
            kept.append(row)
        alerts_kept = []
        for a in alerts:
            if str(a.get("incident_id") or "") in dropped_ids:
                counts["json_offline_alerts_collapsed"] += 1
                continue
            alerts_kept.append(a)
        json_changed = len(kept) != len(incidents) or len(alerts_kept) != len(alerts)

        # --- create DB rows ---
        for row in kept:
            legacy = str(row.get("id") or "").strip()
            if not legacy:
                continue
            counts["incidents_seen"] += 1
            if (elder.id, legacy) in existing:
                counts["incidents_skipped_existing"] += 1
                continue
            kind = _db_kind(row)
            status = str(row.get("status") or "open").lower()
            if status not in ("open", "resolved", "closed"):
                status = "open"
            opened_at = _parse_dt(row.get("created_at"))
            resolved_at = _parse_dt(row["resolved_at"]) if row.get("resolved_at") else None
            inc = Incident(
                tenant_id=elder.tenant_id,
                elder_id=elder.id,
                kind=kind,
                severity=_severity(kind),
                status=status,
                source=_source(row, kind),
                device_mac=(row.get("mac_address") or None),
                hub_key=(row.get("hub_id") or None),
                note=str(row.get("note") or "")[:2000] or None,
                opened_at=opened_at,
                resolved_at=resolved_at if status != "open" else None,
                resolved_by_label=str(row.get("resolved_by") or "")[:255] or None if status != "open" else None,
                outcome=("family_resolved" if status != "open" else None),
                legacy_id=legacy[:64],
                escalation_level=0,
            )
            counts["incidents_created"] += 1
            existing.add((elder.id, legacy))
            if apply:
                db.add(inc)
                db.flush()
                db.add(
                    IncidentEvent(
                        incident_id=inc.id,
                        at=opened_at,
                        event="received",
                        detail="backfilled from family_hub JSON",
                    )
                )
                if status != "open":
                    db.add(
                        IncidentEvent(
                            incident_id=inc.id,
                            at=resolved_at or opened_at,
                            event=status,
                            detail=f"backfilled: resolved_by={row.get('resolved_by') or 'unknown'}",
                        )
                    )
        if apply and json_changed:
            hub["incidents"] = kept
            hub["alerts"] = alerts_kept
            sh["family_hub"] = hub
            attrs["safe_home"] = sh
            elder.custom_attributes = attrs
            flag_modified(elder, "custom_attributes")
    if apply:
        db.commit()
    else:
        db.rollback()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    args = parser.parse_args()
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL not set — refusing to guess a database.", file=sys.stderr)
        sys.exit(2)
    db = SessionLocal()
    try:
        counts = backfill(db, apply=args.apply)
    finally:
        db.close()
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] backfill_incidents_from_hub")
    for key, value in counts.items():
        print(f"  {key:36s} {value}")
    if not args.apply:
        print("Re-run with --apply to write.")


if __name__ == "__main__":
    main()
