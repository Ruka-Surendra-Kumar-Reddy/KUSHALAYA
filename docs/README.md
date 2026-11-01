# Documentation index — SafeHomeOps

Authoritative docs for the **Kushalaya™** vertical deploy
(public brand name is configurable — see [BRAND.md](BRAND.md)).
Product docs previously under ElderCareOps `docs/livewell/` now live here.

## Start here

| Doc | Purpose |
|-----|---------|
| [BRAND.md](BRAND.md) | Configure public product name (`NEXT_PUBLIC_BRAND_NAME` / `BRAND_NAME`) |
| [VERTICAL_BOUNDARIES.md](VERTICAL_BOUNDARIES.md) | SafeHome vs shared spine |
| [SAFEHOMEOPS_SPLIT.md](SAFEHOMEOPS_SPLIT.md) | Split from ElderCareOps / deploy notes |
| [SAFEHOME_SEED.md](SAFEHOME_SEED.md) | Seed & purge demo users / clients |
| [DEMO_USERS.md](DEMO_USERS.md) | Demo logins (password `demo1234`) |
| [E2E_TESTING.md](E2E_TESTING.md) | Playwright UI tests |
| [deploy/POSTGRES_BACKUP.md](deploy/POSTGRES_BACKUP.md) | Postgres daily dump + restore runbook |
| [livewell/README.md](livewell/README.md) | Assessor / family URLs |
| [livewell/FAMILY_PORTAL_USER_GUIDE.md](livewell/FAMILY_PORTAL_USER_GUIDE.md) | Kushalaya family PWA — score, plan, schedule, chat, circle, digests, SOS, multi-elder |
| [livewell360/KAA_SPEC.md](livewell360/KAA_SPEC.md) | Kushalaya Assessment (KAA) v2.0 |
| [livewell360/RULE_ENGINE.md](livewell360/RULE_ENGINE.md) | Configuration-driven Rule Engine |
| [livewell360/CONTENT_ROADMAP.md](livewell360/CONTENT_ROADMAP.md) | Domains, catalog, memberships, phases |

## LiveWell product docs

| Doc | Purpose |
|-----|---------|
| [livewell/SAFEHOME360_ASSESSMENT.md](livewell/SAFEHOME360_ASSESSMENT.md) | Assessment framework |
| [livewell/ASSESSOR_ITEM_TRAINING.md](livewell/ASSESSOR_ITEM_TRAINING.md) | Per-item rating training |
| [livewell/SOLUTION_CATALOG_PRICING.md](livewell/SOLUTION_CATALOG_PRICING.md) | Catalog, pricing, master workbook |
| [livewell/CONDITIONAL_LOGIC.md](livewell/CONDITIONAL_LOGIC.md) | Intake conditional rules |
| [livewell/CUSTOMER_SIGNED_DOCUMENTS.md](livewell/CUSTOMER_SIGNED_DOCUMENTS.md) | Paper pack + wet-signed uploads |
| [livewell/IOT_B7_MG7_ROADMAP.md](livewell/IOT_B7_MG7_ROADMAP.md) | B7 wristband + MG7 hub → Mosquitto → LiveWell SOS |
| [livewell/IOT_B7_MG7_FIELD_SETUP.md](livewell/IOT_B7_MG7_FIELD_SETUP.md) | Configure B7 (BeaconSET) + MG7 (MinewLink) + elder bind |
| [livewell/IOT_B7_MG7_ARCHITECTURE.md](livewell/IOT_B7_MG7_ARCHITECTURE.md) | Mosquitto, ingestor, API — how SOS flows |
| [deploy/mqtt/SERVER_SETUP.md](../deploy/mqtt/SERVER_SETUP.md) | Server runbook + install scripts |

Elder Care operations docs (matching, caregiver PWA, monitoring, agency pitch) belong in
[ElderCareOps](https://github.com/krishnaposa/ElderCareOps), not this deploy.
