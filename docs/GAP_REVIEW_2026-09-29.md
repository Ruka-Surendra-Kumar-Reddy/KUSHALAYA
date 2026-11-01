# KushAlaya — gap review against the Functionality Master List

**Basis:** "KushAlaya Functionality Master List" (prepared for the Bharani–Surendra review, 28 Sept 2026), checked line by line against the source tree on 29 Sept 2026. Paths are relative to the repo root. Verdicts are from code, not from the live site, except where marked *(live)*.

Status words: **Confirmed** = the document is right, the gap is real · **Wider** = real and bigger than written · **Not a gap** = the code already does it · **Fixed since** = closed after 28 Sept.

---

## 1. Things the review reported that are not gaps (don't spend time on these)

| Review item | Truth | Evidence |
|---|---|---|
| Family wallet "add-money redirects to operations billing" | **Not a gap.** Top-up is an in-page Razorpay checkout with server-side verify and a signed webhook. The reviewer was almost certainly using the staff "log in as family" session on the ops host, where the back-link goes to Clients. | `family/(portal)/wallet/page.tsx:52-120`, `home_safety_family.py:562-637` |
| Family messages "send control disabled" | **Not a gap as written.** The button is only disabled while the box is empty. See §2 for the real problem (messages are one-way). | `family/(portal)/messages/page.tsx:82` |
| Family documents "empty" | **Works end to end** (type allowlist, 10 MB limit, local/S3/Azure storage, tests). The list hides staff-uploaded types, so it can look empty. | `family_care_hub.py:613-740`, `tests/test_family_document_upload.py` |
| Settings → App links show "/livewell" | **Fixed since.** Labels and targets both read `/kushalaya…` in source; if prod shows otherwise the build was stale. | `app/(app)/settings/page.tsx:187-189` |
| `/livewell` route still serves the app | **Fixed since (owner decision: removed, not redirected).** It now returns the branded 404. Nothing live links to it. | `middleware.ts`, `next.config.mjs:72-87` |
| Pricing "not found" on marketing | **Wrong.** `/packages` shows four plan prices with a "See pricing" header link. Only the catalog copy on the home page is price-stripped. | `components/marketing/CarePlans.tsx:97-104`, `lib/marketing/plans.ts` |
| Marketing "no contact details" | **Partly fixed since.** The founder block (phone + email) is live. But see §2: the business phone/WhatsApp are not configured in production at all. | *(live)* |

---

## 2. Confirmed gaps, by priority

### P0 — launch blockers

**P0-1. Staff SOS operations do not exist. (Wider)**
There is no incidents table: SOS and wearable incidents are JSON blobs on the elder record, capped at 50 incidents / 100 alerts. Staff have no queue, no acknowledge, no escalation, no closure. The *only* way an incident gets closed is a family member pressing "Acknowledge" in the family portal, which silently resolves it. External notification is one-shot at ingest (email/SMS/Telegram to static env lists); a family-raised SOS sends nothing outside the portal. No timers, no on-call roster, no delivery records.
- Evidence: `livewell/family_care_hub.py:100-131,169-196,286-341`, `livewell/iot_ingest_service.py:100-143,200-325`, `api/v1/iot.py`, no ops page under `app/(app)/kushalaya/`.
- Build: `incident` + `incident_event` tables (append-only chain: received → notified per channel → acknowledged → escalated → contacted → closed); staff endpoints list/ack/resolve with required outcome + note; ops "Alerts" page with open queue and badge; escalation policy (levels, recipients, timeout) driven by a periodic job in `app/jobs`; stop family "read" from resolving. Also enforce server-side dedupe on `dedupe_key` (today only the ingestor dedupes; a replayed POST creates duplicates).
- Business rule needed first (Bharani): who receives an SOS, ack deadline, next-in-line, what proof closes it.

**P0-2. Household isolation is untested. (Confirmed)**
Scoping exists (`family_elder_access.resolve_active_elder`), but no test uses two unrelated families. Uncovered: `POST /elders/active` with an unlinked id, `/documents/{id}/file`, `/photos/{id}/image`, `/visits/{id}` + rating, `/alerts`, `/wallet`, `/service-requests/{id}/pay|cancel`, `/messages`, `/circle`, `/incidents/{id}/resolve`. `list_linked_elders` does not check tenant.
- Build: `backend/tests/test_family_household_isolation.py` — families A and B, same tenant and different tenants, assert 404/403 and no leakage on every endpoint above.

**P0-3. Family messages never reach staff. (Wider)**
Families can send; messages are stored on the elder JSON (last 200) and *no backend or ops code reads them*. The page promises "replies appear in Alerts and this thread" — nothing can reply.
- Build: staff endpoints under `care_router` to list/reply (`sender_role="team"`), an ops inbox with unread badge, notification to the care manager on new message, and a service level (who answers, how fast).

**P0-4. Production has no business phone or WhatsApp number. (live)**
`NEXT_PUBLIC_FAMILY_PHONE` and `NEXT_PUBLIC_FAMILY_WHATSAPP` are absent from the VM's `frontend/.env.local`. Every "Book via WhatsApp" button on the site falls back to the Google Form, the header "Call us" is hidden, the family-login help popup is hidden, and the brochure prints no number.
- Fix: decide the number (business line vs founder's), set both keys on the VM, rebuild (values are baked at build time).

**P0-5. Release controls are minimal. (Confirmed)**
One production VM, no staging, no tagged releases, no CI, rollback is a manual tarball restore, migrations run `init_db` unversioned, no external uptime monitor. Docs disagree on the branch (`develop` vs `main`) and on the deploy method (git pull vs tarball).
- Build: staging host (or `staging.kushalaya.com` on the same VM with its own DB), deploy by tag, one-command rollback script, external monitor on `/health/ready`, fix the docs to one method.

### P1 — before public launch

**P1-1. No read-only scored assessment report; completed assessments stay editable and unversioned.**
Both the ops detail page and the assessor PWA render the editable wizard; "Save changes" re-stamps and republishes. The only report is plain text via clipboard/`navigator.share`, and its share title is the raw legacy string "SafeHome 360 — …". Backend accepts overwrites of completed assessments with no version.
- Build: `/kushalaya/assessments/[id]/report` read-only + print CSS; lock completed (edit = new version); family printable report.

**P1-2. Scoring is inconsistent in five places. (Wider)**
- `riskLevel()` uses different thresholds from the Independence bands, so a 65 shows "Moderate Risk" and "High Risk" together; a 43 shows "High Risk" and "Immediate Action Required" (`ScoreSummary.tsx`, text report, prospect notes).
- Frontend and backend disagree on the NRI flag (`childrenAbroad` vs `familyAbroad`) and domain scores key (`familyDomainScores` vs `domainScores`), so the backend rule engine and AI contract never see them; the frontend's hard-coded pathway wins over tenant-configured rules.
- The backend never recomputes the score from ratings; it trusts the client number.
- The four packages have two name sets: website (Essential / Care Plus / Total Care / NRI Complete) vs catalog and family portal (Independent Living / Assisted Living at Home / Premium Living360 / NRI Family Peace of Mind).
- "Critical" means one thing on the Independence scale and another on care stability; `care_level` is free text with a third vocabulary in seeds.
- Build: one server-side scoring function from ratings + rubric; delete or align `riskLevel()`; one published table band → pathway → ECM → care_level; one set of package names.

**P1-3. Family invoices/receipts.** No family invoice page; paying from the wallet produces no receipt. `api/v1/customer_portal.py` is an orphan (imports a module that doesn't exist, not registered). Build: receipts page backed by wallet entries + service requests, PDF receipt.

**P1-4. Demo data hygiene (root causes, not seeds).** The 99 identical offline alerts come from the ingestor re-raising `DEVICE_OFFLINE` every 60 minutes with no collapse against an open incident. "Baseline exists but status says awaiting baseline" comes from `compute_care_status` reading only the newest visit's check-in and ignoring the stored baseline. Fix both in code, then purge the demo elder's alerts.

**P1-5. Brand remnants still visible in ops.**
- SVC-001 catalog name comes from the DB unbranded; the 29 Sept rename only turned "LWA" into "KAA", so prod likely shows "LiveWell360 Assessment (KAA)". Fix the data (reset to factory name) and wrap catalog names in `withPublicBrand` at `SuppliersAdminEditor.tsx:385`, `ProductQuoteDraftPanel.tsx:612`.
- "SafeHome 360" is not a brand token, so it leaks raw: suppliers/pricing page H1s, share title, purchase-order header, quote-report footer, rubric source label, prospect notes, settings placeholder. Replace with the brand name / "KAA".
- Bare "LiveWell" (no 360) leaks in `RecommendationChatLaunchCard.tsx:13`, `assessment-report.ts:358`, `report-visualizations.ts:19`.
- IoT panel option "LiveWell livewell/homes/…/ble" → relabel only; keep the wire topic (renaming the topic means reconfiguring MG7 hubs, ACLs and stored `mqtt_topic`).
- "LW-" solution codes: keep as internal keys (they are foreign keys in catalog, AI config, published plans), but stop printing them in customer-facing text (`assessment-report.ts:260`, `quote-report.ts:50,67`, `improvement-plan.ts:138`).
- Settings page shows the "WorkforceOS platform" maturity table, a broken "Scheduling →" link (404) and "Workforce economics" because `isSafeHome` is always false for this vertical (`nav.json` maps LIVEWELL360 to layout `livewell360`).

**P1-6. Public offer copy contradicts the operating decision.** Marketing says installations are "quoted as complete jobs (materials and labor together)" in two places and the catalog says the same, while `CarePlans.tsx` says "quoted separately"; `catalog.ts` actively rewrites "billed separately" copy as legacy and suppresses labour lines in the quote engine. "Membership" vs "Care plans" is mixed. Decision (Bharani), then copy + `catalog.ts` + catalog JSON change.

**P1-7. Business audit log covers almost nothing.** `AuditLog` is written only by academy, identity, documents, geofence, leave and shift-swap services. Not covered: enrollment/conversion, score changes, pricing, billing/subscription, user invites and role changes (there is no role-change endpoint at all, though the UI says admins can change roles). Build: `AuditService.log` calls at each of those mutations.

**P1-8. Family circle permissions.** Any family user can invite anyone (sets their password directly, no email token) and the invitee is linked to every elder the inviter has. No remove/revoke, no staff unlink. Build: primary-member flag, email-token invites, `DELETE /circle/{member}`, staff unlink.

**P1-9. Weekly digest is never sent.** Preferences and a text preview exist; the page only copies text to the clipboard. No job sends it. Build: `family_digest_send` job on the worker, WhatsApp/email provider, last-sent stamp.

### P2 — after launch

- **P2-1. Family device status.** Battery/last-seen exist on `IotDevice` but only staff endpoints expose them; ingest never updates `last_seen_at`/`battery_level` anyway. Build: update on ingest, `GET /home-safety/family/devices`, a "Devices" card.
- **P2-2. Telemetry quality.** Sessions never idle-out and any event re-opens an ended one, so durations run for days; the system session is never ended. Partner ratings are stored unrounded (4.3333). Fix: 30-min idle split, stop re-opening ended sessions, round ratings to one decimal on save.
- **P2-3. Empty modules.** Ops *Documents* only attaches to elders/caregivers with Aadhaar/PAN types, so it looks empty for Kushalaya clients. *Workflows* has zero templates for this vertical (`workflow_templates.json` has ELDER_CARE and HOUSEKEEPING only). No feature flag hides either. Decide: hide (`lib/i18n/nav.ts:52`, settings card) or configure.
- **P2-4. Privacy and retention.** No retention rule for photos, documents, messages or the assessor device cache (localStorage/IndexedDB never cleared). Every assessment photo is auto-approved for families on upload with no staff review. Files stream through auth endpoints (fine) but no signed-URL expiry.
- **P2-5. Users page.** No role edit, no deactivate, invite sets a password directly.
- **P2-6. Navigation label.** Leads/pipeline live under "Assessor recruits" (`/prospects`); nothing is labelled Leads.

---

## 3. To-do list

### A. Decisions the business owner must make first (Bharani / Krish)
1. **SOS operating rule:** who gets it, ack deadline (minutes), next-in-line, closing proof. Blocks P0-1.
2. **Business phone + WhatsApp number** for the site, and whether the founder's number stays public everywhere or only in the founder block. Blocks P0-4.
3. **Public prices:** keep the `/packages` prices public or hide them until approved.
4. **Quote structure:** "complete job" (product + labour together) or separate charges. Blocks P1-6.
5. **One name set** for the four packages (website vs portal). Blocks P1-2.
6. **"Care plans" or "membership"** — pick one.
7. **Retention periods** for photos, documents, messages; whether staff review photos before families see them.
8. **Documents and Workflows modules:** hide or configure.

### B. Quick fixes (≤ 1 day each, no decisions needed) — can start now
- [ ] Reset SVC-001 name in prod DB to "Kushalaya Assessment (KAA)"; brandify catalog names in the two ops editors.
- [ ] Replace raw "SafeHome 360" / bare "LiveWell" strings (list in P1-5) with the brand name / "KAA".
- [ ] Relabel the IoT topic option; keep the wire topic.
- [ ] Stop printing "LW-…" codes in customer-facing report text.
- [ ] Fix `isSafeHome` on Settings so the WorkforceOS table, broken Scheduling link and economics card disappear.
- [ ] Delete or align `riskLevel()`; fix `childrenAbroad`/`familyAbroad` and `domainScores` key mismatches.
- [ ] Collapse repeated offline alerts against an open incident; make `compute_care_status` use the stored baseline; purge the demo elder's 99 alerts.
- [ ] Round partner ratings on save; add 30-minute idle split to sessions.
- [ ] Empty-state hint under the family message box.
- [ ] Fix `app/not-found.tsx` comment and `README.md` references to `/livewell`.
- [ ] Set `NEXT_PUBLIC_FAMILY_PHONE` / `_WHATSAPP` on the VM once decided (item A-2) and rebuild.

### C. Launch blockers to build (Surendra / dev)
- [ ] **Incidents:** tables, staff list/ack/resolve endpoints, ops Alerts queue page + badge, escalation job, per-channel delivery records, server-side dedupe. (Est. 1–2 weeks after A-1.)
- [ ] **Household isolation test suite** covering every family endpoint with two unrelated families. (2 days.)
- [ ] **Staff inbox for family messages** with reply and notification. (3–4 days.)
- [ ] **Staging + tagged releases + rollback script + uptime monitor**; reconcile the deploy docs to one method. (3 days.)
- [ ] **Read-only assessment report** (staff, print) and lock completed assessments with versioning. (1 week.)
- [ ] **Server-side scoring** from ratings + rubric; one band → pathway → ECM → care_level table. (1 week, needs A-5.)
- [ ] **Family receipts/invoices** page + PDF; delete or finish the orphaned `customer_portal.py`. (1 week.)
- [ ] **Audit log** calls on enrollment, scores, pricing, billing, users/roles; add role-change and deactivate endpoints. (3 days.)
- [ ] **Family circle**: primary member, email-token invites, remove member, staff unlink. (3 days.)
- [ ] **Digest sender job.** (2 days.)

### D. After launch
- [ ] Family device status card + ingest updating battery/last-seen.
- [ ] Retention jobs and photo review step.
- [ ] Documents/Workflows: hide or configure per A-8.
- [ ] Rename "Assessor recruits" nav to Leads / Pipeline (or split).

---

## 4. Acceptance evidence to demand for each closed item
- SOS: a timed drill — press the band button, show the ops queue entry, ack within the deadline, escalate on a missed ack, close with a note; export the incident_event chain.
- Isolation: the test file green in CI, plus a manual two-browser check on family.kushalaya.com.
- Messages: family sends, care manager sees it in the ops inbox, replies, family sees the reply.
- Scoring: the same assessment shows one band, one pathway and one care level on the ops report, the family portal and the text report.
- Brand: `curl` of the ops pages and a case-insensitive grep of `.next/static` for "SafeHome 360", "LiveWell " (with trailing space) and "LW-".
- Release: a tagged deploy to staging, smoke test, promote, then a rollback rehearsal.
