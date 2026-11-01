#!/usr/bin/env bash
# Build frontend, install systemd + nginx, and start SafeHomeOps services.
#
# Use after the app is cloned and DB initialized (manual or deploy-safehome.sh).
# Idempotent — safe to re-run after git pull.
#
# Usage (on the VM):
#
# As safehomeops (day-to-day after git pull) — preferred:
#   cd /opt/safehomeops/app && bash scripts/start-livewell.sh
#   bash scripts/start-livewell.sh --backend-migrate
#
# As root/opc (first install of units + nginx): app builds still run as safehomeops:
#   sudo bash scripts/deploy/start-livewell-services.sh
#   sudo bash scripts/deploy/install-safehome-sudoers.sh   # once: passwordless restart for app user
#
# Options (this root script):
#   --env PATH          Deploy config (default: /etc/workforceos/safehome.env if present)
#   --skip-frontend     Do not npm ci / build (restart units only)
#   --skip-nginx        Do not touch nginx
#   --skip-tls          Do not request Let's Encrypt cert
#   --backend-migrate   Run pip install + python -m app.init_db before start
#   KEEP_APP_DOMAIN=1   Do not auto-promote APP_DOMAIN to ops.kushalaya.com
#   --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=workforceos-deploy-lib.sh
source "$SCRIPT_DIR/workforceos-deploy-lib.sh"

ENV_FILE="${DEPLOY_ENV_FILE:-}"
SKIP_FRONTEND=0
SKIP_NGINX=0
SKIP_TLS_FLAG=""
BACKEND_MIGRATE=0

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="${2:?}"
      shift 2
      ;;
    --skip-frontend)
      SKIP_FRONTEND=1
      shift
      ;;
    --skip-nginx)
      SKIP_NGINX=1
      shift
      ;;
    --skip-tls)
      SKIP_TLS_FLAG=1
      shift
      ;;
    --backend-migrate)
      BACKEND_MIGRATE=1
      shift
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
  : "${WORKFORCEOS_CORE_PATH:=/opt/workforceos-core}"
  : "${APP_ROOT:=/opt/safehomeops/app}"
  : "${APP_USER:=safehomeops}"
  : "${APP_DOMAIN:=ops.kushalaya.com}"
  : "${MARKETING_DOMAIN:=www.kushalaya.com}"
  : "${LEGACY_APP_DOMAIN:=safehome.tekmatrix.ai}"
  : "${INSTALL_LEGACY_REDIRECT:=1}"
  : "${INSTALL_FAMILY_REDIRECT:=0}"
  : "${API_PORT:=8010}"
  : "${WEB_PORT:=3010}"
  : "${SKIP_TLS:=0}"
  : "${CERTBOT_EMAIL:=}"
  : "${DEPLOY_NGINX:=1}"
  : "${DEPLOY_SYSTEMD:=1}"
  : "${KEEP_APP_DOMAIN:=0}"

  if [[ -z "$ENV_FILE" && -f /etc/workforceos/safehome.env ]]; then
    ENV_FILE=/etc/workforceos/safehome.env
  fi

  if [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]]; then
    log "Loading config: $ENV_FILE"
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    : "${WORKFORCEOS_CORE_PATH:=/opt/workforceos-core}"
    : "${APP_ROOT:=/opt/safehomeops/app}"
    : "${APP_USER:=safehomeops}"
    : "${APP_DOMAIN:=ops.kushalaya.com}"
    : "${MARKETING_DOMAIN:=www.kushalaya.com}"
    : "${LEGACY_APP_DOMAIN:=safehome.tekmatrix.ai}"
    : "${INSTALL_LEGACY_REDIRECT:=1}"
    : "${INSTALL_FAMILY_REDIRECT:=0}"
    : "${API_PORT:=8010}"
    : "${WEB_PORT:=3010}"
    : "${SKIP_TLS:=0}"
    : "${CERTBOT_EMAIL:=}"
    : "${DEPLOY_NGINX:=1}"
    : "${DEPLOY_SYSTEMD:=1}"
    : "${KEEP_APP_DOMAIN:=0}"
  else
    log "No env file — using defaults (APP_ROOT=$APP_ROOT DOMAIN=$APP_DOMAIN)"
  fi

  if [[ -n "$SKIP_TLS_FLAG" ]]; then
    SKIP_TLS=1
  fi

  # Cut over to the Kushalaya ops host unless KEEP_APP_DOMAIN=1.
  # Old /etc/workforceos/safehome.env may still carry a retired tekmatrix.ai host.
  if [[ "${KEEP_APP_DOMAIN}" != "1" ]]; then
    if [[ "${APP_DOMAIN}" != "ops.kushalaya.com" ]]; then
      log "Promoting APP_DOMAIN ${APP_DOMAIN} -> ops.kushalaya.com (set KEEP_APP_DOMAIN=1 to skip)"
      # A retiring tekmatrix.ai host becomes the legacy redirect target.
      case "${APP_DOMAIN}" in
        *.tekmatrix.ai) LEGACY_APP_DOMAIN="${APP_DOMAIN}" ;;
      esac
      LEGACY_APP_DOMAIN="${LEGACY_APP_DOMAIN:-livewellops.tekmatrix.ai}"
      if [[ "${LEGACY_APP_DOMAIN}" == "ops.kushalaya.com" ]]; then
        LEGACY_APP_DOMAIN=livewellops.tekmatrix.ai
      fi
      APP_DOMAIN=ops.kushalaya.com
    fi
    : "${MARKETING_DOMAIN:=www.kushalaya.com}"
    INSTALL_LEGACY_REDIRECT=1
  fi

  [[ -d "$APP_ROOT/backend" ]] || die "App not found at $APP_ROOT (clone SafeHomeOps first)"
  [[ -f "$APP_ROOT/backend/.env" ]] || die "Missing $APP_ROOT/backend/.env — create it or run deploy-safehome.sh once"
  id "$APP_USER" &>/dev/null || die "OS user $APP_USER missing — run setup-safehome-postgres.sh or deploy-safehome.sh"
}

sync_public_urls() {
  local fe_env="$APP_ROOT/frontend/.env.local"
  local be_env="$APP_ROOT/backend/.env"
  local origins="https://${APP_DOMAIN}"
  if [[ -n "${MARKETING_DOMAIN}" && "${MARKETING_DOMAIN}" != "${APP_DOMAIN}" ]]; then
    origins="${origins},https://${MARKETING_DOMAIN}"
  fi
  if [[ "${INSTALL_LEGACY_REDIRECT}" == "1" \
    && -n "${LEGACY_APP_DOMAIN}" \
    && "${LEGACY_APP_DOMAIN}" != "${APP_DOMAIN}" \
    && "${LEGACY_APP_DOMAIN}" != "${MARKETING_DOMAIN}" ]]; then
    origins="${origins},https://${LEGACY_APP_DOMAIN}"
  fi

  {
    echo "NEXT_PUBLIC_API_URL=https://${APP_DOMAIN}"
    echo "NEXT_PUBLIC_FAMILY_PORTAL_URL=${FAMILY_PORTAL_URL:-https://family.kushalaya.com/login}"
    echo "NEXT_PUBLIC_BRAND_NAME=${NEXT_PUBLIC_BRAND_NAME:-${BRAND_NAME:-KushAlaya}}"
    if [[ -n "${NEXT_PUBLIC_BRAND_MARK:-}" ]]; then
      echo "NEXT_PUBLIC_BRAND_MARK=${NEXT_PUBLIC_BRAND_MARK}"
    fi
    if [[ -n "${NEXT_PUBLIC_BRAND_ACCENT:-}" ]]; then
      echo "NEXT_PUBLIC_BRAND_ACCENT=${NEXT_PUBLIC_BRAND_ACCENT}"
    fi
  } >"$fe_env"
  chown "$APP_USER:$APP_USER" "$fe_env"
  log "Wrote $fe_env (NEXT_PUBLIC_API_URL=https://${APP_DOMAIN})"

  if [[ -f "$be_env" ]]; then
    if grep -q '^CORS_ORIGINS=' "$be_env"; then
      sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=${origins}|" "$be_env"
    else
      echo "CORS_ORIGINS=${origins}" >>"$be_env"
    fi
    if grep -q '^BRAND_NAME=' "$be_env"; then
      sed -i "s|^BRAND_NAME=.*|BRAND_NAME=${BRAND_NAME:-KushAlaya}|" "$be_env"
    else
      echo "BRAND_NAME=${BRAND_NAME:-KushAlaya}" >>"$be_env"
    fi
    log "Updated CORS_ORIGINS / BRAND_NAME in $be_env"
  fi
}

ensure_frontend_env() {
  sync_public_urls
}

run_backend_migrate() {
  [[ "$BACKEND_MIGRATE" == "1" ]] || return 0
  log "Backend deps + init_db"
  sudo -u "$APP_USER" bash -lc "
    set -euo pipefail
    cd '$APP_ROOT/backend'
    if [[ ! -d .venv ]]; then python3.11 -m venv .venv; fi
    source .venv/bin/activate
    export WORKFORCEOS_CORE='$WORKFORCEOS_CORE_PATH'
    bash '$APP_ROOT/scripts/install-backend-deps.sh'
    python -m app.init_db
  "
}

build_frontend() {
  [[ "$SKIP_FRONTEND" == "1" ]] && {
    log "Skipping frontend build"
    return 0
  }
  ensure_frontend_env

  # Prefer a real (non-symlink) vendored tree with LIVEWELL360. A symlink to
  # /opt/workforceos-core is treated as shared core — always resolve to the
  # real path so safehomeops cds into /opt, not only via the app symlink.
  local core_for_fe="$WORKFORCEOS_CORE_PATH"
  local app_core="$APP_ROOT/workforceos-core"
  local core_real=""
  if [[ -e "$app_core" ]]; then
    core_real="$(readlink -f "$app_core" 2>/dev/null || true)"
  fi

  if [[ -d "$app_core" && ! -L "$app_core" ]] \
    && [[ -f "$app_core/contracts/verticals.json" ]] \
    && grep -q '"LIVEWELL360"' "$app_core/contracts/verticals.json"; then
    core_for_fe="$app_core"
    log "Frontend contracts: vendored $core_for_fe (LIVEWELL360)"
  elif [[ -n "$core_real" ]] \
    && [[ -f "$core_real/contracts/verticals.json" ]] \
    && grep -q '"LIVEWELL360"' "$core_real/contracts/verticals.json"; then
    core_for_fe="$core_real"
    log "Frontend contracts: shared $core_for_fe (LIVEWELL360 via $app_core)"
  elif [[ -f "$core_for_fe/contracts/verticals.json" ]] \
    && grep -q '"LIVEWELL360"' "$core_for_fe/contracts/verticals.json"; then
    core_for_fe="$(readlink -f "$core_for_fe" 2>/dev/null || echo "$core_for_fe")"
    log "Frontend contracts: $core_for_fe (LIVEWELL360)"
  else
    log "Frontend contracts: $core_for_fe"
  fi

  # Always build as safehomeops. Shared /opt core is opc:opc with group write
  # for app users (safehomeops ∈ opc); refresh perms before npm.
  local contracts_root="$core_for_fe"
  if [[ "$contracts_root" == /opt/workforceos-core || "$contracts_root" == /opt/workforceos-core/* ]]; then
    configure_workforceos_core_permissions "$contracts_root"
  fi

  log "Building @workforceos/contracts (as $APP_USER in $contracts_root)"
  sudo -u "$APP_USER" bash -lc "
    set -euo pipefail
    cd '$contracts_root/typescript'
    npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts
    npm run build
  "
  if [[ "$contracts_root" == /opt/workforceos-core || "$contracts_root" == /opt/workforceos-core/* ]]; then
    configure_workforceos_core_permissions "$contracts_root"
  fi

  log "Building frontend"
  deploy_frontend "$APP_ROOT" "$APP_USER" "$core_for_fe"
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

  # Fallback template for arbitrary ops hostnames
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
  [[ -n "$CERTBOT_EMAIL" ]] || die "Set CERTBOT_EMAIL in env file or pass --skip-tls"
  log "Requesting TLS certificate for $domain"
  certbot certonly --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --webroot -w /var/www/certbot -d "$domain"
}

deploy_nginx() {
  [[ "$SKIP_NGINX" == "1" || "$DEPLOY_NGINX" != "1" ]] && {
    log "Skipping nginx"
    return 0
  }
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
  log "Installing / restarting safehomeops systemd units"
  [[ -f "$APP_ROOT/deploy/systemd/safehomeops-api.service" ]] \
    || die "Missing $APP_ROOT/deploy/systemd/safehomeops-api.service"
  # Only the two app units — deploy/systemd also holds the IoT ingestor unit
  # (install-livewell-iot-ingestor.sh), the staging units (install-staging.sh)
  # and the health-watch timer (install-health-watch.sh).
  cp "$APP_ROOT"/deploy/systemd/safehomeops-api.service      "$APP_ROOT"/deploy/systemd/safehomeops-web.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable safehomeops-api safehomeops-web
  systemctl restart safehomeops-api safehomeops-web
  sleep 2
  systemctl --no-pager --full status safehomeops-api safehomeops-web || true
}

main() {
  require_root
  load_config

  log "Starting SafeHomeOps services (APP_ROOT=$APP_ROOT)"

  ensure_safehomeops_user
  run_backend_migrate
  build_frontend
  install_systemd
  deploy_nginx

  log "Health checks"
  verify_vertical_health "SafeHome" "$API_PORT" "$WEB_PORT" "$APP_DOMAIN" "$SKIP_TLS"
  log "Done."
  echo ""
  echo "  Local API:  http://127.0.0.1:${API_PORT}/health"
  echo "  Local web:  http://127.0.0.1:${WEB_PORT}/"
  if [[ "$SKIP_TLS" != "1" ]]; then
    echo "  Marketing:  https://${MARKETING_DOMAIN:-livewell.tekmatrix.ai}/"
    echo "  Ops:        https://${APP_DOMAIN}/"
  fi
  echo "  Logs:       journalctl -u safehomeops-api -f"
}

main "$@"
