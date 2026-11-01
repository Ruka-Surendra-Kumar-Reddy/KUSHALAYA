# SafeHomeOps / LiveWell360 — source bundle

Snapshot of the `develop` branch at commit `93980f9`, taken 2026-09-19.
This is the branch that production deploys from.

Full deploy runbook: [`docs/deploy/DEPLOY_UPDATE.md`](docs/deploy/DEPLOY_UPDATE.md)

---

## Server details

| | |
|---|---|
| VM | `opc@129.213.45.105` (Oracle Cloud, `instance-eldercareops`, OL9 / ARM aarch64) |
| OCI instance | `instance-eldercareops`, region `us-ashburn-1`, compartment `krishnaposa` |
| Deploy branch | **`develop`** |
| App directory | `/opt/safehomeops/app` |
| App OS user | `safehomeops` (in group `opc`) |
| Shared platform | `/opt/workforceos-core` (deployed separately, untracked in the app checkout) |
| Services | `safehomeops-api` (:8010), `safehomeops-web` (:3010), `safehomeops-iot-ingestor` |
| Public URL | https://livewellops.tekmatrix.ai |
| Repo | `git@github.com:krishnaposa/SafeHomeOps.git` |

Other apps sharing the same VM: ElderCareOps (`workforceos-*`) and
HousekeepingOps (`housekeepingops-*`). A SafeHomeOps deploy does not touch them.

Other domains served: `livewell.tekmatrix.ai` (marketing),
`safehome.tekmatrix.ai`, `family.tekmatrix.ai`.

---

## Two things are NOT in this zip

### 1. SSH private key

Deliberately left out — private keys should not travel inside archives that get
emailed, synced or copied to USB sticks.

**Option A — reuse the existing key.** Copy both files from the machine that
already has access:

```
C:\Users\<you>\.ssh\oracle_safehome_vm
C:\Users\<you>\.ssh\oracle_safehome_vm.pub
```

into `~/.ssh/` on the new machine, then:

```bash
chmod 600 ~/.ssh/oracle_safehome_vm
```

**Option B — generate a fresh key for the new machine (preferred).**

```bash
# on the new machine
ssh-keygen -t ed25519 -f ~/.ssh/oracle_safehome_vm -N "" -C "safehome-vm-<machine>"
cat ~/.ssh/oracle_safehome_vm.pub
```

Then, from a machine that already has access, authorise it:

```bash
ssh -i ~/.ssh/oracle_safehome_vm opc@129.213.45.105 \
  "echo '<paste the new .pub line>' >> ~/.ssh/authorized_keys"
```

Per-machine keys let you revoke one laptop without locking out the rest.

Verify either way:

```bash
ssh -i ~/.ssh/oracle_safehome_vm opc@129.213.45.105 "hostname"
```

### 2. `backend/.env`

Left out because it holds live production secrets. Build a **local dev** copy
from the template:

```bash
cp backend/.env.example backend/.env
```

and fill in your own local values. Do not copy production values onto a dev
machine. The real `backend/.env` stays on the server at
`/opt/safehomeops/app/backend/.env` and must never be deleted by a deploy — the
API will not start without it.

---

## Local setup

```bash
# backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit
python -m app.db_migrate
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
npm ci
npm run dev
```

Useful checks:

```bash
cd backend && python -m pytest -q
cd frontend && npm run typecheck && npm run lint
```

---

## Deploying an update

```bash
# 1. push to develop
git push origin develop

# 2. pull + rebuild on the VM
ssh -i ~/.ssh/oracle_safehome_vm opc@129.213.45.105
sudo -u safehomeops -i
cd app
git pull origin develop
bash scripts/start-livewell.sh
```

Done when you see `API :8010 OK`, `Web :3010 OK`, `IoT ingestor OK`.

**Check what will actually deploy** — `git status` only shows changes since your
last *commit*, so it hides committed-but-unpushed work. Always compare against
the deployed branch:

```bash
git fetch origin develop
git diff --stat FETCH_HEAD
```

Run `npm run typecheck` in `frontend/` before deploying. The VM build uses
`set -euo pipefail`, so a TypeScript error aborts the deploy before services
restart (production keeps serving the previous build, but nothing updates).

Script options:

```bash
bash scripts/start-livewell.sh --skip-frontend    # backend-only change
bash scripts/start-livewell.sh --backend-migrate  # DB model/schema changes
bash scripts/start-livewell.sh --no-restart       # build only
```

---

## Security note

The repository history on `develop` and `master` still contains committed
secrets in `backend/.env` and `backend/scratchpad.txt` — Postgres passwords,
Azure OpenAI, fal.ai and Gemini API keys, Cloudflare R2 credentials, and the app
`SECRET_KEY`. Those two files were stripped from *this bundle*, but they remain
in git history and anyone with repo access can read them.

Rotating those credentials is the fix that actually matters; scrubbing history
alone does not help once they have been exposed.
