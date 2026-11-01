# Public brand name (configurable)

The **customer-facing product name** defaults to **Kushalaya**. The internal vertical id stays `LIVEWELL360` / `/livewell` routes — do not rename those when you pick a new brand.

## App / marketing (runtime)

| Variable | Where | Purpose |
|----------|--------|---------|
| `NEXT_PUBLIC_BRAND_NAME` | Frontend `.env.local` | Public display name (SEO, marketing, family portal, i18n, docs templates in UI) |
| `NEXT_PUBLIC_BRAND_MARK` | Frontend | Optional 2–3 letter logo mark (default derived, e.g. `LW`) |
| `NEXT_PUBLIC_BRAND_ACCENT` | Frontend | Optional logo accent suffix (default `360` when the name ends with `360`) |
| `BRAND_NAME` | Backend `.env` | Same display name for AI prompts, family digests, publish summaries |

Keep **frontend and backend names in sync** on each deploy.

The ops left-nav logo uses tenant `portal_title`. Seeded values like `Kushalaya™` are treated as the product brand and rewritten to `NEXT_PUBLIC_BRAND_NAME` / `BRAND_NAME`. Custom agency titles are left alone.

Example:

```bash
# frontend/.env.local
NEXT_PUBLIC_BRAND_NAME=CareNest
NEXT_PUBLIC_BRAND_MARK=CN

# backend/.env
BRAND_NAME=CareNest
```

Rebuild / restart the frontend after changing `NEXT_PUBLIC_*` (build-time inlined).

Code entry points:

- `frontend/lib/public-brand.ts` — `publicBrandName()`, `withPublicBrand()`
- `backend/app/livewell/brand.py` — `brand_name()`, `with_brand()`

Source copy may still contain the authoring token `Kushalaya`; helpers rewrite it at runtime when the env name differs.

## Documentation (markdown)

Repo docs under `docs/` use **Kushalaya** as the default written name. Markdown cannot read env vars at view time.

When you finalize a new brand:

1. Set the env vars above and redeploy.
2. Optionally find-replace `Kushalaya` → your name in `docs/` (and `README.md`) for humans reading GitHub.
3. Leave `LIVEWELL360`, `livewell`, and hostnames alone unless you are also doing an infra rename.

## Deploy

`scripts/deploy/deploy.safehome.env.example` documents `BRAND_NAME` / `NEXT_PUBLIC_BRAND_NAME`. Deploy scripts write them into app env when set.
