# LiveWell IoT — processes, services, and how they talk to B7 / MG7

This document explains **what runs on the server**, **what runs in the home**, and **how a B7 SOS press becomes a LiveWell alert**.

Field install steps: [IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md)  
Server install: [../../deploy/mqtt/SERVER_SETUP.md](../../deploy/mqtt/SERVER_SETUP.md)

---

## Big picture

```text
 HOME / SITE                         LIVEWELL SERVER
 ─────────────────                   ─────────────────────────────────────────

  ┌─────────┐  BLE ads               ┌──────────────────┐
  │ Minew   │  (SOS button)          │ mosquitto        │  systemd
  │ B7      │─────────────────┐      │ :8883 TLS (MG7)  │
  │ band    │                 │      │ :1883 localhost  │
  └─────────┘                 │      └────────┬─────────┘
                              │               │ subscribe
                       ┌──────▼──────┐        │
                       │ Minew MG7   │ MQTT   │
                       │ BLE gateway │────────┘
                       │ (Wi‑Fi/Eth) │
                       └─────────────┘        ┌──────────────────┐
                                              │ safehomeops-     │  systemd
                                              │ iot-ingestor     │
                                              │ (python -m       │
                                              │  iot_ingestor)   │
                                              └────────┬─────────┘
                                                       │ HTTP POST
                                                       │ X-IoT-Ingest-Key
                                                       ▼
                                              ┌──────────────────┐
                                              │ safehomeops-api  │  systemd
                                              │ (uvicorn FastAPI)│
                                              │ POST /api/v1/iot │
                                              │     /events      │
                                              └────────┬─────────┘
                                                       │ DB write
                                                       │ family_hub alerts
                                                       ▼
                                              ┌──────────────────┐
                                              │ Postgres / app   │
                                              │ DB + elder JSON  │
                                              └────────┬─────────┘
                                                       │
                       ┌──────────────┐                │ HTTPS
                       │ Family /     │◄───────────────┘
                       │ staff apps   │  nginx → API
                       └──────────────┘
```

**Important:** The B7 never talks to LiveWell directly. The MG7 never calls the FastAPI API. Mosquitto is a message bus; the **ingestor** is the bridge into LiveWell.

---

## Home-side devices (not server processes)

| Device | Role | Protocol |
|--------|------|----------|
| **Minew B7** | Wearable SOS button (+ optional accel). Broadcasts BLE advertisements when pressed (and normally at a slower rate). | Bluetooth LE only |
| **Minew MG7** | Scans BLE, packages ads, publishes to your MQTT broker over the internet. | BLE in → MQTT/TLS out |

Configured with Minew apps (**BeaconSET Plus** for B7, **MinewLink** for MG7), not inside the LiveWell UI (Phase 1).

---

## Server processes and services

These are created or used by the LiveWell IoT install (`install-livewell-iot.sh` / mqtt + ingestor scripts).

### 1. `mosquitto.service` (MQTT broker)

| | |
|--|--|
| **Unit** | `mosquitto.service` (native package; default) |
| **User** | `mosquitto` |
| **Config** | `/etc/mosquitto/mosquitto.conf` → `include_dir /etc/mosquitto/conf.d` → **`livewell.conf`** |
| **Runtime files** | `/var/lib/safehomeops/mqtt/` (passwd, acl, TLS certs, data) |
| **Listens** | **8883** (public MQTTS for MG7) · **1883** on `127.0.0.1` only (ingestor) |

**Does:** Accepts publishes from the MG7; fans out to any local subscriber (the ingestor). Does **not** know about elders, SOS product logic, or the LiveWell database.

**Users (typical):**

- `mg7_home1` — hub may **write** `livewell/homes/home1/hubs/+/ble`
- `livewell_ingestor` — may **read** `livewell/#`

**Check:**

```bash
sudo systemctl status mosquitto
sudo journalctl -u mosquitto -n 50 --no-pager
```

---

### 2. `safehomeops-iot-ingestor.service` (MQTT → HTTP bridge)

| | |
|--|--|
| **Unit** | `/etc/systemd/system/safehomeops-iot-ingestor.service` |
| **User** | `safehomeops` |
| **Code** | `backend/iot_ingestor` → `python -m iot_ingestor` |
| **Env** | `/opt/safehomeops/app/backend/iot_ingestor.env` |
| **Connects to** | Mosquitto `127.0.0.1:1883` as `livewell_ingestor` |
| **Calls** | `http://127.0.0.1:8010/api/v1/iot/events` with `X-IoT-Ingest-Key` |

**Does:**

1. Subscribe to comma-separated `MQTT_TOPIC` filters (must include `/mg7/+/status` for Minew).
2. Decode MG7 JSON arrays: iBeacon **1/1 = SOS**; Minew **FFE1 A103** XYZ delta = motion; other ads (including always-on iBeacon 1/2) = last-seen heartbeat.
3. Map **MAC → elder_id** from `GET /api/v1/iot/device-map` (env `IOT_DEVICE_MAP` optional override).
4. **SOS dedupe** ~65s per band (B7 keeps advertising after a press).
5. Minute watch: `DEVICE_OFFLINE` if not heard; `IMMOBILITY_WARNING` if online, no A103 XYZ change recently, during active hours (immobility **on** by default).
6. POST normalized events to the LiveWell API.

**Does not:** Store long-term incidents itself; talk to B7; expose a public port.

**Check:**

```bash
sudo systemctl status safehomeops-iot-ingestor
journalctl -u safehomeops-iot-ingestor -f
```

### Successful ingest log patterns (developer)

Each accepted event is two INFO lines: the HTTP POST to the API, then the ingestor summary with the JSON body. Filter live logs with:

```bash
sudo journalctl -u safehomeops-iot-ingestor -f | grep -E 'Ingested |Watch |HTTP Request: POST.*iot/events'
```

**Immobility** (watch loop → API → family warning alert):

```text
… INFO livewell.iot_ingestor Watch IMMOBILITY_WARNING mac=c3:00:00:98:f3:f8
… INFO httpx HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"
… INFO livewell.iot_ingestor Ingested IMMOBILITY_WARNING → {"accepted":true,"incident_id":"dimm_ae67c3b506","duplicate":false,"detail":null}
```

**SOS** (button press, after decode + dedupe):

```text
… INFO httpx HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"
… INFO livewell.iot_ingestor Ingested SOS_BUTTON → {"accepted":true,"incident_id":"dsos_…","duplicate":false,"detail":null}
```

**Offline** (band not heard for `offline_seconds`):

```text
… INFO livewell.iot_ingestor Watch DEVICE_OFFLINE mac=c3:00:00:98:f3:f8
… INFO httpx HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"
… INFO livewell.iot_ingestor Ingested DEVICE_OFFLINE → {"accepted":true,"incident_id":"doff_…","duplicate":false,"detail":null}
```

| `event_type` | Typical `incident_id` prefix | Family UI |
|--------------|------------------------------|-----------|
| `SOS_BUTTON` | `dsos_` | Critical SOS |
| `IMMOBILITY_WARNING` | `dimm_` | Warning — no motion |
| `DEVICE_OFFLINE` | `doff_` | Warning — wearable not heard |
| `FALL_SUSPECTED` | `dfall_` | Warning (experimental; not from watch loop yet) |

Other useful lines: `Dedupe skip SOS mac=…`, `No local map for mac=…` (Wearables bind missing), `Starting ingestor … immobility=15m` (policy loaded). `accepted:true` with HTTP 200 means the care-hub alert was written; check that elder’s family **Alerts** page.

---

### 3. `safehomeops-api.service` (LiveWell FastAPI)

| | |
|--|--|
| **Unit** | `safehomeops-api.service` (existing LiveWell API) |
| **User** | `safehomeops` |
| **Listen** | `127.0.0.1:8010` (nginx terminates HTTPS publicly) |
| **IoT route** | `POST /api/v1/iot/events` |
| **Auth** | Header `X-IoT-Ingest-Key` = `IOT_INGEST_API_KEY` in `backend/.env` |

**Does (for IoT):**

- Validate the ingest key.
- On `SOS_BUTTON`, `IMMOBILITY_WARNING`, `DEVICE_OFFLINE`, or `FALL_SUSPECTED`, call `IotIngestService.raise_device_event`.
- SOS → critical care-hub incident; watch events → **warning** alerts (not SOS).
- Family/staff apps then show the alert when they poll/load alerts.

**Does not:** Speak MQTT; scan BLE; talk to the MG7.

**Check:**

```bash
sudo systemctl status safehomeops-api
curl -sS -X POST https://ops.kushalaya.com/api/v1/iot/events \
  -H "Content-Type: application/json" \
  -H "X-IoT-Ingest-Key: $IOT_INGEST_API_KEY" \
  -d '{"event_type":"SOS_BUTTON","elder_id":2,"mac_address":"aa:bb:cc:dd:ee:ff"}'
```

---

### 4. `safehomeops-web` + **nginx** (unchanged roles)

| Service | Role for IoT |
|---------|----------------|
| **nginx** | Public HTTPS for family/ops UI and API proxy. **Not** used for MQTT (MQTT is direct to :8883). |
| **safehomeops-web** | Next.js UI — displays alerts; does not ingest IoT. |

MG7 must reach **`host:8883`**, not `https://…/api/…`.

---

### 5. Database

Not a separate “IoT service,” but the API persists SOS into the elder’s care-hub JSON (incidents + alerts). Later phases may add `iot_hub` / `iot_device` / `device_event` tables; Phase 1 binding is **`IOT_DEVICE_MAP`** in the ingestor env file.

---

## End-to-end: one SOS press

| Step | Who | What happens |
|------|-----|----------------|
| 1 | **B7** | User presses SOS → BLE advertisement changes / bursts (SOS flag in payload). |
| 2 | **MG7** | Scans BLE, builds MQTT message(s), publishes to `livewell/homes/home1/hubs/mg7-1/ble` on **8883** with TLS + hub credentials. |
| 3 | **mosquitto** | Accepts publish; delivers to subscribers on that topic. |
| 4 | **iot-ingestor** | Receives message; classifies SOS/motion/seen; looks up elder; SOS-dedupes; POSTs to API. Watch loop may later POST offline/immobility. |
| 5 | **safehomeops-api** | Creates incident + critical alert for that elder. |
| 6 | **Family / staff app** | User opens Alerts (or feed) and sees wearable SOS. |

Repeated BLE ads within ~65s are collapsed to **one** LiveWell SOS incident.

---

## Files and secrets (where config lives)

| Path | Purpose |
|------|---------|
| `/etc/mosquitto/conf.d/livewell.conf` | Listeners 1883/8883, TLS paths, password/ACL files |
| `/var/lib/safehomeops/mqtt/passwd` | MQTT users (hub + ingestor) |
| `/var/lib/safehomeops/mqtt/acl` | Topic permissions |
| `/var/lib/safehomeops/mqtt/certs/` | TLS cert/key (from Let’s Encrypt copy) |
| `/var/lib/safehomeops/mqtt/.credentials.app` | Human-readable passwords for installers (`safehomeops`) |
| `/opt/safehomeops/app/backend/iot_ingestor.env` | Ingestor MQTT + `IOT_DEVICE_MAP` + API key |
| `/opt/safehomeops/app/backend/.env` | `IOT_INGEST_API_KEY` for the API |

---

## What is *not* a separate process

| Myth | Reality |
|------|---------|
| “LiveWell API is the MQTT broker” | No — FastAPI only receives HTTP from the ingestor. |
| “Ingestor must be public” | No — localhost MQTT + localhost API. |
| “nginx proxies MQTT” | No — open **8883** to Mosquitto. |
| “B7 needs Wi‑Fi” | No — BLE to MG7 only. |
| “Each press = one MQTT message” | Often many ads; ingestor dedupes. |

---

## Operational cheat sheet

```bash
# Services
sudo systemctl status mosquitto safehomeops-iot-ingestor safehomeops-api

# Live SOS / watch path
journalctl -u safehomeops-iot-ingestor -f
# Success looks like: Watch IMMOBILITY_WARNING / Ingested SOS_BUTTON → {"accepted":true,"incident_id":"…"}
journalctl -u mosquitto -n 30 --no-pager

# 1. Live MQTT from hub (best for Minew / PYG) — topic + JSON on each line
source /var/lib/safehomeops/mqtt/.credentials.app
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/+/hubs/+/ble' -v

# PYG01 / non-ble subtopics (noisy: use -t '#' only for debug)
# mosquitto_sub ... -t 'livewell/homes/+/hubs/+/+' -v

# 2. Lab SOS without hardware (registered MAC required)
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/home1/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'
```

**Ops UI:** `/livewell/activity` → filter **Actor → System** → expand **Details (JSON)** on IoT events. Set `ACTIVITY_LOG_MODE=verbose` in API `.env` for full `raw_payload`.

Full manual testing steps: [IOT_B7_MG7_FIELD_SETUP.md § Manual testing](./IOT_B7_MG7_FIELD_SETUP.md#manual-testing--mqtt-json--ingest-path).

---

## Related docs

| Doc | Contents |
|-----|----------|
| [IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md) | Configure B7 + MG7 + MAC bind |
| [IOT_B7_MG7_ROADMAP.md](./IOT_B7_MG7_ROADMAP.md) | Phased product plan |
| [IOT_PILOT_IMPLEMENTATION.md](./IOT_PILOT_IMPLEMENTATION.md) | Pilot build (after validation gate) |
| [../../deploy/mqtt/SERVER_SETUP.md](../../deploy/mqtt/SERVER_SETUP.md) | Install Mosquitto + ingestor on the VM |
| [../../backend/iot_ingestor/README.md](../../backend/iot_ingestor/README.md) | Ingestor env vars |
