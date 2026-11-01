# PostgreSQL backup & restore — SafeHome / Kushalaya

Daily dumps are **not** installed by the main deploy by default. Use the scripts below (config-driven).

## Quick setup (production VM)

```bash
# 1) Optional: set backup options in /etc/workforceos/safehome.env
sudo nano /etc/workforceos/safehome.env

# 2) Run one backup now
sudo bash /opt/safehomeops/app/scripts/deploy/backup-safehome-postgres.sh

# 3) Install daily cron (default 02:15)
sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-postgres-backup-cron.sh
```

Config is read from (exported env wins; then each file fills missing keys):

1. Environment / CLI  
2. `/etc/workforceos/safehome.env`  
3. `$APP_ROOT/backend/.env` (`DATABASE_URL`)

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASE_URL` | from `backend/.env` or built from `APP_DB_*` | Connection for `pg_dump` / `pg_restore` |
| `APP_DB_NAME` / `APP_DB_USER` | `safehomeops` | Database / role |
| `BACKUP_DIR` | `/var/backups/safehomeops/postgres` | Dump directory |
| `BACKUP_RETENTION_DAYS` | `14` | Delete older dumps |
| `BACKUP_FORMAT` | `plain` | `plain` → `.sql.gz` · `custom` → `.dump` |
| `BACKUP_PREFIX` | `safehomeops` | Filename prefix |
| `BACKUP_CRON_SCHEDULE` | `15 2 * * *` | cron.d schedule (daily 02:15) |
| `BACKUP_OFFSITE_CMD` | _(empty)_ | Optional shell snippet; `$1` is the new backup path |
| `BACKUP_STOP_API` | `1` | Restore stops `safehomeops-api` unless `--keep-api` |

Example offsite copy:

```bash
BACKUP_OFFSITE_CMD='rsync -az "$1" backup@vault:/data/safehomeops/postgres/'
```

## Backup

```bash
sudo bash scripts/deploy/backup-safehome-postgres.sh
sudo bash scripts/deploy/backup-safehome-postgres.sh --list
```

Cron log: `/var/log/safehomeops-postgres-backup.log`

Remove cron:

```bash
sudo bash scripts/deploy/install-safehome-postgres-backup-cron.sh --remove
```

## Restore

**This replaces the live database.** Confirm carefully.

```bash
# See dumps
sudo bash scripts/deploy/restore-safehome-postgres.sh --list

# Restore newest dump (prompts: type RESTORE)
sudo bash scripts/deploy/restore-safehome-postgres.sh

# Specific file, no prompt, then migrations
sudo bash scripts/deploy/restore-safehome-postgres.sh \
  --file /var/backups/safehomeops/postgres/safehomeops-HOST-YYYYMMDD-HHMMSS.sql.gz \
  --yes \
  --migrate
```

What restore does:

1. Optionally stops `safehomeops-api`  
2. Terminates DB sessions, `DROP DATABASE` / `CREATE DATABASE`  
3. Loads `.sql.gz` via `psql` or `.dump` via `pg_restore`  
4. Reassigns ownership to `APP_DB_USER`  
5. Optionally runs `python -m app.init_db` (`--migrate`)  
6. Restarts the API if it was stopped  

### After restore checklist

```bash
curl -fsS http://127.0.0.1:8010/health
sudo -u postgres psql -d safehomeops -c '\dt'
sudo systemctl status safehomeops-api safehomeops-web --no-pager
```

**Uploads are not in the DB dump.** If you need photos/files back, restore `/var/lib/safehomeops/uploads` (or R2) from your file backup separately.

## Windows (dev)

```powershell
$env:DATABASE_URL = "postgresql://…"
.\scripts\backup-postgres.ps1
```

## Scripts

| Script | Role |
|--------|------|
| `scripts/deploy/postgres-backup-lib.sh` | Shared config loader |
| `scripts/deploy/backup-safehome-postgres.sh` | Dump + retention |
| `scripts/deploy/restore-safehome-postgres.sh` | Interactive / scripted restore |
| `scripts/deploy/install-safehome-postgres-backup-cron.sh` | Install `/etc/cron.d/safehomeops-postgres-backup` |
