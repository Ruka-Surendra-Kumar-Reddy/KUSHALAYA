#!/usr/bin/env bash
# Shared helpers for WorkforceOS VM deploy scripts.
# Source from deploy-*.sh — do not execute directly.

[[ -n "${WORKFORCEOS_DEPLOY_LIB_LOADED:-}" ]] && return 0
WORKFORCEOS_DEPLOY_LIB_LOADED=1

log() { echo "==> $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

require_root() {
  [[ $EUID -eq 0 ]] || die "Run as root: sudo bash $0"
}

ensure_opc_group() {
  getent group opc >/dev/null || groupadd opc
}

ensure_app_user() {
  local user=$1 home=$2
  ensure_opc_group
  if id "$user" &>/dev/null; then
    if ! id -nG "$user" | tr ' ' '\n' | grep -qx opc; then
      usermod -aG opc "$user"
      log "Added $user to group opc"
    else
      log "OS user $user already exists (group opc)"
    fi
    # Ensure home exists when user was created manually with a different -d path.
    if [[ -n "$home" && ! -d "$home" ]]; then
      mkdir -p "$home"
      chown "$user:$user" "$home"
      log "Created missing home directory $home for $user"
    fi
  else
    useradd -r -m -d "$home" -s /bin/bash -G opc "$user"
    log "Created OS user $user (group opc)"
  fi
}

ensure_eldercareops_user() {
  ensure_app_user eldercareops /opt/eldercareops
  mkdir -p /opt/eldercareops /var/lib/eldercareops/uploads /var/backups/eldercareops
  chown -R eldercareops:eldercareops /opt/eldercareops /var/lib/eldercareops
  chcon -R -t httpd_sys_rw_content_t /var/lib/eldercareops/uploads 2>/dev/null || true
}

ensure_housekeepingops_user() {
  ensure_app_user housekeepingops /opt/housekeepingops
  mkdir -p /opt/housekeepingops /var/lib/housekeepingops/uploads /var/backups/housekeepingops
  chown -R housekeepingops:housekeepingops /opt/housekeepingops /var/lib/housekeepingops
  chcon -R -t httpd_sys_rw_content_t /var/lib/housekeepingops/uploads 2>/dev/null || true
}

ensure_safehomeops_user() {
  ensure_app_user safehomeops /opt/safehomeops
  mkdir -p /opt/safehomeops/app /var/lib/safehomeops/uploads /var/backups/safehomeops
  chown -R safehomeops:safehomeops /opt/safehomeops /var/lib/safehomeops /var/backups/safehomeops
  chcon -R -t httpd_sys_rw_content_t /var/lib/safehomeops/uploads 2>/dev/null || true
}

postgres_role_exists() {
  local role=$1
  [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${role}'" 2>/dev/null | tr -d '[:space:]')" == "1" ]]
}

postgres_database_exists() {
  local db=$1
  [[ "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" 2>/dev/null | tr -d '[:space:]')" == "1" ]]
}

configure_workforceos_core_permissions() {
  local path=$1
  ensure_opc_group
  mkdir -p "$path"
  chown -R opc:opc "$path"
  chmod -R g+rwX "$path"
  find "$path" -type d -exec chmod g+s {} \;
  for u in eldercareops housekeepingops safehomeops; do
    id "$u" &>/dev/null && usermod -aG opc "$u" 2>/dev/null || true
  done
}

git_url() {
  local url=$1
  if [[ -n "${GITHUB_TOKEN:-}" && "$url" == https://github.com/* ]]; then
    echo "https://${GITHUB_TOKEN}@${url#https://}"
  else
    echo "$url"
  fi
}

clone_or_update_repo() {
  local dest=$1 url=$2 branch=$3 owner_user=$4
  local clone_url
  clone_url=$(git_url "$url")
  mkdir -p "$(dirname "$dest")"
  if [[ -d "$dest/.git" ]]; then
    log "Updating $(basename "$dest") ($branch) as $owner_user"
    # Production secrets live on disk; deploy scripts rewrite these after pull.
    for local_only in backend/.env frontend/.env.local; do
      if [[ -f "$dest/$local_only" ]]; then
        sudo -u "$owner_user" git -C "$dest" update-index --skip-worktree "$local_only" 2>/dev/null || true
      fi
    done
    sudo -u "$owner_user" git -C "$dest" fetch origin "$branch"
    if ! sudo -u "$owner_user" git -C "$dest" merge --ff-only "origin/$branch" 2>/dev/null; then
      log "Branch diverged — resetting to origin/$branch (skip-worktree files preserved)"
      sudo -u "$owner_user" git -C "$dest" checkout -B "$branch" "origin/$branch"
    fi
  else
    if [[ -d "$dest" ]] && [[ -n "$(ls -A "$dest" 2>/dev/null || true)" ]]; then
      die "Destination $dest exists but is not a git repo — move it aside or choose another APP_ROOT"
    fi
    log "Cloning $url -> $dest ($branch) as $owner_user"
    rm -rf "$dest"
    sudo -u "$owner_user" git clone -b "$branch" "$clone_url" "$dest"
  fi
  if [[ "$owner_user" != opc && -d "$dest/.git" ]]; then
    chown -R "$owner_user:$(id -gn "$owner_user")" "$dest"
  fi
}

pull_workforceos_core() {
  local path=$1 repo=$2 branch=$3
  : "${path:?}"
  : "${repo:?}"
  : "${branch:=develop}"
  log "Pulling workforceos-core at $path"
  clone_or_update_repo "$path" "$repo" "$branch" opc
  configure_workforceos_core_permissions "$path"
  ln -sf "$path/README.md" "$path/python/README.md"
  log "Building @workforceos/contracts (npm) as opc"
  sudo -u opc bash -lc "
    set -euo pipefail
    cd '$path/typescript'
    npm ci
    npm run build
  "
  configure_workforceos_core_permissions "$path"
}

ensure_postgres_role_db() {
  local role=$1 db=$2 password=$3
  local preserve_pw=${PRESERVE_DB_PASSWORD:-0}
  local escaped_pw=${password//\'/\'\'}

  if postgres_role_exists "$role"; then
    log "PostgreSQL role ${role} already exists"
    if [[ "$preserve_pw" == "1" ]]; then
      log "PRESERVE_DB_PASSWORD=1 — keeping existing role password"
    elif [[ -n "$password" ]]; then
      sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
        "ALTER ROLE ${role} WITH PASSWORD '${escaped_pw}';"
    fi
  else
    [[ -n "$password" ]] || die "Password required to create PostgreSQL role ${role}"
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
      "CREATE ROLE ${role} LOGIN PASSWORD '${escaped_pw}';"
    log "Created PostgreSQL role ${role}"
  fi

  if postgres_database_exists "$db"; then
    log "PostgreSQL database ${db} already exists"
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
      "ALTER DATABASE ${db} OWNER TO ${role};" 2>/dev/null || true
  else
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
      "CREATE DATABASE ${db} OWNER ${role};"
    log "Created PostgreSQL database ${db}"
  fi

  sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
    "GRANT ALL PRIVILEGES ON DATABASE ${db} TO ${role};"
}

configure_pg_hba_dual() {
  configure_pg_hba_apps
}

configure_pg_hba_apps() {
  local hba
  hba=$(sudo -u postgres psql -tAc "SHOW hba_file" | tr -d '[:space:]')
  [[ -f "$hba" ]] || die "pg_hba.conf not found"
  local changed=0
  local line
  for line in \
    "host    eldercareops        eldercareops        127.0.0.1/32    scram-sha-256" \
    "host    housekeepingops     housekeepingops     127.0.0.1/32    scram-sha-256" \
    "host    safehomeops         safehomeops         127.0.0.1/32    scram-sha-256"
  do
    if ! grep -qF "$line" "$hba"; then
      if [[ "$changed" -eq 0 ]]; then
        log "Adding scram-sha-256 rules to $hba"
        if ! grep -q "# workforceos app deploy" "$hba"; then
          printf '\n# workforceos app deploy\n' >>"$hba"
        fi
      fi
      echo "$line" >>"$hba"
      changed=1
    fi
  done
  if [[ "$changed" -eq 1 ]]; then
    systemctl restart postgresql
  else
    log "pg_hba already configured for WorkforceOS apps"
  fi
}

deploy_frontend() {
  local app_root=$1 user=$2 core_path=$3
  sudo -u "$user" bash -lc "
    set -euo pipefail
    export WORKFORCEOS_CORE='$core_path'
    bash '$app_root/scripts/link-workforceos-core.sh'
    cd '$app_root/frontend'
    rm -rf node_modules .next
    npm ci
    npm run build
  "
}

deploy_backend_venv() {
  local app_root=$1 user=$2 core_path=$3 seed_cmd=$4
  local backend=$app_root/backend
  sudo -u "$user" bash -lc "
    set -euo pipefail
    cd '$backend'
    if [[ ! -d .venv ]]; then python3.11 -m venv .venv; fi
    source .venv/bin/activate
    export WORKFORCEOS_CORE='$core_path'
    bash '$app_root/scripts/install-backend-deps.sh'
    python -m app.init_db
    $seed_cmd
  "
}

verify_vertical_health() {
  local label=$1 api_port=$2 web_port=$3 domain=$4 skip_tls=$5
  local i api_ok=0
  for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${api_port}/health" >/dev/null 2>&1; then
      echo "  ${label} API :${api_port} OK"
      api_ok=1
      break
    fi
    sleep 1
  done
  if [[ "$api_ok" != "1" ]]; then
    echo "  ${label} API :${api_port} FAILED"
  fi
  curl -fsS -o /dev/null "http://127.0.0.1:${web_port}/" 2>/dev/null \
    && echo "  ${label} web :${web_port} OK" \
    || echo "  ${label} web :${web_port} FAILED"
  if [[ "$skip_tls" != "1" && -n "$domain" ]]; then
    curl -fsS "https://${domain}/health" >/dev/null 2>&1 \
      && echo "  https://${domain}/health OK" \
      || echo "  https://${domain}/health FAILED"
  fi
}

install_tekmatrix_static_site() {
  local app_root=$1
  [[ "${DEPLOY_TEKMATRIX_SITE:-1}" == "1" ]] || return 0

  local web_root="${TEKMATRIX_WEB_ROOT:-/var/www/tekmatrix}"
  local src_html="$app_root/frontend/public/tekmatrix-home.html"
  local src_logo="$app_root/frontend/public/tekmatrix.jpeg"

  [[ -f "$src_html" ]] || die "Missing corporate site source: $src_html"

  log "Publishing Tek Matrix corporate site -> $web_root"
  mkdir -p "$web_root"
  cp "$src_html" "$web_root/index.html"
  [[ -f "$src_logo" ]] && cp "$src_logo" "$web_root/tekmatrix.jpeg"

  if id nginx &>/dev/null; then
    chown -R nginx:nginx "$web_root"
  elif id www-data &>/dev/null; then
    chown -R www-data:www-data "$web_root"
  fi
  chmod -R a+rX "$web_root"
  chcon -R -t httpd_sys_content_t "$web_root" 2>/dev/null || true
}

install_tekmatrix_nginx_site() {
  local app_root=$1
  [[ "${DEPLOY_TEKMATRIX_SITE:-1}" == "1" ]] || return 0
  [[ "${DEPLOY_NGINX:-1}" == "1" ]] || return 0

  local domain="${TEKMATRIX_DOMAIN:-tekmatrix.ai}"
  local dst="/etc/nginx/conf.d/${domain}.conf"
  local https="$app_root/deploy/nginx/${domain}.conf"
  local http="$app_root/deploy/nginx/${domain}-http-only.conf"
  local src

  if [[ -f "/etc/letsencrypt/live/${domain}/fullchain.pem" && -f "$https" ]]; then
    src="$https"
  elif [[ -f "$http" ]]; then
    src="$http"
  else
    die "No nginx template for $domain under $app_root/deploy/nginx/"
  fi

  log "Installing nginx (corporate): $src -> $dst"
  cp "$src" "$dst"
}

obtain_tekmatrix_tls_cert() {
  [[ "${DEPLOY_TEKMATRIX_SITE:-1}" == "1" ]] || return 0
  [[ "${SKIP_TLS:-0}" == "1" ]] || return 0

  local domain="${TEKMATRIX_DOMAIN:-tekmatrix.ai}"
  local www="${TEKMATRIX_WWW_DOMAIN:-www.tekmatrix.ai}"

  [[ -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]] && return 0
  log "Requesting TLS certificate for $domain (+ $www)"
  certbot certonly --non-interactive --agree-tos -m "$CERTBOT_EMAIL" \
    --webroot -w /var/www/certbot -d "$domain" -d "$www"
}

deploy_tekmatrix_corporate_site() {
  local app_root=$1
  [[ "${DEPLOY_TEKMATRIX_SITE:-1}" == "1" ]] || return 0

  install_tekmatrix_static_site "$app_root"
  install_tekmatrix_nginx_site "$app_root"

  if [[ "${DEPLOY_NGINX:-1}" == "1" ]]; then
    systemctl enable --now nginx 2>/dev/null || true
    nginx -t
    systemctl reload nginx
    if [[ "${SKIP_TLS:-0}" != "1" ]]; then
      obtain_tekmatrix_tls_cert
      install_tekmatrix_nginx_site "$app_root"
      nginx -t && systemctl reload nginx
    fi
  fi
}

verify_tekmatrix_site() {
  [[ "${DEPLOY_TEKMATRIX_SITE:-1}" == "1" ]] || return 0
  local domain="${TEKMATRIX_DOMAIN:-tekmatrix.ai}"
  curl -fsS -o /dev/null "http://127.0.0.1/" -H "Host: ${domain}" \
    && echo "  Tek Matrix corporate site (Host: ${domain}) OK"
  if [[ "${SKIP_TLS:-0}" != "1" ]]; then
    curl -fsS -o /dev/null "https://${domain}/" \
      && echo "  https://${domain}/ OK"
  fi
}
