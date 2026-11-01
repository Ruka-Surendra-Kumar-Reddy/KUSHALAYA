#!/usr/bin/env bash
# Deploy SafeHome vertical + shared workforceos-core on Oracle Linux 9.
#
# Usage (on the VM, as root):
#   sudo mkdir -p /etc/workforceos
#   sudo cp scripts/deploy/deploy.safehome.env.example /etc/workforceos/safehome.env
#   sudo $EDITOR /etc/workforceos/safehome.env
#   sudo bash scripts/deploy/deploy-safehome.sh
#
# Options:
#   --env /path/to/safehome.env   (default: /etc/workforceos/safehome.env)
#   --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=workforceos-deploy-lib.sh
source "$SCRIPT_DIR/workforceos-deploy-lib.sh"

ENV_FILE="${DEPLOY_ENV_FILE:-/etc/workforceos/safehome.env}"

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:?}"
      shift 2
      ;;
    --help|-h)
      usage
      ;;
    *)
      die "Unknown argument: $1 (try --help)"
      ;;
  esac
done

load_config() {
  [[ -f "$ENV_FILE" ]] || die "Missing config: $ENV_FILE (copy scripts/deploy/deploy.safehome.env.example)"
  # shellcheck disable=SC1090
  source "$ENV_FILE"

  : "${WORKFORCEOS_CORE_REPO:?}"
  : "${WORKFORCEOS_CORE_BRANCH:=develop}"
  : "${APP_REPO:?}"
  # develop is the branch the VM checkout tracks (docs/deploy/DEPLOY_UPDATE.md).
  # Day-to-day updates do NOT use git at all — they are tarballs applied by
  # scripts/deploy/apply-release.sh; this path is for a fresh clone only.
  : "${APP_BRANCH:=develop}"
  : "${APP_DOMAIN:?}"
  : "${MARKETING_DOMAIN:=www.kushalaya.com}"
  : "${LEGACY_APP_DOMAIN:=safehome.tekmatrix.ai}"
  : "${APP_DB_USER:=safehomeops}"
  : "${APP_DB_NAME:=safehomeops}"
  : "${PRESERVE_DB_PASSWORD:=0}"
  : "${SKIP_DB_SETUP:=0}"
  : "${APP_DB_PASSWORD:=}"
  : "${APP_SECRET_KEY:?}"
  : "${CERTBOT_EMAIL:=}"
  : "${SKIP_TLS:=0}"
  : "${RUN_BOOTSTRAP:=0}"
  : "${DEPLOY_WORKFORCEOS_CORE:=1}"
  : "${DEPLOY_NGINX:=1}"
  : "${DEPLOY_SYSTEMD:=1}"
  : "${APP_SEED:=admin}"
  : "${WORKFORCEOS_CORE_PATH:=/opt/workforceos-core}"
  : "${APP_ROOT:=/opt/safehomeops/app}"
  : "${APP_USER:=safehomeops}"
  : "${API_PORT:=8010}"
  : "${WEB_PORT:=3010}"
  # Empty string disables legacy redirect vhost
  : "${INSTALL_LEGACY_REDIRECT:=1}"
  : "${INSTALL_FAMILY_REDIRECT:=0}"

  if [[ "$SKIP_TLS" != "1" && -z "$CERTBOT_EMAIL" ]]; then
    die "Set CERTBOT_EMAIL in $ENV_FILE or SKIP_TLS=1"
  fi
  if [[ -z "$APP_DB_PASSWORD" || "$APP_DB_PASSWORD" == CHANGE_ME_* ]]; then
    die "Set APP_DB_PASSWORD in $ENV_FILE (needed for DATABASE_URL — use your manual DB password if already created)"
  fi
  if [[ "$APP_SECRET_KEY" == CHANGE_ME_* ]]; then
    die "Set real APP_SECRET_KEY in $ENV_FILE"
  fi
  export PRESERVE_DB_PASSWORD SKIP_DB_SETUP
}

cors_origins_csv() {
  local origins="https://${APP_DOMAIN}"
  if [[ -n "${MARKETING_DOMAIN}" && "${MARKETING_DOMAIN}" != "${APP_DOMAIN}" ]]; then
    origins="${origins},https://${MARKETING_DOMAIN}"
  fi
  # The family portal is a separate host and calls this API cross-origin.
  # Without it, family login fails with a CORS error.
  if [[ -n "${FAMILY_DOMAIN:-}" && "${FAMILY_DOMAIN}" != "${APP_DOMAIN}" ]]; then
    origins="${origins},https://${FAMILY_DOMAIN}"
  fi
  if [[ "${INSTALL_LEGACY_REDIRECT}" == "1" && -n "${LEGACY_APP_DOMAIN}" && "${LEGACY_APP_DOMAIN}" != "${APP_DOMAIN}" && "${LEGACY_APP_DOMAIN}" != "${MARKETING_DOMAIN}" ]]; then
    origins="${origins},https://${LEGACY_APP_DOMAIN}"
  fi
  printf '%s' "$origins"
}

write_safehome_env() {
  cat >"$APP_ROOT/backend/.env" <<EOF
ENVIRONMENT=production
LOG_LEVEL=INFO
DEPLOY_VERTICAL=LIVEWELL360
BRAND_NAME=${BRAND_NAME:-KushAlaya}
DATABASE_URL=postgresql://${APP_DB_USER}:${APP_DB_PASSWORD}@127.0.0.1:5432/${APP_DB_NAME}
SECRET_KEY=${APP_SECRET_KEY}
CORS_ORIGINS=$(cors_origins_csv)
STORAGE_BACKEND=${STORAGE_BACKEND:-local}
UPLOAD_DIR=/var/lib/safehomeops/uploads
ENABLE_TELEMETRY=false
GEMINI_API_KEY=${GEMINI_API_KEY:-}
AI_VISION_PROVIDER=${AI_VISION_PROVIDER:-gemini}
AI_VISION_MODEL=${AI_VISION_MODEL:-gemini-3.5-flash}
FAL_KEY=${FAL_KEY:-}
AI_RENDER_PROVIDER=${AI_RENDER_PROVIDER:-}
S3_ENDPOINT_URL=${S3_ENDPOINT_URL:-}
S3_BUCKET=${S3_BUCKET:-}
S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID:-}
S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY:-}
S3_REGION=${S3_REGION:-auto}
S3_PUBLIC_BASE_URL=${S3_PUBLIC_BASE_URL:-}
EOF
  # Extra lines for non-production boxes (test: ENVIRONMENT=test, log providers).
  # Later keys win when python-dotenv loads the file.
  if [[ -n "${EXTRA_BACKEND_ENV:-}" ]]; then
    printf '%b\n' "$EXTRA_BACKEND_ENV" >>"$APP_ROOT/backend/.env"
  fi
  chown safehomeops:safehomeops "$APP_ROOT/backend/.env"
  chmod 600 "$APP_ROOT/backend/.env"
  {
    echo "NEXT_PUBLIC_API_URL=https://${APP_DOMAIN}"
    echo "NEXT_PUBLIC_FAMILY_PORTAL_URL=${FAMILY_PORTAL_URL:-https://family.kushalaya.com/login}"
    echo "NEXT_PUBLIC_BRAND_NAME=${NEXT_PUBLIC_BRAND_NAME:-${BRAND_NAME:-LiveWell360}}"
    if [[ -n "${NEXT_PUBLIC_BRAND_MARK:-}" ]]; then
      echo "NEXT_PUBLIC_BRAND_MARK=${NEXT_PUBLIC_BRAND_MARK}"
    fi
    if [[ -n "${NEXT_PUBLIC_BRAND_ACCENT:-}" ]]; then
      echo "NEXT_PUBLIC_BRAND_ACCENT=${NEXT_PUBLIC_BRAND_ACCENT}"
    fi
    if [[ -n "${EXTRA_FRONTEND_ENV:-}" ]]; then
      printf '%b\n' "$EXTRA_FRONTEND_ENV"
    fi
  } >"$APP_ROOT/frontend/.env.local"
  chown safehomeops:safehomeops "$APP_ROOT/frontend/.env.local"
}

safehome_seed_cmd() {
  case "$APP_SEED" in
    admin|demo) echo "python -m app.seed_safehome" ;;
    skip) echo ":" ;;
    *) die "Unknown APP_SEED=$APP_SEED (admin | demo | skip)" ;;
  esac
}

install_nginx_site() {
  # Usage: install_nginx_site <domain> <app_root> [app|redirect]
  local domain=$1 app_root=$2
  local mode="${3:-app}"
  local src dst="/etc/nginx/conf.d/${domain}.conf"
  local https http template template_http

  if [[ "$mode" == "redirect" ]]; then
    https="${app_root}/deploy/nginx/${domain}-redirect.conf"
    http="${app_root}/deploy/nginx/${domain}-redirect-http-only.conf"
  else
    https="${app_root}/deploy/nginx/${domain}.conf"
    http="${app_root}/deploy/nginx/${domain}-http-only.conf"
  fi

  template="${app_root}/deploy/nginx/livewellops.tekmatrix.ai.conf"
  template_http="${app_root}/deploy/nginx/livewellops.tekmatrix.ai-http-only.conf"

  if [[ -f "/etc/letsencrypt/live/${domain}/fullchain.pem" && -f "$https" ]]; then
    src="$https"
  elif [[ -f "$http" ]]; then
    src="$http"
  elif [[ "$mode" == "app" && -f "$template_http" ]]; then
    src="$template_http"
  elif [[ "$mode" == "app" && -f "$template" ]]; then
    src="$template"
  else
    die "No nginx template for $domain (mode=$mode) under $app_root/deploy/nginx/"
  fi

  log "Installing nginx ($mode): $src -> $dst"
  case "$(basename "$src")" in
    livewellops.tekmatrix.ai.conf|livewellops.tekmatrix.ai-http-only.conf)
      sed "s/livewellops\\.tekmatrix\\.ai/${domain}/g" "$src" >"$dst"
      ;;
    *)
      cp "$src" "$dst"
      ;;
  esac
}

obtain_tls_cert() {
  local domain=$1
  [[ "$SKIP_TLS" == "1" ]] && return 0
  [[ -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]] && return 0
  [[ -n "$CERTBOT_EMAIL" ]] || die "Set CERTBOT_EMAIL in env file or SKIP_TLS=1"
  log "Requesting TLS certificate for $domain"
  certbot certonly --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --webroot -w /var/www/certbot -d "$domain"
}

deploy_nginx() {
  [[ "$DEPLOY_NGINX" == "1" ]] || return 0
  log "Configuring nginx for ops=$APP_DOMAIN marketing=${MARKETING_DOMAIN:-none}"
  mkdir -p /var/www/certbot/.well-known/acme-challenge
  chmod -R 755 /var/www/certbot
  chcon -R -t httpd_sys_content_t /var/www/certbot 2>/dev/null || true
  if [[ -f /etc/nginx/conf.d/default.conf && ! -f /etc/nginx/conf.d/default.conf.bak ]]; then
    mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak
  fi

  local install_redirect=0
  if [[ "${INSTALL_LEGACY_REDIRECT}" == "1" \
    && -n "${LEGACY_APP_DOMAIN}" \
    && "${LEGACY_APP_DOMAIN}" != "${APP_DOMAIN}" \
    && "${APP_DOMAIN}" == "livewellops.tekmatrix.ai" ]]; then
    install_redirect=1
  fi

  local install_family_redirect=0
  if [[ "${INSTALL_FAMILY_REDIRECT}" == "1" ]]; then
    install_family_redirect=1
  fi

  install_nginx_site "$APP_DOMAIN" "$APP_ROOT" app
  if [[ -n "${MARKETING_DOMAIN}" && "${MARKETING_DOMAIN}" != "${APP_DOMAIN}" ]]; then
    install_nginx_site "$MARKETING_DOMAIN" "$APP_ROOT" app
  fi
  if [[ "$install_redirect" == "1" ]]; then
    install_nginx_site "$LEGACY_APP_DOMAIN" "$APP_ROOT" redirect
  fi
  if [[ "$install_family_redirect" == "1" ]]; then
    install_nginx_site "family.tekmatrix.ai" "$APP_ROOT" redirect
  fi
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  if [[ "$SKIP_TLS" != "1" ]]; then
    obtain_tls_cert "$APP_DOMAIN"
    if [[ -n "${MARKETING_DOMAIN}" && "${MARKETING_DOMAIN}" != "${APP_DOMAIN}" ]]; then
      obtain_tls_cert "$MARKETING_DOMAIN"
    fi
    if [[ "$install_redirect" == "1" ]]; then
      obtain_tls_cert "$LEGACY_APP_DOMAIN"
    fi
    if [[ "$install_family_redirect" == "1" ]]; then
      obtain_tls_cert "family.tekmatrix.ai"
    fi
    install_nginx_site "$APP_DOMAIN" "$APP_ROOT" app
    if [[ -n "${MARKETING_DOMAIN}" && "${MARKETING_DOMAIN}" != "${APP_DOMAIN}" ]]; then
      install_nginx_site "$MARKETING_DOMAIN" "$APP_ROOT" app
    fi
    if [[ "$install_redirect" == "1" ]]; then
      install_nginx_site "$LEGACY_APP_DOMAIN" "$APP_ROOT" redirect
    fi
    if [[ "$install_family_redirect" == "1" ]]; then
      install_nginx_site "family.tekmatrix.ai" "$APP_ROOT" redirect
    fi
    nginx -t && systemctl reload nginx
  fi
}

install_systemd() {
  [[ "$DEPLOY_SYSTEMD" == "1" ]] || return 0
  log "Installing safehomeops systemd units"
  # Only the two app units. deploy/systemd also holds the IoT ingestor unit
  # (installed by install-livewell-iot-ingestor.sh), the staging units
  # (install-staging.sh) and the health-watch timer (install-health-watch.sh).
  cp "$APP_ROOT"/deploy/systemd/safehomeops-api.service      "$APP_ROOT"/deploy/systemd/safehomeops-web.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable safehomeops-api safehomeops-web
  systemctl restart safehomeops-api safehomeops-web
}

main() {
  require_root
  load_config

  log "SafeHome deploy (config: $ENV_FILE)"

  if [[ "$RUN_BOOTSTRAP" == "1" ]]; then
    bash "$SCRIPT_DIR/bootstrap-ol9.sh"
  fi

  ensure_safehomeops_user
  if [[ "$SKIP_DB_SETUP" != "1" ]]; then
    ensure_postgres_role_db "$APP_DB_USER" "$APP_DB_NAME" "$APP_DB_PASSWORD"
    configure_pg_hba_apps
  else
    log "SKIP_DB_SETUP=1 — PostgreSQL role/database left unchanged"
  fi

  if [[ "$DEPLOY_WORKFORCEOS_CORE" == "1" ]]; then
    pull_workforceos_core "$WORKFORCEOS_CORE_PATH" "$WORKFORCEOS_CORE_REPO" "$WORKFORCEOS_CORE_BRANCH"
  fi

  log "Deploying SafeHome -> $APP_ROOT"
  clone_or_update_repo "$APP_ROOT" "$APP_REPO" "$APP_BRANCH" "$APP_USER"
  write_safehome_env
  deploy_backend_venv "$APP_ROOT" "$APP_USER" "$WORKFORCEOS_CORE_PATH" "$(safehome_seed_cmd)"
  deploy_frontend "$APP_ROOT" "$APP_USER" "$WORKFORCEOS_CORE_PATH"

  install_systemd
  deploy_nginx

  log "Health checks"
  verify_vertical_health "SafeHome" "$API_PORT" "$WEB_PORT" "$APP_DOMAIN" "$SKIP_TLS"
  log "Done."
}

main "$@"
