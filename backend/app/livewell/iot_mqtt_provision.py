"""Run Mosquitto user/ACL updates via privileged helper (sudo) when needed."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import settings


def _apply_script() -> Path:
    configured = (getattr(settings, "IOT_MQTT_APPLY_SCRIPT", None) or "").strip()
    if configured:
        return Path(configured)
    # Production checkout
    prod = Path("/opt/safehomeops/app/scripts/deploy/apply-mqtt-hub-user.sh")
    if prod.is_file():
        return prod
    # Dev / relative to repo (backend/app/livewell → ../../../scripts/...)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "scripts" / "deploy" / "apply-mqtt-hub-user.sh"
        if cand.is_file():
            return cand
    return prod


def provision_hub_user(username: str, password: str) -> dict:
    """Add/update Mosquitto hub user via sudo helper (same pattern as ingestor)."""
    user = (username or "").strip()
    password = password or ""
    if not user:
        return {"ok": False, "detail": "hub username empty"}
    if not password:
        return {"ok": False, "detail": "hub_password empty — save broker settings first"}

    script = _apply_script()
    if not script.is_file():
        return {
            "ok": False,
            "detail": (
                f"hub helper missing: {script} — git pull, then: "
                "sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-sudoers.sh"
            ),
        }

    try:
        r = subprocess.run(
            ["sudo", "-n", str(script), user],
            input=password + "\n",
            capture_output=True,
            text=True,
            timeout=45,
        )
    except FileNotFoundError:
        return {"ok": False, "detail": "sudo not on PATH"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)}

    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    combined = f"{err} {out}".strip()
    if r.returncode == 0:
        detail = out.replace("OK: ", "") if out.startswith("OK:") else (out or "applied via sudo")
        return {"ok": True, "detail": detail}
    if "command not found" in combined.lower() or "no such file" in combined.lower():
        return {
            "ok": False,
            "detail": (
                f"helper missing or not executable: {script} — "
                "chmod 755 the script, then: sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-sudoers.sh"
            ),
        }
    if (
        "password is required" in combined.lower()
        or "a password is required" in combined.lower()
        or "a terminal is required" in combined.lower()
    ):
        return {
            "ok": False,
            "detail": (
                "sudo denied for apply-mqtt-hub-user.sh — as root run: "
                "sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-sudoers.sh"
            ),
        }
    return {"ok": False, "detail": combined or f"exit {r.returncode}"}


def _ingestor_apply_script() -> Path:
    configured = (getattr(settings, "IOT_MQTT_INGESTOR_APPLY_SCRIPT", None) or "").strip()
    if configured:
        return Path(configured)
    prod = Path("/opt/safehomeops/app/scripts/deploy/apply-mqtt-ingestor.sh")
    if prod.is_file():
        return prod
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "scripts" / "deploy" / "apply-mqtt-ingestor.sh"
        if cand.is_file():
            return cand
    return prod


def provision_ingestor_user(
    username: str,
    password: str,
    *,
    mqtt_topic: str | None = None,
    dedupe_seconds: int | None = None,
) -> dict:
    """Update Mosquitto ingestor user, iot_ingestor.env, and restart the unit."""
    user = (username or "").strip() or "livewell_ingestor"
    password = password or ""
    if not password:
        return {"ok": False, "detail": "ingestor_password empty — save broker settings first"}

    topic = (mqtt_topic or "").strip() or (
        "livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status"
    )
    try:
        dedupe = int(dedupe_seconds if dedupe_seconds is not None else 65)
    except (TypeError, ValueError):
        dedupe = 65
    dedupe = max(1, min(3600, dedupe))

    script = _ingestor_apply_script()
    if not script.is_file():
        return {"ok": False, "detail": f"ingestor helper missing: {script}"}

    try:
        r = subprocess.run(
            ["sudo", "-n", str(script), user],
            input=f"{password}\n{topic}\n{dedupe}\n",
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return {"ok": False, "detail": "sudo not on PATH"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)}

    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    combined = f"{err} {out}".strip()
    if r.returncode == 0:
        detail = out.replace("OK: ", "") if out.startswith("OK:") else (out or "ingestor applied")
        return {"ok": True, "detail": detail}
    if "password is required" in combined.lower() or "a terminal is required" in combined.lower():
        return {
            "ok": False,
            "detail": (
                "sudo denied for apply-mqtt-ingestor.sh — as root run: "
                "sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-sudoers.sh"
            ),
        }
    return {"ok": False, "detail": combined or f"exit {r.returncode}"}


def apply_broker_mqtt(broker: dict) -> dict:
    """Apply hub + ingestor credentials from Wearables broker settings."""
    parts: list[str] = []
    ok = True

    hub = provision_hub_user(
        str(broker.get("hub_username") or ""),
        str(broker.get("hub_password") or ""),
    )
    parts.append(f"hub: {hub.get('detail')}")
    if not hub.get("ok"):
        ok = False

    ingest_pw = str(broker.get("ingestor_password") or "")
    if ingest_pw:
        try:
            dedupe = int(broker.get("dedupe_seconds") or 65)
        except (TypeError, ValueError):
            dedupe = 65
        ing = provision_ingestor_user(
            str(broker.get("ingestor_username") or "livewell_ingestor"),
            ingest_pw,
            mqtt_topic=str(broker.get("ingestor_mqtt_topic") or ""),
            dedupe_seconds=dedupe,
        )
        parts.append(f"ingestor: {ing.get('detail')}")
        if not ing.get("ok"):
            ok = False
    else:
        parts.append("ingestor: skipped (no password saved)")

    return {"ok": ok, "detail": "; ".join(parts)}
