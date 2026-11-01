# Deploying an update — SafeHomeOps / Kushalaya

How to get code from your laptop onto the production VM. Read the
[Before you start](#before-you-start) checks the first time; after that the
[Quick version](#quick-version) is all you need.

---

## The setup

| Thing | Value |
|---|---|
| VM | `opc@129.213.45.105` (Oracle Cloud, `instance-eldercareops`, OL9 / ARM) |
| Deploy branch | **`develop`** — the VM tracks this, not `master` or `testing` |
| App directory | `/opt/safehomeops/app` |
| App OS user | `safehomeops` (member of group `opc`) |
| Services | `safehomeops-api` (:8010), `safehomeops-web` (:3010), `safehomeops-iot-ingestor` |
| Public URL | https://ops.kushalaya.com |
| Build/restart script | `scripts/start-livewell.sh` |

The same VM also runs ElderCareOps and HousekeepingOps (`workforceos-*`,
`housekeepingops-*` units) and the shared platform at `/opt/workforceos-core`.
A SafeHomeOps deploy does not touch those.

---

## Before you start

**1. You need SSH access.** Test it:

```bash
ssh -i ~/.ssh/<your-key> opc@129.213.45.105 "hostname"
```

If you get `Permission denied (publickey)`, you are not set up yet. Ask someone
who already has access to append your **public** key to `~opc/.ssh/authorized_keys`
on the VM. Never share private keys around the team — each person gets their own.

**2. Your work must actually be committed and pushed to `develop`.**
This is where deploys usually go wrong — see
[Check what will actually deploy](#check-what-will-actually-deploy).

---

## Quick version

```bash
# 1. Push your work to develop (from your laptop)
git push origin develop

# 2. Pull and rebuild on the VM
ssh -i ~/.ssh/<your-key> opc@129.213.45.105
sudo -u safehomeops -i
cd app
git pull origin develop
bash scripts/start-livewell.sh
```

The script rebuilds the frontend and restarts all three services, then runs
health checks. You are done when you see:

```
==> Health checks
  API :8010 OK
  Web :3010 OK
  IoT ingestor OK
==> Done.
```

---

## Check what will actually deploy

**Do not trust `git status`.** It only shows changes since your *last commit*.
If you committed work earlier but never pushed it, `git status` looks clean
while the server is still missing everything.

Always diff against what is actually deployed:

```bash
git fetch origin develop

# What differs between your working tree and production?
git diff --stat FETCH_HEAD

# Which files, specifically?
git diff --name-status FETCH_HEAD
```

If that list is empty, there is nothing to deploy. If it shows files you
expected to already be live, they were never pushed.

To confirm what the server is currently running:

```bash
ssh -i ~/.ssh/<your-key> opc@129.213.45.105 \
  "sudo -u safehomeops -i bash -c 'cd app && git log --oneline -1'"
```

---

## Script options

```bash
bash scripts/start-livewell.sh                    # default: rebuild frontend + restart all
bash scripts/start-livewell.sh --skip-frontend    # restart services only (backend-only change)
bash scripts/start-livewell.sh --backend-migrate  # pip install + DB migrate, then rebuild
bash scripts/start-livewell.sh --no-restart       # build only, don't restart
```

Use `--backend-migrate` when your change adds or alters database models. If you
only changed Python logic (no schema change), the default run is enough — the
API restart picks it up.

---

## Verify the deploy

```bash
# On the VM — confirm the commit landed
sudo -u safehomeops -i bash -c 'cd app && git log --oneline -1'

# Public site (307 on / is normal — it redirects to login)
curl -s -o /dev/null -w "%{http_code}\n" https://ops.kushalaya.com/login   # expect 200

# Watch logs if something looks wrong
journalctl -u safehomeops-api -f
journalctl -u safehomeops-web -f
journalctl -u safehomeops-iot-ingestor -f
```

Then open https://ops.kushalaya.com and click through the pages you
changed. A green health check only means the process started — it does not mean
your feature works.

---

## Rolling back

```bash
sudo -u safehomeops -i
cd app
git log --oneline -5          # find the commit you want to go back to
git reset --hard <commit>
bash scripts/start-livewell.sh
```

If the bad commit is already on `develop`, revert it there too so the next
person's `git pull` does not bring it straight back:

```bash
git revert <commit> && git push origin develop
```

---

## Things that will bite you

**`backend/.env` lives only on the server.** It holds the production
`DATABASE_URL`, `SECRET_KEY` and API keys, and it is gitignored locally. If a
deploy ever tries to delete it, stop — that will take the API down. Never
propagate a "deleted `backend/.env`" change to the server.

**`workforceos-core/` is deployed separately.** It lives at
`/opt/workforceos-core`, owned `opc:opc` and group-writable, and is *untracked*
inside the app checkout. Do not commit it into this repo as part of an app
deploy.

**Deploys restart live services.** There is a short interruption while the
frontend rebuilds and the units restart. Avoid deploying during a demo.

**The VM pulls over SSH (`git@github.com:krishnaposa/SafeHomeOps.git`).** If the
pull fails with a permissions error, the VM's GitHub deploy key is the problem,
not your laptop's key.

**A slow shutdown is normal.** If you ever reboot this VM, stopping all the
services takes 1.5–2.5 minutes. It is not hung.

---

## If the frontend build fails

The build runs as `safehomeops` and needs group-write access to
`/opt/workforceos-core`. If you see permission errors on that path:

```bash
sudo bash scripts/deploy/start-livewell-services.sh
```

which repairs ownership (`opc:opc`, `g+rwX`) before rebuilding. See
[`scripts/deploy/README.md`](../../scripts/deploy/README.md) for the full
first-time setup, nginx/TLS, and Postgres backup runbooks.
