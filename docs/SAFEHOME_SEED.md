# SafeHome seed & purge

Create and remove demo accounts for **SafeHomeOps** (`SAFEHOME360`).

**Marketing:** [`https://www.kushalaya.com`](https://www.kushalaya.com) · **Ops:** [`https://ops.kushalaya.com`](https://ops.kushalaya.com)  
Customer / field URLs (assessor, family, showcase): [home-safety/README.md](livewell/README.md#apps--urls)

All demo passwords: **`demo1234`**

| Item | Value |
|------|--------|
| Tenant | **SafeHome Demo** |
| Vertical | `SAFEHOME360` |
| Register slug | `safehome-demo` |
| Modules | `app.seed_safehome`, `app.purge_safehome_seed` |

---

## Seed (create)

Use the **backend venv** (system Python will fail with `No module named 'sqlalchemy'`).

```bash
cd /opt/safehomeops/app/backend   # or: cd backend locally
source .venv/bin/activate
python -m app.db_migrate          # if needed
python -m app.seed_safehome
```

Without activating:

```bash
/opt/safehomeops/app/backend/.venv/bin/python -m app.seed_safehome
```

### What it creates

| Role | Email | Login path |
|------|-------|------------|
| Platform super admin | `superadmin@safehomeops.com` | `/login` |
| Tenant admin | `admin@sunrise-care.example` | `/login` |
| Manager | `manager@sunrise-care.example` | `/login` |
| Family (self) | `lakshmi.family@sunrise-care.example` | `/livewell/family/login` |
| Family (son, multi-elder) | `arjun.family@sunrise-care.example` | `/livewell/family/login` |
| Family (Clairview) | `clairview.family@sunrise-care.example` | `/livewell/family/login` |
| Assessor | `anita.caregiver@sunrise-care.example` | `/home-safety` (assessor PWA) |

Also creates clients **Lakshmi Reddy** and **Padmaja Posa**, and seeds empty master-data
entities from `backend/app/livewell/data/Kushalaya_Configuration.xlsx`.

### Partial entry points

```bash
python -m app.seed_super_admin       # super admin only
python -m app.seed_safehome_admin    # tenant + tenant admin
python -m app.seed_safehome_demo     # clients, family, assessor, master data
```

`python -m app.seed_care_demo` and `python -m app.seed_care_admin` are aliases that
call the SafeHome seeds above.

### Deploy

`APP_SEED=admin` or `APP_SEED=demo` in `/etc/workforceos/safehome.env` runs:

```bash
python -m app.seed_safehome
```

On an existing VM after `git pull`:

```bash
cd /opt/safehomeops/app/backend
source .venv/bin/activate
python -m app.seed_safehome
```

---

## Purge (remove seed users)

Requires `--confirm`. Does **not** delete the tenant row or live master-data
`workflow_config` (catalog/rubric/etc.).

```bash
cd /opt/safehomeops/app/backend   # or: cd backend locally
source .venv/bin/activate

# Preview
python -m app.purge_safehome_seed --confirm --dry-run

# Remove staff + family + assessor logins
python -m app.purge_safehome_seed --confirm

# Also delete seeded clients (Lakshmi, Padmaja) and assessor caregiver row
python -m app.purge_safehome_seed --confirm --include-clients

# Also remove platform super admin
python -m app.purge_safehome_seed --confirm --include-super-admin

# Everything seed-related (users + clients + super admin)
python -m app.purge_safehome_seed --confirm --include-clients --include-super-admin
```

Re-create afterward:

```bash
python -m app.seed_safehome
```

### Family app note

Family routes require an `ELDER_PORTAL` user. Staff accounts are redirected to
`/dashboard`. Use `/livewell/family/login` with a family email above
(or a private window if you are already logged in as admin).  
Full guide: [FAMILY_PORTAL_USER_GUIDE.md](livewell/FAMILY_PORTAL_USER_GUIDE.md).

---

## Catalog showcase photos

`seed_safehome` does **not** include product photo binaries. Use Catalog UI uploads, or:

```bash
cd /opt/safehomeops/app/backend && source .venv/bin/activate

# From a folder (files named by ProductID, or ProductID/ subfolders)
python -m app.create_catalog_images --from-dir /path/to/photos --dry-run
python -m app.create_catalog_images --from-dir /path/to/photos --confirm
python -m app.create_catalog_images --from-dir /path/to/photos --replace --confirm

# From ElderCare (or another) DB + its upload directory — remaps to new document IDs
python -m app.create_catalog_images \
  --from-db "postgresql://eldercareops:...@127.0.0.1:5432/eldercareops" \
  --from-upload-dir /var/lib/eldercareops/uploads \
  --from-tenant-name "Sunrise Elder Care" \
  --confirm
```

Only products that exist in the destination catalog (matching **ProductID**) receive
images. Then open `/home-safety/showcase?tenant_id=<id>`.

---

## Related

- Demo user matrix (incl. legacy Elder Care notes): [DEMO_USERS.md](DEMO_USERS.md)
- Master spreadsheet / Master Data UI: [home-safety/README.md](livewell/README.md)
- Deploy split notes: [SAFEHOMEOPS_SPLIT.md](SAFEHOMEOPS_SPLIT.md)
