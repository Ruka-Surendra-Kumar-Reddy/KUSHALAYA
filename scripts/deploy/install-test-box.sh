#!/usr/bin/env bash
# One-shot installer for the TEST instance (docs/deploy/TEST_INSTANCE.md).
# Fresh Oracle Linux 9 box, run as root. Idempotent enough to re-run.
#
# Pre-conditions (owner): DNS test/test-ops/test-family -> this box; the public
# half of /home/opc/.ssh/github_deploy added as a read-only deploy key on
# Ruka-Surendra-Kumar-Reddy/KUSHALAYA and krishnaposa/workforceos-core.
#
# Bootstrap from a laptop (Windows cmd, one line):
#   ssh -i %USERPROFILE%\oracle_safehome_vm opc@150.136.230.200 "sudo dnf -y -q install git && mkdir -p ~/.ssh && printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n  IdentitiesOnly yes\n  StrictHostKeyChecking accept-new\n' > ~/.ssh/config && chmod 600 ~/.ssh/config && rm -rf /tmp/kushalaya-bootstrap && git clone -q -b develop git@github.com:Ruka-Surendra-Kumar-Reddy/KUSHALAYA.git /tmp/kushalaya-bootstrap && sudo bash /tmp/kushalaya-bootstrap/scripts/deploy/install-test-box.sh"
#
# What it does: users + deploy key for them, /etc/workforceos/safehome.env with
# generated secrets, deploy-safehome.sh (bootstrap packages, postgres, clone,
# build, nginx, certs, systemd, demo seed), the family vhost + its cert, firewall,
# then a smoke test. Never installs the IoT ingestor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=workforceos-deploy-lib.sh
source "$SCRIPT_DIR/workforceos-deploy-lib.sh"
require_root

ENV_FILE=/etc/workforceos/safehome.env
DEPLOY_KEY_SRC=/home/opc/.ssh/github_deploy
# GitHub allows a deploy key on ONE repository, so the shared package has its own key.
CORE_KEY_SRC=/home/opc/.ssh/github_deploy_core
TEST_IP=150.136.230.200
APP_DOMAIN=test-ops.kushalaya.com
MARKETING_DOMAIN=test.kushalaya.com
FAMILY_DOMAIN=test-family.kushalaya.com

[[ -f "$DEPLOY_KEY_SRC" ]] || die "Missing $DEPLOY_KEY_SRC (generate: ssh-keygen -t ed25519 -f ~/.ssh/github_deploy as opc)"
[[ -f "$CORE_KEY_SRC" ]] || die "Missing $CORE_KEY_SRC (ssh-keygen -t ed25519 -f ~/.ssh/github_deploy_core as opc; add .pub to krishnaposa/workforceos-core)"

# --- 0. refuse to run on production -----------------------------------------
if [[ -f /opt/safehomeops/app/backend/.env ]] && grep -q "^ENVIRONMENT=production" /opt/safehomeops/app/backend/.env \
   && ! grep -q "^ENVIRONMENT=test" /opt/safehomeops/app/backend/.env; then
  die "This box already runs a PRODUCTION .env — refusing. The test installer never runs on prod."
fi
for d in "$APP_DOMAIN" "$MARKETING_DOMAIN" "$FAMILY_DOMAIN"; do
  got=$(getent ahostsv4 "$d" | awk 'NR==1{print $1}')
  [[ "$got" == "$TEST_IP" ]] || die "DNS: $d resolves to '${got:-nothing}', expected $TEST_IP"
done

# --- 1. users and the deploy key for both clone owners -----------------------
ensure_safehomeops_user
for u in opc safehomeops; do
  home=$(getent passwd "$u" | cut -d: -f6)
  install -d -m 700 -o "$u" -g "$u" "$home/.ssh"
  if ! [ "$DEPLOY_KEY_SRC" -ef "$home/.ssh/github_deploy" ]; then
    install -m 600 -o "$u" -g "$u" "$DEPLOY_KEY_SRC" "$home/.ssh/github_deploy"
  fi
  if ! [ "$CORE_KEY_SRC" -ef "$home/.ssh/github_deploy_core" ]; then
    install -m 600 -o "$u" -g "$u" "$CORE_KEY_SRC" "$home/.ssh/github_deploy_core"
  fi
  cat >"$home/.ssh/config" <<EOF
Host github.com
  IdentityFile $home/.ssh/github_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
Host github-core
  HostName github.com
  User git
  IdentityFile $home/.ssh/github_deploy_core
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
  chown "$u:$u" "$home/.ssh/config"; chmod 600 "$home/.ssh/config"
done
log "Checking GitHub access for safehomeops"
sudo -u safehomeops git ls-remote -h git@github.com:Ruka-Surendra-Kumar-Reddy/KUSHALAYA.git develop >/dev/null \
  || die "GitHub refused the deploy key for KUSHALAYA — add $(cat "$DEPLOY_KEY_SRC.pub" 2>/dev/null || echo 'the key') as a read-only deploy key"
sudo -u opc git ls-remote -h git@github-core:krishnaposa/workforceos-core.git develop >/dev/null \
  || die "GitHub refused the workforceos-core key — add $(cat "$CORE_KEY_SRC.pub" 2>/dev/null) as a read-only deploy key on krishnaposa/workforceos-core"

# --- 2. config with generated secrets (kept only on this box) -----------------
mkdir -p /etc/workforceos
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$SCRIPT_DIR/deploy.test.env.example" "$ENV_FILE"
  sed -i "s|^APP_DB_PASSWORD=.*|APP_DB_PASSWORD=$(openssl rand -hex 24)|" "$ENV_FILE"
  sed -i "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$(openssl rand -hex 32)|" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  log "Wrote $ENV_FILE with fresh secrets"
else
  log "Keeping existing $ENV_FILE"
fi
grep -q "CHANGE_ME" "$ENV_FILE" && die "$ENV_FILE still has CHANGE_ME values"

# --- 3. the standard install (packages, db, clone, build, nginx, tls, units, seed)
DEPLOY_ENV_FILE="$ENV_FILE" bash "$SCRIPT_DIR/deploy-safehome.sh" --env "$ENV_FILE"

# --- 4. family vhost: http first (for the ACME challenge), cert, then full conf
APP_ROOT=/opt/safehomeops/app
mkdir -p /var/www/certbot/.well-known/acme-challenge
cat >/etc/nginx/conf.d/"$FAMILY_DOMAIN".conf <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $FAMILY_DOMAIN;
    location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
EOF
nginx -t && systemctl reload nginx
if [[ ! -d /etc/letsencrypt/live/$FAMILY_DOMAIN ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  certbot certonly --non-interactive --agree-tos -m "${CERTBOT_EMAIL:?}" --webroot -w /var/www/certbot -d "$FAMILY_DOMAIN"
fi
sed "s/family\.kushalaya\.com/$FAMILY_DOMAIN/g" "$APP_ROOT/deploy/nginx/family.kushalaya.com.conf" >/etc/nginx/conf.d/"$FAMILY_DOMAIN".conf
nginx -t && systemctl reload nginx

# --- 5. firewall + make sure no ingestor ever runs here ----------------------
firewall-cmd --permanent --add-service=http >/dev/null; firewall-cmd --permanent --add-service=https >/dev/null; firewall-cmd --reload >/dev/null
systemctl disable --now safehomeops-iot-ingestor 2>/dev/null || true
systemctl mask safehomeops-iot-ingestor 2>/dev/null || true

# --- 6. smoke -----------------------------------------------------------------
log "Smoke test"
for u in "https://$MARKETING_DOMAIN/" "https://$APP_DOMAIN/login" "https://$FAMILY_DOMAIN/login" "https://$APP_DOMAIN/health/ready"; do
  code=$(curl -s -o /dev/null -m 30 -H "Sec-Fetch-Dest: document" -w "%{http_code}" "$u" || true)
  printf '  %-45s %s\n' "$u" "$code"
done
curl -s -m 10 "https://$APP_DOMAIN/health" | grep -o '"environment":"[a-z]*"' || true
curl -s -m 10 "https://$MARKETING_DOMAIN/" | grep -qi "test system" && echo "  TEST band: present" || echo "  TEST band: MISSING"
log "Done. Demo logins: manager@sunrise-care.example / lakshmi.family@sunrise-care.example (seed password)."
