#!/usr/bin/env python3
"""Generate docs/kushalaya/MANUAL_TEST_CASES.html for manual QA."""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "livewell" / "MANUAL_TEST_CASES.html"


def tc(
    tid: str,
    title: str,
    role: str,
    priority: str,
    pre: str,
    steps: list[str],
    expected: list[str],
    notes: str = "",
) -> str:
    steps_li = "".join(f"<li>{s}</li>" for s in steps)
    exp_li = "".join(f"<li>{e}</li>" for e in expected)
    note_html = f'<p class="tc-note"><strong>Note:</strong> {notes}</p>' if notes else ""
    return f"""
<article class="tc" id="{tid.lower()}">
  <div class="tc-head">
    <span class="tc-id">{tid}</span>
    <span class="pill pri-{priority.lower()}">{priority}</span>
    <span class="pill role">{role}</span>
    <label class="pass"><input type="checkbox" /> Pass</label>
    <label class="pass fail-lbl"><input type="checkbox" /> Fail</label>
  </div>
  <h3>{title}</h3>
  <p class="pre"><strong>Preconditions:</strong> {pre}</p>
  <div class="cols">
    <div><strong>Steps</strong><ol>{steps_li}</ol></div>
    <div><strong>Expected results</strong><ul class="exp">{exp_li}</ul></div>
  </div>
  {note_html}
</article>"""


# (id, title, role, priority, pre, steps, expected, notes?)
CASES: list[tuple] = []

def add(area: str, *rows):
    for i, row in enumerate(rows, 1):
        tid = f"TC-{area}-{i:03d}"
        CASES.append((tid, *row))


# --- AUTH ---
add(
    "AUTH",
    (
        "Staff login — care manager",
        "CARE_MANAGER",
        "P0",
        "Demo seed or valid staff account on ops host.",
        [
            "Open /login on livewellops host.",
            "Enter manager@sunrise-care.example / demo1234 (or env credentials).",
            "Submit.",
        ],
        [
            "Login succeeds; redirected to /dashboard.",
            "Sidebar shows Care delivery items.",
            "No console errors blocking render.",
        ],
    ),
    (
        "Staff login — invalid password",
        "Any",
        "P1",
        "Known staff email.",
        [
            "Open /login.",
            "Enter valid email + wrong password.",
            "Submit.",
        ],
        [
            "Login rejected with clear error.",
            "User remains on login page; no token issued.",
        ],
    ),
    (
        "Family login",
        "ELDER_PORTAL",
        "P0",
        "Family user seeded (e.g. lakshmi.family@sunrise-care.example / demo1234).",
        [
            "Open /kushalaya/family/login.",
            "Sign in with family credentials.",
        ],
        [
            "Lands on family dashboard (/kushalaya/family/dashboard).",
            "Bottom nav: Home, Schedule, Updates, Chat, More.",
        ],
    ),
    (
        "Assessor login",
        "CAREGIVER",
        "P0",
        "Assessor seeded (anita.caregiver@sunrise-care.example / demo1234).",
        [
            "Sign in via /login or assessor entry.",
            "Navigate to /livewell.",
        ],
        [
            "Assessor shell loads assessment list.",
            "No ops admin sidebar (HomeSafetyShell).",
        ],
    ),
    (
        "Family blocked from staff APIs",
        "ELDER_PORTAL",
        "P0",
        "Logged in as family; browser devtools available.",
        [
            "While on family app, attempt direct URL /kushalaya/customers or /dashboard.",
        ],
        [
            "Redirect to unauthorized or login; no client PII from staff APIs.",
        ],
        "Automated: backend/tests/test_portal_access.py",
    ),
    (
        "Logout — staff",
        "CARE_MANAGER",
        "P1",
        "Logged in as staff.",
        ["Use Sign out from shell.", "Try /dashboard without re-login."],
        ["Session cleared; redirected to login."],
    ),
    (
        "Logout — family",
        "ELDER_PORTAL",
        "P1",
        "Logged in as family.",
        ["Sign out from family shell.", "Navigate to /kushalaya/family/dashboard."],
        ["Requires login again."],
    ),
)

# --- NAV / RBAC ---
add(
    "NAV",
    (
        "VIEWER sidebar scope",
        "VIEWER",
        "P1",
        "Account with VIEWER role only.",
        [
            "Log in as VIEWER.",
            "Inspect sidebar groups.",
        ],
        [
            "Sees Overview + Care delivery only.",
            "No Catalog, Platform, or Partner network.",
        ],
    ),
    (
        "CARE_MANAGER sidebar scope",
        "CARE_MANAGER",
        "P1",
        "Care manager account.",
        [
            "Log in as CARE_MANAGER.",
            "Inspect sidebar.",
        ],
        [
            "Sees Care delivery, Partner network, People, Admin (Team/Settings).",
            "Does NOT see Catalog & quotes or Platform tools (Wearables, Master data, AI).",
        ],
    ),
    (
        "TENANT_ADMIN full LiveWell nav",
        "TENANT_ADMIN",
        "P1",
        "Tenant admin account.",
        [
            "Log in as TENANT_ADMIN.",
            "Verify Catalog, Platform, Users visible.",
        ],
        [
            "All LiveWell admin routes present except Tenants (system admin only).",
        ],
    ),
    (
        "Session activity nav vs page access",
        "VIEWER / CARE_MANAGER",
        "P2",
        "VIEWER and CARE_MANAGER accounts.",
        [
            "As VIEWER: open /kushalaya/activity if linked in nav.",
            "As CARE_MANAGER: open /kushalaya/activity.",
        ],
        [
            "CARE_MANAGER can view session list and expand sessions.",
            "VIEWER either blocked or sees limited data per page guard.",
        ],
        "Known: nav may show Activity to all; API requires WRITE_ROLES.",
    ),
)

# --- CLIENTS ---
add(
    "CLI",
    (
        "Clients list loads",
        "CARE_MANAGER+",
        "P0",
        "Staff logged in.",
        ["Open /kushalaya/customers."],
        ["Client/lead list renders; no infinite loading."],
    ),
    (
        "Create new lead",
        "CARE_MANAGER+",
        "P1",
        "Staff on Clients page.",
        [
            "Create new lead/prospect with name + contact.",
            "Save.",
        ],
        [
            "Lead appears in list.",
            "Can open detail.",
        ],
    ),
    (
        "Convert lead to client",
        "CARE_MANAGER+",
        "P0",
        "Open lead exists.",
        [
            "Open lead → Convert to client.",
            "Complete required fields.",
        ],
        [
            "Client record created; lead absorbed.",
            "Client usable for assessment link and visits.",
        ],
    ),
    (
        "Start assessment from client",
        "CARE_MANAGER+",
        "P0",
        "Client exists.",
        [
            "From client row/detail, start or open assessment.",
        ],
        [
            "Navigates to assessor flow with client linked.",
        ],
    ),
    (
        "Republish assessment to family",
        "CARE_MANAGER+",
        "P0",
        "Client has completed assessment; family user linked.",
        [
            "Open client → Republish to family (or equivalent action).",
            "Log in as linked family user.",
            "Open family dashboard.",
        ],
        [
            "Family Home shows Independence Score™ and plan data.",
            "Living plan priorities visible under More → Living plan.",
        ],
    ),
    (
        "Permanent delete client (admin only)",
        "TENANT_ADMIN",
        "P2",
        "Test client with no production data.",
        [
            "As admin, use danger-zone permanent delete on test client.",
        ],
        [
            "Client removed; confirm dialog required.",
            "Non-admin cannot see or use permanent delete.",
        ],
    ),
)

# --- ASSESSMENTS ---
add(
    "ASM",
    (
        "Create new assessment",
        "CAREGIVER",
        "P0",
        "Assessor logged in at /livewell.",
        [
            "Tap + New assessment.",
            "Enter resident first name on profile step.",
        ],
        [
            "Wizard opens at profile step.",
            "Progress indicator visible.",
        ],
    ),
    (
        "Conditional logic hides items",
        "CAREGIVER",
        "P1",
        "New assessment.",
        [
            "On profile, select options that hide sections (e.g. no stairs).",
            "Navigate scored sections.",
        ],
        [
            "Irrelevant sections/items hidden per profile.",
            "Profile shows count of hidden questions.",
        ],
    ),
    (
        "Rate checklist items",
        "CAREGIVER",
        "P0",
        "Assessment in progress.",
        [
            "Rate items Excellent / Acceptable / Unsafe / N/A across sections.",
            "Use dot nav to jump sections.",
        ],
        [
            "Ratings persist when navigating away.",
            "Completion % updates.",
        ],
    ),
    (
        "Save blocked until 100% applicable",
        "CAREGIVER",
        "P1",
        "Assessment with unrated applicable items.",
        [
            "Go to Review & save without completing all applicable items.",
            "Attempt Save.",
        ],
        [
            "Save blocked with clear message.",
            "After completing all applicable items, Save enabled.",
        ],
    ),
    (
        "Complete assessment — score and plan",
        "CAREGIVER",
        "P0",
        "100% applicable items rated; assessor signed in.",
        [
            "Complete review step; Save/finalize.",
            "Note SafeHome Score™ and improvement plan.",
        ],
        [
            "Score 0–100 and grade shown.",
            "Improvement plan lists solutions for Unsafe/Acceptable items.",
            "Customer quote section populated when catalog linked.",
        ],
    ),
    (
        "Upload assessment photo",
        "CAREGIVER",
        "P1",
        "Assessment with photo step.",
        [
            "Upload before photo for a room/finding.",
        ],
        [
            "Photo appears in assessment.",
            "After publish, family can see under Photos & visuals.",
        ],
    ),
    (
        "Draft auto-save (localStorage)",
        "CAREGIVER",
        "P2",
        "Assessment in progress.",
        [
            "Rate several items.",
            "Refresh browser (same device).",
        ],
        [
            "Draft restored from local storage.",
        ],
    ),
    (
        "Signed document upload",
        "CAREGIVER / CARE_MANAGER",
        "P2",
        "Assessment linked to client.",
        [
            "Upload signed customer document from assessment flow.",
            "Check family Documents page.",
        ],
        [
            "Document listed for family under More → Documents.",
        ],
    ),
)

# --- VISITS ---
add(
    "VIS",
    (
        "Visits page loads",
        "CARE_MANAGER+",
        "P0",
        "Enrolled client exists.",
        ["Open /kushalaya/visits.", "Select client."],
        ["Visit form and history visible."],
    ),
    (
        "Baseline visit — score 50",
        "CARE_MANAGER+",
        "P0",
        "Client with no prior completed visit.",
        [
            "Create visit; complete baseline protocol fields.",
            "Set visit type Baseline profile.",
            "Add optional family message.",
            "Save visit.",
        ],
        [
            "Stability score = 50.",
            "Baseline stored; family dashboard shows care status message.",
        ],
    ),
    (
        "Check-in visit — stability delta",
        "CARE_MANAGER+",
        "P0",
        "Client with baseline completed.",
        [
            "Log check-in visit with mood/mobility/eating vs normal.",
            "Save.",
        ],
        [
            "Score changes from 50 based on answers.",
            "Mom-is-OK status GREEN/YELLOW/RED shown appropriately.",
            "Family trend chart updates.",
        ],
    ),
    (
        "Living plan item status",
        "CARE_MANAGER+",
        "P1",
        "Client with published plan.",
        [
            "On Visits, set plan item to Scheduled / Done.",
            "Check family Living plan.",
        ],
        [
            "Status reflected on family plan.",
            "Done items drop from Home top priorities.",
        ],
    ),
    (
        "Family service request — confirm",
        "CARE_MANAGER+",
        "P0",
        "Family user logged in.",
        [
            "Family: Schedule → Request a service.",
            "Staff: Visits → confirm request (optionally create visit).",
            "Family: check Updates / Schedule.",
        ],
        [
            "Request moves from pending to confirmed.",
            "Family sees confirmation in timeline.",
        ],
    ),
    (
        "Family service request — decline",
        "CARE_MANAGER+",
        "P2",
        "Pending family request exists.",
        [
            "Staff declines request with reason if prompted.",
        ],
        [
            "Family sees declined status; no visit created.",
        ],
    ),
)

# --- ACTIVITY ---
add(
    "ACT",
    (
        "Session activity list",
        "CARE_MANAGER+",
        "P1",
        "Staff has performed actions while logged in.",
        [
            "Open /kushalaya/activity.",
            "Filter by actor type (Staff / Family / Assessor).",
        ],
        [
            "Sessions listed with email, time, event count.",
            "Accordion expands to show actions and API calls.",
        ],
    ),
    (
        "System session — IoT event",
        "TENANT_ADMIN",
        "P2",
        "IoT SOS lab test or mosquitto_pub performed.",
        [
            "Filter Actor → System.",
            "Expand System session after SOS ingest.",
        ],
        [
            "IoT Sos Button (or similar) event present.",
            "Details (JSON) shows meta when verbose mode on.",
        ],
        "Requires ACTIVITY_LOG_MODE=verbose for full raw_payload.",
    ),
    (
        "Wearables staff action logged",
        "TENANT_ADMIN",
        "P2",
        "Logged in with session header active.",
        [
            "Register kit on /kushalaya/iot-devices.",
            "Open Session activity → own staff session.",
        ],
        [
            "User action: Registered IoT kit (or similar) recorded.",
        ],
    ),
)

# --- CATALOG / MASTER DATA ---
add(
    "CAT",
    (
        "Product catalog list",
        "TENANT_ADMIN",
        "P1",
        "Tenant admin logged in.",
        ["Open /kushalaya/catalog."],
        ["SKU list loads; can open product detail."],
    ),
    (
        "Edit catalog SKU",
        "TENANT_ADMIN",
        "P2",
        "Catalog has products.",
        [
            "Edit product name/price/link to solution.",
            "Save.",
        ],
        [
            "Changes persist after refresh.",
            "Assessor quote reflects updated SKU if linked.",
        ],
    ),
    (
        "Solution library edit",
        "TENANT_ADMIN",
        "P2",
        "Solutions exist.",
        [
            "Open /kushalaya/solutions.",
            "Edit one solution rubricItemIds link.",
        ],
        [
            "Save succeeds; matching plan uses solution on next assessment.",
        ],
    ),
    (
        "Pricing config",
        "TENANT_ADMIN",
        "P2",
        "Pricing page accessible.",
        [
            "Adjust margin or GST setting.",
            "Save.",
            "Run assessment quote on review step.",
        ],
        [
            "Grand total changes per pricing rules.",
        ],
    ),
    (
        "Rubric checklist editor",
        "TENANT_ADMIN",
        "P2",
        "Rubric page accessible.",
        [
            "Open /kushalaya/rubric.",
            "View section weights.",
        ],
        [
            "Checklist items load; edits save if permitted.",
        ],
    ),
)

add(
    "MD",
    (
        "Master data export",
        "TENANT_ADMIN",
        "P1",
        "Master data page accessible.",
        [
            "Open /kushalaya/master-data.",
            "Export/download workbook.",
        ],
        [
            "Excel file downloads with expected sheets.",
        ],
    ),
    (
        "Master data import — stage and approve",
        "TENANT_ADMIN",
        "P1",
        "Valid configuration xlsx available.",
        [
            "Upload workbook → Stage.",
            "Review staged diff.",
            "Approve.",
        ],
        [
            "Tenant config updated.",
            "Catalog/rubric/solutions reflect approved version.",
        ],
    ),
    (
        "Master data rollback",
        "TENANT_ADMIN",
        "P2",
        "Multiple approved versions exist.",
        [
            "Rollback to prior approved version.",
        ],
        [
            "Previous config restored.",
        ],
    ),
)

# --- PARTNERS ---
add(
    "PAR",
    (
        "Partners list",
        "CARE_MANAGER+",
        "P2",
        "Partner network nav visible.",
        ["Open /kushalaya/partners."],
        ["Partner orgs listed with roles/tiers."],
    ),
    (
        "Vendors / supplier offers",
        "CARE_MANAGER+",
        "P2",
        "Suppliers page accessible.",
        [
            "Open /kushalaya/suppliers.",
            "View SKU vendor offer.",
        ],
        [
            "Vendor costs and MOQ display.",
        ],
    ),
    (
        "Pick installer on visit",
        "CARE_MANAGER+",
        "P2",
        "Partners include installer role.",
        [
            "On visit or service request, select installer partner.",
        ],
        [
            "Selection saved on visit/request record.",
        ],
    ),
)

# --- AI ---
add(
    "AI",
    (
        "AI jobs list",
        "TENANT_ADMIN",
        "P2",
        "AI jobs page accessible.",
        ["Open /kushalaya/ai-jobs."],
        ["Job board loads; statuses visible."],
    ),
    (
        "Create visualization job from assessment",
        "CAREGIVER",
        "P2",
        "Assessment with photo; AI enabled.",
        [
            "From assessment, request AI visualization for a photo.",
            "Open AI jobs as admin.",
        ],
        [
            "Job appears in queue.",
            "Progresses through phases or stub completes.",
        ],
    ),
    (
        "Approve AI concept for family",
        "CAREGIVER / TENANT_ADMIN",
        "P1",
        "Completed AI job with output.",
        [
            "Approve visualization for family.",
            "Family: More → Photos & visuals.",
        ],
        [
            "Approved before/after visible to family.",
            "Unapproved concepts NOT visible to family.",
        ],
    ),
)

# --- IOT ---
add(
    "IOT",
    (
        "Wearables page — admin only",
        "TENANT_ADMIN",
        "P1",
        "Tenant admin logged in.",
        ["Open /kushalaya/iot-devices."],
        ["Register kit form and hub/device lists visible."],
        "CARE_MANAGER does not see this in nav.",
    ),
    (
        "Register MG7 + B7 kit",
        "TENANT_ADMIN",
        "P0",
        "Client (elder) exists; MAC addresses known.",
        [
            "Select elder.",
            "Enter band MAC.",
            "Register MG7 + B7 kit.",
        ],
        [
            "Hub + device rows created.",
            "MQTT credentials and topic shown (copy for MinewLink).",
        ],
    ),
    (
        "Update MAC for elder",
        "TENANT_ADMIN",
        "P1",
        "Existing device for elder.",
        [
            "Use Update MAC for client.",
            "Enter new MAC.",
            "Save.",
        ],
        [
            "Device map updates within ~30s (ingestor poll).",
            "Old MAC no longer resolves to elder.",
        ],
    ),
    (
        "Lab SOS — mosquitto_pub",
        "Ops + TENANT_ADMIN",
        "P0",
        "MAC registered; ingestor + API running.",
        [
            "SSH to server; run mosquitto_pub with registered MAC and sos:true (see field setup doc).",
            "Check family Alerts for bound elder.",
        ],
        [
            "Critical wearable SOS alert within ~10s.",
            "Ingestor log: Ingested SOS_BUTTON.",
        ],
    ),
    (
        "SOS dedupe ~65 seconds",
        "Ops",
        "P1",
        "Lab or hardware SOS path working.",
        [
            "Trigger SOS twice within 65 seconds.",
        ],
        [
            "Only one incident/alert created.",
            "Ingestor may log Dedupe skip SOS.",
        ],
    ),
    (
        "Hardware SOS end-to-end",
        "Ops",
        "P0",
        "MG7 configured with kit MQTT settings; band in range.",
        [
            "Press band SOS button.",
            "Watch family Alerts and Session activity (System).",
        ],
        [
            "Family critical alert.",
            "System session shows IoT event with MAC/elder in summary.",
        ],
    ),
    (
        "IoT ingest ignored event type",
        "Ops",
        "P2",
        "MAC registered.",
        [
            "Publish non-SOS event type via API or MQTT if supported.",
        ],
        [
            "No family SOS alert.",
            "Session activity may show IoT event ignored when MAC resolves.",
        ],
    ),
)

# --- FAMILY ---
add(
    "FAM",
    (
        "Family dashboard — published client",
        "ELDER_PORTAL",
        "P0",
        "Assessment published to linked elder.",
        [
            "Log in as family.",
            "View Home dashboard.",
        ],
        [
            "Independence Score™ displayed.",
            "Care status / stability visible after baseline visit.",
            "No perpetual Loading state.",
        ],
    ),
    (
        "Multi-elder Viewing switcher",
        "ELDER_PORTAL",
        "P1",
        "User linked to 2+ elders (e.g. arjun.family@).",
        [
            "Log in as multi-elder family user.",
            "Use Viewing dropdown to switch elder.",
        ],
        [
            "Score, plan, visits reload for selected elder.",
            "Context clearly shows active senior name.",
        ],
    ),
    (
        "Family SOS button",
        "ELDER_PORTAL",
        "P0",
        "Family logged in.",
        [
            "More → Alerts & SOS → raise SOS.",
            "Staff check client alerts / visits.",
        ],
        [
            "Critical alert created.",
            "Appears in family Alerts list.",
        ],
    ),
    (
        "Mark alert read",
        "ELDER_PORTAL",
        "P2",
        "Unread alerts exist.",
        [
            "Open Alerts.",
            "Mark alert as read.",
        ],
        [
            "Unread badge on More decreases.",
        ],
    ),
    (
        "Family chat message",
        "ELDER_PORTAL",
        "P1",
        "Family logged in.",
        [
            "Chat tab → send message.",
            "Staff views message context (visits/updates).",
        ],
        [
            "Message appears in family Chat and Updates.",
            "Staff can reply (if workflow enabled).",
        ],
    ),
    (
        "Schedule — request service",
        "ELDER_PORTAL",
        "P1",
        "Family logged in.",
        [
            "Schedule → Request a service.",
            "Submit wellness or repair request.",
        ],
        [
            "Request shows as pending on family Schedule.",
            "Staff sees request on Visits for triage.",
        ],
    ),
    (
        "Cancel pending service request",
        "ELDER_PORTAL",
        "P2",
        "Pending request exists.",
        [
            "Family cancels pending request.",
        ],
        [
            "Request removed or marked cancelled.",
        ],
    ),
    (
        "Visit experience rating",
        "ELDER_PORTAL",
        "P2",
        "Completed visit exists.",
        [
            "Family → Visit history → open visit.",
            "Submit experience rating.",
        ],
        [
            "Rating saved; cannot rate incomplete visit.",
        ],
    ),
    (
        "Family circle invite",
        "ELDER_PORTAL",
        "P2",
        "Family logged in.",
        [
            "More → Family circle → Invite by email.",
        ],
        [
            "Invite succeeds or shows clear error if email invalid.",
            "Invitee gets access to same household elders when accepted.",
        ],
    ),
    (
        "Digest preferences",
        "ELDER_PORTAL",
        "P2",
        "Family logged in.",
        [
            "More → Update digests.",
            "Set channel, cadence, timezone.",
            "Open preview.",
        ],
        [
            "Preferences save.",
            "Preview renders shareable content.",
        ],
    ),
    (
        "Emergency contacts tap-to-call",
        "ELDER_PORTAL",
        "P2",
        "Elder has emergency contact on profile.",
        [
            "More → Emergency contacts.",
            "Tap phone link.",
        ],
        [
            "Contact name and phone displayed.",
            "tel: link works on mobile.",
        ],
    ),
    (
        "Share update (NRI)",
        "ELDER_PORTAL",
        "P2",
        "Published score on dashboard.",
        [
            "Home → Share update.",
            "Use copy or device share sheet.",
        ],
        [
            "Share text includes score/pathway summary.",
        ],
    ),
    (
        "Unpublished client — family empty state",
        "ELDER_PORTAL",
        "P2",
        "Family linked to elder without published assessment.",
        [
            "Log in as that family user.",
            "View Home.",
        ],
        [
            "Clear not-published or empty state (not broken UI).",
            "Republish from staff fixes display.",
        ],
    ),
)

# --- ADMIN / SETTINGS ---
add(
    "ADM",
    (
        "Users — invite staff",
        "TENANT_ADMIN",
        "P1",
        "Admin on /users.",
        [
            "Invite new user with CARE_MANAGER role.",
            "New user sets password and logs in.",
        ],
        [
            "User appears in team list.",
            "Login works with assigned role nav.",
        ],
    ),
    (
        "Settings — branding",
        "TENANT_ADMIN",
        "P2",
        "Settings accessible.",
        [
            "Change display branding field.",
            "Save.",
            "Refresh app.",
        ],
        [
            "Brand name reflects in shell where configured.",
        ],
    ),
    (
        "Workflows — list and enable",
        "TENANT_ADMIN",
        "P2",
        "Workflows page accessible.",
        [
            "Open /settings/workflows.",
            "Toggle workflow definition.",
        ],
        [
            "State persists.",
            "Tasks/events visible when triggered.",
        ],
    ),
    (
        "Documents verification",
        "CARE_MANAGER+",
        "P2",
        "Document uploaded.",
        [
            "Open /documents.",
            "Verify or reject document.",
        ],
        [
            "Status updates.",
        ],
    ),
    (
        "Assessor recruits pipeline",
        "CARE_MANAGER+",
        "P2",
        "Prospects page accessible.",
        [
            "Open /prospects.",
            "View assessor recruit entry.",
        ],
        [
            "Pipeline list loads.",
        ],
    ),
    (
        "Tenants — system admin",
        "SYSTEM_ADMIN",
        "P2",
        "System admin account.",
        [
            "Open /tenants.",
            "View tenant list.",
        ],
        [
            "Tenants visible; not available to tenant admin.",
        ],
    ),
)

# --- SECURITY / NEGATIVE ---
add(
    "SEC",
    (
        "Unauthenticated API returns 401",
        "Any",
        "P1",
        "No auth header.",
        [
            "curl or browser: GET /api/v1/elders without token.",
        ],
        [
            "401 or 403; no data returned.",
        ],
    ),
    (
        "Cross-tenant isolation",
        "TENANT_ADMIN",
        "P0",
        "Two tenants with data (if available).",
        [
            "Log in as tenant A admin.",
            "Attempt to access tenant B elder ID via API URL manipulation.",
        ],
        [
            "404 or 403; no leak of other tenant data.",
        ],
    ),
    (
        "IoT events without ingest key",
        "Any",
        "P1",
        "API running.",
        [
            "POST /api/v1/iot/events without X-IoT-Ingest-Key.",
        ],
        [
            "403 Forbidden.",
        ],
    ),
    (
        "Direct URL — unauthorized role",
        "VIEWER",
        "P1",
        "Viewer logged in.",
        [
            "Navigate directly to /kushalaya/catalog or /kushalaya/iot-devices.",
        ],
        [
            "Blocked, redirected, or empty — no edit capability.",
        ],
    ),
)

# --- SMOKE / REGRESSION ---
add(
    "SMOKE",
    (
        "Smoke — ops host health",
        "Any",
        "P0",
        "Production or staging URL.",
        [
            "GET /health on API.",
            "Load /login and /kushalaya/family/login.",
        ],
        [
            "API health OK.",
            "Both login pages render without chunk 400 errors.",
        ],
        "Rebuild frontend if _next/static chunks return 400.",
    ),
    (
        "Smoke — core care path",
        "CARE_MANAGER + ELDER_PORTAL",
        "P0",
        "Demo seed data.",
        [
            "Staff: open Clients, Visits, one catalog page (admin).",
            "Family: dashboard, Schedule, Alerts.",
            "Assessor: /livewell list.",
        ],
        [
            "All pages load within 10s.",
            "No uncaught JS errors on critical paths.",
        ],
    ),
    (
        "Smoke — API docs",
        "Any",
        "P2",
        "API exposed.",
        [
            "Open /docs on ops host.",
        ],
        [
            "OpenAPI UI loads; iot and home-safety routes listed.",
        ],
    ),
    (
        "Mobile PWA — family bottom nav",
        "ELDER_PORTAL",
        "P2",
        "Mobile viewport or device.",
        [
            "Open family app on phone width.",
            "Tap each bottom nav tab.",
        ],
        [
            "All five tabs navigate correctly.",
            "No horizontal overflow breaking layout.",
        ],
    ),
    (
        "Assessor mobile wizard",
        "CAREGIVER",
        "P2",
        "Mobile viewport.",
        [
            "Open assessment wizard on phone.",
            "Complete one section using Back/Next.",
        ],
        [
            "Wizard usable on small screen.",
            "Dot nav accessible.",
        ],
    ),
)

# Build HTML sections grouped by area prefix
from collections import defaultdict

by_area: dict[str, list[str]] = defaultdict(list)
area_titles = {
    "AUTH": "1. Authentication & sessions",
    "NAV": "2. Ops navigation & RBAC",
    "CLI": "3. Clients (Care delivery)",
    "ASM": "4. Assessments (Assessor PWA)",
    "VIS": "5. Visits & care stability",
    "ACT": "6. Session activity",
    "CAT": "7. Catalog, rubric, solutions, pricing",
    "MD": "8. Master data",
    "PAR": "9. Partners & vendors",
    "AI": "10. AI visualizations",
    "IOT": "11. Wearables / IoT (pilot)",
    "FAM": "12. Family portal",
    "ADM": "13. Admin, settings, documents",
    "SEC": "14. Security & negative tests",
    "SMOKE": "15. Smoke & regression",
}

for item in CASES:
    tid = item[0]
    area = tid.split("-")[1]
    by_area[area].append(
        tc(tid, item[1], item[2], item[3], item[4], item[5], item[6], item[7] if len(item) > 7 else "")
    )

sections_html = ""
for key in area_titles:
    if key not in by_area:
        continue
    sections_html += f'<section id="area-{key.lower()}"><h2>{area_titles[key]}</h2>\n'
    sections_html += "\n".join(by_area[key])
    sections_html += "</section>\n"

total = len(CASES)
p0 = sum(1 for c in CASES if c[3] == "P0")

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kushalaya — Manual Test Cases</title>
  <style>
    :root {{
      --ink: #1a2332;
      --muted: #5a6577;
      --line: #d8dee8;
      --bg: #f4f6fa;
      --card: #fff;
      --accent: #1e4d8c;
      --accent-soft: #e8f0fa;
      --pass: #0b6e4f;
      --fail: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.5; font-size: 14px; }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    header.hero {{
      background: linear-gradient(135deg, #1a3a6b, #2d6a9f);
      color: #fff; border-radius: 14px; padding: 1.75rem; margin-bottom: 1rem;
    }}
    header.hero h1 {{ margin: 0 0 0.35rem; font-size: 1.65rem; }}
    header.hero p {{ margin: 0.35rem 0; opacity: 0.92; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem; font-size: 0.85rem; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; align-items: center; }}
    .toolbar button {{ padding: 0.4rem 0.8rem; border-radius: 8px; border: 1px solid var(--line); background: var(--card); cursor: pointer; }}
    nav.toc {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem; margin-bottom: 1.5rem; }}
    nav.toc h2 {{ margin: 0 0 0.5rem; font-size: 1rem; }}
    nav.toc ul {{ columns: 2; margin: 0; padding-left: 1.2rem; }}
    @media (max-width: 640px) {{ nav.toc ul {{ columns: 1; }} }}
    section {{ margin-bottom: 2rem; }}
    section > h2 {{ color: var(--accent); border-bottom: 2px solid var(--accent-soft); padding-bottom: 0.35rem; margin-bottom: 1rem; }}
    .setup {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.15rem; margin-bottom: 1.5rem; }}
    .setup table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    .setup th, .setup td {{ border: 1px solid var(--line); padding: 0.35rem 0.5rem; text-align: left; }}
    .setup th {{ background: var(--accent-soft); }}
    code {{ background: #eef1f6; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.88em; }}
    article.tc {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 0.75rem; }}
    .tc-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }}
    .tc-id {{ font-family: monospace; font-weight: 700; color: var(--accent); }}
    .pill {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; padding: 0.12rem 0.4rem; border-radius: 999px; background: #eee; }}
    .pri-p0 {{ background: #fde8e8; color: #9b1c1c; }}
    .pri-p1 {{ background: #fff6e5; color: #8a5a00; }}
    .pri-p2 {{ background: #eef1f6; color: #555; }}
    .role {{ background: var(--accent-soft); color: var(--accent); }}
    .pass {{ font-size: 0.8rem; margin-left: auto; }}
    article.tc h3 {{ margin: 0 0 0.4rem; font-size: 1rem; }}
    .pre {{ font-size: 0.88rem; color: var(--muted); margin: 0 0 0.5rem; }}
    .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.88rem; }}
    @media (max-width: 700px) {{ .cols {{ grid-template-columns: 1fr; }} }}
    .cols ol, .cols ul {{ margin: 0.25rem 0; padding-left: 1.2rem; }}
    .exp li {{ margin: 0.2rem 0; }}
    .tc-note {{ font-size: 0.82rem; color: var(--muted); margin: 0.5rem 0 0; padding-top: 0.5rem; border-top: 1px dashed var(--line); }}
    .log {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem; margin-top: 2rem; }}
    .log table {{ width: 100%; border-collapse: collapse; }}
    .log th, .log td {{ border: 1px solid var(--line); padding: 0.4rem; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem; }}
    @media print {{
      .toolbar {{ display: none; }}
      body {{ background: #fff; }}
      article.tc {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <h1>Kushalaya — Manual Test Cases</h1>
    <p>Step-by-step QA checklist for ops, assessor, family, and IoT pilot flows.</p>
    <div class="stats">
      <span><strong>{total}</strong> test cases</span>
      <span><strong>{p0}</strong> P0 (must pass before release)</span>
      <span>Host: ops.kushalaya.com</span>
      <span>Version: 2026-08-28</span>
    </div>
  </header>

  <div class="toolbar">
    <button type="button" onclick="window.print()">Print / Save as PDF</button>
    <button type="button" onclick="document.querySelectorAll('.tc input[type=checkbox]').forEach(c=>c.checked=false)">Clear all checks</button>
  </div>

  <div class="setup" id="setup">
    <h2 style="margin-top:0;color:var(--accent)">Test environment &amp; accounts</h2>
    <p><strong>Before testing:</strong> API healthy (<code>/health</code>), frontend built (no 400 on <code>_next/static</code> chunks), demo seed optional.</p>
    <p>Seed demo data (from <code>backend/</code>): <code>python -m app.seed_safehome_demo</code> — password <code>demo1234</code> for all demo users.</p>
    <table>
      <thead><tr><th>Role</th><th>Email (demo)</th><th>Entry URL</th></tr></thead>
      <tbody>
        <tr><td>TENANT_ADMIN</td><td>admin@sunrise-care.example</td><td>/login → /dashboard</td></tr>
        <tr><td>CARE_MANAGER</td><td>manager@sunrise-care.example</td><td>/login → /dashboard</td></tr>
        <tr><td>CAREGIVER (assessor)</td><td>anita.caregiver@sunrise-care.example</td><td>/livewell</td></tr>
        <tr><td>ELDER_PORTAL (family)</td><td>lakshmi.family@sunrise-care.example</td><td>/kushalaya/family/login</td></tr>
        <tr><td>ELDER_PORTAL (multi-elder)</td><td>arjun.family@sunrise-care.example</td><td>/kushalaya/family/login</td></tr>
        <tr><td>ELDER_PORTAL</td><td>clairview.family@sunrise-care.example</td><td>/kushalaya/family/login</td></tr>
      </tbody>
    </table>
    <p style="margin-top:0.75rem"><strong>Priority:</strong> P0 = release blocker · P1 = important · P2 = nice to verify</p>
    <p><strong>How to execute:</strong> Check Pass or Fail on each case. Log defects with Test ID (e.g. TC-FAM-003). For IoT hardware tests see also <code>IOT_B7_MG7_FIELD_SETUP.md</code>.</p>
  </div>

  <nav class="toc">
    <h2>Contents</h2>
    <ul>
      {"".join(f'<li><a href="#area-{k.lower()}">{v}</a></li>' for k, v in area_titles.items() if k in by_area)}
      <li><a href="#execution-log">Execution log</a></li>
    </ul>
  </nav>

  {sections_html}

  <div class="log" id="execution-log">
    <h2 style="margin-top:0;color:var(--accent)">Test execution log</h2>
    <table>
      <thead>
        <tr><th>Date</th><th>Tester</th><th>Build / env</th><th>P0 passed</th><th>P0 failed</th><th>Notes</th></tr>
      </thead>
      <tbody>
        <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
        <tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
      </tbody>
    </table>
  </div>

  <footer>
    Kushalaya / SafeHomeOps · Manual Test Cases · Open in browser → Print → Save as PDF<br/>
    Related: ADMIN_FUNCTIONAL_OVERVIEW.html · IOT_B7_MG7_FIELD_SETUP.md
  </footer>
</div>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML, encoding="utf-8")
print(f"Wrote {OUT} ({total} test cases)")
