#!/usr/bin/env bash
# Stand up (or refresh) the STAGING copy of Kushalaya on the production VM.
# Run ON the VM as root. Idempotent: re-running re-syncs code, re-restores the
# DB when --restore-db is given, and re-installs units/nginx.
#
#   sudo bash scripts/deploy/install-staging.sh                # first install (code + DB + units + nginx + certs)
#   sudo bash scripts/deploy/install-staging.sh --restore-db   # also reload DB from the newest prod backup
#   sudo bash scripts/deploy/install-staging.sh --skip-tls     # no certbot (DNS not ready yet)
#   sudo bash scripts/deploy/install-staging.sh --code-only    # rsync + rebuild only
#
# Layout it creates:
#   /opt/safehomeops-staging/app          rsync of /opt/safehomeops/app (no uploads, no .env, no node_modules/.venv/.next)
#   /opt/safehomeops-staging/app/.deploy-env   SERVICE_PREFIX/API_PORT/WEB_PORT/SMOKE_* for start-livewell.sh
#   /var/lib/safehomeops-staging/uploads
#   PostgreSQL database safehomeops_staging (role safehomeops), restored from
#     the newest /var/backups/safehomeops/postgres dump on first install
#   systemd safehomeops-staging-api (:8020) / safehomeops-staging-web (:3020)
#   nginx /etc/nginx/conf.d/staging.kushalaya.com.conf + one cert for the 3 names
#
# DNS the owner must add BEFORE --skip-tls is dropped (A records -> 129.213.45.105):
#   staging-ops.kushalaya.com   staging-www.kushalaya.com   staging-family.kushalaya.com
#
# Secrets: backend/.env is generated from deploy/staging/backend.env.template.
# The DB password is read from the PRODUCTION backend/.env on this VM and a new
# SECRET_KEY is generated. Nothing is printed and nothing is written to the repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=postgres-backup-lib.sh
source "$SCRIPT_DIR/postgres-backup-lib.sh"   # _load_env_file, log, die, require_root

PROD_ROOT="${PROD_ROOT:-/opt/safehomeops/app}"
STAGING_ROOT="${STAGING_ROOT:-/opt/safehomeops-staging/app}"
STAGING_UPLOADS="${STAGING_UPLOADS:-/var/lib/safehomeops-staging/uploads}"
APP_USER="${APP_USER:-safehomeops}"
STAGING_DB="${STAGING_DB:-safehomeops_staging}"
STAGING_API_PORT=8020
STAGING_WEB_PORT=3020
PREFIX=safehomeops-staging
OPS_HOST=staging-ops.kushalaya.com
WWW_HOST=staging-www.kushalaya.com
FAMILY_HOST=staging-family.kushalaya.com
CERT_NAME=staging.kushalaya.com
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

RESTORE_DB=0
SKIP_TLS=0
CODE_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --restore-db) RESTORE_DB=1; shift ;;
    --skip-tls) SKIP_TLS=1; shift ;;
    --code-only) CODE_ONLY=1; shift ;;
    --help|-h) sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown argument: $1 (try --help)" ;;
  esac
done

require_root
[[ -d "$PROD_ROOT/backend" ]] || die "Production app not found at $PROD_ROOT"
[[ -f "$PROD_ROOT/backend/.env" ]] || die "Missing $PROD_ROOT/backend/.env"
id "$APP_USER" &>/dev/null || die "OS user $APP_USER missing"
command -v rsync >/dev/null || die "rsync not installed (dnf install rsync)"

# ---------------------------------------------------------------------------
# 1. code
# ---------------------------------------------------------------------------
sync_code() {
  log "Syncing $PROD_ROOT -> $STAGING_ROOT"
  mkdir -p "$STAGING_ROOT" "$STAGING_UPLOADS"
  rsync -a --delete \
    --exclude='/backend/.env' --exclude='/frontend/.env.local' --exclude='/backend/iot_ingestor.env' \
    --exclude='/.deploy-env' \
    --exclude='node_modules' --exclude='.next' --exclude='.next-staging' --exclude='.next-previous' \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.db' \
    --exclude='uploads' --exclude='test_uploads' --exclude='.git' --exclude='_ssh' \
    "$PROD_ROOT/" "$STAGING_ROOT/"
  # workforceos-core is a symlink to the shared /opt/workforceos-core (rsync -a keeps it).
  [[ -e "$STAGING_ROOT/workforceos-core" ]] || ln -sfn /opt/workforceos-core "$STAGING_ROOT/workforceos-core"
  chown -R "$APP_USER:$APP_USER" /opt/safehomeops-staging /var/lib/safehomeops-staging
  chcon -R -t httpd_sys_rw_content_t "$STAGING_UPLOADS" 2>/dev/null || true

  cat >"$STAGING_ROOT/.deploy-env" <<EOF
# Read by scripts/start-livewell.sh — staging copy. No secrets here.
export SERVICE_PREFIX=$PREFIX
export API_PORT=$STAGING_API_PORT
export WEB_PORT=$STAGING_WEB_PORT
export APP_DOMAIN=$OPS_HOST
export SMOKE_OPS_BASE=$OPS_HOST
export SMOKE_WWW_BASE=$WWW_HOST
export SMOKE_FAMILY_BASE=$FAMILY_HOST
EOF
  chown "$APP_USER:$APP_USER" "$STAGING_ROOT/.deploy-env"
}

# ---------------------------------------------------------------------------
# 2. env files (placeholders filled from the prod env; never echoed)
# ---------------------------------------------------------------------------
staging_database_url() {
  # Prod DATABASE_URL with the database name swapped for $STAGING_DB.
  local prod_url="$1"
  local prefix="${prod_url%/*}"      # up to the last '/'
  local tail="${prod_url##*/}"       # dbname[?params]
  local params=""
  [[ "$tail" == *\?* ]] && params="?${tail#*\?}"
  printf '%s/%s%s' "$prefix" "$STAGING_DB" "$params"
}

write_env_files() {
  local be="$STAGING_ROOT/backend/.env" fe="$STAGING_ROOT/frontend/.env.local"
  local tpl_be="$STAGING_ROOT/deploy/staging/backend.env.template"
  local tpl_fe="$STAGING_ROOT/deploy/staging/frontend.env.local.template"
  [[ -f "$tpl_be" && -f "$tpl_fe" ]] || die "Templates missing under $STAGING_ROOT/deploy/staging/ (deploy them first)"

  # Load prod values into this shell only (postgres-backup-lib's safe loader).
  ( set +u
    _load_env_file "$PROD_ROOT/backend/.env"
    [[ -n "${DATABASE_URL:-}" ]] || die "DATABASE_URL not found in $PROD_ROOT/backend/.env"
    [[ "${DATABASE_URL}" == postgresql* ]] || die "Production DATABASE_URL is not PostgreSQL — staging expects Postgres"
    st_url="$(staging_database_url "$DATABASE_URL")"
    brand="${BRAND_NAME:-KushAlaya}"

    if [[ -f "$be" ]] && grep -q '^SECRET_KEY=' "$be"; then
      secret="$(sed -n 's/^SECRET_KEY=//p' "$be" | head -1)"   # keep: existing staging sessions stay valid
    else
      secret="$(openssl rand -hex 32)"
    fi

    umask 077
    sed -e "s|__DATABASE_URL__|${st_url}|" -e "s|__SECRET_KEY__|${secret}|" -e "s|__BRAND_NAME__|${brand}|" \
      "$tpl_be" >"$be.tmp"
    mv "$be.tmp" "$be"

    fe_brand="$brand"
    if [[ -f "$PROD_ROOT/frontend/.env.local" ]]; then
      v="$(sed -n 's/^NEXT_PUBLIC_BRAND_NAME=//p' "$PROD_ROOT/frontend/.env.local" | head -1)"
      [[ -n "$v" ]] && fe_brand="$v"
    fi
    sed -e "s|__BRAND_NAME__|${fe_brand}|" "$tpl_fe" >"$fe.tmp"
    mv "$fe.tmp" "$fe"
  )
  chown "$APP_USER:$APP_USER" "$be" "$fe"
  chmod 600 "$be"
  chmod 640 "$fe"
  if grep -q '__[A-Z_]*__' "$be" "$fe"; then die "Unfilled placeholder left in staging env files"; fi
  log "Wrote $be and $fe (DB=$STAGING_DB, ENVIRONMENT=staging, secrets not shown)"
}

# ---------------------------------------------------------------------------
# 3. database
# ---------------------------------------------------------------------------
ensure_pg_hba() {
  local hba line
  hba=$(sudo -u postgres psql -tAc "SHOW hba_file" | tr -d '[:space:]')
  line="host    ${STAGING_DB}    ${APP_DB_USER:-safehomeops}    127.0.0.1/32    scram-sha-256"
  if ! grep -qE "^host\s+${STAGING_DB}\s+" "$hba"; then
    log "Adding pg_hba rule for $STAGING_DB"
    printf '%s\n' "$line" >>"$hba"
    systemctl reload postgresql
  fi
}

restore_db() {
  # restore-safehome-postgres.sh drops/creates $APP_DB_NAME and loads the
  # newest dump. Exported vars win over its env files, so point it at staging.
  # --keep-api: never stop the PRODUCTION api for a staging restore.
  local st_url
  st_url="$(sed -n 's/^DATABASE_URL=//p' "$STAGING_ROOT/backend/.env" | head -1)"
  [[ -n "$st_url" ]] || die "No DATABASE_URL in staging .env"
  log "Restoring newest production backup into $STAGING_DB (production untouched)"
  APP_DB_NAME="$STAGING_DB" DATABASE_URL="$st_url" APP_ROOT="$STAGING_ROOT" BACKUP_STOP_API=0 \
    bash "$STAGING_ROOT/scripts/deploy/restore-safehome-postgres.sh" --yes --keep-api
}

db_exists() {
  [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${STAGING_DB}'" | tr -d '[:space:]')" == "1" ]]
}

# ---------------------------------------------------------------------------
# 4. units + sudoers + nginx + TLS
# ---------------------------------------------------------------------------
install_units() {
  log "Installing $PREFIX-api / $PREFIX-web units"
  cp "$STAGING_ROOT/deploy/systemd/$PREFIX-api.service" "$STAGING_ROOT/deploy/systemd/$PREFIX-web.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable "$PREFIX-api" "$PREFIX-web" >/dev/null

  # start-livewell.sh restarts its units with `sudo -n systemctl restart`.
  local dest=/etc/sudoers.d/safehomeops-staging
  cat >"$dest" <<EOF
# Kushalaya staging — app user may restart the staging units (install-staging.sh)
safehomeops ALL=(root) NOPASSWD: /usr/bin/systemctl restart $PREFIX-api, /usr/bin/systemctl restart $PREFIX-web, /usr/bin/systemctl restart $PREFIX-api $PREFIX-web, /usr/bin/systemctl restart $PREFIX-web $PREFIX-api, /usr/bin/systemctl status $PREFIX-api, /usr/bin/systemctl status $PREFIX-web, /usr/bin/systemctl status $PREFIX-api $PREFIX-web, /usr/bin/systemctl is-active $PREFIX-api, /usr/bin/systemctl is-active $PREFIX-web
EOF
  chmod 440 "$dest"
  visudo -cf "$dest" >/dev/null
}

install_nginx() {
  local dst=/etc/nginx/conf.d/staging.kushalaya.com.conf
  local https="$STAGING_ROOT/deploy/nginx/staging.kushalaya.com.conf"
  local http="$STAGING_ROOT/deploy/nginx/staging.kushalaya.com-http-only.conf"
  mkdir -p /var/www/certbot/.well-known/acme-challenge
  if [[ -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" ]]; then
    cp "$https" "$dst"; log "nginx: HTTPS vhosts -> $dst"
  else
    cp "$http" "$dst"; log "nginx: HTTP-only vhost (no cert yet) -> $dst"
  fi
  nginx -t
  systemctl reload nginx
}

obtain_cert() {
  [[ "$SKIP_TLS" == "1" ]] && { log "Skipping TLS (--skip-tls)"; return 0; }
  [[ -f "/etc/letsencrypt/live/$CERT_NAME/fullchain.pem" ]] && { log "Cert $CERT_NAME already present"; return 0; }
  if [[ -z "$CERTBOT_EMAIL" && -f /etc/workforceos/safehome.env ]]; then
    CERTBOT_EMAIL="$(sed -n 's/^CERTBOT_EMAIL=//p' /etc/workforceos/safehome.env | head -1)"
  fi
  [[ -n "$CERTBOT_EMAIL" ]] || die "Set CERTBOT_EMAIL=... (or --skip-tls)"
  local h
  for h in "$OPS_HOST" "$WWW_HOST" "$FAMILY_HOST"; do
    if ! getent hosts "$h" >/dev/null; then
      die "DNS for $h does not resolve yet — add the A record, or re-run with --skip-tls"
    fi
  done
  log "Requesting one certificate for $OPS_HOST, $WWW_HOST, $FAMILY_HOST"
  certbot certonly --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --webroot -w /var/www/certbot --cert-name "$CERT_NAME" \
    -d "$OPS_HOST" -d "$WWW_HOST" -d "$FAMILY_HOST"
}

# ---------------------------------------------------------------------------
# 5. build + start (start-livewell.sh reads .deploy-env for the staging names)
# ---------------------------------------------------------------------------
build_and_start() {
  local flags=("$@")
  log "start-livewell.sh ${flags[*]:-} (as $APP_USER, staging)"
  sudo -u "$APP_USER" -H bash "$STAGING_ROOT/scripts/start-livewell.sh" "${flags[@]}"
}

main() {
  log "Kushalaya staging install: $STAGING_ROOT (api :$STAGING_API_PORT web :$STAGING_WEB_PORT db $STAGING_DB)"
  sync_code
  write_env_files
  if [[ "$CODE_ONLY" == "1" ]]; then
    build_and_start
    log "Done (code only)."
    return
  fi
  ensure_pg_hba
  if [[ "$RESTORE_DB" == "1" ]] || ! db_exists; then
    restore_db
  else
    log "Database $STAGING_DB exists — keeping it (use --restore-db to reload from backup)"
  fi
  install_units
  install_nginx
  obtain_cert
  install_nginx   # swap to HTTPS vhosts now that the cert exists
  build_and_start --backend-migrate
  echo ""
  echo "Staging is up:"
  echo "  https://$OPS_HOST/health      https://$WWW_HOST/      https://$FAMILY_HOST/login"
  echo "  Deploy a release to staging:  sudo APP_ROOT=$STAGING_ROOT bash $STAGING_ROOT/scripts/deploy/apply-release.sh /tmp/<id>.tar.gz"
  echo "  Logs: journalctl -u $PREFIX-api -f   journalctl -u $PREFIX-web -f"
}

main
