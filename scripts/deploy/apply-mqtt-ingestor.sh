#!/usr/bin/env bash
# Privileged helper: set Mosquitto ingestor user + sync iot_ingestor.env + restart unit.
# Stdin line 1 = password; line 2 (optional) = MQTT_TOPIC; line 3 (optional) = IOT_DEDUPE_SECONDS
#
#   printf '%s\n%s\n%s\n' "$PW" "$TOPIC" "$DEDUPE" | sudo -n apply-mqtt-ingestor.sh livewell_ingestor

set -euo pipefail

MQTT_RUNTIME="${MQTT_RUNTIME:-/var/lib/safehomeops/mqtt}"
PASSWD_FILE="${MQTT_RUNTIME}/passwd"
ACL_FILE="${MQTT_RUNTIME}/acl"
APP_ROOT="${APP_ROOT:-/opt/safehomeops/app}"
INGESTOR_ENV="${IOT_INGESTOR_ENV:-${APP_ROOT}/backend/iot_ingestor.env}"
CRED_APP="${MQTT_RUNTIME}/.credentials.app"
CRED_ROOT="${MQTT_RUNTIME}/.credentials"
UNIT="${IOT_INGESTOR_UNIT:-safehomeops-iot-ingestor}"
DEFAULT_TOPIC='livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status'
DEFAULT_DEDUPE=65

[[ $EUID -eq 0 ]] || {
  echo "ERROR: must run as root (via sudo -n from safehomeops)" >&2
  exit 1
}

user="${1:-livewell_ingestor}"
if [[ -z "$user" || ! "$user" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$ ]]; then
  echo "ERROR: usage: $0 <mqtt_username>" >&2
  exit 2
fi

IFS= read -r password || true
IFS= read -r topic || true
IFS= read -r dedupe || true
if [[ -z "${password:-}" ]]; then
  echo "ERROR: password required on stdin (line 1)" >&2
  exit 3
fi
topic="${topic:-$DEFAULT_TOPIC}"
topic="${topic//$'\r'/}"
topic="${topic//$'\n'/}"
if [[ -z "$topic" || ${#topic} -gt 500 || "$topic" == *[[:space:]]* ]]; then
  echo "ERROR: invalid MQTT_TOPIC" >&2
  exit 5
fi
dedupe="${dedupe:-$DEFAULT_DEDUPE}"
dedupe="${dedupe//$'\r'/}"
if ! [[ "$dedupe" =~ ^[0-9]+$ ]] || [[ "$dedupe" -lt 1 || "$dedupe" -gt 3600 ]]; then
  echo "ERROR: invalid IOT_DEDUPE_SECONDS (1-3600)" >&2
  exit 6
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
detail="passwd updated"

# Read-only ACL for ingestor (idempotent)
need_acl=1
if [[ -f "$ACL_FILE" ]]; then
  block="$(awk -v u="user ${user}" '
    $0 == u {p=1; next}
    p && /^user / {exit}
    p {print}
  ' "$ACL_FILE" 2>/dev/null || true)"
  if grep -q 'livewell/#' <<<"$block" 2>/dev/null && grep -q '/mg7/#' <<<"$block" 2>/dev/null; then
    need_acl=0
  fi
fi

if [[ "$need_acl" -eq 1 ]]; then
  cat >>"$ACL_FILE" <<EOF

# ingestor from Wearables / apply-mqtt-ingestor.sh
user ${user}
topic read livewell/#
topic read mg7/#
topic read /mg7/#
EOF
  detail="${detail}; acl appended"
else
  detail="${detail}; acl ok"
fi

mq_user=mosquitto
getent passwd mosquitto >/dev/null 2>&1 || mq_user=root
chown "${mq_user}:${mq_user}" "$PASSWD_FILE" 2>/dev/null || true
chmod 640 "$PASSWD_FILE" 2>/dev/null || true
chown "${mq_user}:${mq_user}" "$ACL_FILE" 2>/dev/null || true
chmod 644 "$ACL_FILE" 2>/dev/null || true

# Sync iot_ingestor.env (MQTT_USERNAME / MQTT_PASSWORD / MQTT_TOPIC / IOT_DEDUPE_SECONDS)
if [[ -f "$INGESTOR_ENV" ]]; then
  tmp="$(mktemp)"
  awk -v u="$user" -v p="$password" -v t="$topic" -v d="$dedupe" '
    BEGIN { u_set=0; p_set=0; t_set=0; d_set=0 }
    /^MQTT_USERNAME=/ { print "MQTT_USERNAME=" u; u_set=1; next }
    /^MQTT_PASSWORD=/ { print "MQTT_PASSWORD=" p; p_set=1; next }
    /^MQTT_TOPIC=/ { print "MQTT_TOPIC=" t; t_set=1; next }
    /^IOT_DEDUPE_SECONDS=/ { print "IOT_DEDUPE_SECONDS=" d; d_set=1; next }
    { print }
    END {
      if (!u_set) print "MQTT_USERNAME=" u
      if (!p_set) print "MQTT_PASSWORD=" p
      if (!t_set) print "MQTT_TOPIC=" t
      if (!d_set) print "IOT_DEDUPE_SECONDS=" d
    }
  ' "$INGESTOR_ENV" >"$tmp"
  owner="$(stat -c '%U:%G' "$INGESTOR_ENV" 2>/dev/null || echo "safehomeops:safehomeops")"
  install -o "${owner%%:*}" -g "${owner##*:}" -m 600 "$tmp" "$INGESTOR_ENV"
  rm -f "$tmp"
  detail="${detail}; iot_ingestor.env updated"
else
  detail="${detail}; iot_ingestor.env missing (${INGESTOR_ENV})"
fi

_sync_cred_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local tmp
  tmp="$(mktemp)"
  awk -v u="$user" -v p="$password" '
    /^MQTT_INGESTOR_USER=/ { print "MQTT_INGESTOR_USER=" u; next }
    /^MQTT_INGESTOR_PASSWORD=/ { print "MQTT_INGESTOR_PASSWORD=" p; next }
    { print }
  ' "$f" >"$tmp"
  cat "$tmp" >"$f"
  rm -f "$tmp"
  chmod 600 "$f" 2>/dev/null || true
}

_sync_cred_file "$CRED_APP"
_sync_cred_file "$CRED_ROOT"
[[ -f "$CRED_APP" ]] && chown safehomeops:safehomeops "$CRED_APP" 2>/dev/null || true

if systemctl reload mosquitto 2>/dev/null; then
  detail="${detail}; mosquitto reloaded"
elif systemctl restart mosquitto 2>/dev/null; then
  detail="${detail}; mosquitto restarted"
else
  detail="${detail}; mosquitto reload skipped"
fi

if systemctl restart "$UNIT" 2>/dev/null; then
  detail="${detail}; ${UNIT} restarted"
else
  detail="${detail}; ${UNIT} restart skipped"
fi

echo "OK: ${detail}"
