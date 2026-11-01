# SafeHomeOps vertical split

SafeHome 360™ moves from **ElderCareOps** into a sibling deploy repo **SafeHomeOps**, following the same pattern as [HousekeepingOps](HOUSEKEEPINGOPS_SPLIT.md).

| Repo | `DEPLOY_VERTICAL` | Database | Domain |
|------|-------------------|----------|--------|
| **ElderCareOps** | `ELDER_CARE` | `eldercareops.db` | Elders, care plans, monitoring, family portal |
| **SafeHomeOps** | `SAFEHOME360` | `safehomeops` (PostgreSQL) or `safehomeops.db` (SQLite pilot) | Assessments, catalog, pricing, AI jobs, family PWA |
| **HousekeepingOps** | `HOUSEKEEPING` | `housekeepingops.db` | Cleaning CRM, dispatch |

Shared platform: [workforceos-core](https://github.com/krishnaposa/workforceos-core).

---

## Step 1 — Patch workforceos-core

```bash
cd ElderCareOps
export WORKFORCEOS_CORE=/path/to/workforceos-core
python scripts/apply_workforceos_core_safehome_patches.py
```

Then **manually merge** JSON fragments from `scripts/workforceos-core-safehome/patches/`:

| Fragment | Target file |
|----------|-------------|
| `verticals.fragment.json` | `contracts/verticals.json` — add `SAFEHOME360` vertical + features |
| `database_packs.fragment.json` | `contracts/database_packs.json` — add `safehome360` pack |
| `nav.fragment.json` | `contracts/nav.json` — Safe Home admin group |
| `messages.fragment.json` | `contracts/messages/platform.en.json` |

Rebuild core:

```bash
cd "$WORKFORCEOS_CORE/typescript" && npm ci && npm run build
pip install -e "$WORKFORCEOS_CORE/python"
```

---

## Step 2 — Bootstrap SafeHomeOps repo

```bash
cd ElderCareOps
python scripts/bootstrap_safehomeops.py --target ../SafeHomeOps
cd ../SafeHomeOps
git init
git add .
git commit -m "Bootstrap SafeHomeOps from ElderCareOps main"
```

Create GitHub repo `SafeHomeOps` and push.

---

## Step 3 — Run SafeHomeOps locally

```bash
export WORKFORCEOS_CORE=/path/to/workforceos-core
cd SafeHomeOps
bash scripts/link-workforceos-core.sh
cd backend && bash ../scripts/install-backend-deps.sh
python -m app.init_db
uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend && npm install && npm run dev -- -p 3010
```

---

## PostgreSQL (production)

Use a **dedicated database** on the same PostgreSQL instance as Elder Care / Housekeeping — never share a `DATABASE_URL` across verticals.

| Setting | Value |
|---------|--------|
| Role | `safehomeops` |
| Database | `safehomeops` |
| API / Web ports (dual-VM) | `8010` / `3010` |
| Example hostname | `ops.kushalaya.com` (marketing `www.kushalaya.com`; legacy `ops.kushalaya.com` → 301) |

### Create the database (VM, as root)

```bash
sudo SAFEHOME_DB_PASSWORD="$(openssl rand -base64 24)" bash scripts/deploy/setup-safehome-postgres.sh
# Save the password — it is printed once.
```

Or manually:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER safehomeops WITH PASSWORD 'REPLACE_STRONG_PASSWORD';
CREATE DATABASE safehomeops OWNER safehomeops;
SQL
```

### Backend `.env`

```env
DEPLOY_VERTICAL=SAFEHOME360
DATABASE_URL=postgresql://safehomeops:REPLACE_STRONG_PASSWORD@127.0.0.1:5432/safehomeops
UPLOAD_DIR=/var/lib/safehomeops/uploads
```

Then migrate:

```bash
cd backend && source .venv/bin/activate
python -m app.init_db
```

### Local dev (Windows / macOS)

Install PostgreSQL, create role + database, then point `backend/.env` at:

```env
DATABASE_URL=postgresql://safehomeops:your-password@localhost:5432/safehomeops
```

URL-encode special characters in the password (`@`, `:`, `/`, etc.).

### Automated VM deploy

```bash
sudo cp scripts/deploy/deploy.safehome.env.example /etc/workforceos/safehome.env
sudo nano /etc/workforceos/safehome.env
sudo bash scripts/deploy/deploy-safehome.sh
```

If you **already created** the `safehomeops` OS user and PostgreSQL database manually, set in `safehome.env`:

```bash
PRESERVE_DB_PASSWORD=1   # do not rotate the Postgres role password on re-deploy
APP_DB_PASSWORD=<the password you chose>   # still required for backend/.env DATABASE_URL
RUN_BOOTSTRAP=0
```

Optional: `SKIP_DB_SETUP=1` skips role/DB creation entirely (only ensures dirs, clone, app).

Re-running `deploy-safehome.sh` or `setup-safehome-postgres.sh` is safe — existing user/DB are detected and skipped.

### Start / restart services

**As `safehomeops` (daily):** after `git pull`, rebuild and restart:

```bash
sudo -u safehomeops -i
cd /opt/safehomeops/app
bash scripts/start-livewell.sh
# optional: bash scripts/start-livewell.sh --backend-migrate
```

Once (as root), allow passwordless restart:

```bash
sudo bash scripts/deploy/install-safehome-sudoers.sh
```

**As root (first-time systemd + nginx):**

```bash
sudo bash scripts/deploy/start-livewell-services.sh
# options: --backend-migrate | --skip-tls | --skip-frontend
```

See also [scripts/deploy/README.md](../scripts/deploy/README.md) for Kushalaya VM deploy.

---

## What lives where

### workforceos-core (contracts only)

- `SAFEHOME360` vertical + `home_safety` feature flag
- `safehome360` database pack ID
- Nav + route guards for `/home-safety/*`
- `workforceos_core.safehome.config_keys` — `workflow_config` key names
- `workforceos_core.safehome.document_types` — photo / catalog image types
- Optional TS: `@workforceos/contracts/safehome` pricing types

### SafeHomeOps (product code)

| Asset | Path |
|-------|------|
| Backend services | `backend/app/livewell/` |
| API routes | `backend/app/api/v1/home_safety_*.py` |
| Models | `home_safety_assessment`, `home_safety_ai_job` |
| Assessor + family PWAs | `frontend/app/home-safety/` |
| Admin | `frontend/app/(app)/home-safety/` |
| Components + lib | `frontend/components/livewell/`, `frontend/lib/livewell/` |
| Master workbook | `backend/app/livewell/data/Kushalaya_Configuration.xlsx` |
| Docs (authoritative) | `docs/livewell/`, `docs/SAFEHOMEOPS_SPLIT.md` |

### ElderCareOps (after cutover)

SafeHome product code should be removed from ElderCareOps once SafeHomeOps is the production destination:

1. **`backend/app/models/packs.py`** — remove from `ELDER_CARE_MODULES`:
   - `app.models.home_safety_ai_job`
   - `app.models.home_safety_assessment`

2. **`backend/app/api/v1/router.py`** — remove all `home_safety_*` imports and `include_router` lines

3. **Delete or archive** `backend/app/livewell/`, `home_safety_*.py` APIs, frontend home-safety trees

4. **`workforceos-core/contracts/verticals.json`** — remove `home_safety` from `ELDER_CARE.features`

5. **Settings page** — remove Home safety assessments card

6. **Optional integration** — ElderCare prospect sync calls SafeHomeOps API instead of in-process `syncProspect`

(Use ElderCareOps `docs/SAFEHOMEOPS_SPLIT.md` for the up-to-date cutover status in that repo.)

---

## Dual-vertical VM (optional)

Same host as ElderCare + Housekeeping:

| Service | Port | Domain |
|---------|------|--------|
| ElderCareOps API | 8000 | care.tekmatrix.ai |
| HousekeepingOps API | 8001 | cleaning.example.com |
| SafeHomeOps API | 8010 | ops.kushalaya.com |

Each app has its own database file and `DEPLOY_VERTICAL`.

---

## Customer / prospect spine

SafeHomeOps keeps **`elders`** + **`elder_prospects`** via the `customer_spine` pack (same interim pattern as HousekeepingOps). Assessments link via `prospect_id` / `elder_id` columns and `customer_link.py`.

For standalone SafeHome-only agencies, use `/api/v1/prospects` without full elder care admin UI.

---

## CSS note

Bootstrap copies full `globals.css` including `.home-safety-*` rules. A later cleanup can move those rules to `frontend/styles/safehome.css` imported only in SafeHome layouts.
