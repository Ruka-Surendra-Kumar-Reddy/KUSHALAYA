# Fix checklist (from docs/PORTAL_REVIEW_PLAN.md)

How each phase works:
1. Build it.
2. Run tests.
3. Two reviewers check it: an **auditor** (correctness, security, permissions) and a **UX reviewer** (clean, clear, works on phones).
4. Fix whatever they find, then re-check.
5. Deploy and verify on the live site.
6. Tick the items off and move to the next phase.

Marks: `[ ]` to do · `[~]` in progress · `[x]` done and live

## Phase 0: safety, security, money
- [x] 1 Turn off public family self-sign-up (built locally, not deployed)
- [x] 2 Team limits: login-as-family, family/caregiver logins, caregivers, documents, incidents, SOS count
- [x] 3 Coupon must not skip discount approval
- [x] 4 Manager can't move an order waiting for approval to scheduled/completed
- [x] 5 Allowed order status changes only
- [x] 6 Audit log for discounts, approvals, price changes and cancellations
- [x] 7 Family SOS: staff email and SMS right away
- [x] 8 Connect the "SOS & safety alerts" email setting
- [x] 9 SOS SMS wording (brand, no device IDs, ops link)
- [x] 10 Family can only "We're OK — cancel SOS", with a confirm
- [x] 11 Tell the family when an SOS is seen and when it's closed
- [x] 12 Ops: red SOS banner, chime and browser notification, check every 10 seconds
- [x] 13 Times: IST input labels and conversion; correct times in emails
- [x] 14 SMS/WhatsApp follow each person's settings (default: only SOS and missed visits)

## KushLife K1
- [x] 15 Family "KushLife" shows the real 4-check data (retire the stability number)
- [x] 16 One KushLife record per visit: "Same as usual", chips, optional vitals and photo
- [x] 17 Family card after every visit
- [x] 18 Trend grid (8 visits for family, 12 for staff) with one plain sentence
- [x] 19 Amber/red flags → manager task, family message, suggest reassessment; alert when KushLife is skipped
- [x] 20 "Why this score?" sheets (Independence Score and KushLife)
- [x] 21 Journey view (family home and client page)
- [x] 22 One set of score colour bands everywhere
- [x] 23 Rename to KushLife; plan cards show visits per month

## Phase 1: core flows
- [x] 24 Missed visit: Rebook button, red row, family sees "Didn't happen"
- [x] 25 Family request status follows the job
- [x] 26 Family cancelling a request cancels the job
- [x] 27 "I've arrived" confirmation; warn before leaving an unfinished visit
- [x] 28 "Needs finishing" strip
- [x] 29 Date picker for reschedule; allowed when the visit is "on the way"
- [x] 30 Warn on double-booking and duplicate assessments
- [x] 31 Assessment done → report → products → order; ask before submitting with gaps
- [x] 32 Every action shows success or an error
- [x] 33 Wording for care managers
- [x] 34 No booking in the past
- [x] 35 Dashboard: reassessments due
- [x] 36 Dashboard: missed and overdue
- [x] 37 Dashboard: "Today" rows start the visit
- [x] 38 Dashboard alerts: type, readable age, Acknowledge, filter to the team
- [x] 39 Approvals shown to admins only
- [x] 40 Messages and hazards link to the right client
- [x] 41 Dashboard clean-up: tenant warning, real name, Retry and auto-refresh, matching counts
- [x] 42 Messages: unread first, no auto-read, Mark unread
- [x] 43 Messages: refresh, client context line, quick replies, Ctrl+Enter
- [x] 44 Team ⋯ menu: Edit, Role, Reset, Deactivate; Status column; show Viewers
- [x] 45 Staff and caregiver password reset; "Forgot password"
- [x] 46 Reassign a team when a manager leaves
- [x] 47 Manager team and caseload view
- [x] 48 Edit caregivers / mark as left
- [x] 49 One caregiver-creation rule; rename "Assessor"; no family login without a client
- [x] 50 Edit client details
- [x] 51 Client page tabs: Overview · Timeline · **Assessments** · Orders & wallet · Alerts & devices · Documents
- [x] 52 Client header: next visit, last visit, next assessment, open items, care manager
- [x] 53 Family logins: inline add, reset and deactivate (no pop-ups)
- [x] 54 Client list: badges, next visit, filters
- [x] 55 Message button opens this client's thread
- [x] 56 Client wording and empty states

## Phase 2: family portal
- [x] 57 5 tabs + More, with redirects
- [x] 58 Home: status line, Needs you, next and last visit, call
- [x] 59 Care team phone, WhatsApp and 112/108
- [x] 60 "Request a visit"; form first; IST label
- [x] 61 Remove jargon and raw status words
- [x] 62 Errors with Retry
- [x] 63 Alerts history
- [x] 64 Stop notices about your own actions
- [x] 65 Families reset their own password (Forgot password? on family login, Phase 1)
- [x] 66 Quote → family accepts → pay
- [x] 67 Remove the Schedule page's dead code and duplicate list

## Phase 3: assessment, products, admin pages
- [x] 68 Question editor: reorder, hide, help text, product chip, confirm, unsaved warning, counts, visit tag
- [x] 69 Question editor wording
- [x] 70 Family report: found / fix and cost / after / "Area by area" / plain ratings
- [x] 71 Send score history and critical findings to families
- [x] 72 Products: new product, edit, labels, margin internal, phone layout
- [x] 73 Order install: date picker and caregiver; Reject / Cancel / Reschedule
- [x] 74 Coupons: edit, help note, error handling
- [x] 75 "SafeHome quote" brand leak
- [x] 76 Hiring polish
- [x] 77 Settings polish
- [x] 78 Alert row wording
- [x] 79 Alert row: phone, address, call family, acknowledged by
- [x] 80 Bands list: battery, last seen, test, replace, Band ID
- [x] 81 Confirm before escalating
- [x] 82 Device offline / low battery alerts
- [x] 83 Notify on ops completion and on confirm (with date)
- [x] 84 Hazard and order notices to family; approval email to admins
- [x] 85 Staff told when a family cancels a request
- [x] 86 Missed-visit email wording
- [x] 87 Email deep links and titles

## KushLife K2
- [x] 88 Family phone numbers, with channel, timezone and level for each person
- [x] 89 Monday KushLife card
- [x] 90 Weekly summary (manager approves)
- [x] 91 "Call me" / "Ask about…"; siblings see replies
- [x] 92 "Normal for Amma" baseline

## Phase 4: care operations
- [x] 93 Recurring visits and weekly roster
- [x] 94 One-page client sheet
- [x] 95 Care plan (goals, review date)
- [x] 96 Leave and cover
- [x] 97 Incident reports
- [x] 98 Handover notes and risk register
- [x] 99 Per-client visit checklist

## KushLife K3 + Phase 5: business
- [x] 100 Monthly KushLife letter PDF, voice notes, vitals trends, quality numbers
- [x] 101 Owner dashboard
- [x] 102 GST tax invoices (needs GSTIN and HSN/SAC codes)
- [x] 103 Monthly exports
- [x] 104 Data-protection (DPDP) consent, export and delete
- [x] 105 Nightly off-server encrypted backup with a restore test
- [x] 106 Visit rating and NPS
- [x] 107 Service areas, paid assessment slot, WhatsApp, lead tracking
- [x] 108 Marketing: hero, /kushlife page, trial and referral, assessment price, testimonials, company details

## Added
- [x] 109 Client page **Assessments** tab: list of every assessment (date, score, who did it, status), View report, Start or continue, Book new, compare with the previous one
- [x] 110 Clean, consistent admin and manager pages (same header, actions, empty states and buttons on every page)
- [x] 112 (Phase 3) Staff-raised emergency: manager/caregiver logs an emergency from a phone call (caregiver or elder) — one button "Raise emergency" on client + caregiver app
- [x] 113 (Phase 3) Emergency process to close: steps (call elder → call family → ambulance/hospital → partner notified) each timed and ticked, owner assigned, escalation if untouched, close needs outcome + note; family sees status; timeline report
- [x] 114 (Phase 3) Emergency partner hand-off + feedback loop: send to vendor partner/internal list (configurable in Settings), partner acknowledges via link, outcome recorded; exact partners/requirements from Surendra
- [x] 115 (Phase 4) Live location on visits: once the caregiver taps "On the way"/check-in, family and ops see where they are on a map with ETA; "Get directions" opens Google Maps / Apple Maps / Waze; location sharing stops at check-out
- [ ] 116 (needs definition) "PMS" asked by the field team — meaning to be confirmed before building

## Next (owner, 11 Oct) — in this order
- [ ] 117 Competitor review: Anvayaa (anvayaa.com) — pricing, plans, services, site, trust signals, journey — scored against Kushalaya on one rubric; list of enhancements
- [ ] 118 About us page on www (company, why, team, how we work, Hyderabad presence)
- [ ] 119 Website chat assistant with a named person ("Hi, I'm Surendra — how can I help?"): answers FAQs, books KushCare Discovery, hands off to WhatsApp/call — design after 117
- [ ] 120 More blog posts (SEO topics, Codex images)
- [ ] 121 Full live E2E: marketing, ops, family on desktop + phone (links, images, flows)

## Deployed with Phase 0 (6 Oct)
Start assessment one tap, log-visit page, product photos, product question panel, Settings tiles.
- [x] 111 Family profile editing: own name/phone + parent's emergency contacts directly; health details via "request a change" approved by staff
