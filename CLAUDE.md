# CLAUDE.md — working in this repo

Product: **Kushalaya** (elder care, Hyderabad). Old names in code (`LiveWell360`,
`SafeHomeOps`, `tekmatrix.ai`) are history, not another product.

## Owner's rule: keep token usage low

- Do only what was asked. No extra audits or "while I'm here" work.
- Read only the lines you need (`grep -n`, `sed -n`). Don't re-read what you wrote.
- Screenshots: one or two per change, clipped to what changed.
- Run tsc/vitest once at the end; production build only before a deploy.
- Short replies: result first, a few bullets.
- Don't message other sessions unless you touch their files.
- Small `Edit`s, not whole-file rewrites.
- **Ask before anything large** (multi-agent work, rebuilds, image batches) and say how big.

## Layout

```
SafeHomeOps-source/
├── SafeHomeOps/          this app — NOT a git repo
│   ├── backend/          FastAPI + SQLAlchemy 2.0
│   ├── frontend/         Next.js 14 App Router
│   ├── _ssh/             production SSH key (never commit)
│   └── workforceos-core  JUNCTION -> ../workforceos-core
└── workforceos-core/     shared package (git, branch develop)
```

`workforceos-core` is shared with two other products on the same VM. Editing it
changes what this frontend compiles against, and it deploys separately.

## Run and verify

```bash
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --port 8010
cd frontend && npx next dev -p 3010

cd frontend && npx tsc --noEmit && npx vitest run          # 405 tests
cd backend && ./.venv/Scripts/python.exe -m pytest -q      # 641 pass, 17 skipped, ~3 min
```

A dev server locks `.next`; to test a production build, build in a copy of `frontend/`.

## Deploy (copy files to the VM, rebuild in place)

VM `opc@129.213.45.105` · app `/opt/safehomeops/app` · services `safehomeops-api`
:8010, `safehomeops-web` :3010, `safehomeops-iot-ingestor` · sites www / ops /
family `.kushalaya.com`. Always `ssh -i _ssh/oracle_safehome_vm` (plain ssh fails).

```bash
# 1. payload — exclusions are mandatory
tar -czf /tmp/deploy.tar.gz --exclude=node_modules --exclude=.next --exclude=.venv \
  --exclude=__pycache__ --exclude='*.pyc' --exclude='*.db' --exclude='.env*' \
  --exclude=uploads --exclude=tsconfig.tsbuildinfo \
  frontend/app frontend/components frontend/lib frontend/messages frontend/public \
  frontend/styles frontend/middleware.ts backend/app backend/tests
tar -tzf /tmp/deploy.tar.gz | grep -E "\.env|_ssh|\.key$|\.pem$"   # must print nothing

# 2. on the VM: snapshot the same paths to /tmp/rollback-<date>.tar.gz
# 3. extract over /opt/safehomeops/app, chown -R safehomeops:safehomeops,
#    confirm backend/.env and frontend/.env.local size + mtime are UNCHANGED
# 4. rebuild
sudo -u safehomeops -i bash -lc 'cd /opt/safehomeops/app && bash scripts/start-livewell.sh'
```

Flags: `--skip-frontend`, `--backend-migrate` (new tables/columns), `--no-restart`,
`--full`. The build goes to `.next-staging` and is swapped in when done; keep it
that way (building in place served unstyled pages for minutes).

Rollback: extract the snapshot, re-run step 4. Verify the actual change, not just
health checks: `curl` the page and grep `.next/static` for what you changed.

Shared-package changes: copy the file into `/opt/workforceos-core/...` on the VM,
then rebuild. `NEXT_PUBLIC_*` values are baked at build time; the VM's
`frontend/.env.local` overrides source defaults.

Draft scripts, not yet used on the VM: `scripts/release.sh`,
`scripts/deploy/{rollback-livewell,smoke-test,install-staging,health-watch}.sh`.

## Branding

- `LiveWell360` in source copy is an **authoring token**, rewritten at runtime by
  `withPublicBrand()` / `brandifyDeep()` (frontend) and `with_brand()` (backend).
  **Do not mass-replace it.** Only "SafeHome 360", bare "LiveWell" and unbranded DB
  values leak; `lib/brand-leaks.test.ts` guards that. Check rendered output, not source.
- `lib/livewell/`, `components/livewell/`, `backend/app/livewell/`,
  `/api/v1/home-safety/*`, `DEPLOY_VERTICAL=LIVEWELL360` and unit names are internal.
  Import paths are not URLs — never rewrite them.
- `care.tekmatrix.ai` and `clean.tekmatrix.ai` are other products. Leave them.
- `/livewell/*` URLs were removed at the owner's request and 404. Don't reinstate.
  On the family host an unknown path goes to `/` (see `FAMILY_SEGMENTS` in
  `middleware.ts`); on ops it shows the branded `app/not-found.tsx`.
- Service workers (`kushalaya-sw.js`, `kushalaya-family-sw.js`) have **no fetch
  handler on purpose**. Bump `CACHE` and the `?v=` in the registration together.
- Logo: one square mark everywhere. `lib/brand-assets.ts` names the files; after
  replacing one, bump `BRAND_ASSET_VERSION` and run
  `node scripts/gen-brand-inline.mjs` (`/brand/*` is cached for a year). Keep it
  44px or larger.
- Copyright text lives in `LEGAL_ENTITY_NAME` (`lib/public-brand.ts`).
- Nav routes live in the shared package (`contracts/nav.json`, `shell/nav.ts`,
  and the prebuilt `typescript/dist/shell/nav.js` — change all three).

## Traps

- **Never ship `.env` / `.env.local`.** They exist only on the server; the local
  one points at localhost and breaks production.
- **Platform message catalogs are public** — the whole JSON is bundled into the
  client. Never put credentials there. Prove removal by grepping the built output.
- **`_ssh/` is not git-ignored.** Never commit it.
- **The VM's git tree is dirty on purpose.** No `git checkout .` there.
- **Money is integer paise**, never float (`backend/app/core/money.py`).
- **Razorpay webhook signatures** are HMAC-SHA256 over the raw bytes.
- **Middleware cannot see `RSC` / `_rsc`** (Next strips them). Redirect only real
  page loads: use `Sec-Fetch-Dest: document` / `Sec-Fetch-Mode: navigate`. With
  curl, send `-H "Sec-Fetch-Dest: document"`.
- **A scrolling flex child needs `min-height: 0`.**
- **Shared shell styles go in `components/ks-shell.css`**, not a page's own CSS.
- **SSH "permission denied" means you forgot `-i`**, not that access is gone.
