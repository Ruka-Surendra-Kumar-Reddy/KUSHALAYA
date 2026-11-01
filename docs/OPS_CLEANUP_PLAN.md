# KushAlaya ops clean-up — plan and to-do

Agreed with the owner on 2026-10-01. Ops portal first, then the family portal.
Every phase is built locally, reviewed, then deployed. Each tab must look
professional, with no leftover demo data, extra fields or questions nobody uses.

## Decisions

| Topic | Decision |
|---|---|
| Old multi-partner setup (partners, suppliers, agencies/tenants, cleaning, workforce, prospects, master data, AI-jobs page, price lists) | Disconnect: hidden from menus, direct URLs go to the dashboard, code kept, nothing new built on it (`frontend/lib/ops-retired.ts`) |
| Roles | Admin (the owner and Surendra; everything, creates users), Manager (their team only), Caregiver (field app; also does assessments) |
| Manager scope | Only caregivers reporting to them and the clients those caregivers serve; enforced in the API |
| Products | Exactly 9: the 7 on the website (fixed grab bar, fold-up toilet rail, shower chair, anti-slip bath mat, anti-slip floor treatment, bathroom emergency pull cord, adult bed rail) + SOS wearable + KushAlaya Assessment (KAA) |
| Pricing | Each product: original (cost) price + margin % → selling price, integer paise; never sold below cost. Prices entered before GST; 18% GST added on top as a separate line |
| Discounts | Manager up to 10%; more needs admin approval. Admin creates coupon codes (% or ₹, expiry, usage limit); staff apply them. Families don't enter codes |
| Requests | A family member can request one of three things: a service, a product, or an assessment visit. They can only request; the manager schedules (date, time, place, tasks, caregiver) |
| Notifications | Family portal + email (sender contact@kushalaya.com) + SMS and WhatsApp through MSG91 (account not set up yet), on every request, schedule, change and cancellation |
| Demo data | Keep Lakshmi only (for testing); delete all other demo data after a full DB backup |
| Suggestions | Not a separate tab. Whenever an assessment or visit is completed, suggestions appear right there: findings → our products, with an AI before/after picture of the room (owner OK with image cost). Which product fixes which finding is set on the Products page |
| Wearables | Kept. Current kit: MG7 beacon + gateway + band; the gateway sends over MQTT into the existing IoT ingestor. SOS alerts go to the dashboard and the client profile |
| Family chatbot | Fixed FAQs only (no AI). Anything else is sent to the team, and the family sees "Our team will get back to you shortly" |

## Ops menu after clean-up

Dashboard · Clients · Visits · Assessments · Requests & messages · Products ·
Coupons · Wearables · Users · Settings

## Phases and to-do

### 1. Clean the menu and access — *live 2026-10-01*
- [x] Retired-pages list + menu filter (`lib/ops-retired.ts`, `lib/i18n/nav.ts`, `AppShell.tsx`)
- [x] Retired URLs redirect to the dashboard (`middleware.ts`)
- [x] Removed links to retired pages from settings, catalog, quote and order panels
- [x] Tests updated (405/405)
- [x] Menu renamed: Requests & messages, Visits, Products, Assessment questions, Wearables; groups Care / Products & assessments / Devices / Admin
- [x] Solution library, workflows, subscription and background jobs off the menu too
- [x] Every tab walked: removed developer notes (activity), escalation jargon (alerts), installer/partner field (visits), WorkforceOS subscription card and dev links (settings), tenant chip and duplicate quick links (dashboard); Users shows Admin / Manager / Caregiver only, no Viewer, no family logins
- [x] Deployed

### 2. Users and roles — *live 2026-10-01*
- [x] Map old roles: system/tenant admin → Admin, care manager → Manager; remove Viewer
- [x] Users page: Create manager · Create caregiver (profile + login in one form) · "Reports to" manager
- [x] Add `manager_user_id` to caregivers and clients (migration); existing clients and caregivers moved to the one live manager
- [x] Client → manager picker on the client profile header
- [x] API: manager sees only their team's caregivers and clients; tests for each role

### 3. Dashboard — *live 2026-10-01*
- [x] "Needs attention": new requests, unread client messages, wearable SOS alerts
- [x] "Today": visits and assessments, late or not checked in
- [x] Key numbers: clients, open requests, unread messages, SOS alerts, visits today (+ this week)

### 4. Data clean-up — *done 2026-10-01* (backup `/tmp/db-backup-phase4-20261001-034440.sql.gz` on the VM)
- [x] Deleted every client except Lakshmi (Padmaja Posa, Test Lead), their family login and 3 empty draft assessments; fixed the permanent-delete bug with AI picture jobs
- [x] Old catalog items off screen; Products shows the 9
- [x] Smoke test passes

### 5. Assessments (caregivers do them) — *live 2026-10-01*
- [x] Question bank ("Assessment questions"): clean header, sections · questions · points, no source cards; add/edit/remove as before (reorder and switch-off still to do)
- [ ] Per-client add/skip of questions (standard set is the agency question bank)
- [x] Assign an assessment (Assessments page → "Assign an assessment"): client, date and time, caregiver, notes; new `care_jobs` table shared with visits and installs
- [x] Field app: one question at a time, big Safe / Needs attention / Risk / Not applicable buttons, progress bar, drafts saved on the phone and server, review then submit
- [x] Camera room photos in the field assessment
- [x] Score and report reach the family (server scoring + publish + portal notification)
- [x] Wearables page already registers each MG7 kit to a client over MQTT; SOS raises an alert (dashboard + client)

### 6. Suggestions with before/after (inside the assessment / visit, no separate tab) — *live 2026-10-01*
- [x] Products page "Fixes" column: which assessment questions each product fixes (keyword defaults, admin can edit)
- [x] Suggestions appear in the caregiver's assessment review, on the client's Orders tab (one-click "Add to order") and for the family
- [x] Caregivers add room photos in the field assessment; Orders tab → "Make picture" starts the existing AI before/after job with the suggested products
- [x] Family Independence Score™ page: "Recommended for the home" with price incl. GST and a Request button (before/after shows after staff approve it)

### 7. Requests and visits — *live 2026-10-01*
- [x] Family portal "Requests": service (care visit, physio, discharge help, safety re-check) / product (7 website products + SOS wearable) / assessment visit
- [x] Requests land on the manager's dashboard; "Schedule" opens the Visits form pre-filled
- [x] Manager schedules: date and time, location, tasks, caregiver; family told; request marked confirmed
- [x] Product request → order on the client's Orders tab, then "Schedule installation"
- [x] The job goes to the caregiver's field app: On my way → Check in (GPS) → Complete with a note for the family
- [x] Statuses: Requested → Scheduled → On the way → Checked in → Completed / Cancelled (Missed: to add an automatic rule)

### 8. Client profile — *live 2026-10-01*
- [x] Tabs: Overview · History · Visits (map) · Wallet & receipts · Requests · Alerts & devices · Documents; admin picks the client's manager in the header
- [x] History: every scheduled job, logged visit, assessment and family request with status, who, when, check-in, notes, KushLife and Independence Score™; filter by type and open/finished; "Upcoming" with schedule/cancel/reassign
- [ ] Activity: logins per client (Session activity page has it globally)
- [x] Family Schedule shows scheduled jobs (no staff notes); its old request form now links to Requests

### 9. Products, pricing, discounts and coupons — *live 2026-10-01*
- [x] Products page shows only the 9 products (new `products` table; the old 108-item catalog is no longer on screen)
- [x] Per product: original price, margin %, selling price, price with GST, margin ₹, on/off
- [x] Orders tab on the client: products + qty, discount % with reason or coupon, live price with GST and margin; manager > 10% waits for admin (shown on dashboard); never below cost; approved order → "Schedule installation"
- [x] Coupons page: admin creates % or ₹ codes with expiry and usage limit, turns them on/off; use count shown

### 10. Notifications — *live 2026-10-01 (portal on; email/SMS/WhatsApp wait for settings)*
- [x] Every family update (request received, scheduled, changed, cancelled, on the way, arrived, completed, assessment score) goes to the portal and, through `app/livewell/family_notify.py`, to email (family logins), SMS and WhatsApp (emergency contact phone); new requests also email the client's manager
- [ ] Turn on email: add to backend/.env on the VM — `NOTIFICATION_EMAIL_PROVIDER=smtp`, `SMTP_HOST=smtp.zoho.in`, `SMTP_PORT=587`, `SMTP_USERNAME=contact@kushalaya.com`, `SMTP_PASSWORD=<Zoho app password>`, `SMTP_FROM_EMAIL=contact@kushalaya.com` — then restart the API
- [ ] SMS: `NOTIFICATION_SMS_PROVIDER=msg91` + `MSG91_AUTH_KEY`, `MSG91_SENDER_ID`, `MSG91_TEMPLATE_ID` once the account is open
- [ ] WhatsApp via MSG91: needs a small provider adapter (only Twilio/Meta exist today) and approved templates
- [x] Caregiver sees new and changed jobs in the field app (no push notification yet)

### 11. Family chatbot — *live 2026-10-01*
- [x] Help button on every family page: 8 fixed answers (plans/pay as you go, visits, KushLife, Independence Score™, products, SOS wearable, payments, changes)
- [x] Link to Requests (service / product / assessment)
- [x] Anything else goes to the team as a family message ("Our team will get back to you shortly"); team replies show in the chat and in Messages

## Order

1 → 2 → 3 → 4 → 5 → 7 → 8 → 9 → 6 → 10 → 11 (suggestions need the 9-product catalog first)

## Answered 2026-10-01

- Admins: the owner and Surendra
- Email: Zoho Mail for contact@kushalaya.com (SMTP login still needed)
- GST: prices are entered before GST; 18% is added on top
- MG7 gateway sends over MQTT, like the existing IoT ingestor
- MSG91 keys: when the account is open

## Still open (2026-10-01)

1. Email on: Zoho app password for contact@kushalaya.com (settings in Phase 10)
2. SMS on: MSG91 keys; WhatsApp needs an MSG91 adapter + approved templates
3. Per-client add/skip of assessment questions
4. Per-client login activity on the client profile
5. "Missed" status set automatically when a job passes without a check-in

## From the 2026-10-03 documents (Trust Playbook, Per-visit review) — live 2026-10-03

- [x] "Know them" card per client (approach, likes, avoid, routine) — edited on the client History tab, shown to the caregiver as "Before you knock"
- [x] Visit report: caregiver completes a visit/install with the KushLife check (Safe / Steady / Settled / Connected), a note and photos; family gets it on Schedule and as a notification
- [x] Spotted → fixed: caregiver flags a hazard (+ product) on the report → dashboard "Hazard" → Orders tab "Create order" → "Schedule installation" → install completed closes the order and marks the hazard fixed; family sees "Spotted → fixed" on the Independence Score™ page
- [ ] Products 9 → ~24 from the mapping (waiting on the owner)
- [ ] Question bank 83 → the mapped 57 (waiting on the owner)
- [ ] 18 revised per-visit questions and scoring (waiting on Raju)
- [ ] Website prices / pay-as-you-go menu (waiting on Krish)

## End-to-end tab clean-up (audit of all 40 pages, 2026-10-03) — live

### Ops portal
- [x] Client profile: the 8 tabs are solid blue buttons → quiet segmented tabs
- [x] Settings: drop the colour-theme picker ("WorkforceOS look"), custom profile fields and developer text; keep language, name/logo, and links
- [x] Wearables: device list first; MQTT broker/ingestor settings (hosts, usernames, passwords) folded into "Technical settings"
- [x] Assessment questions: 8,000 px page → each section folds open; no "AARP/CDC" jargon in the main view
- [x] Assessments: remove the empty "Unnamed · No mobile · 0%" drafts; hide unnamed drafts
- [x] Session activity, Messages, Clients, Schedule rebuilt (done today)

### Family portal
- [x] Brand leaks: "CareNest" (living plan, score summary) and "Premium Living360" (care pathway)
- [x] Home: "No visit scheduled" while a visit is booked today → count scheduled jobs
- [x] Independence Score page: remove the old "Suggested care pathway" (old plan names)
- [x] "Everything else" page: remove duplicate tiles (Visit reports, Wellness reports = Care updates)
- [x] Update digests: remove developer note ("delivery hooks into ops messaging later")
