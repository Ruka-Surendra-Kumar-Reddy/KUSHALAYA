# LiveWell IoT pilot — implementation plan

**Status:** Draft — **implementation starts after initial validation**  
**Audience:** Engineering + Kushalaya ops  
**Related:** [IOT_B7_MG7_ARCHITECTURE.md](./IOT_B7_MG7_ARCHITECTURE.md) · [IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md) · [IOT_B7_MG7_ROADMAP.md](./IOT_B7_MG7_ROADMAP.md)

This document turns the Kushalaya pilot functional design into a **gated build plan**. It deliberately separates:

1. **Phase V — Initial validation** (prove hardware + MQTT + LiveWell SOS path)  
2. **Phases A–K — Pilot product** (install, escalate, monitor, support) — **start only after Phase V passes**

Do **not** build the alert worker, escalation plans, installer PWA, or ECM screens until the gate below is green.

---

## Target architecture

```text
Band → Gateway → Mosquitto → IoT Ingestor → FastAPI → PostgreSQL
                                                        │
                                             notification_outbox
                                                        │
                                                        ▼
                                         safehomeops-alert-worker
                                          ├─ Push / SMS / WhatsApp
                                          ├─ Escalation timers
                                          ├─ Device-health checks
                                          ├─ Monthly test reminders
                                          └─ Support / ECM tasks

Family App ── acknowledge / respond / resolve ──► FastAPI
Installer App ── install / test / replace ──────► FastAPI
ECM App ── accept / update follow-up ───────────► FastAPI
```

**Hard rule:** Do not use FastAPI `BackgroundTasks` (or in-process timers) for escalation. Pending alerts must survive API restarts via **durable PostgreSQL jobs** (`notification_outbox` and/or typed `background_jobs`).

Reuse the existing ledger pattern where possible (`BackgroundJob` from `workforceos_core`). Prefer a dedicated `notification_outbox` table for SOS steps if claim semantics differ from generic jobs.

---

## What exists today (baseline)

| Piece | Status |
|-------|--------|
| Mosquitto TLS **`:8883`** + localhost **`:1883`** | Done (`deploy/mqtt`) |
| `safehomeops-iot-ingestor` | Done |
| `iot_hubs` / `iot_devices` + register-kit / update MAC | Done |
| Per-hub MQTT user + topic ACL (kit provision) | Done (best-effort on register) |
| `POST /api/v1/iot/events` → care-hub JSON SOS + family in-app alert | Done (lab) |
| Session activity IoT logging (`meta` / `raw_payload`) | Done |
| Wearables ops UI (`/livewell/iot-devices`) | Done (admin) |
| Relational `safety_incident` + ack / escalate | **Not started** |
| `notification_outbox` + `safehomeops-alert-worker` | **Not started** |
| Multi-contact / OTP / escalation groups | **Not started** (elder has one name/phone) |
| Installer / staging / monthly test / support / ECM | **Not started** |
| Gateway heartbeat / band NOT_DETECTED policy | `last_seen_at` columns exist; **logic not started** |

SOS today is a **family care-hub JSON blob** (`IotIngestService.raise_device_sos` → care-hub incidents + in-app alert), not a durable incident with acknowledgement that can cancel escalation. That is acceptable for **Phase V only**.

---

## Phase V — Initial validation (gate)

**Goal:** Prove one real home (or lab) can press SOS and create a LiveWell family critical alert, with inspectable MQTT JSON.

**Owner:** Ops + one engineer on call. **No large schema work.**

### V.1 Hardware & broker

- [ ] Mosquitto + `safehomeops-iot-ingestor` + `safehomeops-api` active  
- [ ] Firewall allows **TCP 8883**  
- [ ] Credentials in `/var/lib/safehomeops/mqtt/.credentials.app`  
- [ ] Kit registered under **Platform → Wearables** (MAC → elder)  
- [ ] Gateway configured in MinewLink / PYG tool with kit MQTT settings  

### V.2 Manual path tests

Follow [IOT_B7_MG7_FIELD_SETUP.md § Manual testing](./IOT_B7_MG7_FIELD_SETUP.md#manual-testing--mqtt-json--ingest-path):

- [ ] Live MQTT: `mosquitto_sub` shows topic + JSON on band press (or PYG scan)  
- [ ] Ingestor log: `Ingested SOS_BUTTON → {"accepted":true,"incident_id":"dsos_…",…}` (HTTP 200)  
- [ ] Family portal **Alerts** shows critical wearable SOS  
- [ ] Immobility (optional in V): `Watch IMMOBILITY_WARNING` then `Ingested IMMOBILITY_WARNING → {"accepted":true,"incident_id":"dimm_…",…}`  
- [ ] Offline (optional in V): `Watch DEVICE_OFFLINE` then `Ingested DEVICE_OFFLINE → {"accepted":true,"incident_id":"doff_…",…}`  
- [ ] Session activity → Actor **System** shows IoT event (+ Details JSON if `ACTIVITY_LOG_MODE=verbose`)  
- [ ] Lab `mosquitto_pub` with registered MAC works without hardware  
- [ ] Dedupe: rapid second press within ~65s does not create a second incident (`Dedupe skip SOS`)  

Log pattern reference: [IOT_B7_MG7_ARCHITECTURE.md — Successful ingest log patterns](./IOT_B7_MG7_ARCHITECTURE.md#successful-ingest-log-patterns-developer).

### V.3 Decoder decision

- [ ] Capture **one real gateway JSON** sample (Minew MG7 and/or Pengyou / PYG)  
- [ ] Confirm SOS field mapping (or document decoder gap + temporary lab `sos: true`)  
- [ ] If battery missing: note “no TLM / KSensor yet” — do not invent % from voltage  

### V.4 Gate criteria (all required)

| # | Criterion | Pass? |
|---|-----------|-------|
| G1 | End-to-end SOS in &lt; ~10s from button to family alert | |
| G2 | MAC binding via Wearables (DB), not only env `IOT_DEVICE_MAP` | |
| G3 | Raw JSON capturable via `mosquitto_sub` and/or session activity | |
| G4 | Ingestor + API restart does not break path (`bash scripts/start-livewell.sh` OK) | |
| G5 | Stakeholder sign-off: “path validated; build pilot product” | |

**Until G1–G5 pass, engineering works only on:** decoder fixes, field docs, Wearables UX bugs, logging.  
**Do not start Phases A–K.**

---

## After the gate — pilot product (Phases A–K)

Aligned with the functional design. Order is intentional: incidents and contacts before the worker; health and monthly test after notifications work.

### Phase A — Device registry + installation workflow

**Functionality:** Home installation and testing; preconfigured kits (staging).

| Deliverable | Notes |
|-------------|--------|
| Inventory lifecycle | `RECEIVED → TESTED → CONFIGURED → ASSIGNED → INSTALLED → ACTIVE` (+ `FAULTY` / `REPLACED`) |
| Staging at office | Create elder/home → register MACs → unique MQTT user/password per gateway → topic ACL → bench SOS → QR/asset label → `READY_FOR_INSTALLATION` |
| Installer PWA flow | `SCHEDULED → IN_PROGRESS → TESTING → COMPLETED` / `FAILED` |
| Installation record | Gateway/band MAC+serial, location photo, Wi‑Fi, RSSI room samples, UPS/inverter, SOS latency, contacts who acked test, warranty, signature |
| Completion gates | Hub heartbeat, band detected, SOS received, ≥2 contacts notified, ≥1 ack |

**Tables (new/extend):** `iot_installation`, `iot_device_assignment`, extend `iot_hubs` / `iot_devices` status enums, optional `inventory_asset` stub.

**Screens:** Ops installation queue; Installer PWA (can start as ops-only wizard if PWA later).

**Exit:** One staged kit installed in lab with COMPLETED checklist recorded.

---

### Phase B — Incident tables + acknowledgement

**Functionality:** Alert acknowledgement; foundation for history.

| Deliverable | Notes |
|-------------|--------|
| `safety_incident` | Durable row per SOS (not only care-hub JSON) |
| States | `OPEN → ACKNOWLEDGED → RESPONDING → RESOLVED` / `FALSE_ALARM` |
| Family actions | “I will respond” / “I cannot respond” / “False alarm” (confirm) |
| Rules | Delivery ≠ ack; respond stops escalation; cannot-respond advances; open until outcome |

Migrate ingest to create `safety_incident` + keep care-hub alert for UX continuity during transition.

**Tables:** `safety_incident`, `incident_timeline` (minimal events: pressed, notified, ack).

**Screens:** Family active incident + actions; Ops active incidents list.

**Exit:** Family can resolve a lab SOS with timeline entries; no worker required yet.

---

### Phase C — Multiple contacts + escalation plans

**Functionality:** Multiple family contacts; plans for later escalation.

| Deliverable | Notes |
|-------------|--------|
| `emergency_contact` | name, relationship, phone, email, language, priority, channel flags, `verified_at`, active |
| Groups | 1 primary family · 2 local · 3 caregiver · 4 Kushalaya ECM |
| OTP verify phones | Required before pilot live |
| Reminder to confirm list | Periodic (can be simple ops task first) |
| `escalation_plan` + `escalation_step` | Per-elder; default T+0 push, T+30s SMS, T+90s secondary, T+180s voice/caregiver, T+300s ECM |

**Screens:** Family → Safety → Emergency Contacts (add/remove/verify/reorder).

**Exit:** Elder has ≥2 verified contacts and a stored default plan (not yet executed by worker).

---

### Phase D — Durable notification worker

**Functionality:** Automatic escalation (engine only).

| Deliverable | Notes |
|-------------|--------|
| `notification_outbox` | Due-at, claim, retry, cancel |
| `safehomeops-alert-worker` systemd unit | Poll / `FOR UPDATE SKIP LOCKED` |
| On SOS | Enqueue plan steps; cancel remaining when RESPONDING / RESOLVED / FALSE_ALARM |
| Provider adapter stub | Log-only or console first; real SMS later |
| No auto-112 | Hard-coded policy for pilot |

**Exit:** Lab SOS with fake provider logs timed steps; ack cancels pending rows; API restart mid-escalation resumes correctly.

---

### Phase E — Push + SMS delivery

**Functionality:** Real notifications for primary/secondary contacts.

| Deliverable | Notes |
|-------------|--------|
| Push (if family PWA capable) | Prefer existing channel patterns |
| SMS provider | India-capable; record delivery status |
| WhatsApp optional | After SMS stable |
| `notification_delivery` | Attempt, provider id, status, error |

**Exit:** Real phone receives SMS on lab SOS; delivery row stored; ops can see failures.

---

### Phase F — Gateway-offline monitoring

**Functionality:** Coverage unavailable alerts.

| Deliverable | Notes |
|-------------|--------|
| Heartbeat ingest | Prefer dedicated alive topic; also refresh `last_seen_at` on BLE traffic |
| Policy | 60s interval; DEGRADED after 3 misses; OFFLINE after 5 min; RESTORED on next beat |
| Notify ops + family | “SOS coverage currently unavailable” |
| Outage record | Start, restore, duration, cause |
| External monitors | Mosquitto, ingestor, API, alert worker (Uptime Kuma / similar) — system cannot only self-report |

**Exit:** Kill gateway power → OFFLINE + notifications → restore → notice; outage row closed.

---

### Phase G — Monthly testing

**Functionality:** Monthly test reminders + TEST_SOS.

| Deliverable | Notes |
|-------------|--------|
| `device_test` | schedule, start, button, notify, ack, result, latency, rssi, failure_reason |
| Reminder ladder | Due → +3d → +7d family warning → +14d support ticket |
| Test mode | Single device; auto-expire; **never** globally suppress real SOS |

**Screens:** Family “Start monthly test”; Ops “tests due”.

**Exit:** Full PASSED test recorded; overdue reminder enqueued by worker.

---

### Phase H — Incident history + metrics

**Functionality:** Relational history (family + ops views).

| Deliverable | Notes |
|-------------|--------|
| Rich `incident_timeline` | Press → gateway → push/SMS → ack → resolve |
| Ops extras | Raw payload, decoder version |
| Metrics | Median response time, unacked rate, false-alarm rate, gateway uptime, test compliance, delivery success |

**Screens:** Family simplified timeline; Ops incident detail.

**Exit:** Post-incident review usable without reading JSON in Session activity alone.

---

### Phase I — Support + fast replacement

**Functionality:** Local telephone support; spare pool; RMA swap.

| Deliverable | Notes |
|-------------|--------|
| Support number policy | Product support ≠ 24/7 emergency unless staffed |
| `support_ticket` | OPEN → DIAGNOSING → VISIT_REQUIRED → REPLACEMENT_SCHEDULED → CLOSED |
| Categories | Offline, not detected, battery, accidental, Wi‑Fi, test fail, damage, replace |
| `inventory_asset` | Hyderabad spares (bands, gateways, adapters) |
| Replace flow | Reserve spare → visit → new MAC on same elder → old FAULTY → E2E SOS → quarantine |
| Contacts/plan unchanged on swap | Already true if MAC update reuses elder_id |

**Exit:** Dry-run replacement on lab elder with MAC update + PASSED SOS test.

---

### Phase J — Band heartbeat + battery

**Functionality:** NOT_DETECTED / battery policies.

| Deliverable | Notes |
|-------------|--------|
| Every ad updates | `last_seen_at`, `last_rssi`, `last_gateway_id` |
| States | ACTIVE, NOT_DETECTED, LOW_BATTERY, BATTERY_CRITICAL, FAULTY, REPLACED |
| Policy | ~15 min → NOT_DETECTED UI; longer → notify per plan; seen again → ACTIVE |
| Battery | Only if vendor TLM/KSensor; else last-charge date + ~90d reminder + monthly test check |
| No fake % | Until vendor discharge curve |

**Exit:** Documented policy live for chosen hardware; battery path deferred if unsupported.

---

### Phase K — Optional ECM follow-up

**Functionality:** Premium / NRI escalation.

| Deliverable | Notes |
|-------------|--------|
| `ecm_task` | UNASSIGNED → ASSIGNED → CONTACTING → COORDINATING → COMPLETED |
| Trigger | Escalation step or unresolved after plan |
| ECM screen | Elder profile, contacts, medical notes, hospital, access, timeline, who responded |
| Contract copy | ECM coordinates; not ambulance / EMS |

**Exit:** One subscribed elder creates ECM task on T+300s; ECM completes follow-up notes.

---

## Required screens (checklist)

### Family

- [ ] Safety status  
- [ ] Active incident (+ ack actions)  
- [ ] Emergency contacts  
- [ ] Escalation preferences (view / limited edit)  
- [ ] Device health  
- [ ] Start monthly test  
- [ ] Incident history  
- [ ] Request support  

### Operations

- [ ] Installation queue  
- [ ] All gateways / bands  
- [ ] Offline / low-battery dashboard  
- [ ] Active incidents  
- [ ] Notification delivery failures  
- [ ] Support tickets  
- [ ] Replacement inventory  
- [ ] Monthly tests due  

### ECM

- [ ] Unassigned escalations  
- [ ] My active cases  
- [ ] Elder emergency information  
- [ ] Incident timeline  
- [ ] Follow-up notes  

---

## Minimum database additions

| Table | Phase |
|-------|-------|
| `iot_hubs` / `iot_devices` | Exists — extend statuses |
| `iot_device_assignment` | A |
| `iot_installation` | A |
| `emergency_contact` | C |
| `escalation_plan` / `escalation_step` | C |
| `iot_event` (optional raw ingest log) | B/F |
| `safety_incident` | B |
| `incident_timeline` | B → H |
| `notification_delivery` | E |
| `notification_outbox` | D |
| `device_test` | G |
| `support_ticket` | I |
| `inventory_asset` | I (stub in A OK) |
| `ecm_task` | K |

---

## Suggested sprint mapping (post-gate)

| Sprint | Phases | Outcome |
|--------|--------|---------|
| S1 | A (thin) + B | Durable incidents + family ack; install record MVP |
| S2 | C + D | Contacts, plans, worker with stub notifier |
| S3 | E | Real SMS (+ push if ready) |
| S4 | F + G | Offline + monthly test |
| S5 | H + I | History metrics + support/replace |
| S6 | J + K | Battery/heartbeat polish + ECM |

Adjust after Phase V: if decoder work is large, insert a **V+** spike before S1.

---

## Explicit non-goals (pilot)

- Automatic call to **112** / public EMS  
- Advertising Hyderabad number as **24/7 emergency** without staffing  
- Inventing battery % without vendor curve  
- Global “test mode” that suppresses all SOS  
- Reusing one MQTT password across customer homes  
- Building ECM / support UIs before G1–G5  

---

## Validation gate sign-off

| Field | Value |
|-------|--------|
| Date | |
| Elder / home used | |
| Hardware (band + gateway) | |
| Sample MQTT JSON stored at | |
| Engineer | |
| Ops / Kushalaya | |
| Proceed to Phase A? | Yes / No |

---

## Doc maintenance

When Phase V passes, update:

1. This doc status → **Active — Phase A**  
2. [IOT_B7_MG7_ROADMAP.md](./IOT_B7_MG7_ROADMAP.md) — mark MQTT PoC / Phase V complete  
3. [README.md](./README.md) — optional “pilot build in progress” note  

Field procedures stay in [IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md); this file is the **build backlog and gate**, not the installer runbook.
