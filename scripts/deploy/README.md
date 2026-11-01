# Automated VM deploy — SafeHomeOps / Kushalaya

Scripts deploy **workforceos-core** (shared platform) plus the **SafeHome / Kushalaya** app on Oracle Linux 9.

Elder Care and Housekeeping vertical deploys live in their own repos
([ElderCareOps](https://github.com/krishnaposa/ElderCareOps), [HousekeepingOps](https://github.com/krishnaposa/HousekeepingOps)).

## Layout

| Path | Purpose |
|------|---------|
| `workforceos-deploy-lib.sh` | Shared helpers (git pull, opc group, npm build) |
| `deploy-safehome.sh` | Kushalaya / SafeHome full deploy (`APP_DOMAIN=ops.kushalaya.com`) |
| `start-livewell-services.sh` | LiveWell: frontend build + systemd + nginx (no DB/clone) |
| `setup-safehome-postgres.sh` | SafeHome OS user + PostgreSQL DB |
| `install-safehome-sudoers.sh` | Passwordless restart for `safehomeops` |
| `bootstrap-ol9.sh` | First-time OL9 packages (nginx, node, etc.) |
| `deploy/nginx/*.conf` | See `../../deploy/nginx/README.md` (`livewell` marketing + `livewellops` ops) |
| `deploy.safehome.env.example` | Config for SafeHome |
| `backup-safehome-postgres.sh` | Config-driven `pg_dump` → `/var/backups/safehomeops/postgres` |
| `restore-safehome-postgres.sh` | Drop/recreate DB and load a dump |
| `install-safehome-postgres-backup-cron.sh` | Daily cron.d installer |
| `install-livewell-iot.sh` | **One-shot** Mosquitto + IoT ingestor systemd |
| `install-livewell-mqtt.sh` | Mosquitto Docker + TLS certs + users + firewall 8883 |
| `install-livewell-iot-ingestor.sh` | Ingestor env, pip deps, `safehomeops-iot-ingestor` unit |
| `../docs/deploy/POSTGRES_BACKUP.md` | Backup + restore runbook |
| `../../deploy/mqtt/SERVER_SETUP.md` | IoT MQTT server runbook |

## OS user and workforceos-core

App service user **`safehomeops`** is a member of group **`opc`**. Shared platform code lives at:

```text
/opt/workforceos-core   owned by opc:opc, group-writable (2775 / g+rwX)
```

## Quick start — SafeHome

```bash
sudo mkdir -p /etc/workforceos
sudo cp scripts/deploy/deploy.safehome.env.example /etc/workforceos/safehome.env
sudo nano /etc/workforceos/safehome.env   # DB password, APP_SECRET_KEY, CERTBOT_EMAIL
sudo bash scripts/deploy/deploy-safehome.sh
```

## Updates after git push

```bash
# As safehomeops (daily rebuild + restart)
cd /opt/safehomeops/app && git pull && bash scripts/start-livewell.sh

# As root (nginx / TLS / first-time systemd)
sudo bash scripts/deploy/start-livewell-services.sh
# options: --backend-migrate | --skip-tls | --skip-frontend
```

## Quick start — SafeHome as app user

```bash
# Once as root: passwordless systemctl restart for safehomeops
sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-sudoers.sh

# Daily as safehomeops (or sudo from opc — start-livewell.sh re-execs as safehomeops):
cd /opt/safehomeops/app && git pull && bash scripts/start-livewell.sh
```

## Env file

See `deploy.safehome.env.example` for `APP_DOMAIN`, `MARKETING_DOMAIN`, TLS, family WhatsApp CTAs, and optional `BACKUP_*` settings.

## PostgreSQL backups

Not enabled by default. After deploy:

```bash
sudo bash /opt/safehomeops/app/scripts/deploy/backup-safehome-postgres.sh
sudo bash /opt/safehomeops/app/scripts/deploy/install-safehome-postgres-backup-cron.sh
```

Restore runbook: [docs/deploy/POSTGRES_BACKUP.md](../../docs/deploy/POSTGRES_BACKUP.md).
