# Target structure (tabs to add / remove)

## Ops menu
- **Today:** Today (was Dashboard) · Schedule (+ Roster week view, + Log a past visit) · Alerts (NEW in menu, + History tab) · Messages
- **Care:** Clients (Care plan tab inside each client) · Incidents (NEW)
- **Business (admin; managers limited):** Orders & quotes (NEW pipeline) · Invoices & payments (NEW, GST) · Products & pricing (Coupons tab merged in) · Reports (NEW; owner KPIs, exports, assessment reports)
- **Team:** Users · Caregivers · Hiring · Leave & cover
- **Settings:** Notifications & SOS · Assessment questions (moved) · Devices (was Wearables) · Company & GST (NEW) · Activity log

## Roles
- **Admin:** everything.
- **Care Manager:** own team only. Quotes allowed; discounts over 10% go to an admin. Selling price only, no cost or margin, no coupons. Invoices read-only. Own reports. Own caregivers and leave. Settings view-only with a banner.
- **Viewer:** read-only Today, Clients and Reports.

## Family portal
**Tabs:** Home · Updates · Requests · Alerts · More
- **More:** Score & plan · Messages · Wallet & receipts · Documents · Emergency contacts
- **Profile menu:** Family members · Notifications · Password

**Redirects:**
- visits, wellness → updates
- schedule → services
- plan, photos → safety anchors
- receipts → wallet

**Page sections (top to bottom):**
- **Home:** status sentence · Needs you · Next visit (IST + local) · Last visit · Call / Message · Score + KushLife
- **Requests:** form first, then Upcoming, Open, Past
- **Alerts:**
  - phone / WhatsApp / 112-108 bar
  - live SOS with "We're OK — cancel"
  - open alerts, then history
- **Score & plan:** explainer · What we found · Fix & cost · Approve · After fixes · Area by area · Photos
- **Wallet:** balance · pay · GST invoices · statement

## Ops pages (sections → primary actions)

**Today**
- SOS strip
- Needs attention (missed, reassessments, alerts)
- Today's visits
- Unread messages
- Approvals (admin only)
- Device problems
- *Actions:* Start visit · Reschedule

**Schedule**
- Day / Roster toggle
- Needs finishing
- Missed (Rebook)
- Today
- Upcoming
- Past
- *Actions:* + Book · I've arrived

**Alerts**
- Open (status, owner, timer, phone, address)
- Acknowledged
- History
- *Actions:* Acknowledge · Call family

**Client profile**
- Header: name, status, care manager (Change), stats
- Tabs: Overview (one-page sheet + Family) · Care plan · Timeline · Orders & wallet · Alerts & devices · Documents
- *Actions:* Edit details · Message family

**Care plan:** goals with review date · medicines · recurring visit routine · risk register · handover notes

**Incidents:** open list (severity, owner, age) · detail (what happened, actions, family told)

**Orders:** Draft · Sent · Accepted · Awaiting approval · Scheduled · Done · Cancelled

**Invoices:** dues by age · invoices · payments · credit notes

**Reports:** KPI row · monthly exports · assessment reports

**Team tabs:** Users (⋯ menu) · Caregivers · Hiring · Leave & cover

**Devices:** bands with battery, last seen and online status, problems first · MAC behind an expander · Send test · Replace band

## Content to remove
- Unassigned
- the "Set tenant vertical" message
- Client #id
- MAC / mqtt shown up front
- Pathway, ECM, "Personal normal", "Projected"
- raw status words and "unsafe"
- decimals
- brand leaks
- Excel / "tenant database" notes
- duplicate tiles
- the sidebar "Call team" link that dials the elder's own contacts
- `window.prompt` pop-ups
- notices to yourself about your own actions

## Content to add
- page subtitles
- empty states with a button
- field help text
- times shown as IST + local
- "Not recorded" instead of "—"
- "View only" banner
- Retry on errors

## Migration order
1. Wording only.
2. Family nav and redirects.
3. Ops menu regroup. Nav lives in three places: nav.json, shell/nav.ts and dist nav.js.
4. Rebuild Today, Client profile and Schedule.
5. Orders, Leave & cover, Roster (use existing models).
6. Care plan, Incidents, Invoices/GST, Reports (need new models).
