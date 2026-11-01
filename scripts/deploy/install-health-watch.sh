#!/usr/bin/env bash
# Install the 5-minute health watch timer — run ON the VM as root.
#
#   sudo bash scripts/deploy/install-health-watch.sh            # install + enable + run once
#   sudo bash scripts/deploy/install-health-watch.sh --test     # also send a test email
#   sudo bash scripts/deploy/install-health-watch.sh --remove
#
# Units: deploy/systemd/safehomeops-health-watch.{service,timer}
# Script: scripts/deploy/health-watch.sh (emails via SMTP_* in backend/.env)
# Docs:   docs/deploy/MONITORING.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
UNIT=safehomeops-health-watch

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash $0" >&2; exit 1; }

case "${1:-}" in
  --remove)
    systemctl disable --now "$UNIT.timer" 2>/dev/null || true
    rm -f "/etc/systemd/system/$UNIT.service" "/etc/systemd/system/$UNIT.timer"
    systemctl daemon-reload
    echo "==> Removed $UNIT.timer"
    exit 0 ;;
  --test|"") ;;
  *) echo "Unknown argument: $1" >&2; exit 1 ;;
esac

for f in "$APP_ROOT/deploy/systemd/$UNIT.service" "$APP_ROOT/deploy/systemd/$UNIT.timer" "$APP_ROOT/scripts/deploy/health-watch.sh"; do
  [[ -f "$f" ]] || { echo "Missing $f" >&2; exit 1; }
done
chmod 755 "$APP_ROOT/scripts/deploy/health-watch.sh"
cp "$APP_ROOT/deploy/systemd/$UNIT.service" "$APP_ROOT/deploy/systemd/$UNIT.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now "$UNIT.timer"
echo "==> Installed and started $UNIT.timer (every 5 min)"

if [[ "${1:-}" == "--test" ]]; then
  echo "==> Sending test email"
  sudo -u safehomeops -H bash "$APP_ROOT/scripts/deploy/health-watch.sh" --test
fi

echo "==> First check:"
systemctl start "$UNIT.service" || true
journalctl -u "$UNIT.service" -n 5 --no-pager || true
echo ""
echo "Status:   systemctl list-timers $UNIT.timer"
echo "Log:      journalctl -u $UNIT.service -f"
echo "State:    cat /var/tmp/safehomeops-health-watch.state"
