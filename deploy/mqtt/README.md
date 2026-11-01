# Mosquitto for LiveWell (B7 / MG7)

Run MQTT on the **same Linux host** as LiveWell for Phase 1. Hubs publish with TLS; the ingestor subscribes (often via localhost).

## Quick start (automated on the LiveWell VM)

`/opt/safehomeops/app` is **safehomeops-only**. **Docker is optional** — default install uses the native `mosquitto` package. Runtime: `/var/lib/safehomeops/mqtt`.

```bash
sudo -iu safehomeops
cd /opt/safehomeops/app && git pull
sudo bash scripts/deploy/install-livewell-iot.sh \
  --elder-map '{"aa:bb:cc:dd:ee:ff":YOUR_ELDER_ID}'
```

Full runbook: **[SERVER_SETUP.md](./SERVER_SETUP.md)**  
Hardware (B7 + MG7): **[../../docs/livewell/IOT_B7_MG7_FIELD_SETUP.md](../../docs/livewell/IOT_B7_MG7_FIELD_SETUP.md)**

## Ports

| Port | Binding | Use |
|------|---------|-----|
| **8883** | public (firewall allow) | MG7 → MQTTS |
| **1883** | `127.0.0.1` only | Optional local ingestor without TLS |

## TLS

Use Let's Encrypt certs (same as nginx), e.g.:

```text
/etc/letsencrypt/live/livewellops.tekmatrix.ai/fullchain.pem
/etc/letsencrypt/live/livewellops.tekmatrix.ai/privkey.pem
```

Update paths in `mosquitto.conf`. Cert user (`mosquitto`) must be able to read them (or copy into `deploy/mqtt/certs/` with correct perms).

## Users & ACLs

1. Create password file:

```bash
mosquitto_passwd -c passwd mg7_home1
mosquitto_passwd passwd livewell_ingestor
```

2. ACL example (`acl`): hubs may only publish their topic prefix; ingestor may subscribe broadly.

```text
user livewell_ingestor
topic read livewell/#

user mg7_home1
topic write livewell/homes/home1/hubs/+/ble
topic read livewell/homes/home1/hubs/+/ble
topic write mg7/#
topic write /mg7/#
topic read mg7/#
topic read /mg7/#
```

## MG7 (MinewLink)

- Mode: Gateway / scanning  
- Broker: `livewellops.tekmatrix.ai` (or your host)  
- Port: **8883**, SSL/TLS on  
- Username/password: hub-specific  
- Publish topic: Minew often uses **`/mg7/{bandMac}/status`** (firmware-fixed). Custom `livewell/homes/…/ble` only if MinewLink allows it.  
- Subscribe / reply: leave blank (Phase 1)  
- Prefer Ethernet / PoE  
- Filter to known B7 MACs when the firmware allows  
- SOS decode: iBeacon major=1, minor=1 (idle 0/0)

## Firewall

```bash
sudo ufw allow 8883/tcp comment 'MQTT TLS LiveWell IoT'
# Do NOT expose 1883 publicly
```

## Verify

```bash
# Local publish (after creating user)
mosquitto_pub -h 127.0.0.1 -p 1883 -u livewell_ingestor -P '***' \
  -t 'livewell/homes/demo/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true,"test":true}'

# Or TLS
mosquitto_pub -h livewellops.tekmatrix.ai -p 8883 \
  --cafile /etc/ssl/certs/ca-certificates.crt \
  -u mg7_home1 -P '***' \
  -t 'livewell/homes/demo/hubs/mg7-1/ble' \
  -m '{"mac":"AA:BB:CC:DD:EE:FF","sos":true}'
```

Then run the [iot_ingestor](../../backend/iot_ingestor/README.md).

## See also

- [IOT_B7_MG7_ROADMAP.md](../../docs/livewell/IOT_B7_MG7_ROADMAP.md)
