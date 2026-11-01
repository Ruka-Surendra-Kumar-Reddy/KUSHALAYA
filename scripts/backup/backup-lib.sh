#!/usr/bin/env bash
# Shared helpers for scripts/backup/backup-db.sh and restore-test.sh (#105).
#
# Settings come from /etc/safehomeops/backup.env (see docs/BACKUP.md). The database
# password is NEVER copied there: DATABASE_URL is read from backend/.env at run time.

set -Eeuo pipefail

BACKUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Reuse the env-file reader + pg_* finders from the existing local-backup scripts.
# shellcheck source=../deploy/postgres-backup-lib.sh
source "$BACKUP_LIB_DIR/../deploy/postgres-backup-lib.sh"

load_offsite_backup_config() {
  _load_env_file "${BACKUP_ENV_FILE:-/etc/safehomeops/backup.env}"
  load_safehome_backup_config # reads $APP_ROOT/backend/.env (DATABASE_URL, UPLOAD_DIR)

  : "${BACKUP_RCLONE_REMOTE:?Set BACKUP_RCLONE_REMOTE (e.g. oci-backup:kushalaya-backups/safehomeops)}"
  : "${BACKUP_KEY_FILE:?Set BACKUP_KEY_FILE (gpg passphrase file or age identity file)}"
  : "${BACKUP_CIPHER:=gpg}"                       # gpg | age
  : "${BACKUP_KEEP_DAILY:=14}"
  : "${BACKUP_KEEP_WEEKLY:=8}"
  : "${BACKUP_WORK_DIR:=/var/backups/safehomeops/offsite}"
  : "${BACKUP_STATUS_FILE:=/var/lib/safehomeops/backup/status.json}"
  : "${BACKUP_LOCK_FILE:=/run/safehomeops-backup.lock}"
  : "${RESTORE_PG_AS:=postgres}"                  # OS user that may createdb/dropdb
  : "${RESTORE_PG_PORT:=5432}"

  if [[ -z "${BACKUP_UPLOADS_DIR:-}" ]]; then
    local up="${UPLOAD_DIR:-uploads}"
    [[ "$up" == /* ]] || up="$APP_ROOT/backend/$up"
    BACKUP_UPLOADS_DIR="$up"
  fi

  [[ -r "$BACKUP_KEY_FILE" ]] || die "Key file not readable: $BACKUP_KEY_FILE"
  command -v rclone >/dev/null 2>&1 || die "rclone not installed"
  case "$BACKUP_CIPHER" in
    gpg) command -v gpg >/dev/null 2>&1 || die "gpg not installed" ;;
    age) command -v age >/dev/null 2>&1 || die "age not installed" ;;
    *) die "BACKUP_CIPHER must be gpg or age" ;;
  esac
  RCLONE_ARGS=()
  [[ -n "${RCLONE_CONFIG:-}" ]] && RCLONE_ARGS+=(--config "$RCLONE_CONFIG")
  export BACKUP_UPLOADS_DIR
}

# pg_dump/psql want postgresql://, SQLAlchemy URLs may say postgresql+psycopg2://
libpq_url() {
  local url
  url="$(resolve_database_url)"
  url="${url/postgresql+psycopg2:\/\//postgresql://}"
  url="${url/postgresql+psycopg:\/\//postgresql://}"
  url="${url/postgres:\/\//postgresql://}"
  [[ "$url" == postgresql://* ]] || die "DATABASE_URL is not PostgreSQL"
  echo "$url"
}

# Keep the password out of argv (visible in `ps`): write it to a 0600 PGPASSFILE and
# print the same URL WITHOUT the password. The URL reaches python through the
# environment, never the command line.
#   SAFE_URL="$(pgpass_url "$URL" "$PGPASS_TMP")"; export PGPASSFILE="$PGPASS_TMP"
pgpass_url() { # url pgpass_file
  ( umask 077 && : >"$2" )
  chmod 600 "$2"
  PGPASS_URL_IN="$1" python3 - "$2" <<'PY'
import os, sys
from urllib.parse import unquote, urlsplit, urlunsplit

url = os.environ["PGPASS_URL_IN"]
parts = urlsplit(url)
user = unquote(parts.username or "")
password = unquote(parts.password or "")
host = parts.hostname or ""
netloc = parts.netloc.rsplit("@", 1)[-1]
if user:
    netloc = parts.netloc.rsplit("@", 1)[0].split(":", 1)[0] + "@" + netloc


def esc(value):
    return value.replace("\\", "\\\\").replace(":", "\\:")


if password:
    line = ":".join([esc(host) if host else "*", str(parts.port or "*"), "*", esc(user) if user else "*",
                     esc(password)])
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(line + "\n")
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

rc() { rclone "${RCLONE_ARGS[@]}" "$@"; }

encrypt_file() { # in out
  case "$BACKUP_CIPHER" in
    gpg) gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$BACKUP_KEY_FILE" \
           --symmetric --cipher-algo AES256 --output "$2" "$1" ;;
    age) age --encrypt --recipient "$(age-keygen -y "$BACKUP_KEY_FILE")" --output "$2" "$1" ;;
  esac
}

decrypt_file() { # in out
  case "$BACKUP_CIPHER" in
    gpg) gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$BACKUP_KEY_FILE" \
           --decrypt --output "$2" "$1" ;;
    age) age --decrypt --identity "$BACKUP_KEY_FILE" --output "$2" "$1" ;;
  esac
}

enc_ext() { [[ "$BACKUP_CIPHER" == age ]] && echo age || echo gpg; }

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Merge KEY=VALUE pairs into the JSON status file the admin dashboard reads.
# Values that are plain integers are stored as numbers. No secrets go in here.
write_status() {
  local dir
  dir="$(dirname "$BACKUP_STATUS_FILE")"
  mkdir -p "$dir"
  chmod 755 "$dir" 2>/dev/null || true
  python3 - "$BACKUP_STATUS_FILE" "$@" <<'PY'
import json, os, sys
path, pairs = sys.argv[1], sys.argv[2:]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except (OSError, ValueError):
    data = {}
for pair in pairs:
    key, _, value = pair.partition("=")
    data[key] = int(value) if value.isdigit() else value
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
os.chmod(tmp, 0o644)
os.replace(tmp, path)
PY
}
