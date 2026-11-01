#!/usr/bin/env bash
# One-shot LiveWell IoT install: Mosquitto + ingest API key + ingestor systemd unit.
# Idempotent: safe to re-run (preserves MQTT passwords + device map unless overridden).
#
#   sudo -iu safehomeops
#   cd /opt/safehomeops/app && git pull
#   sudo bash scripts/deploy/install-livewell-iot.sh \
#     --elder-map '{"aa:bb:cc:dd:ee:ff":42}'
#
set -euo pipefail

[[ ${EUID:-0} -eq 0 ]] || {
  echo "ERROR: Run as root via sudo from the safehomeops checkout:" >&2
  echo "  sudo -iu safehomeops" >&2
  echo "  cd /opt/safehomeops/app && sudo bash scripts/deploy/install-livewell-iot.sh ..." >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MQTT_ARGS=()
INGESTOR_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --elder-map)
      INGESTOR_ARGS+=(--elder-map "$2")
      shift 2
      ;;
    --docker)
      MQTT_ARGS+=(--docker)
      shift
      ;;
    --skip-firewall|--force-passwords)
      MQTT_ARGS+=("$1")
      shift
      ;;
    --skip-restart-api)
      INGESTOR_ARGS+=("$1")
      shift
      ;;
    --app-root)
      export APP_ROOT="$2"
      MQTT_ARGS+=(--app-root "$2")
      INGESTOR_ARGS+=(--app-root "$2")
      shift 2
      ;;
    --runtime-dir)
      export MQTT_RUNTIME="$2"
      MQTT_ARGS+=(--runtime-dir "$2")
      INGESTOR_ARGS+=(--runtime-dir "$2")
      shift 2
      ;;
    --domain)
      export APP_DOMAIN="$2"
      MQTT_ARGS+=(--domain "$2")
      shift 2
      ;;
    -h|--help)
      sed -n '1,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

echo "==> [1/2] Mosquitto (native package by default; runtime ${MQTT_RUNTIME:-/var/lib/safehomeops/mqtt})"
bash "${SCRIPT_DIR}/install-livewell-mqtt.sh" ${MQTT_ARGS[@]+"${MQTT_ARGS[@]}"}

echo "==> [2/2] IoT ingestor"
bash "${SCRIPT_DIR}/install-livewell-iot-ingestor.sh" ${INGESTOR_ARGS[@]+"${INGESTOR_ARGS[@]}"}

ROOT="${APP_ROOT:-/opt/safehomeops/app}"
RUNTIME="${MQTT_RUNTIME:-/var/lib/safehomeops/mqtt}"
echo ""
echo "==> LiveWell IoT install finished."
echo "    Runbook:  ${ROOT}/deploy/mqtt/SERVER_SETUP.md"
echo "    Runtime:  ${RUNTIME}"
echo "    Secrets:  ${RUNTIME}/.credentials.app  (readable as safehomeops)"
echo "    Logs:     journalctl -u safehomeops-iot-ingestor -f"
