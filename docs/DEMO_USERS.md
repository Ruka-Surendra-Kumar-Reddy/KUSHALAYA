# Demo users, seed, and purge

All demo accounts use password **`demo1234`**.

---

## Kushalaya (`https://www.kushalaya.com`)

**Full seed / purge instructions:** [SAFEHOME_SEED.md](SAFEHOME_SEED.md)  
**App URLs (assessor, family, showcase):** [livewell/README.md](livewell/README.md#apps--urls)

**Demo tenant:** SafeHome Demo (`SAFEHOME360` / `LIVEWELL360`) · password **`demo1234`**

| Role | Email | Sign-in |
|------|-------|---------|
| Tenant admin | `admin@sunrise-care.example` | `/login` |
| Manager | `manager@sunrise-care.example` | `/login` |
| Family | `lakshmi.family@sunrise-care.example` | `/livewell/family/login` |
| Family (multi-elder) | `arjun.family@sunrise-care.example` | `/livewell/family/login` — use **Viewing** to switch seniors |
| Family (Clairview) | `clairview.family@sunrise-care.example` | `/livewell/family/login` |
| Assessor | `anita.caregiver@sunrise-care.example` | `/livewell` |
| Super admin | `superadmin@safehomeops.com` | `/login` |

**Family features:** [livewell/FAMILY_PORTAL_USER_GUIDE.md](livewell/FAMILY_PORTAL_USER_GUIDE.md)

Examples:

- Assessor: https://www.kushalaya.com/livewell
- Family: https://www.kushalaya.com/livewell/family/login
- Showcase: https://www.kushalaya.com/livewell/showcase

```bash
cd backend
python -m app.seed_safehome
python -m app.purge_safehome_seed --confirm
```

Elder Care and Housekeeping demo users live in their sibling repos ([ElderCareOps](https://github.com/krishnaposa/ElderCareOps), HousekeepingOps), not this deploy.
