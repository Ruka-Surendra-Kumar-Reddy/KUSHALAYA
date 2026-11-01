# UI / E2E testing (Playwright)

End-to-end tests live in `frontend/e2e/` and run against the real Next.js UI plus the FastAPI backend.

## Prerequisites

- Python 3.11+ with `backend/requirements.txt` installed
- Node 20+ with `frontend` dependencies installed
- Demo data (auto-seeded on first run if login fails)

## Run locally

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

Playwright starts the backend (`:8000`) and frontend (`:3000`) unless they are already running.

### Options

| Variable | Purpose |
|----------|---------|
| `PLAYWRIGHT_REUSE_SERVERS=1` | Reuse already-running API/UI (skip fresh `.env.local` server) |
| `PLAYWRIGHT_SKIP_SERVERS=1` | Do not start API/UI (you start them manually) |
| `PLAYWRIGHT_REUSE_SERVERS=1` | Reuse running servers instead of starting fresh ones |
| `PLAYWRIGHT_BASE_URL` | Frontend URL (default `http://127.0.0.1:3000`) |
| `NEXT_PUBLIC_API_URL` | API URL (default `http://127.0.0.1:8000`) |

Interactive UI mode:

```bash
npm run test:e2e:ui
```

Report after a run:

```bash
npx playwright show-report
```

## Test coverage

| Role | Tests |
|------|--------|
| **Care manager** | Login, dashboard, sidebar ops pages, Academy card |
| **Tenant admin** | Dashboard, Users + Settings nav, no `/tenants` access |
| **Super admin** | Tenants screen, marketplace, no tenant-admin-only restrictions on tenants |
| **Elder portal** | Dashboard, activity/notifications/contact nav, staff blocked on elder login |

Also: invalid API credentials, optional program completion on caregiver detail.

See **[DEMO_USERS.md](./DEMO_USERS.md)** for all demo accounts, seed, and purge commands.

### Demo accounts (password `demo1234`)

| Role | Email |
|------|-------|
| Care manager | `manager@sunrise-care.example` |
| Tenant admin | `admin@sunrise-care.example` |
| Super admin | `superadmin@eldercareops.com` |
| Elder portal | `lakshmi.family@sunrise-care.example` |

## CI

The GitHub Actions `e2e` job runs the same suite on pull requests (see `.github/workflows/ci.yml`).
