# Configure Minew B7 + MG7 with LiveWell

**Audience:** Ops / installers setting up wearable SOS for a senior  
**Hardware:** Minew **B7** button wristband + **MG7** Ethernet/Wi‑Fi BLE gateway  
**Cloud:** LiveWell ops host (e.g. `ops.kushalaya.com`) with Mosquitto + `safehomeops-iot-ingestor`

There is an ops screen **Platform → Wearables (B7/MG7)** (`/livewell/iot-devices`) that registers a new kit (hub + band) in one step. Minew apps still need a one-time field config using the credentials the screen shows.

Related:

- Server install: [SERVER_SETUP.md](../../deploy/mqtt/SERVER_SETUP.md)
- Roadmap: [IOT_B7_MG7_ROADMAP.md](./IOT_B7_MG7_ROADMAP.md)
- Architecture (services): [IOT_B7_MG7_ARCHITECTURE.md](./IOT_B7_MG7_ARCHITECTURE.md)
- Pilot build (after validation): [IOT_PILOT_IMPLEMENTATION.md](./IOT_PILOT_IMPLEMENTATION.md)

---

## What you need

| Item | Notes |
|------|--------|
| B7 wristband | Charged / fresh coin cell; BeaconSET Plus on a phone |
| MG7 gateway | PoE/Ethernet preferred; MinewLink app; same site network as the home |
| LiveWell server | Mosquitto listening on **8883** (TLS); ingestor service running |
| Elder id | Integer id of the senior in LiveWell (`GET /api/v1/elders` or Clients / Visits tooling) |
| MQTT hub password | From `/var/lib/safehomeops/mqtt/.credentials.app` on the server |

Architecture:

```text
B7 (SOS) --BLE--> MG7 --MQTT/TLS:8883--> Mosquitto --> iot_ingestor --> LiveWell alerts
```

---

## Step 1 — Confirm the server is ready

SSH as `safehomeops` (or use sudo from that account):

```bash
sudo systemctl is-active mosquitto
sudo systemctl is-active safehomeops-iot-ingestor

# Hub MQTT user/password (and public host)
sudo cat /var/lib/safehomeops/mqtt/.credentials.app
```

Expect:

- `mosquitto` = `active`
- `safehomeops-iot-ingestor` = `active`
- Cloud security list / firewall allows **TCP 8883** to the LiveWell host
- Fields like `MQTT_HUB_USER=mg7_home1`, `MQTT_HUB_PASSWORD=…`, `MQTT_PUBLIC_HOST=ops.kushalaya.com`

If Mosquitto is not installed yet, see [SERVER_SETUP.md](../../deploy/mqtt/SERVER_SETUP.md).

Optional dry-run **without** hardware (proves LiveWell path):

```bash
source /var/lib/safehomeops/mqtt/.credentials.app
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/home1/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'
```

(Use a MAC already registered under Wearables / `register-kit`, or still present in optional `IOT_DEVICE_MAP`.)

---

## Step 2 — Configure the B7 (BeaconSET Plus)

App: **Minew BeaconSET Plus** (phone Bluetooth on).

1. Open BeaconSET Plus and connect to the B7.
2. Record the band **MAC address** (example: `AA:BB:CC:DD:EE:FF`).  
   LiveWell binds on this MAC — write it down accurately.
3. Enable **SOS / button** triggered advertising (wording varies by firmware).
4. If available, enable **faster / rapid advertising when the button is pressed**.
5. Enable **battery / TLM** advertising if the firmware supports it (helps later low-battery alerts).
6. **Advertisements** (LiveWell decode, field-proven on B7 + MG7):

   | Frame | How to spot in `rawData` | LiveWell |
   |------|--------------------------|----------|
   | SOS | Apple iBeacon or F1FF service data, UUID `FDA50693-…7825`, major=1 **minor=1** | SOS (~60s after button) |
   | Accelerometer | `E1FFA103` (Minew FFE1) | Motion when XYZ **changes**; drives immobility |
   | iBeacon 1/2 | same UUID, major=1 **minor=2** | Often always-on — **heartbeat only**, not motion |
   | Eddystone / A108 | `AAFE` / `E1FFA108` | Heartbeat → `lastSeenAt` only |

   **Time Since** in BeaconSET is **uptime / last reboot**, not last movement — do not use it for immobility.
7. **Write / save** settings to the device.
8. Confirm the band advertises (BeaconSET or another BLE scanner such as nRF Connect).

### Tips

- Keep advertising intervals reasonable for battery life; SOS mode should be aggressive only after a press.
- One B7 → one senior for the first install.
- Leave Minew **A103 accelerometer** advertising on (needed for immobility).
- XYZ / accelerometer “possible fall” is **experimental** and is not used for this watch loop.
- Official SOS byte layout from Minew is preferred for production; until then the LiveWell ingestor accepts common gateway JSON (including lab shape `{"mac":"…","sos":true}`).

---

## Step 3 — Configure the MG7 (MinewLink)

App: **Minew MinewLink**. Prefer **Ethernet / PoE** on the MG7.

**Source of truth:** Platform → **Wearables** → **MQTT broker (source of truth)**. Save host/port/TLS/user/password/topic mode there first; optionally **Load from .credentials.app**, then **Apply to Mosquitto**. Register kit copies those values into the MinewLink cheat-sheet (shared hub user such as `mg7_home1`, topic `/mg7/{bandMac}/status`).

**Apply to Mosquitto** updates hub + **ingestor** passwords in Mosquitto, writes `backend/iot_ingestor.env`, and restarts `safehomeops-iot-ingestor`. Needs a one-time root grant:

```bash
cd /opt/safehomeops/app && git pull
sudo bash scripts/deploy/install-safehome-sudoers.sh
sudo systemctl restart safehomeops-api
```

Then in Wearables: **Load from .credentials.app** → set/confirm hub + ingestor passwords → **Save** → **Apply to Mosquitto**.

**Band watch** (same Save): SOS dedupe default **65s**; offline warning default **on** (180s); immobility default **on** (30 min, `Asia/Kolkata` 07–21). Motion is A103 XYZ change, not iBeacon 1/2. Policy is on `GET /api/v1/iot/device-map` — the ingestor picks it up within ~30s without Apply, except SOS `IOT_DEDUPE_SECONDS` in `iot_ingestor.env` which Apply writes as a fallback.

1. Power the MG7 and join it to the site LAN (or configure Wi‑Fi via MinewLink if required).
2. Set mode to **Gateway / scanning** (collect BLE advertisements — not beacon-only).
3. Configure the **MQTT server** from Wearables broker settings / Register kit cheat-sheet:

| Setting | Value |
|--------|--------|
| Host | from Wearables MQTT broker (e.g. `ops.kushalaya.com`) |
| Port | **8883** (or as saved) |
| SSL / TLS | **On** (or as saved) |
| Username | shared hub user from Wearables (e.g. `mg7_home1`) |
| Password | same Wearables broker password |
| Publish topic | `/mg7/{bandMac}/status` when topic mode is Minew (band MAC, no colons) |
| Subscribe / reply | Leave blank unless set in Wearables |

4. If MinewLink supports a MAC / UUID **filter**, restrict to this B7’s MAC (reduces noise).
5. Save and confirm the hub shows connected / publishing.

**Minew payload (field-proven):** JSON **array** — Gateway header + BLE ads. SOS = iBeacon **major=1, minor=1**; motion = **FFE1 A103** XYZ delta; iBeacon **1/2** is typically always-on (seen only). Bind the **band** MAC (ad rows), not the gateway MAC.

### Topic and ACL notes

Default server ACL allows hub user `mg7_home1` to publish under:

```text
livewell/homes/home1/hubs/+/ble
mg7/#
/mg7/#
```

Ingestor subscribes to (comma-separated `MQTT_TOPIC`):

```text
livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status
```

If you change `home1` or the MQTT username, update Mosquitto ACL (`/var/lib/safehomeops/mqtt/acl`) and recreate/reload users as needed — or keep the defaults for the first home.

No new DNS **A** record is required if the hub uses the same hostname as the LiveWell ops site.

---

## Step 4 — Register kit in LiveWell (automates bind + MQTT user)

**Preferred:** ops UI **Platform → Wearables (B7/MG7)**.

0. Confirm **MQTT broker** settings at the top of Wearables (shared hub + Minew topic mode).
1. Choose the client (elder).
2. Enter the B7 **MAC** from BeaconSET.
3. Click **Register MG7 + B7 kit** (reuses shared hub + band bind), **or** use **Update MAC for client** to change/bind only the MAC for an existing client (pick by name) without creating a new hub.
4. Copy the **MinewLink settings** cheat-sheet into the MG7 (same values as broker settings + `/mg7/{MAC}/status`).
5. Within ~30s the ingestor picks up the new MAC→elder binding **and** watch policy from `GET /api/v1/iot/device-map` (no `IOT_DEVICE_MAP` edit required).

MAC-only update API:

```bash
curl -sS -X PUT "$API/api/v1/iot/devices/mac" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"elder_id":2,"mac_address":"AA:BB:CC:DD:EE:FF"}'
```

API equivalent:

```bash
# staff JWT
curl -sS -X POST "$API/api/v1/iot/register-kit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"elder_id":2,"mac_address":"AA:BB:CC:DD:EE:FF","home_key":"home1"}'
```

On the LiveWell host, registration also best-effort runs `mosquitto_passwd` + ACL append under `/var/lib/safehomeops/mqtt` and reloads Mosquitto. If MQTT provision fails (permissions), credentials are still stored — add the user manually or re-run with sufficient privileges.

### Fallback — static env map (lab only)

```bash
sudo bash scripts/deploy/install-livewell-iot-ingestor.sh \
  --elder-map '{"aa:bb:cc:dd:ee:ff":2}'
```

Env `IOT_DEVICE_MAP` merges **over** the DB map (override). Prefer the registry for production.

### Find elder_id

- Staff API: `GET /api/v1/elders` (each object has `"id"`)
- Or Clients screen / Wearables dropdown

This is the **senior’s** id, not the family user’s id.

---

## Step 5 — Acceptance test

1. Stand in range of the MG7 with the B7 on the senior (or a tester).
2. Press the **SOS** button.
3. On the server within a few seconds:

```bash
journalctl -u safehomeops-iot-ingestor -f
```

You should see an ingest / SOS line (not “No elder mapping” / not repeated duplicates while SOS still advertises ~60s).

4. In the **family portal** for that elder: **Alerts** shows a critical wearable SOS.
5. Press again immediately — second press within **~65 seconds** should **not** create another incident (dedupe; Wearables default).
6. Press again after ~70 seconds — a new incident is OK.

7. In ops **Care flow → Session activity** (`/livewell/activity`), filter **Actor → System**. Expand the **System** session and look for **IoT Sos Button** (or **IoT Immobility Warning** / **IoT Device Offline**). Expand **Details (JSON)** for `raw_payload` when verbose logging is on (see [Manual testing](#manual-testing--mqtt-json--ingest-path) below).

### If nothing happens

| Check | Action |
|-------|--------|
| Hub not connected | MinewLink MQTT host/port/TLS/user/password; firewall **8883** |
| Wrong topic | Must match ACL; default `livewell/homes/home1/hubs/mg7-1/ble` |
| “No elder mapping” in logs | MAC registered under Wearables; ingestor refreshes map ~30s (or restart ingestor) |
| MQTT message arrives but no SOS | Capture payload; Minew JSON may differ from `sos:true` — update decoder when Minew docs arrive |
| API 403/503 | `IOT_INGEST_API_KEY` in API `.env` and `iot_ingestor.env` must match |

---

## Manual testing — MQTT JSON & ingest path

Use these when validating hardware, debugging decoders (Minew B7/MG7 or Pengyou PYG60/PYG01), or proving the LiveWell path without a band.

### 1. Live MQTT from the hub (best for PYG / Minew)

SSH to the LiveWell VM and subscribe to hub traffic on localhost Mosquitto:

```bash
source /var/lib/safehomeops/mqtt/.credentials.app
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/+/hubs/+/ble' -v
```

Press SOS on the band (or wait for gateway scan traffic). Each line is **topic + JSON body** — copy one message for decoder work or vendor support.

For a **PYG01** (or any hub publishing outside the default `ble` subtopic), widen the filter:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/+/hubs/+/+' -v
# or -t '#'  (everything — noisy; debug only)
```

**Practical path for new hardware:** run `mosquitto_sub`, press SOS once, save the JSON from the terminal, then wire the decoder from that sample.

### 2. Ingestor logs (partial JSON)

```bash
journalctl -u safehomeops-iot-ingestor -f
```

Typical lines:

| Log | Meaning |
|-----|---------|
| `Watch IMMOBILITY_WARNING mac=…` | Watch loop decided the band is online but still (A103) during active hours |
| `Watch DEVICE_OFFLINE mac=…` | Band not heard for offline threshold (default 180s) |
| `HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"` | Ingestor reached the API |
| `Ingested SOS_BUTTON → {"accepted":true,"incident_id":"dsos_…",…}` | SOS stored; family critical alert |
| `Ingested IMMOBILITY_WARNING → {"accepted":true,"incident_id":"dimm_…",…}` | Immobility stored; family warning alert |
| `Ingested DEVICE_OFFLINE → {"accepted":true,"incident_id":"doff_…",…}` | Offline stored; family warning alert |
| `Dedupe skip SOS mac=…` | Second press within SOS dedupe window (~65s default) |
| `No local map for mac=…` | MAC not in registry yet; API may still resolve if registered in Wearables |
| `Starting ingestor … immobility=15m` (or `off`) | Watch policy from device-map |

Field-proven immobility success (abbreviated):

```text
Watch IMMOBILITY_WARNING mac=c3:00:00:98:f3:f8
HTTP Request: POST http://127.0.0.1:8010/api/v1/iot/events "HTTP/1.1 200 OK"
Ingested IMMOBILITY_WARNING → {"accepted":true,"incident_id":"dimm_ae67c3b506","duplicate":false,"detail":null}
```

```bash
sudo journalctl -u safehomeops-iot-ingestor -f | grep -E 'IMMOBILITY_WARNING|DEVICE_OFFLINE|SOS_BUTTON|Ingested '
```

More detail (decoder, policy, HTTP pairs): [IOT_B7_MG7_ARCHITECTURE.md — Successful ingest log patterns](./IOT_B7_MG7_ARCHITECTURE.md#successful-ingest-log-patterns-developer).

To see more scan traffic temporarily:

```bash
# in backend/iot_ingestor.env
LOG_LEVEL=DEBUG
sudo systemctl restart safehomeops-iot-ingestor
```

### 3. Lab / fake JSON (no hardware)

Proves Mosquitto → ingestor → API without a band (MAC must be registered):

```bash
source /var/lib/safehomeops/mqtt/.credentials.app
mosquitto_pub -h 127.0.0.1 -p 1883 \
  -u livewell_ingestor -P "$MQTT_INGESTOR_PASSWORD" \
  -t 'livewell/homes/home1/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'
```

Or POST directly to the API (same shape the ingestor sends after decode):

```bash
# IOT_INGEST_API_KEY from backend/.env
curl -sS -X POST http://127.0.0.1:8010/api/v1/iot/events \
  -H "X-IoT-Ingest-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "SOS_BUTTON",
    "elder_id": 2,
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "raw_payload": {"mac":"aa:bb:cc:dd:ee:ff","sos":true}
  }'
```

OpenAPI: `https://ops.kushalaya.com/docs` → `POST /api/v1/iot/events`.

### 4. Session activity UI (ops)

After deploy, IoT ingest is written to the tenant **System** session timeline (not the Wearables page).

1. Log in to ops as care manager / admin.
2. Open **Care flow → Session activity** (`/livewell/activity`).
3. Filter **Actor → System**.
4. Expand the **System** session → **System events**.
5. Look for **IoT Sos Button**, **IoT Immobility Warning**, **IoT Device Offline**, or **IoT event ignored**.
6. Expand **Details (JSON)** on an event for `meta.raw_payload`.

For full gateway JSON in the UI (not truncated), set in API `backend/.env`:

```bash
ACTIVITY_LOG_MODE=verbose
```

Then restart API: `sudo systemctl restart safehomeops-api` (or `bash scripts/start-livewell.sh --skip-frontend`).

Staff actions on **Platform → Wearables** (register kit, update MAC) appear under **User actions** on the logged-in staff session when `X-Session-ID` is present.

### 5. What you still see elsewhere

| Surface | Shows |
|---------|--------|
| **Wearables** (`/livewell/iot-devices`) | Hub/band registry, MQTT credentials — not live MQTT JSON |
| **Family alerts** | Human-readable SOS text — not raw gateway payload |
| **Ingestor → API** | `raw_payload` forwarded on ingest; stored in session activity `meta`, not on the incident record |

For Pengyou / KKM before hardware arrives, request the **KGateway MQTT+JSON API** PDF from the vendor; after the PYG01 is on your broker, **`mosquitto_sub`** is the source of truth.

---

## Day-2 changes

| Change | What to do |
|--------|------------|
| New B7 for another client | BeaconSET → new MAC; **Register kit** on Wearables (pick client **by name**) |
| Unbind / remove a band | Wearables → Registered bands → **Remove** |
| Replace MG7 | Reconfigure MinewLink with same MQTT settings; serial is not required in Phase 1 |
| Rotate MQTT passwords | Wearables → update passwords → **Apply to Mosquitto**, then update every MG7 MinewLink password |
| Second home / second kit | See [Second kit](#second-kit--second-home-hyderabad) below |

### Second kit / second home (Hyderabad)

All homes share **Asia/Kolkata** watch policy and (by default) one MQTT hub user. Routing is by **B7 MAC → client**.

1. Charge/configure the new B7; note its MAC.
2. Wearables → Register kit: pick the **client name**, enter MAC, set **Home key** to a residence label (e.g. `hyd-jubilee-12`), optional band label (`Mom B7`).
3. MinewLink on the new MG7: same Host/Port/TLS/User/Password as kit #1.
4. Publish topic = **`/mg7/{THIS_BAND_MAC}/status`** (this band only — not the first kit’s MAC).
5. Prefer a MAC filter on that MG7 so it doesn’t also forward the neighbour’s band.
6. Acceptance: SOS and immobility appear on **that client’s** family portal only.

Shared MQTT is fine for a trusted Hyderabad fleet. If a password ever leaks, rotate it and update **all** MG7s.

---

## Known limitations (Phase 1)

- B7 does **not** give the wearer confirmation that LiveWell received the SOS (no haptic/voice ACK from the cloud).
- Accelerometer “fall” (if enabled by Minew) should be treated as **suspect** until validated; product focus is **SOS button**. Immobility uses **A103 XYZ change**, not iBeacon 1/2.
- SMS / voice escalation ladder is a later phase; today the critical path is in-app family/staff alerts via the care hub.
- Raw gateway JSON is not stored on the incident record; use [manual testing](#manual-testing--mqtt-json--ingest-path) (MQTT subscribe, ingestor logs, Session activity) to capture payloads.

---

## Checklist (print / field)

- [ ] Mosquitto + ingestor active; port 8883 open  
- [ ] B7 MAC recorded; SOS advertising enabled; Minew A103 accelerometer advertising on  
- [ ] MG7 → `ops.kushalaya.com:8883` TLS + hub MQTT credentials (from Register kit)  
- [ ] Topic matches kit (e.g. `livewell/homes/home1/hubs/mg7-a1b2/ble` or `/mg7/{MAC}/status`)  
- [ ] MAC registered under **Platform → Wearables** (or env `IOT_DEVICE_MAP` for lab only)  
- [ ] Button press → ingestor log → family Alerts within ~5s  
- [ ] Optional: **Session activity** (Actor → System) shows IoT event with JSON details  
- [ ] Rapid re-press deduped (~65s)  
- [ ] Second kit: unique B7 MAC registered to the correct client name; Minew topic uses **that** MAC  
- [ ] Second kit: SOS reaches that client’s family portal only  
