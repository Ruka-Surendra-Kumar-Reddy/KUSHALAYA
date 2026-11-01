# SafeHomeOps boundaries

| Layer | Location |
|-------|----------|
| Feature pack, nav, DB pack IDs | `workforceos-core/contracts/` |
| Config key names, document types | `workforceos-core/python/.../safehome/` |
| Assessment, catalog, AI, APIs | **this repo** (`backend/app/livewell/`) |
| Assessor + family PWAs | **this repo** (`frontend/app/home-safety/`) |
| Prospect / client spine | Shared `elders` + `elder_prospects` tables (customer_spine pack; API names are legacy) |

SafeHomeOps is a standalone deploy (`DEPLOY_VERTICAL=SAFEHOME360`). Care visits, caregiver matching,
and elder-care agency ops are out of scope here.
