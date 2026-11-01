#!/usr/bin/env bash
# Bootstrap Oracle Linux 9 (aarch64/x86_64) for WorkforceOS.
# Run as root: sudo bash scripts/deploy/bootstrap-ol9.sh
# Does NOT clone the repo or start app services — see scripts/deploy/README.md

set -euo pipefail

echo "==> WorkforceOS bootstrap (Oracle Linux 9)"

dnf update -y

# Python 3.11+ required (code uses str | None syntax; OL9 default python3 is often 3.9)
dnf install -y \
  git curl nginx \
  python3.11 python3.11-pip python3.11-devel \
  gcc postgresql postgresql-server postgresql-contrib \
  firewalld \
  || dnf install -y python3 python3-pip python3-devel

if ! dnf install -y epel-release 2>/dev/null; then
  dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm 2>/dev/null || true
fi
if ! dnf install -y certbot python3-certbot-nginx 2>/dev/null; then
  echo "WARN: certbot not in dnf — install via: sudo python3.11 -m pip install certbot certbot-nginx"
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

mkdir -p /opt/safehomeops /var/lib/safehomeops/uploads /var/backups/safehomeops
chown -R safehomeops:safehomeops /opt/safehomeops /var/lib/safehomeops

if [[ ! -f /var/lib/pgsql/data/PG_VERSION ]]; then
  postgresql-setup --initdb
fi
systemctl enable --now postgresql

systemctl enable --now firewalld
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --permanent --add-service=ssh
firewall-cmd --reload

setsebool -P httpd_can_network_connect 1 2>/dev/null || true
chcon -R -t httpd_sys_rw_content_t /var/lib/safehomeops/uploads 2>/dev/null || true

mkdir -p /opt/workforceos-core
chown opc:opc /opt/workforceos-core
chmod 2775 /opt/workforceos-core

echo ""
echo "Bootstrap complete. App user safehomeops uses group opc for /opt/workforceos-core."
echo "Next:"
echo "  sudo cp scripts/deploy/deploy.safehome.env.example /etc/workforceos/safehome.env"
echo "  sudo nano /etc/workforceos/safehome.env   # passwords, secrets, RUN_BOOTSTRAP=0"
echo "  sudo bash scripts/deploy/deploy-safehome.sh"
echo ""
echo "See: scripts/deploy/README.md and docs/SAFEHOMEOPS_SPLIT.md"
