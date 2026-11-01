# LiveWell IoT — server setup (MQTT + ingestor)

`/opt/safehomeops/app` is owned by **`safehomeops`** (often mode `0700`). Do not expect `opc` or other users to `cd` there.

**Mosquitto does not require Docker.** The install script defaults to the **native** `mosquitto` package (`dnf`/`yum`/`apt`). Runtime files live under **`/var/lib/safehomeops/mqtt`**.

---

## Automated install (recommended)

```bash
sudo -iu safehomeops
cd /opt/safehomeops/app
git pull

sudo bash scripts/deploy/install-livewell-iot.sh \
  --elder-map '{"aa:bb:cc:dd:ee:ff":YOUR_ELDER_ID}'
```

That will:

1. Install **native Mosquitto** (EPEL on OL9/RHEL if needed) — **idempotent** (safe to re-run)
2. Copy TLS certs + ACL → `/var/lib/safehomeops/mqtt` (keeps existing MQTT passwords)
3. Create MQTT users only if missing; refresh `.credentials.app`
4. Open firewall **8883** (`firewalld` or `ufw`)
5. `systemctl enable --now mosquitto` (stops briefly for config validate, then restarts)
6. Set `IOT_INGEST_API_KEY` if missing; preserve `IOT_DEVICE_MAP` unless `--elder-map` is passed
7. Enable/restart `safehomeops-iot-ingestor`

Re-run anytime after `git pull` without rotating secrets:

```bash
sudo bash scripts/deploy/install-livewell-iot.sh
# or rotate MQTT passwords:
sudo bash scripts/deploy/install-livewell-mqtt.sh --force-passwords
```

### Oracle Linux 9 — enable EPEL (if `dnf` says “No match: mosquitto”)

The package lives in **developer EPEL**, which is often installed but **disabled**:

```bash
sudo dnf install -y oracle-epel-release-el9
sudo dnf config-manager --set-enabled ol9_developer_EPEL
sudo dnf config-manager --set-enabled ol9_codeready_builder
sudo dnf makecache
sudo dnf install -y mosquitto mosquitto-clients
```

Then re-run `install-livewell-iot.sh`. Newer scripts do this automatically (and fall back to a direct EPEL RPM or a source build).

### Pieces

```bash
sudo bash scripts/deploy/install-livewell-mqtt.sh
sudo bash scripts/deploy/install-livewell-iot-ingestor.sh \
  --elder-map '{"aa:bb:cc:dd:ee:ff":42}'
```

| Variable / flag | Meaning |
|-----------------|--------|
| `APP_ROOT` | Default `/opt/safehomeops/app` |
| `MQTT_RUNTIME` / `--runtime-dir` | Default `/var/lib/safehomeops/mqtt` |
| `APP_DOMAIN` / `--domain` | TLS name under `/etc/letsencrypt/live/` |
| `APP_USER` | Default `safehomeops` |
| `--skip-firewall` | Skip `ufw allow 8883` |
| `--elder-map JSON` | MAC → elder_id |

Secrets:

- Root: `/var/lib/safehomeops/mqtt/.credentials`
- As **safehomeops**: `/var/lib/safehomeops/mqtt/.credentials.app` (and optionally `deploy/mqtt/.credentials`)

---

## Permissions model

| Path | Who |
|------|-----|
| `/opt/safehomeops/app` | `safehomeops` only (git, `.env`, venv, ingestor env) |
| `/var/lib/safehomeops/mqtt` | Root/Docker (Mosquitto uid **1883** reads certs + passwd) |
| systemd `safehomeops-iot-ingestor` | Runs as `safehomeops` |

Install scripts run as **root** (`sudo bash …`) but use `runuser -u safehomeops` for anything under `APP_ROOT`.

---

## Manual smoke tests

### API key (after install)

```bash
curl -sS -X POST https://livewellops.tekmatrix.ai/api/v1/iot/events \
  -H "Content-Type: application/json" \
  -H "X-IoT-Ingest-Key: YOUR_KEY" \
  -d '{"event_type":"SOS_BUTTON","elder_id":YOUR_ELDER_ID,"mac_address":"aa:bb:cc:dd:ee:ff","hub_id":"lab"}'
```

Key is in `backend/.env` as `IOT_INGEST_API_KEY` (read as safehomeops).

### Dry-run MQTT (no hardware)

```bash
# as safehomeops or root
source /var/lib/safehomeops/mqtt/.credentials.app   # or .credentials

mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/home1/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'

journalctl -u safehomeops-iot-ingestor -n 50 --no-pager
```

### MG7 (MinewLink)

| Setting | Value |
|--------|--------|
| Broker | `livewellops.tekmatrix.ai` |
| Port | `8883` + TLS |
| User / password | `mg7_home1` / from `.credentials.app` |
| Topic | `livewell/homes/home1/hubs/mg7-1/ble` |

No new DNS A record if you reuse `livewellops.tekmatrix.ai`.

---

## Day-2

```bash
sudo -iu safehomeops
cd /opt/safehomeops/app && git pull

# Update device map
nano backend/iot_ingestor.env    # IOT_DEVICE_MAP=...
sudo systemctl restart safehomeops-iot-ingestor

# Broker (native — default)
sudo systemctl status mosquitto --no-pager
sudo journalctl -u mosquitto -n 40 --no-pager
```

Re-install after code changes:

```bash
sudo bash scripts/deploy/install-livewell-iot-ingestor.sh --elder-map '...'
```

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `cd: Permission denied` on `/opt/safehomeops/app` | Use `sudo -iu safehomeops` |
| `docker is not installed` | Normal — native install is default |
| `Empty include_dir value` / line ~905 | Stock `mosquitto.conf` is broken — replace with stub (see below) or re-run install script after `git pull` |


| Script can’t see `deploy/mqtt` | `git pull` as safehomeops; scripts use `runuser -u safehomeops` |
| Mosquitto won’t start | `journalctl -u mosquitto -n 80`; check certs under `/var/lib/safehomeops/mqtt/certs` |
| API `503` IoT not configured | `IOT_INGEST_API_KEY` in `backend/.env`; restart `safehomeops-api` |
| Empty device map | Pass `--elder-map` or edit `iot_ingestor.env` as safehomeops |

---

## See also

- [README.md](./README.md)  
- [../../backend/iot_ingestor/README.md](../../backend/iot_ingestor/README.md)  
- [../../docs/livewell/IOT_B7_MG7_ROADMAP.md](../../docs/livewell/IOT_B7_MG7_ROADMAP.md)  
- [../../docs/livewell/IOT_B7_MG7_FIELD_SETUP.md](../../docs/livewell/IOT_B7_MG7_FIELD_SETUP.md) — configure B7 + MG7 in the field  
- [../../docs/livewell/IOT_B7_MG7_ARCHITECTURE.md](../../docs/livewell/IOT_B7_MG7_ARCHITECTURE.md) — processes and data flow
