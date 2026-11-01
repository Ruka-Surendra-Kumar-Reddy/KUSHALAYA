# Kushalaya — Running TODO

Backlog compiled 2026-09-20. Each item has a status note grounded in what's
actually in the codebase today (not assumptions) so priorities can be set
with real information. Update this file directly as items move / get added —
it's meant to be the durable running list, not a one-off snapshot.

Legend: 🔴 not started · 🟡 partial / needs decision · 🟢 exists, needs
validation or polish

---

## Quick view

**🟡 Ongoing**
- Rename LiveWell → Kushalaya — **UI renaming done.** Still renaming remaining places: backend code, internal IDs, docs, everywhere else.
- Vendors & Partners — merging into a single place; also making it easier and more reliable to add/manage vendors, especially at large numbers.
- Azure AI image generation (solution kit list) — reviewing the current AI image generation for solution kits, trying to switch to OpenAI instead of Azure.
- WhatsApp & SMS — **SOS email testing completed.** WhatsApp and SMS notification channels still need to be checked/tested.
- Monitoring & KPI — ongoing.
- Full functional testing — testing the whole app regularly as changes are made, not a one-time pass.
- UI cleanup — polishing the look and removing old branding leftovers.

- Prefunded wallet — **backend + family UI built** (ledger, recharge, pay-on-approval, refunds). Remaining: live Razorpay keys, webhook URL registration, staff-side pricing UI.
- Family portal cleanup — **first pass done** (service requests wired up, duplicate nav removed). Remaining: broader layout/usability review.

**🔴 Not Started**
- AARP/CDC validation — checking our safety questions match trusted guidelines.
- Production readiness checklist — final steps before going fully live.
- Rotate exposed secrets — changing old passwords/keys found in code history.
- Push stranded commits — saving recent server changes back to GitHub.

*(Dropped from your latest list: "Rename LWA → KAA" — now done, see below; "TLS auto-renewal check" and "Fall detection" — see note below, let me know if these should stay tracked separately.)*

---

## Full detail

## Branding

- [ ] 🟡 **Rename LiveWell → Kushalaya everywhere.** Domain/infra migration to
      kushalaya.com is done (see recent work). `BRAND_NAME` /
      `NEXT_PUBLIC_BRAND_NAME` already default to "Kushalaya" for
      user-facing display text. Still LiveWell-branded: internal identifiers
      (`DEPLOY_VERTICAL=LIVEWELL360`, `/livewell/...` routes, DB pack name),
      `docs/` markdown (written copy, not env-driven), and code comments.
      Per `docs/BRAND.md` the original design intentionally keeps internal
      IDs stable across brand changes — **open question below** on how far
      to go.
- [x] 🟡 **Rename LWA → KAA** (Kushalaya Assessment). Done 2026-09-28 for
      every user-facing string, doc, comment and the catalog workbook:
      marketing copy, `messages/*.json`, `workforceos-core` platform catalogs,
      `lwa-rubric.ts` title, `rubric-sources.ts` labels, `default_rubric.json`,
      `default_catalog.json` + `generated/catalog-from-workbook.json`,
      `Kushalaya_Configuration.xlsx`, `docs/livewell360/KAA_SPEC.md` (renamed).
      Identifiers (`LWA_TITLE`, `LWA_CATEGORIES`, `LWA_RAW_MAX`, the
      `lwa-rubric.ts` module) deliberately kept — internal names stay stable
      across brand changes, per `docs/BRAND.md`.
      - [x] **Production data** (done 2026-09-29 via
            `backend/scripts/rename_lwa_to_kaa.py`, idempotent, dry-run by
            default): the catalog is persisted in the DB
            (`app_global_settings.home_safety_catalog` + legacy copies in
            `tenant.workflow_config`), which a deploy never touches. 8 strings
            renamed on the VM, including a package description no seed file
            had. PDFs already exported keep "LWA"; regenerated reports pick up
            "KAA" since the title comes from `LWA_TITLE`, not the record.

## Assessment quality & compliance

- [ ] 🔴 **AI cross-reference assessment questions + severity/scoring against
      AARP and CDC home fall-risk standards.** Rubric lives in
      `backend/app/livewell/default_rubric.json` /
      `frontend/lib/livewell/lwa-rubric.ts`. No existing validation against
      external standards found — net-new work.

## Vendors vs. Partners

- [ ] 🟡 **Resolve vendor/partner overlap.** Confirmed two *separate* admin
      screens exist today: `/livewell/suppliers` (`SuppliersAdminEditor.tsx`,
      backed by a real `Supplier` model in
      `backend/app/schemas/home_safety_suppliers.py`) and
      `/livewell/partners` (`PartnersAdminEditor.tsx`). Plus two marketing
      pages (`/marketing/partners`, `/marketing/become-a-partner`) pitching a
      "Trusted Partner Network." Real ambiguity, not imagined — worth a
      product decision (see questions below).

## AI / integrations

- [ ] 🟡 **Azure OpenAI for photo AI — evaluate replacing.** Codebase finding:
      the photo *visualization* pipeline (`ai_visualization_service.py`,
      `ai_provider.py`) is already provider-abstracted and configured for
      **Gemini** (vision analysis) + **fal.ai Kontext** (image render) via
      `AI_VISION_PROVIDER` / `AI_RENDER_PROVIDER`, not hardcoded to Azure.
      Azure OpenAI usage found instead in `workforce_copilot_service.py`,
      `resume_intelligence_service.py`, `recommendation_chat_service.py` —
      i.e. copilot chat + resume parsing, not photo processing. Need to
      confirm with you which pipeline is actually costing Azure spend today
      (production `.env` may be configured differently than the code
      defaults suggest).
- [ ] 🟡 **WhatsApp integration.** Groundwork exists, not production-live:
      `notifications/meta_whatsapp_stub.py` (Meta Cloud API — stub, blocked
      on Meta Business/BSP template approval) and
      `notifications/twilio_messaging.py` (Twilio — sandbox-ready faster,
      less "official"). Provider-selection already exists via
      `NOTIFICATION_WHATSAPP_PROVIDER`. Decision needed: which provider to
      productionize first.

## Safety features

- [ ] 🟡 **SOS — test thoroughly + expand family portal visibility.** Not a
      blank slate: `SOS_BUTTON` is a real supported IoT event type
      (`backend/app/api/v1/iot.py`), tied to wearable B7/MG7 bands, and
      `PANIC` is a monitoring alert type. Needs: end-to-end test (band press
      → ingest → alert → notification → family portal), and a decision on
      what family portal should surface (live status? history? escalation
      path?).
- [ ] 🟡 **Fall detection — sequence after other priorities (per your note).**
      Also not a blank slate: `FALL_SUSPECTED` is already a defined IoT
      event type alongside `SOS_BUTTON`. Unclear how much of the
      detection→alert→resolution path is actually wired vs. just the event
      type existing. Worth a quick audit before scoping it as "new" work.

## Family portal

- [x] 🟢 **Cleanup pass done (2026-09-24).** Two things fixed:
      1. **Service requests were orphaned** — the backend endpoints and the
         frontend API client both existed, but no page ever called them, so
         families could not actually request a service. Now a real
         `/livewell/family/services` page (request, see quotes, approve & pay,
         cancel).
      2. **Navigation duplication** — the dashboard's 7 "quick tile" links
         duplicated the More page entirely; removed. More is now the single
         index (it was also missing Visit reports).
- [ ] 🔴 **Remaining: broader layout/usability review.** The dashboard is
      still long (score, care status, stability chart, pathway chip, 5 cards,
      share row, 3 KPIs, alert strip, priorities, visuals). Worth a proper
      information-hierarchy pass with real families.

## UI cleanup

- [ ] 🟡 **General UI cleanup pass across the app — ongoing.** Consistent spacing,
      colors, fonts, and layout across ops portal + family portal +
      marketing pages; remove leftover LiveWell-era visuals (old logo marks,
      screenshots, placeholder copy) now that branding is moving to
      Kushalaya; tidy up rough/unfinished-looking screens. Needs a walkthrough
      to build the specific punch list — flagging as its own tracked item for
      now.

## Observability & monitoring

- [ ] 🟡 **Session activity visibility — enhance.** Already substantial:
      `session_activity_service.py`, `/api/v1/activity`, configurable
      `ACTIVITY_LOG_MODE` (standard: user actions + mutations/errors;
      verbose: also logs successful reads). Question: what's missing today —
      filtering/search, export, real-time view, alerting on unusual
      patterns?
- [ ] 🟡 **Application/infra monitoring — assess coverage.** Azure
      Application Insights + OpenTelemetry are wired into the codebase but
      **commented out / optional** in `.env.example`
      (`APPLICATIONINSIGHTS_CONNECTION_STRING`, `ENABLE_TELEMETRY`). Need to
      confirm whether this is actually turned on in production — if not,
      there may currently be **no APM/error tracking running at all**, which
      would be a production-readiness gap worth prioritizing.

## KPIs

- [ ] 🟡 **Build KPI dashboard.** Not starting from zero: an "Executive
      Command Center" (`backend/app/services/executive_service.py`) already
      aggregates workforce/finance KPIs (bench cost, utilization target
      85%, etc.) — appears to be inherited from the shared WorkforceOS
      platform rather than SafeHome/Kushalaya-specific. Likely need:
      elder-care-specific KPIs layered on top (assessment completion rate,
      visit compliance %, alert response time, family engagement,
      conversion from assessment → quote → install).

## New: Prefunded wallet

- [x] 🟢 **Wallet core built (2026-09-24).** One wallet per elder, any linked
      family member can top it up. `family_wallets` + `wallet_transactions`
      (append-only, signed amounts, integer paise — deliberately *not* stored
      in `elder.custom_attributes` like service requests, because money needs
      ACID + constraints). Idempotency keys on every write, row lock on
      balance mutation, CHECK constraint against negative balance. 21 tests
      cover the money invariants incl. webhook signature tampering.
- [x] 🟢 **Recharge + spend flow.** Razorpay provider (order + HMAC webhook
      verification) behind a provider interface, with a local stub so the
      flow is walkable without keys. Debit is upfront on family approval of a
      staff-quoted price; cancelling a paid request auto-refunds to the wallet.
- [ ] 🔴 **Remaining before going live with real money:**
      - Live Razorpay keys + `PAYMENTS_PROVIDER=razorpay` in production env
      - Register the webhook URL (`/api/v1/home-safety/family/wallet/webhook`)
        in the Razorpay dashboard and set `RAZORPAY_WEBHOOK_SECRET`
      - Staff-side UI to enter the quoted price (API accepts
        `quoted_amount_minor`; `FamilyServiceRequestsAdmin.tsx` has no field yet)
      - Reconciliation job comparing `SUM(ledger)` to cached balances
        (`WalletService.reconciled_balance_minor` exists, nothing schedules it)
      - Decide GST/invoice treatment for wallet top-ups vs. service billing

## Testing & QA

- [ ] 🔴 **Full functional testing pass — ongoing.** End-to-end testing across
      ops portal, family portal, assessments, pricing/quotes, IoT alerts, and
      notifications as features stabilize. Treat as a continuous item, not a
      one-time task — re-run after each major change (branding rollout, UI
      cleanup, SOS/fall detection work, etc.), not just once at the end.

## Production readiness

- [ ] 🔴 **"Make it ready for production."** Too broad to action as one item
      — needs breaking into a checklist once the above are clearer (security
      review, load testing, backup/restore drill, error monitoring — see
      Observability above, legal/privacy review, on-call runbook, rate
      limiting, secrets rotation — note current `backend/.env` history
      exposure flagged in `SETUP-README.md`).

## Additions from codebase research (not in your original list)

- [ ] 🔴 **Rotate exposed production secrets.** `SETUP-README.md` explicitly
      flags that `backend/.env` and `backend/scratchpad.txt` secrets
      (Postgres password, Azure OpenAI, fal.ai, Gemini keys, Cloudflare R2,
      app `SECRET_KEY`) are in git history on `develop`/`master`. This is a
      live security exposure independent of everything else on this list —
      worth prioritizing regardless of production-readiness timing.
- [ ] 🔴 **TLS cert auto-renewal.** The certs issued during the domain
      migration (kushalaya.com/.in/www/ops) are Let's Encrypt, 90-day expiry
      (2026-12-18). Confirm certbot auto-renewal is actually cron'd on the
      VM — an unrelated app on the same box (`care.tekmatrix.ai`) was found
      with an **already-expired** cert during this work, so this isn't
      hypothetical.
- [ ] 🔴 **Sync GitHub with what's live.** Two commits from the domain
      rename are sitting on the VM's `develop` branch, not yet pushed to
      GitHub — needs a push (or deploy key setup) so source of truth
      matches production.
