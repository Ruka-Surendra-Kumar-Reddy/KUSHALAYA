#!/usr/bin/env bash
# Allow safehomeops to restart its own systemd units without a password.
# Run once as root:
#   sudo bash scripts/deploy/install-safehome-sudoers.sh

set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "ERROR: Run as root: sudo bash $0" >&2
  exit 1
}

APP_ROOT="${APP_ROOT:-/opt/safehomeops/app}"
MQTT_APPLY="${APP_ROOT}/scripts/deploy/apply-mqtt-hub-user.sh"
MQTT_INGESTOR_APPLY="${APP_ROOT}/scripts/deploy/apply-mqtt-ingestor.sh"

DEST=/etc/sudoers.d/safehomeops
cat >"$DEST" <<EOF
# SafeHomeOps — app user may restart its own services after build
safehomeops ALL=(root) NOPASSWD: /usr/bin/systemctl restart safehomeops-api, /usr/bin/systemctl restart safehomeops-web, /usr/bin/systemctl restart safehomeops-iot-ingestor, /usr/bin/systemctl restart safehomeops-api safehomeops-web, /usr/bin/systemctl restart safehomeops-web safehomeops-api, /usr/bin/systemctl restart safehomeops-api safehomeops-web safehomeops-iot-ingestor, /usr/bin/systemctl status safehomeops-api, /usr/bin/systemctl status safehomeops-web, /usr/bin/systemctl status safehomeops-iot-ingestor, /usr/bin/systemctl status safehomeops-api safehomeops-web, /usr/bin/systemctl status safehomeops-api safehomeops-web safehomeops-iot-ingestor, /usr/bin/systemctl is-active safehomeops-api, /usr/bin/systemctl is-active safehomeops-web, /usr/bin/systemctl is-active safehomeops-iot-ingestor
# Wearables → Apply to Mosquitto (hub + ingestor)
safehomeops ALL=(root) NOPASSWD: ${MQTT_APPLY} *
safehomeops ALL=(root) NOPASSWD: ${MQTT_INGESTOR_APPLY} *
EOF
chmod 440 "$DEST"
visudo -cf "$DEST"
if [[ -f "$MQTT_APPLY" ]]; then
  chmod 755 "$MQTT_APPLY"
fi
if [[ -f "$MQTT_INGESTOR_APPLY" ]]; then
  chmod 755 "$MQTT_INGESTOR_APPLY"
fi
echo "==> Installed $DEST"
echo "    Test as safehomeops: sudo -n systemctl restart safehomeops-api safehomeops-web safehomeops-iot-ingestor"
echo "    Hub apply:      printf 'pw' | sudo -n ${MQTT_APPLY} mg7_home1"
echo "    Ingestor apply: printf 'pw' | sudo -n ${MQTT_INGESTOR_APPLY} livewell_ingestor"
