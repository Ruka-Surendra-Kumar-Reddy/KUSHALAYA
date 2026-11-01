# SafeHomeOps

> **Platform:** [WorkforceOS](https://github.com/krishnaposa/workforceos-core) · **Product:** LiveWell360™ (configurable — [docs/BRAND.md](docs/BRAND.md))

Deploy repo for the SafeHome vertical — field assessments, solution catalog, pricing quotes,
master workbook import, AI visualizations, and family PWA.

This is a **single repo**: LiveWell360 (SafeHomeOps) plus vendored **workforceos-core** (`LIVEWELL360` vertical pack).

```text
.
├── backend/              FastAPI API (port 8010)
├── frontend/             Next.js app (port 3010)
└── workforceos-core/     shared contracts + Python/TS packages
```

## Setup

### 1. Platform contracts (TypeScript)

```bash
cd workforceos-core/typescript
npm ci
npm run build
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e ../workforceos-core/python
python -m app.init_db
python -m app.seed_livewell
uvicorn app.main:app --reload --port 8010
```

`init_db` / `seed_livewell` create the LiveWell Demo tenant, staff, clients, family portal users, assessor, and load master data from `LiveWell360_Configuration.xlsx`.

### 3. Frontend

```bash
cd frontend
cp .env.local.example .env.local   # Windows: copy .env.local.example .env.local
npm install
npm run dev -- -p 3010
```

## Demo logins (password `demo1234`)

| App | Email |
|-----|-------|
| Admin | `admin@sunrise-care.example` |
| Manager | `manager@sunrise-care.example` |
| Family | `lakshmi.family@sunrise-care.example` |
| Assessor | `anita.caregiver@sunrise-care.example` |
| Super admin | `superadmin@livewellops.com` |

Family login: `https://family.kushalaya.com/login` (the family portal has its own host; on the ops host `/kushalaya/family*` redirects there)

Purge seed users: `python -m app.purge_safehome_seed --confirm`  
(add `--include-clients` and/or `--include-super-admin` as needed)
## Environment

```env
DEPLOY_VERTICAL=LIVEWELL360
DATABASE_URL=sqlite:///./safehomeops.db
```

## URLs

**Marketing:** [`https://www.kushalaya.com`](https://www.kushalaya.com)  
**Ops:** [`https://ops.kushalaya.com`](https://ops.kushalaya.com)  
**Family:** [`https://family.kushalaya.com`](https://family.kushalaya.com)  
(the old `*.tekmatrix.ai` hosts 301 to these in nginx; the old `/livewell/*` paths were removed and now 404 — see CLAUDE.md)

| App | Production URL |
|-----|----------------|
| Assessor PWA | https://ops.kushalaya.com/kushalaya |
| Assessment wizard | https://ops.kushalaya.com/kushalaya/assess/{id} |
| Product showcase | https://ops.kushalaya.com/kushalaya/showcase |
| Family login | https://family.kushalaya.com/login |
| Family dashboard | https://family.kushalaya.com/dashboard |
| Staff admin | https://ops.kushalaya.com/login → `/dashboard`, `/kushalaya/catalog`, … |

Full path list: [docs/livewell/README.md](docs/livewell/README.md#apps--urls)

TLS / nginx: [deploy/nginx/README.md](deploy/nginx/README.md)


**Docs index:** [docs/README.md](docs/README.md) · Product guide: [docs/livewell/README.md](docs/livewell/README.md) · Seed/purge: [docs/SAFEHOME_SEED.md](docs/SAFEHOME_SEED.md)
