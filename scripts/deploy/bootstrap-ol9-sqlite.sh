#!/usr/bin/env bash
# Bootstrap Oracle Linux 9 for SafeHomeOps using SQLite (no PostgreSQL).
# Run as root: sudo bash scripts/deploy/bootstrap-ol9-sqlite.sh

set -euo pipefail

echo "==> SafeHomeOps bootstrap — SQLite mode (Oracle Linux 9)"

dnf update -y

dnf install -y \
  git curl nginx \
  python3.11 python3.11-pip python3.11-devel \
  gcc \
  firewalld \
  || dnf install -y python3 python3-pip python3-devel gcc

if ! dnf install -y epel-release 2>/dev/null; then
  dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm 2>/dev/null || true
fi
if ! dnf install -y certbot python3-certbot-nginx 2>/dev/null; then
  echo "WARN: certbot not in dnf — try: python3.11 -m pip install certbot certbot-nginx"
fi

if ! command -v node &>/dev/null || [[ "$(node -v 2>/dev/null || echo 0)" != v20* ]]; then
  curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
  dnf install -y nodejs
fi

if ! id safehomeops &>/dev/null; then
  useradd -r -m -d /opt/safehomeops -s /bin/bash -G opc safehomeops
else
  getent group opc >/dev/null && usermod -aG opc safehomeops 2>/dev/null || true
fi

mkdir -p \
  /opt/safehomeops \
  /opt/workforceos-core \
  /var/lib/safehomeops/data \
  /var/lib/safehomeops/uploads \
  /var/backups/safehomeops \
  /var/www/certbot

chown -R safehomeops:safehomeops /opt/safehomeops /var/lib/safehomeops /var/backups/safehomeops
chown opc:opc /opt/workforceos-core
chmod 2775 /opt/workforceos-core

systemctl enable --now firewalld nginx
firewall-cmd --permanent --add-service={http,https,ssh}
firewall-cmd --reload

setsebool -P httpd_can_network_connect 1 2>/dev/null || true
for dir in /var/lib/safehomeops/uploads /var/lib/safehomeops/data; do
  chcon -R -t httpd_sys_rw_content_t "$dir" 2>/dev/null || true
done

echo ""
echo "Bootstrap complete (SQLite). Next: scripts/deploy/README.md"
echo "  1. Clone workforceos-core -> /opt/workforceos-core"
echo "  2. Clone SafeHomeOps -> /opt/safehomeops/app"
echo "  3. sudo cp scripts/deploy/deploy.safehome.env.example /etc/workforceos/safehome.env"
echo "  4. sudo bash scripts/deploy/deploy-safehome.sh"
