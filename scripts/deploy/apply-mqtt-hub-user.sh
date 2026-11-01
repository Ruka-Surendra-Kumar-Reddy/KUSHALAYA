#!/usr/bin/env bash
# Privileged helper: add/update one Mosquitto hub user + ensure /mg7 ACL, then reload.
# Invoked by the API as: sudo -n apply-mqtt-hub-user.sh <username>
# Password is read from stdin (first line). Run install-safehome-sudoers.sh once as root.
#
# Usage (as root or via sudo -n):
#   printf '%s\n' "$HUB_PASSWORD" | sudo -n /opt/safehomeops/app/scripts/deploy/apply-mqtt-hub-user.sh mg7_home1

set -euo pipefail

MQTT_RUNTIME="${MQTT_RUNTIME:-/var/lib/safehomeops/mqtt}"
PASSWD_FILE="${MQTT_RUNTIME}/passwd"
ACL_FILE="${MQTT_RUNTIME}/acl"

[[ $EUID -eq 0 ]] || {
  echo "ERROR: must run as root (via sudo -n from safehomeops)" >&2
  exit 1
}

user="${1:-}"
if [[ -z "$user" || ! "$user" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$ ]]; then
  echo "ERROR: usage: $0 <mqtt_username>" >&2
  exit 2
fi

IFS= read -r password || true
if [[ -z "${password:-}" ]]; then
  echo "ERROR: password required on stdin" >&2
  exit 3
fi

command -v mosquitto_passwd >/dev/null 2>&1 || {
  echo "ERROR: mosquitto_passwd not on PATH" >&2
  exit 4
}

mkdir -p "$MQTT_RUNTIME"
if [[ ! -f "$PASSWD_FILE" ]]; then
  touch "$PASSWD_FILE"
  chmod 640 "$PASSWD_FILE"
fi

mosquitto_passwd -b "$PASSWD_FILE" "$user" "$password"

# Ensure ACL allows Minew /mg7 topics for this user (idempotent append).
need_acl=1
if [[ -f "$ACL_FILE" ]]; then
  # After this user's block, before next "user " line — look for /mg7/#
  block="$(awk -v u="user ${user}" '
    $0 == u {p=1; next}
    p && /^user / {exit}
    p {print}
  ' "$ACL_FILE" 2>/dev/null || true)"
  if grep -q '/mg7/#' <<<"$block" 2>/dev/null; then
    need_acl=0
  fi
fi

if [[ "$need_acl" -eq 1 ]]; then
  cat >>"$ACL_FILE" <<EOF

# shared hub from Wearables / apply-mqtt-hub-user.sh
user ${user}
topic write /mg7/#
topic write mg7/#
topic read /mg7/#
topic read mg7/#
topic write livewell/homes/+/hubs/+/ble
topic read livewell/homes/+/hubs/+/ble
EOF
fi

mq_user=mosquitto
getent passwd mosquitto >/dev/null 2>&1 || mq_user=root
chown "${mq_user}:${mq_user}" "$PASSWD_FILE" 2>/dev/null || true
chmod 640 "$PASSWD_FILE" 2>/dev/null || true
chown "${mq_user}:${mq_user}" "$ACL_FILE" 2>/dev/null || true
chmod 644 "$ACL_FILE" 2>/dev/null || true

detail="passwd updated"
if [[ "$need_acl" -eq 1 ]]; then
  detail="${detail}; acl appended"
else
  detail="${detail}; acl already has /mg7"
fi

if systemctl reload mosquitto 2>/dev/null; then
  detail="${detail}; mosquitto reloaded"
elif systemctl restart mosquitto 2>/dev/null; then
  detail="${detail}; mosquitto restarted"
else
  echo "WARN: could not reload/restart mosquitto (passwd/acl updated)" >&2
  detail="${detail}; mosquitto reload skipped"
fi

echo "OK: ${detail}"
