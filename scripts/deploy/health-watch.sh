#!/usr/bin/env bash
# Health watch — run by safehomeops-health-watch.timer every 5 minutes on the VM.
#
# Curls the readiness endpoint locally (http://127.0.0.1:8010/health/ready) and
# on the public host (https://ops.kushalaya.com/health/ready, which also proves
# nginx + TLS). On a change of state it emails using the SMTP_* settings the
# app already has in backend/.env — read with a safe KEY=VALUE loader, never
# printed, never passed on a command line.
#
#   bash scripts/deploy/health-watch.sh            # one check (runs as safehomeops from the timer)
#   bash scripts/deploy/health-watch.sh --test     # send a test email now
#
# Behaviour:
#   OK  -> FAIL   email "DOWN"   (after HEALTH_WATCH_FAILS consecutive failures, default 2 = ~10 min)
#   FAIL-> OK     email "RECOVERED"
#   still FAIL    reminder every HEALTH_WATCH_REMIND_MIN minutes (default 120)
# State: /var/tmp/safehomeops-health-watch.state. Log: journalctl -u safehomeops-health-watch.
#
# Env (set in the unit or /etc/workforceos/safehome.env):
#   HEALTH_WATCH_TO      recipients, comma-separated (default SMTP_ALERT_TO, then SMTP_FROM_EMAIL)
#   HEALTH_WATCH_URLS    space-separated URLs (default: local + public /health/ready)
#   HEALTH_WATCH_ENV     backend .env to read SMTP_* from (default /opt/safehomeops/app/backend/.env)

set -uo pipefail

ENV_FILE="${HEALTH_WATCH_ENV:-/opt/safehomeops/app/backend/.env}"
STATE="${HEALTH_WATCH_STATE:-/var/tmp/safehomeops-health-watch.state}"
URLS="${HEALTH_WATCH_URLS:-http://127.0.0.1:8010/health/ready https://ops.kushalaya.com/health/ready}"
FAILS_NEEDED="${HEALTH_WATCH_FAILS:-2}"
REMIND_MIN="${HEALTH_WATCH_REMIND_MIN:-120}"
TIMEOUT="${HEALTH_WATCH_TIMEOUT:-15}"
HOSTNAME_="$(hostname -s 2>/dev/null || echo vm)"

TEST=0
[[ "${1:-}" == "--test" ]] && TEST=1

# Same safe loader as postgres-backup-lib.sh (no `source`: a .env is data).
load_env() {
  local file=$1 line key value
  [[ -f "$file" ]] || { echo "health-watch: env file not readable: $file" >&2; return 1; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    key="${line%%=*}"; value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    case "$key" in SMTP_HOST|SMTP_PORT|SMTP_USERNAME|SMTP_PASSWORD|SMTP_FROM_EMAIL|SMTP_FROM_NAME|SMTP_ALERT_TO) ;; *) continue ;; esac
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then value="${value:1:${#value}-2}"; fi
    [[ -z "${!key+x}" ]] && export "$key=$value"
  done <"$file"
}

send_mail() { # subject body
  local subject="$1" body="$2"
  load_env "$ENV_FILE" || return 1
  local to="${HEALTH_WATCH_TO:-${SMTP_ALERT_TO:-${SMTP_FROM_EMAIL:-}}}"
  if [[ -z "${SMTP_USERNAME:-}" || -z "${SMTP_PASSWORD:-}" || -z "$to" ]]; then
    echo "health-watch: SMTP_USERNAME / SMTP_PASSWORD / recipient not configured in $ENV_FILE — cannot email" >&2
    return 1
  fi
  # Credentials travel to python via the environment only.
  HW_TO="$to" HW_SUBJECT="$subject" HW_BODY="$body" python3 - <<'PY'
import os, smtplib, ssl
from email.message import EmailMessage
host = (os.environ.get("SMTP_HOST") or "smtp.gmail.com").strip()
port = int(os.environ.get("SMTP_PORT") or 587)
user = os.environ["SMTP_USERNAME"].strip()
pw = os.environ["SMTP_PASSWORD"].replace(" ", "").strip()
sender = (os.environ.get("SMTP_FROM_EMAIL") or user).strip()
name = (os.environ.get("SMTP_FROM_NAME") or "Kushalaya").strip()
to = [t.strip() for t in os.environ["HW_TO"].split(",") if t.strip()]
msg = EmailMessage()
msg["Subject"] = os.environ["HW_SUBJECT"]
msg["From"] = f"{name} <{sender}>"
msg["To"] = ", ".join(to)
msg.set_content(os.environ["HW_BODY"])
with smtplib.SMTP(host, port, timeout=20) as s:
    s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
    s.login(user, pw)
    s.send_message(msg)
print(f"health-watch: emailed {len(to)} recipient(s)")
PY
}

check_all() { # prints one line per URL; returns 1 if any failed
  local url code ok=0 body
  for url in $URLS; do
    body="$(mktemp)"
    code="$(curl -sS -o "$body" -w '%{http_code}' --max-time "$TIMEOUT" "$url" 2>/dev/null || echo 000)"
    if [[ "$code" == "200" ]]; then
      echo "OK   $code $url"
    else
      ok=1
      echo "FAIL $code $url $(head -c 200 "$body" 2>/dev/null | tr -d '\n')"
    fi
    rm -f "$body"
  done
  return $ok
}

if [[ "$TEST" == "1" ]]; then
  send_mail "[Kushalaya] health-watch test from $HOSTNAME_" "This is a test from scripts/deploy/health-watch.sh on $HOSTNAME_ at $(date -u +%FT%TZ)." && echo "health-watch: test email sent"
  exit $?
fi

now=$(date +%s)
prev_status="ok"; prev_fails=0; prev_alert=0
if [[ -f "$STATE" ]]; then
  # shellcheck disable=SC1090
  source "$STATE"   # written by us only: prev_status= prev_fails= prev_alert=
fi

result="$(check_all)"; rc=$?
echo "$result"

if [[ $rc -ne 0 ]]; then
  fails=$((prev_fails + 1))
  status="fail"
  if [[ "$prev_status" == "ok" && $fails -ge $FAILS_NEEDED ]]; then
    send_mail "[Kushalaya] DOWN — /health/ready failing on $HOSTNAME_" \
"Readiness has failed $fails consecutive checks (every 5 min).

$result

Checked at $(date -u +%FT%TZ). Next steps:
  ssh -i _ssh/oracle_safehome_vm opc@129.213.45.105
  sudo systemctl status safehomeops-api safehomeops-web nginx postgresql
  journalctl -u safehomeops-api -n 100 --no-pager
  sudo bash /opt/safehomeops/app/scripts/deploy/rollback-livewell.sh   # if a deploy just happened
See docs/deploy/MONITORING.md." || true
    prev_alert=$now
  elif [[ "$prev_status" == "fail" && $(( (now - prev_alert) / 60 )) -ge $REMIND_MIN ]]; then
    send_mail "[Kushalaya] STILL DOWN — $HOSTNAME_ ($fails checks)" "$result

Still failing at $(date -u +%FT%TZ)." || true
    prev_alert=$now
  fi
  # Stay "ok" in state until the threshold is reached so one blip never alerts.
  [[ $fails -ge $FAILS_NEEDED ]] || status="ok"
else
  fails=0
  status="ok"
  if [[ "$prev_status" == "fail" ]]; then
    send_mail "[Kushalaya] RECOVERED — /health/ready OK on $HOSTNAME_" "$result

Recovered at $(date -u +%FT%TZ) after $prev_fails failed checks." || true
    prev_alert=0
  fi
fi

printf 'prev_status=%s\nprev_fails=%s\nprev_alert=%s\n' "$status" "$fails" "$prev_alert" >"$STATE.tmp" && mv "$STATE.tmp" "$STATE"
exit $rc
