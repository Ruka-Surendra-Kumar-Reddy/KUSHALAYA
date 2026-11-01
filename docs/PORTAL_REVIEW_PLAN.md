# KushAlaya portal review and improvement plan (6 Oct 2026)

Sources: 10 specialist reviews (one per area) plus 3 reviews written in the voice of
real users: a senior care manager, the agency owner and a family member abroad.
All were read-only reviews of the code. The short notes for each area, with
file and line references, are in `docs/review/`.

## Scores today

| Reviewer | Score | One-line verdict |
|---|---|---|
| Senior care manager | **4.5 / 10** | "I'd use it for assessments and quoting, but I'd still run daily care in WhatsApp and Excel." |
| Agency owner | **5.5 / 10** | "A field tool that nearly works, but not yet a business I can run: no revenue, dues, invoices or audit." |
| Daughter in Dubai | **5.5 / 10** | "The marketing promises more than the portal delivers. The SOS night is the weak point." |

Sub-scores (lowest first):

| Area | Score |
|---|---|
| Team management | 3 |
| Reporting | 3 |
| Business visibility | 3 |
| Emergency confidence (family) | 3 |
| Client knowledge | 4 |
| Safety & SOS | 4 |
| Money & GST | 4 |
| Quality & risk control | 4 |
| Daily workflow, family communication, ease of use | 5 |
| Visits & assessments (the strongest area) | 6 |
| Marketing site | 6 |
| First impression | 7 |

**Target:** 7.5 after Phases 0–1, about 8.5 after Phase 3, and 9 after Phases 4–5.

---

## Phase 0: urgent safety, security and money fixes (about 1–2 days, small changes)

These carry real risk today.

| # | Problem | Fix |
|---|---|---|
| 0.1 | **CRITICAL:** `/auth/register-elder-portal` is public. Anyone who knows a client's phone number can create a family login and see everything. No page uses it. | Turn it off (prepared locally; set `ALLOW_FAMILY_SELF_REGISTER=false`). Families get logins from staff. |
| 0.2 | Managers can reach other teams' clients: login-as-family, create family or caregiver logins, read and edit any caregiver, see other teams' documents, and act on other teams' SOS. | Add team checks to each of these endpoints. Make the SOS count use the same filter as the list. |
| 0.3 | Discount approval is skipped when a coupon is used (`commerce.py:356`). A manager can move a pending-approval order to scheduled or completed. Any order status can change to any other, including reopening a cancelled order. | Require approval when the manual discount is over 10%, for every non-admin. Add a fixed set of allowed status changes. Write an audit record for discounts, approvals and cancellations. |
| 0.4 | A **family SOS reaches staff only after 5 minutes.** The "SOS and safety alerts" email rule is never used. | Email and SMS the care manager and admins as soon as an SOS is raised. |
| 0.5 | The SOS SMS shows the old name "LiveWell360", the device MAC and hub ID, and says "open the family portal". | Change it to: "KushAlaya ALERT: {kind} — {client}, {time} IST. Not acknowledged for {n} min. Open ops.kushalaya.com". |
| 0.6 | The family can mark an SOS "resolved" themselves, and is never told staff have seen it or closed it. | Replace with "We're OK — cancel SOS" plus a confirmation. Tell the family: "Priya from your care team has seen it" and "Closed by Priya at 2:14 AM". |
| 0.7 | Ops has no loud SOS signal, only a silent count that updates every 60 seconds. | Show a red banner on every ops page, play a chime until someone acknowledges, use a browser notification, and check every 10 seconds. |
| 0.8 | Requested times are stored in UTC and printed unconverted: a family in Dubai picking 10:00 gets 11:30 IST, and emails show the wrong time. | Label every time input "India time (IST)", convert it, and show IST everywhere, with the viewer's own time too for families. |
| 0.9 | Every family update also goes out as an SMS and a WhatsApp to the emergency phone, ignoring settings: up to 12 messages per visit. | Make SMS and WhatsApp follow the per-event switches. By default, text only for SOS and missed visits. |

## Phase 1: core flows that work end to end (about 3–4 days)

**Schedule (book → start → finish → close)**
- A missed visit gets a red row and a **Rebook** button. The family sees "Didn't happen", not "scheduled".
- The family request follows the job:
  - completed → "Done"
  - cancelled or missed → "We'll rebook"
  - family cancels the request → the job is cancelled
- Starting becomes two steps: "I've arrived" (with the confirmation "Tell the family you've arrived?"), then **Start assessment / Write report**. Closing the form asks before you leave.
- A **"Needs finishing"** strip lists jobs checked in more than 4 hours ago.
- Reschedule uses a date and time picker, not typed text. On-the-way jobs can be rescheduled or cancelled.
- Double-booking warning: "Ravi already has a visit 10:00–11:00. Book anyway?"
- After an assessment, offer **View report → Review suggested products → Create order**. Ask "6 questions unanswered — submit anyway?" before submitting with gaps.
- Every action shows a success or error message. Wording is written for care managers ("Back to Schedule").

**Dashboard (start of the day)**
- Show reassessments that are due. The data already arrives but isn't displayed.
- Add a Missed / overdue group.
- A "Today" row opens **Start visit / Start assessment**, not the client page.
- Each alert shows its type (SOS / Fall / Device offline) and age ("2 h 10 min"), with an inline **Acknowledge** button.
- Approvals show only to admins, as "Order #42 · ₹1,200 off (15%) — Approve / Reject".
- Use the real first name, not the email. Add Retry and an auto-refresh every 60 seconds. Remove the "Set tenant vertical" text.

**Messages**
- Show unread first, and don't open and mark a thread read automatically. Add "Mark unread" and refresh every 60 seconds.
- Show a context line: "Manager: Priya · Next visit Tue 10:00 · 1 open alert". Add quick replies.

**Team (users)**
- Add a ⋯ menu on each person: **Edit · Change role · Reset password · Deactivate / Reactivate** (the backend already supports most of this). Add a Status column.
- Add a staff and caregiver password reset, plus "Forgot password" on both login pages.
- When a manager leaves, offer "Reassign their clients and caregivers to…".
- Show each manager's team and caseload (clients, caregivers, visits this week).

**Clients**
- Add **Edit details**: phone, address, date of birth, emergency contact, conditions, allergies, mobility.
- Header shows:
  - Care manager
  - Score (with date)
  - Next visit
  - Next assessment
  - Last visit (with "View report")
  - Open items
- Cut from 8 tabs to 5: **Overview** (with Know them, Upcoming and Family) · **Timeline** · **Orders & wallet** · **Alerts & devices** · **Documents**.
- Add, reset and deactivate family members in an inline form, replacing the pop-ups.
- On list cards: badges ("Assessment overdue", "1 alert"), next visit, and the filters My clients / Needs attention / All.

## Phase 2: family portal rebuilt around "Is Amma OK?" (about 3 days)

- Cut from 18 tabs to 5: **Home · Updates · Requests · Alerts · More**. Merge Visits and Wellness into Updates; Safety, Plan and Photos into "Score & plan"; and Receipts into Wallet.
- **Home**, in this order:
  1. "Amma is doing well · last checked Tue 4 Oct by Lakshmi"
  2. **Needs you** (a quote to approve, an alert, an SOS)
  3. Next visit (IST plus your time) and Request a visit
  4. Last visit, with photos and "Read report"
  5. **Call care team / WhatsApp / Message**
  6. Score
- Show the care team's phone, WhatsApp, and 112/108 at the top of Alerts and in the header.
- Use plain words everywhere: no raw status values, Pathway, ECM or "Personal normal". Add Retry on errors.
- Let families reset their own password (email or OTP).
- **Quote → accept → pay:** staff click "Send quote to family", and the family taps **Approve & pay** (Razorpay or wallet).

## Phase 3: assessment, report and products (about 3 days)

- **Question editor:**
  - reorder questions
  - **Show/Hide**, so the bank can go from 83 to 57 without deleting anything
  - help text for the caregiver
  - a "Suggests: Grab bar" chip
  - confirm before removing
  - warn about unsaved changes
  - show "57 active / 83 total"
  - a "Visit question" tag for Raju's 18 questions
- **Family report:**
  - an explainer under the score ("Out of 100, higher is safer…")
  - **What we found** (the risks in plain words)
  - **What to fix and the cost** (total including GST)
  - **After fixes: 62 → 81**
  - "Room by room" in place of "Domain scores"
  - ratings shown as Safe / Needs attention / Risk everywhere
- **Products:**
  - "+ New product" and an Edit drawer
  - labels "Our cost", "Price before GST" and "₹X + GST"
  - margin shown to staff only
  - install scheduling with a date picker and caregiver picker
  - Reject / Cancel / Reschedule on orders
  - card layout on phones
  - remove the "SafeHome quote" brand leak

## Phase 4: real care operations (about 1–2 weeks, large)

The care manager reviewer ranked these. Without them, teams fall back to Excel.
1. **Recurring visits:** "Mon/Wed/Fri 10:00 until 31 Mar", edit one or all, plus a **weekly roster** by caregiver.
2. **One-page client sheet:** medicines, conditions, allergies, mobility, risks, keys and access, language, doctor and hospital, family preferences.
3. **Structured visit report:**
   - checklist for each client
   - BP, sugar, SpO2 and weight, with trends
   - medicines given or refused
   - mood, appetite and sleep chips
   - photo
   - "flag for manager"
4. **Care plan:** goals, interventions and a review date, linked to the 6-month reassessment.
5. **Leave and cover** (the backend models exist): leave calendar, find cover, bulk reassign.
6. **Incident reports:** falls, near-misses, medication errors and complaints, with follow-up.
7. Handover notes between managers, and a client risk register shown as dashboard flags.
8. **Monthly family review pack:** visits, vitals trend, incidents, score change and next goals, as a PDF.

## Phase 5: running the business (about 1–2 weeks)

- **Owner dashboard:**
  - cash collected
  - outstanding dues (aged)
  - orders pipeline (₹)
  - gross margin
  - visits planned / done / missed
  - SOS acknowledge time
  - reassessment compliance
  - staff utilisation
  - clients (new / churned)
  - family satisfaction
- **GST tax invoice:** GSTIN, HSN/SAC, running number, credit notes, PDF.
- **Monthly exports:**
  - GST register
  - dues
  - margins
  - visits per caregiver
  - SOS log
  - discounts
- **DPDP:** consent at onboarding, plus data export and deletion. **Nightly encrypted off-server database backup**, with a restore test.
- A 1–5 rating after each visit, and a quarterly NPS.
- Service areas with a manager per area, a paid "Book assessment" slot plus WhatsApp on the site, and lead tracking from enquiry to paying client.

## Needed from the owner (content and decisions)

1. The care team's **phone and WhatsApp numbers** (for the family portal, SMS and the website).
2. **GSTIN**, company registration and registered address. The **HSN/SAC codes** for services and each product.
3. The assessment price (or "free"), and a typical price range for fixes, for the website.
4. **Real family testimonials** (with consent) to replace the sample quotes.
5. **MSG91 keys** and DLT templates, which SMS needs.
6. The rules for recurring visits (holidays, cover rules) before Phase 4.
7. Confirm that families never sign themselves up, or whether to build an OTP invite later.

## Order of work

Phase 0 (safety, security, money) → Phase 1 (core flows) → Phase 2 (family) →
Phase 3 (assessment/products) → Phase 4 (care operations) → Phase 5 (business).
Each phase is deployed and checked on its own. Changes waiting to deploy: Start
assessment, the log-visit page, product photos, the question panel and the
Settings tiles.

---

## KushLife: the flagship (added after five design reviews)

Design notes: `docs/review/14` (why this score + journey), `15` (target menus),
`16` (KushLife trend), `17` (marketing), `18` (best-in-class features).

**Fix this first.** The family dashboard labels the *old* stability number
"KushLife". Visits recorded with the four checks never update it, and no family
page reads the four checks at all. So families can see a stale "KushLife"
number while getting "Needs attention" messages.

**One score story.** Two names, both explained when tapped:
- **Independence Score™** is about the *home*, measured at each assessment.
- **KushLife** is about the *person*, checked on every visit: Safe / Steady / Settled / Connected.

Remove the 0–100 "stability / pulse" number and "personal normal = 50" from family views.

**Promise:** "Know they're okay. Every visit." The one story the whole business tells: Assess → Fix → Watch (KushLife) → Respond (SOS).

### K1: KushLife MVP (about 1.5 weeks, no migration)
1. **One KushLife record per visit.**
   - Each check opens on "Same as usual ✓"; "Changed" opens chips: fall, near-fall, appetite, sleep, mood, confusion, pain, medicines, hazard, lonely, message for family.
   - Optional BP / sugar / SpO2 and a photo.
   - It maps onto the old check-in, so the history carries on.
   - About 40 seconds when nothing has changed.
2. **Family card on every visit:**
   - 4 coloured checks compared with her usual
   - a photo
   - Amma's message
   - what the team did
3. **Trend for the family:** 4 rows × the last 8 visits as dots, plus one plain sentence ("Steady: 2 concerns in last 3 visits — Asha is reviewing"). Ops sees 12 visits.
4. **Rules:**

   | Level | Trigger | Action |
   |---|---|---|
   | Amber | 2 concerns on the same check in a row, or any Safe concern | manager task within 24 h |
   | Red | a fall, 3 in a row, 3 or more checks in one visit, SpO2 below 92 or a fever | urgent task within 2 h, a family message, and a suggested reassessment |
   | Missed KushLife | no checks recorded | alert |

5. **"Why this score?"** sheets for the Independence and KushLife scores, with the actual wording in note 14. Also a **journey stepper**: Assessment 62 → Fixes chosen → Installed → Weekly KushLife → Reassessment due (target 81).
6. **Wording:** rename "Care stability" and "Wellness" to KushLife. Plan cards say "KushLife checks: 1 / 2 / 4 / 4+ a month", not "weekly", for every plan.

### K2: the family promise (about 2 weeks)
- **Family phone numbers**, with any country code. Each family member chooses:
  - channel and timezone
  - level: every visit / weekly / flags only

  Today the WhatsApp digest goes to the elder's own phones, not the family abroad.
- **Weekly KushLife card on WhatsApp/email**, Monday 8 am in the family's timezone:
  - score
  - 4 lines, one per check
  - next visit time in IST and the family's local time
  - "Reply 1 to request a call"
- **Weekly AI summary**, approved by the manager before it is sent. Observations only, no medical words.
- **"Call me" and "Ask about…"** buttons. Siblings see who has already responded.
- **Personal baseline:** "normal for Amma", the median of her last 6–8 visits.

### K3: proof and polish (about 3 weeks)
- **Monthly KushLife letter (PDF):**
  - score trend
  - 4-check grid
  - manager's note
  - visits and photos
  - actions taken
  - next month's plan
  - invoice
- **Voice notes** in Telugu, Hindi or English, turned into a draft note. Vitals trends and a monthly mobility / loneliness check.
- **Quality numbers:**
  - KushLife completion %
  - time to act on a flag
  - flags per 100 visits
- **Proof for the website:**
  - number of checks done
  - median time from visit to the family knowing
  - SOS response time

### Website (alongside K1–K2)
- **Hero:**
  - "Know they're okay. Every visit."
  - A sample KushLife card in place of the photo.
  - Buttons: "See a sample KushLife report" and "Book an assessment".
- **New `/kushlife` page:**
  - the four checks
  - what you get
  - "When something dips" (a worked example)
  - Assess → Fix → Watch → Respond
  - proof
  - FAQ
  - plans with KushLife frequency
- **Offers:**
  - trial "First 4 KushLife visits"
  - referral "Gift a KushLife month"
  - NRI Complete adds a monthly video review of the trend

### Owner decisions for KushLife
1. Keep two names (Independence Score for the home, KushLife for the person)? Recommended.
2. Add sleep (and appetite) to every visit?
3. The response time we can guarantee ("we call you within X hours").
4. Manager approves AI summaries before families see them? Recommended.
5. Block closing a visit until KushLife is filled in?
6. Which vitals kit care managers carry (BP monitor, pulse oximeter, glucometer)?
