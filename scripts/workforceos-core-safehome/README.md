# workforceos-core patches for SafeHomeOps

Apply these files to your [workforceos-core](https://github.com/krishnaposa/workforceos-core) clone **before** running SafeHomeOps.

## Quick apply (from ElderCareOps root)

```bash
export WORKFORCEOS_CORE=/path/to/workforceos-core
python scripts/apply_workforceos_core_safehome_patches.py
cd "$WORKFORCEOS_CORE/typescript" && npm run build
cd "$WORKFORCEOS_CORE/python" && pip install -e .
```

## Manual merge

### 1. `contracts/verticals.json`

Merge `patches/verticals.fragment.json` into the root object:

- Add `SAFEHOME360` to `validVerticals`
- Add `verticalLabels.SAFEHOME360`
- Add `packs.SAFEHOME360.features` (see fragment)
- **Optional:** remove `home_safety` from `ELDER_CARE` pack when ElderCare no longer ships SafeHome

### 2. `contracts/database_packs.json`

Merge `patches/database_packs.fragment.json`:

- `deployPacks.SAFEHOME360` → `["platform", "workforce", "customer_spine", "safehome360"]`
- `defaultSqliteFiles.SAFEHOME360` → `safehomeops.db`
- `packLabels.safehome360` → `SafeHome 360™`

### 3. `contracts/nav.json`

Merge `patches/nav.fragment.json`:

- Move Safe Home admin items under a nav group visible for `SAFEHOME360` vertical
- Set `routePrefixFeatures["/home-safety"]` → `home_safety`

### 4. Python package

Copy `python/workforceos_core/safehome/` into workforceos-core:

```
python/src/workforceos_core/safehome/
  __init__.py
  config_keys.py
  document_types.py
```

Register in `python/src/workforceos_core/__init__.py` if needed.

### 5. TypeScript contracts (optional)

Copy `typescript/src/safehome/` types for shared pricing/rubric shapes used by both repos.

### 6. Messages

Merge `patches/messages.fragment.json` keys into `contracts/messages/platform.en.json`.

## Verify

```bash
cd workforceos-core/python
python -c "from workforceos_core.database_packs import packs_for_deploy; print(packs_for_deploy('SAFEHOME360'))"
python -c "from workforceos_core.verticals import has_feature; print(has_feature('SAFEHOME360', 'home_safety'))"
```

Expected deploy packs: `platform`, `workforce`, `customer_spine`, `safehome360`.
