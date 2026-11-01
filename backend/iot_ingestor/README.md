# livewell-iot-ingestor

Subscribes to Mosquitto topics from Minew **MG7**, classifies B7 iBeacon ads, and POSTs to LiveWell:

`POST /api/v1/iot/events` with header `X-IoT-Ingest-Key`.

| Event | When |
|-------|------|
| `SOS_BUTTON` | iBeacon major=1 minor=1 (or lab `{"sos":true}`) |
| `DEVICE_OFFLINE` | Band not heard for `offline_seconds` (watch loop) |
| `IMMOBILITY_WARNING` | Online, last A103 motion older than `immobility_minutes`, active hours |

## Setup

```bash
cd backend
python -m venv .venv
# activate venv
pip install -r iot_ingestor/requirements.txt
# API must also have IOT_INGEST_API_KEY set in its .env
```

## Environment

| Variable | Example | Purpose |
|----------|---------|---------|
| `MQTT_HOST` | `127.0.0.1` | Broker |
| `MQTT_PORT` | `1883` | Local listener |
| `MQTT_USERNAME` | `livewell_ingestor` | ACL user |
| `MQTT_PASSWORD` | `…` | |
| `MQTT_TLS` | `0` | Set `1` if using 8883 remotely |
| `MQTT_TOPIC` | `livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status` | Comma-separated subscribe filters |
| `LIVEWELL_API_BASE` | `http://127.0.0.1:8010` | API base (systemd API port) |
| `IOT_INGEST_API_KEY` | same as API `.env` | Shared secret |
| `IOT_DEVICE_MAP` | `{"aa:bb:cc:dd:ee:ff":42}` | MAC → elder_id override |
| `IOT_DEDUPE_SECONDS` | `65` | SOS dedupe fallback until device-map `policy` loads |
| `IOT_WATCH_SECONDS` | `60` | How often to evaluate offline / immobility |
| `IOT_DEVICE_MAP_REFRESH_SECONDS` | `30` | How often to pull device-map + policy |

Watch policy (immobility, offline, active hours, SOS dedupe) is loaded from `GET /api/v1/iot/device-map` → `policy` (Wearables **Save**; no Mosquitto apply required except SOS env fallback).

## Run

```bash
cd backend
python -m iot_ingestor
```

## Simulate (without hardware)

With Mosquitto up and passwd configured:

```bash
# Lab shape
mosquitto_pub -h 127.0.0.1 -p 1883 -u livewell_ingestor -P '***' \
  -t 'livewell/homes/demo/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'

# Minew MG7 shape (SOS = iBeacon major/minor 1/1)
mosquitto_pub -h 127.0.0.1 -p 1883 -u livewell_ingestor -P '***' \
  -t '/mg7/C3000098F3F8/status' \
  -m '[{"type":"Gateway","mac":"3CDC753C23A4","nums":1},{"mac":"C3000098F3F8","rssi":-42,"rawData":"0201061AFF4C000215FDA50693A4E24FB1AFCFC6EB0764782500010001C5"}]'

# Accelerometer motion (FFE1 A103) — lastMotionAt only; does not create an incident
mosquitto_pub -h 127.0.0.1 -p 1883 -u livewell_ingestor -P '***' \
  -t '/mg7/C3000098F3F8/status' \
  -m '[{"type":"Gateway","mac":"3CDC753C23A4"},{"mac":"C3000098F3F8","rawData":"0201060303E1FF1216E1FFA10364FFC0FF8D00E3F8F3980000C3"}]'
```

Ensure that band MAC is in Wearables / `IOT_DEVICE_MAP` and the elder exists.

## Success logs (`journalctl -u safehomeops-iot-ingestor -f`)

Accepted events always show HTTP 200 then `Ingested … → {"accepted":true,"incident_id":"…"}`:

```text
Watch IMMOBILITY_WARNING mac=c3:00:00:98:f3:f8
HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"
Ingested IMMOBILITY_WARNING → {"accepted":true,"incident_id":"dimm_ae67c3b506","duplicate":false,"detail":null}
```

Same shape for `SOS_BUTTON` (`dsos_…`) and `DEVICE_OFFLINE` (`doff_…`). Full table: [IOT_B7_MG7_ARCHITECTURE.md](../../docs/livewell/IOT_B7_MG7_ARCHITECTURE.md#successful-ingest-log-patterns-developer).

## Minew decode

`iot_ingestor.decode.extract_b7_signals()`:

- Lab dict: `{"mac":"…","sos":true}`
- Minew batch array on `/mg7/{bandMac}/status`: Gateway header + BLE ads with `rawData`
- **SOS:** iBeacon major=1 minor=1 (Apple `4C000215` or F1FF service-data UUID)
- **Motion:** Minew FFE1 **A103** when XYZ changes vs the previous sample (iBeacon 1/2 is always-on → seen only)
- Bind **band** MAC from ad rows (e.g. `C3:00:00:98:F3:F8`), not gateway MAC

## See also

- [IOT_B7_MG7_FIELD_SETUP.md](../../docs/livewell/IOT_B7_MG7_FIELD_SETUP.md)
- [IOT_B7_MG7_ROADMAP.md](../../docs/livewell/IOT_B7_MG7_ROADMAP.md)
- [deploy/mqtt/README.md](../../deploy/mqtt/README.md)
