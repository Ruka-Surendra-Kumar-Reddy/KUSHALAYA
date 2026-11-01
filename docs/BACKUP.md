# Nightly off-server backup (#105)

What runs, once installed:

| When | Unit | Script | What it does |
|---|---|---|---|
| Every night 02:30 IST | `safehomeops-backup.timer` | `scripts/backup/backup-db.sh` | `pg_dump` (compressed) + uploads `tar.gz` → encrypted → `rclone` to `<remote>/daily/<date>/`; first run each week also copied to `weekly/<YYYY-Www>/`; keeps 14 daily + 8 weekly |
| Sundays 04:00 IST | `safehomeops-restore-test.timer` | `scripts/backup/restore-test.sh` | downloads the newest daily, checks SHA-256, decrypts, restores into a throwaway database, compares row counts with live, lists the uploads archive, drops the throwaway DB |

Both write `/var/lib/safehomeops/backup/status.json` (no secrets). Admins see it as
"Last backup: <time> ✓" on **Settings → Privacy & backups** (API:
`GET /api/v1/home-safety/privacy/backup-status`, admins only). It turns red if the last run
failed or the last success is older than 36 hours.

The database password is never copied anywhere: `DATABASE_URL` is read from
`/opt/safehomeops/app/backend/.env` each run.

## What the owner must provide

1. **An off-server storage target** and credentials for it — one of:
   - **OCI Object Storage** (recommended, same cloud, different service): a bucket, e.g.
     `kushalaya-backups`, in a *different* compartment, plus a Customer Secret Key
     (S3-compatible access key + secret) for a user that can only write to that bucket.
     Ideally a different region from the VM (`ap-hyderabad-1` VM → `ap-mumbai-1` bucket).
   - **AWS S3 / Backblaze B2 / Cloudflare R2**: bucket + access key + secret.
   - **Google Drive**: a Google account/shared drive to authorise once with `rclone config`.
   Turn on bucket **versioning or retention lock** if available, so a compromised server
   cannot delete old backups.
2. **An encryption key**, chosen once and stored **in two places off the server**
   (password manager + printed copy in a safe). Without it the backups cannot be read —
   by anyone, including us. Either:
   - a long passphrase (gpg, default): `openssl rand -base64 48`, or
   - an age key: `age-keygen -o backup.key` (keep the whole file).
3. **Who gets told** if a backup fails (today: check the Settings badge; `journalctl`).

## Install (on the VM, as root — one time)

```bash
# 0. tools (OL9)
sudo dnf install -y rclone gnupg2 postgresql   # or: age (EPEL) instead of gnupg2
#   pg_dump must be the same major version as the server, or newer.

# 1. rclone remote (interactive; pick "s3" → provider "Other"/"Oracle" for OCI,
#    endpoint https://<namespace>.compat.objectstorage.<region>.oraclecloud.com)
sudo rclone config            # name it e.g. oci-backup
sudo rclone lsd oci-backup:   # must list the bucket

# 2. key + settings (root only)
sudo install -d -m 700 /etc/safehomeops
sudo sh -c 'umask 077; printf "%s" "<the passphrase>" > /etc/safehomeops/backup.key'
sudo install -m 600 /opt/safehomeops/app/scripts/backup/systemd/backup.env.example /etc/safehomeops/backup.env
sudo vi /etc/safehomeops/backup.env      # set BACKUP_RCLONE_REMOTE (and BACKUP_CIPHER=age if using age)

# 3. check config, then run once by hand
sudo bash /opt/safehomeops/app/scripts/backup/backup-db.sh --dry-run
sudo bash /opt/safehomeops/app/scripts/backup/backup-db.sh
sudo bash /opt/safehomeops/app/scripts/backup/restore-test.sh

# 4. timers
sudo cp /opt/safehomeops/app/scripts/backup/systemd/safehomeops-{backup,restore-test}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now safehomeops-backup.timer safehomeops-restore-test.timer
systemctl list-timers 'safehomeops-*'
```

The API reads the status file at `/var/lib/safehomeops/backup/status.json` (override with
`BACKUP_STATUS_FILE` in `backend/.env`). The script makes that directory 755 and the file 644
so the `safehomeops` user can read it.

The older local-only cron (`scripts/deploy/backup-safehome-postgres.sh`) can stay; it keeps a
same-disk copy for quick rollbacks. This one is the off-server copy.

## Restore for real

```bash
sudo systemctl stop safehomeops-api safehomeops-web safehomeops-iot-ingestor safehomeops-jobs.timer
DAY=2026-10-05
rclone copy oci-backup:kushalaya-backups/safehomeops/daily/$DAY /root/restore-$DAY
cd /root/restore-$DAY && sha256sum -c SHA256SUMS
gpg --batch --pinentry-mode loopback --passphrase-file /etc/safehomeops/backup.key -d db.dump.gpg > db.dump
gpg --batch --pinentry-mode loopback --passphrase-file /etc/safehomeops/backup.key -d uploads.tar.gz.gpg > uploads.tar.gz
# take a dump of the current DB first, then:
pg_restore --clean --if-exists --no-owner --no-acl -d "<DATABASE_URL as postgresql://...>" db.dump
tar -C /opt/safehomeops/app/backend -xzf uploads.tar.gz && chown -R safehomeops:safehomeops /opt/safehomeops/app/backend/uploads
sudo systemctl start safehomeops-api safehomeops-web safehomeops-iot-ingestor safehomeops-jobs.timer
```

(age: `age -d -i /etc/safehomeops/backup.key -o db.dump db.dump.age`.)

## Retention and privacy

Backups roll off after 14 days (daily) / 8 weeks (weekly). A family's "Delete my account"
(DPDP) erases live data at once; it disappears from backups when they roll off — the
privacy notice says so ("Backups roll off within 8 weeks"). If you ever restore a backup
taken before an approved deletion, the deletion must be applied again: the COMPLETED
requests are listed in Settings → Privacy & backups (and in the audit log as
`privacy.delete_approved`); ask the developer to re-run them on the restored data.
