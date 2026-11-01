"""Create a local Mosquitto lab broker for LiveWell (Windows / same Wi-Fi as MG7).

Usage (from repo root or this folder):
  python deploy/mqtt/setup_lab.py
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
LAB_SRC = Path(__file__).resolve().parent / "lab"
RUNTIME = Path(os.environ.get("LIVEWELL_MQTT_RUNTIME") or (Path.home() / "AppData" / "Local" / "LiveWellMqtt"))


def lan_ipv4() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return "127.0.0.1"


def mosquitto_hash(password: str, iterations: int = 101) -> str:
    """Mosquitto 2.0 `$7$` PBKDF2-SHA512 line suffix."""
    salt = os.urandom(12)
    dk = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, iterations, dklen=64)
    b64salt = base64.b64encode(salt).decode("ascii")
    b64hash = base64.b64encode(dk).decode("ascii")
    return f"$7${iterations}${b64salt}${b64hash}"


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if path.is_file():
        existing = path.read_text(encoding="utf-8").splitlines()
    keys = set(updates)
    out: list[str] = []
    seen: set[str] = set()
    for line in existing:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        if m and m.group(1) in keys:
            key = m.group(1)
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    missing = [k for k in updates if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# LiveWell IoT lab (written by deploy/mqtt/setup_lab.py)")
        for key in missing:
            out.append(f"{key}={updates[key]}")
    text = "\n".join(out).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def main() -> int:
    host = lan_ipv4()
    runtime = RUNTIME
    data_dir = runtime / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    hub_user = "mg7_home1"
    ingestor_user = "livewell_ingestor"
    sniffer_user = "lab_sniffer"
    hub_password = os.environ.get("MQTT_HUB_PASSWORD", "mg7_password")
    ingestor_password = secrets.token_urlsafe(16)
    sniffer_password = secrets.token_urlsafe(16)
    ingest_key = secrets.token_urlsafe(32)

    passwd_path = runtime / "passwd"
    acl_src = LAB_SRC / "acl"
    acl_path = runtime / "acl"
    conf_path = runtime / "mosquitto.conf"
    creds_path = runtime / ".credentials.app"
    log_path = runtime / "mosquitto.log"

    passwd_path.write_text(
        "\n".join(
            [
                f"{ingestor_user}:{mosquitto_hash(ingestor_password)}",
                f"{hub_user}:{mosquitto_hash(hub_password)}",
                f"{sniffer_user}:{mosquitto_hash(sniffer_password)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    acl_path.write_text(acl_src.read_text(encoding="utf-8"), encoding="utf-8")
    conf_path.write_text(
        "\n".join(
            [
                "# LiveWell lab: 1883 TLS (MG7 SSL on), 1884 localhost plain, 8883 TLS.",
                "per_listener_settings true",
                "persistence true",
                f"persistence_location {posix(data_dir)}/",
                "log_dest file " + posix(log_path),
                "log_type error",
                "log_type warning",
                "log_type notice",
                "log_type information",
                "connection_messages true",
                "listener 1883",
                "protocol mqtt",
                "allow_anonymous false",
                f"password_file {posix(passwd_path)}",
                f"acl_file {posix(acl_path)}",
                f"certfile {posix(runtime / 'server.crt')}",
                f"keyfile {posix(runtime / 'server.key')}",
                "require_certificate false",
                "tls_version tlsv1.2",
                "listener 1884 127.0.0.1",
                "protocol mqtt",
                "allow_anonymous false",
                f"password_file {posix(passwd_path)}",
                f"acl_file {posix(acl_path)}",
                "listener 8883",
                "protocol mqtt",
                "allow_anonymous false",
                f"password_file {posix(passwd_path)}",
                f"acl_file {posix(acl_path)}",
                f"certfile {posix(runtime / 'server.crt')}",
                f"keyfile {posix(runtime / 'server.key')}",
                "require_certificate false",
                "tls_version tlsv1.2",
                "",
            ]
        ),
        encoding="utf-8",
    )
    creds = {
        "MQTT_PUBLIC_HOST": host,
        "MQTT_PORT": "1883",
        "MQTT_TLS": "0",
        "MQTT_HUB_USER": hub_user,
        "MQTT_HUB_PASSWORD": hub_password,
        "MQTT_INGESTOR_USER": ingestor_user,
        "MQTT_INGESTOR_PASSWORD": ingestor_password,
        "MQTT_SNIFFER_USER": sniffer_user,
        "MQTT_SNIFFER_PASSWORD": sniffer_password,
        "MQTT_TOPIC": "livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status,#",
        "IOT_INGEST_API_KEY": ingest_key,
    }
    creds_path.write_text(
        "\n".join(f"{k}={v}" for k, v in creds.items()) + "\n",
        encoding="utf-8",
    )

    upsert_env(
        BACKEND / ".env",
        {
            "IOT_INGEST_API_KEY": ingest_key,
            "IOT_MQTT_PUBLIC_HOST": host,
            "IOT_MQTT_RUNTIME": str(runtime),
        },
    )
    upsert_env(
        BACKEND / "iot_ingestor.env",
        {
            "MQTT_HOST": "127.0.0.1",
            "MQTT_PORT": "1883",
            "MQTT_TLS": "0",
            "MQTT_USERNAME": ingestor_user,
            "MQTT_PASSWORD": ingestor_password,
            "MQTT_TOPIC": creds["MQTT_TOPIC"],
            "LIVEWELL_API_BASE": "http://127.0.0.1:8010",
            "IOT_INGEST_API_KEY": ingest_key,
            "LOG_LEVEL": "INFO",
        },
    )

    sys.path.insert(0, str(BACKEND))
    from app.core.database import SessionLocal  # noqa: E402
    from app.livewell.iot_broker_settings import save_broker_settings  # noqa: E402

    db = SessionLocal()
    try:
        save_broker_settings(
            db,
            {
                "broker_host": host,
                "broker_port": 1883,
                "tls": False,
                "hub_username": hub_user,
                "hub_password": hub_password,
                "ingestor_username": ingestor_user,
                "ingestor_password": ingestor_password,
                "ingestor_mqtt_topic": creds["MQTT_TOPIC"],
                "topic_mode": "minew_status",
                "use_shared_hub": True,
                "notes": "Lab broker on this PC (plain MQTT :1883). Point MG7 at this host; SSL off.",
            },
        )
    finally:
        db.close()

    print("LiveWell MQTT lab is configured.")
    print(f"  Runtime:     {runtime}")
    print(f"  LAN host:    {host}")
    print(f"  Port:        1883  (plain MQTT, SSL off)")
    print(f"  Hub user:    {hub_user}")
    print(f"  Hub password:{hub_password}")
    print(f"  Credentials: {creds_path}")
    print()
    print("MinewLink (MG7) — same Wi-Fi as this PC:")
    print(f"  Host     = {host}")
    print("  Port     = 1883")
    print("  SSL/TLS  = OFF")
    print(f"  Username = {hub_user}")
    print(f"  Password = {hub_password}")
    print("  Topic    = /mg7/{bandMac}/status   (Minew default; leave if firmware-fixed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
