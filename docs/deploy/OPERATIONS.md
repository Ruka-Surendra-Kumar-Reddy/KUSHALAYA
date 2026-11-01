# Operations runbook

Who runs what, where it runs, and what to do when it breaks. Short on purpose; the
deep detail is in the linked documents.

## Servers

| | Production | Test | Krishna's box |
|---|---|---|---|
| OCI name | `instance-eldercareops` | `instance-kushalaya-test` | `instance-20260511-0906` |
| IP | 129.213.45.105 | 150.136.230.200 | 129.158.220.48 |
| Shape | A1.Flex 2 OCPU / 12 GB | A1.Flex 1 OCPU / 6 GB | A1.Flex 1 OCPU / 6 GB |
| Sites | www / ops / family / caregiver `.kushalaya.com` | test / test-ops / test-family | not ours |
| Key | `_ssh/oracle_safehome_vm` (user `opc`) | same key | unknown, do not touch |

Free tier is exactly used (4 OCPU / 24 GB). Resizing one box means shrinking another.

## Services on production

| Unit | Port | Purpose |
|---|---|---|
| `safehomeops-api` | 8010 | FastAPI backend |
| `safehomeops-web` | 3010 | Next.js (all three sites) |
| `safehomeops-iot-ingestor` | — | MQTT → API bridge for watches |
| `mosquitto` | 1883 local, 8883 TLS | watch broker (gateways connect to `ops.kushalaya.com:8883`) |
| `safehomeops-jobs.timer` | — | SOS escalation, missed visits, digests, every 2 min |
| `nginx`, `postgresql` | 80/443, 5432 local | |

ElderCareOps and HousekeepingOps also live on this box (`care.` / `clean.tekmatrix.ai`). Leave them.

## After any reboot of production

```bash
systemctl is-active safehomeops-api safehomeops-web safehomeops-iot-ingestor mosquitto nginx postgresql safehomeops-jobs.timer
ss -tln | grep -E ':(1883|8883|3010|8010)\b'
curl -s https://ops.kushalaya.com/health/ready
```

All must say `active`; both broker ports must be listening. A green website does not
prove the broker is up (2026-11-01: broker failed after a reboot for 10 minutes because
its files had the wrong owner; fix in CLAUDE.md → Traps).

## Deploy

- Production: tarball method, `docs/deploy/DEPLOY_UPDATE.md`, rollback snapshots in `/tmp/rollback-*.tar.gz`.
- Test: `git pull` of `develop` + `scripts/start-livewell.sh` (`TEST_INSTANCE.md`).
- Branching and rules: `GIT_WORKFLOW.md`.

## Backups

Daily Postgres dump to `/var/backups/safehomeops/postgres` (`POSTGRES_BACKUP.md`).
Uploads are **not** in that dump: `/var/lib/safehomeops/uploads` needs its own copy.

## Known incidents

| Date | What | Cause | Fix |
|---|---|---|---|
| 2026-09-28 | blank dark page after login | build overwrote `.next` under the running server; old service worker | staged builds; workers without fetch handler |
| 2026-09-29 | sign-in stuck on "Signing in…" | middleware redirected RSC fetches | `isRscFetch` guard |
| 2026-11-01 | broker down after resize reboot | MQTT files owned by `safehomeops`, not `mosquitto` | chown per `install-livewell-mqtt.sh`; reboot checklist above |

## Contacts

Owner: Krish Posa (+91 83095 00488). Tech: Surendra. Business rules: Bharani.

## Automatic messages (since 2026-11-01)

| Trigger | Who gets what | Code |
|---|---|---|
| Staff / caregiver / family invite without a password | Email + WhatsApp (SMS fallback) with a 72 h set-password link (`/reset-password?token=…&welcome=1`) | `backend/app/services/account_setup.py`, `POST /users/{id}/send-setup-link` |
| Website purchase paid (Razorpay) | Payer becomes a client with a family-portal login (set-password link + welcome), GST invoice issued and sent by email + WhatsApp (`payment_received`, `invoice_ready` with the PDF), staff receipt as before | `plan_purchase_service._after_payment`, `app/livewell/invoice_delivery.py` |
| Any wallet payment that produces an invoice | Every linked family login gets the invoice by email + WhatsApp | `gst_invoices.on_wallet_entry` |
| Invoice links | Signed, 30-day, no login: `GET /api/v1/business/invoices/shared/{token}` | `invoice_delivery.share_token` |
| Sign-in | Email **or** mobile number as the username; forgot-password accepts either | `auth_service.find_user_by_identifier` |

WhatsApp goes through MSG91 (`NOTIFICATION_WHATSAPP_PROVIDER=msg91`, number 919059051085).
All nine Meta templates were approved on 2026-11-01: `sos_alert`, `missed_visit`,
`visit_completed`, `daily_digest`, `kushalaya_update`, `login_otp`, `assessment_report`,
`invoice_ready`, `payment_received`. Template variable order lives at the top of
`invoice_delivery.py`; change it there if a template is edited in MSG91.
