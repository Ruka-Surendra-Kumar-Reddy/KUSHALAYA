# LiveWell IoT roadmap — Minew B7 + MG7 (MQTT-first)

**Status:** Active  
**Date:** 2026-08-21  
**Goal:** Wearable SOS into LiveWell incidents without custom hardware. **Start with MQTT** (no HTTP PoC detour).

## Architecture

```
B7 SOS button
     │ BLE advertisement
     ▼
MG7 gateway
     │ MQTT over TLS (port 8883)
     ▼
Mosquitto (same Linux host as LiveWell, or dedicated VM)
     │
     ▼
livewell-iot-ingestor  (subscribe + decode + dedupe)
     │ HTTP → LiveWell API
     ▼
POST /api/v1/iot/events
     │
     ▼
Family care hub / Incident Service
     ├── In-app alert (family + staff)
     ├── SMS / voice escalation (later)
     └── Acknowledgement and closure
```

FastAPI is **not** an MQTT broker. Mosquitto (or EMQX) is. The ingestor is a separate process.

Deploy assets: [`deploy/mqtt/`](../../deploy/mqtt/README.md) · runbook [`SERVER_SETUP.md`](../../deploy/mqtt/SERVER_SETUP.md)  
Ingestor: [`backend/iot_ingestor/`](../../backend/iot_ingestor/README.md)

**Mosquitto does not require Docker** (native package is the default).

```bash
sudo -iu safehomeops
cd /opt/safehomeops/app && git pull
sudo bash scripts/deploy/install-livewell-iot.sh \
  --elder-map '{"aa:bb:cc:dd:ee:ff":YOUR_ELDER_ID}'
```

App tree stays safehomeops-owned; Mosquitto runs from `/var/lib/safehomeops/mqtt` via `systemctl`.

## Relationships

```
Home / Tenant
 └── MG7 Hub
      └── B7 Band
           └── Elder
```

Topic convention:

```text
livewell/homes/{home_id}/hubs/{hub_id}/ble
```

Normalized event:

```json
{
  "eventType": "SOS_BUTTON",
  "elderId": 123,
  "deviceId": "b7-001",
  "hubId": "mg7-001",
  "macAddress": "aa:bb:cc:dd:ee:ff",
  "occurredAt": "2026-08-21T14:30:00Z",
  "rssi": -61,
  "batteryLevel": null,
  "rawPayload": {}
}
```

Dedupe repeated BLE ads from the same band for ~**65 seconds** (SOS advertises ~60s). Keep `rawPayload` for debugging.

## Field setup (B7 + MG7)

When hardware arrives, follow **[IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md)** (BeaconSET Plus, MinewLink, MAC → elder_id, acceptance test).

Processes and services (Mosquitto, ingestor, API): **[IOT_B7_MG7_ARCHITECTURE.md](./IOT_B7_MG7_ARCHITECTURE.md)**.


Before a ten-unit buy, obtain:

- [ ] B7 advertising protocol + SOS flag/byte position
- [ ] Example packet before/after button press
- [ ] MG7 MQTT JSON schema
- [ ] MG7 MQTT TLS config manual
- [ ] Button reset / repeat-transmission behaviour
- [ ] Battery / TLM field docs
- [ ] Confirmation MG7 forwards the **complete** B7 advertisement

Lab fallback: nRF Connect packet compare. Production decode should use Minew docs.

## Phase 1 — MQTT on the LiveWell server (now)

1. Install Mosquitto with TLS on **8883** (see `deploy/mqtt`).
2. Create per-hub MQTT users + topic ACLs.
3. Configure MG7 (MinewLink): scanning mode, Ethernet preferred, MQTTS to your host.
4. Run `livewell-iot-ingestor` against the broker.
5. Register the kit in LiveWell (UI **Wearables** or `POST /api/v1/iot/register-kit`) — creates MQTT user + MAC→elder bind.
6. Button press → `POST /api/v1/iot/events` → critical family-hub incident + alert.

**Acceptance (Phase 1)**
- [ ] Press creates one LiveWell incident
- [ ] Rapid re-ads do not duplicate (~65s SOS window)
- [ ] Unknown MAC ignored / logged
- [ ] Delivery typically ≤5s when online

## Phase 1.5 — Band watch (implemented)

Per-MAC `lastSeenAt` / `lastMotionAt` on the ingestor. Policy from Wearables → `GET /api/v1/iot/device-map` `policy`.

| Event | When | Family alert |
|-------|------|----------------|
| `SOS_BUTTON` | iBeacon major=1 minor=1 | Critical |
| `DEVICE_OFFLINE` | No ads for ~3 min (default) | Warning |
| `IMMOBILITY_WARNING` | Online, no minor=2 for ~30 min, active hours; **default off** until BeaconSET motion slot | Warning |

Power-off must not look like immobility. XYZ possible-fall is experimental and not in this loop.

## Phase 2 — Registry tables (implemented)

| Entity | Status |
|--------|--------|
| `iot_hubs` | Done — MQTT user/password/topic, home/hub keys |
| `iot_devices` | Done — MAC → elder, optional hub link |
| Staff API | `POST /api/v1/iot/register-kit`, `/hubs`, `/devices` |
| Ops UI | `/livewell/iot-devices` |
| Ingestor | Polls `GET /api/v1/iot/device-map`; env map optional override |

Still later: `device_event` audit table, richer incident workflow (Phase 3).

## Phase 3 — Escalation workflow

**Do not start until Phase V (initial validation) passes.** Full gated backlog: **[IOT_PILOT_IMPLEMENTATION.md](./IOT_PILOT_IMPLEMENTATION.md)**.

On `SOS_BUTTON`:

1. Critical incident  
2. Push to family + care manager  
3. Acknowledge UI  
4. Unacked 30–60s → SMS  
5. Then voice  
6. Audit who responded  

Also: low battery, B7 not seen, MG7 offline, test mode.

## Phase 4 — Hardening

- Multi-hub homes  
- Strict MQTT ACLs per hub  
- **200 presses**, different rooms, zero misses, zero duplicate incidents, ≤5s  
- Optional `FALL_SUSPECTED` (lower confidence than SOS)  
- Future Kushalaya hub: local buzzer/LED ACK (B7 has no documented two-way confirmation)

## Known limitation

B7 does not give the wearer confirmation that LiveWell received the SOS. Caregivers get the alert; the senior may not.

## Why MQTT from day one

- Matches production shape (no throwaway HTTP ingest)  
- Mosquitto is light enough to co-locate with LiveWell  
- Ingestor isolates decode/dedupe from the API process  

HTTP POST from MG7 remains a **debug fallback** only, not the primary path.
