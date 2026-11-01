# Production data reset (keep configuration + named staff)

Script: `backend/scripts/reset_prod_keep_staff.py` · Test: `backend/tests/test_reset_prod_keep_staff.py`

Owner request (2026-11-01): clear everything in production except the accounts of
Krishna, Bharani, Chandhan and Raju.

## What goes, what stays

| Goes (all rows) | Stays |
|---|---|
| clients (elders) and everything on them: visits, check-ins, hub alerts, messages, care status | tenants, settings (`app_global_settings`) |
| family logins, family links, contacts, wallets, wallet ledger, receipts | catalog `products`, `vendors`, rubric/solutions (settings JSON) |
| caregivers, caregiver prospects, client prospects, pipeline activity | subscription plans, tenant subscriptions, SaaS invoices, coupons |
| assessments, AI jobs, vision analyses, hazard checks, photos | contract templates, family questions |
| incidents, incident events, staff alerts, care jobs, goals, series | blog posts and images |
| documents **and their files on disk** | background job definitions |
| contracts, signatories, orders, tax invoices, customer plans | IoT hubs and devices (devices are unassigned, not deleted) |
| sessions, session events, auth attempts, audit log, push devices | the `--keep` users only; every other login is removed |
| KushLife letters/summaries, NPS, privacy requests, leave requests | |

Users not in `--keep` are deleted whatever their role, including the old demo
`manager@sunrise-care.example`, the family demo and any super admin. Rows on kept
tables that pointed at a deleted user are re-pointed to the first kept user (or NULL).

## Procedure (on the production VM)

Copy the script first if the VM does not have it yet (Windows cmd):

```
scp -i %USERPROFILE%\oracle_safehome_vm C:\Users\ASUS\Downloads\SafeHomeOps-source\SafeHomeOps\backend\scripts\reset_prod_keep_staff.py opc@129.213.45.105:/tmp/
ssh -i %USERPROFILE%\oracle_safehome_vm opc@129.213.45.105 "sudo install -o safehomeops -g safehomeops -m 644 /tmp/reset_prod_keep_staff.py /opt/safehomeops/app/backend/scripts/"
```

Then, every command below runs as `safehomeops` from `backend/` with the `.env` loaded.
Define this once per session in cmd (it is the prefix for the three steps):

```
set RUN=ssh -i %USERPROFILE%\oracle_safehome_vm opc@129.213.45.105 "sudo -u safehomeops bash -lc 'cd /opt/safehomeops/app/backend && set -a && . ./.env && set +a && PYTHONPATH=. .venv/bin/python scripts/reset_prod_keep_staff.py
```

1. **Backup** (mandatory):
   `ssh -i %USERPROFILE%\oracle_safehome_vm opc@129.213.45.105 "sudo bash /opt/safehomeops/app/scripts/deploy/backup-safehome-postgres.sh"`
   and copy the newest file in `/var/backups/safehomeops/postgres/` off the box.
2. **List users** and choose the four to keep:
   `%RUN% --list-users'"`
3. **Dry run** with the chosen emails:
   `%RUN% --keep a@x,b@y,c@z,d@w --dry-run'"`
   Read the row counts and the "DELETE users" list. Nothing has changed yet.
4. **Apply** (only after the owner has read the dry run):
   `%RUN% --keep a@x,b@y,c@z,d@w --apply --i-have-a-backup'"` with `CONFIRM=RESET-PROD`
   in front of the python command, i.e. `... && CONFIRM=RESET-PROD PYTHONPATH=. .venv/bin/python ...`
5. **Verify:** re-run the dry run (all counts zero), sign in with a kept account,
   `systemctl is-active safehomeops-api safehomeops-web mosquitto`.

## Afterwards

- Kept users keep their passwords; everyone has to sign in again (sessions are cleared).
- The demo watch is unassigned. Re-assign hubs/devices to real clients in Ops → Wearables.
- Re-create real clients through the normal flow. Do not run the demo seeds on prod.
- Rollback = restore the step-1 backup with `scripts/deploy/restore-safehome-postgres.sh`;
  deleted upload files are not in the DB backup, so take a copy of
  `/var/lib/safehomeops/uploads` as well if any real document must survive.
