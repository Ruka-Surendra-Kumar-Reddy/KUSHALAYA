# Dashboard
P1: show reassessments (backend returns `reassessments`, page type ignores it) + tile; Missed/overdue group (past 7 days scheduled/missed) with Reschedule; Today rows → Start visit/assessment not client page; drop "Unassigned"; alerts tagged by kind/severity, age "2 h 10 min", inline Acknowledge, link /kushalaya/alerts?id=, team filter before limit 50 (dashboard_attention.py:163).
P2: messages → /kushalaya/messages?elder=ID + last-message age, consistent unread count; approvals only for admins, "Order #42 · ₹1,200 off (15%) — Approve/Reject"; hazards "Create quote"; sort by urgency; show preferred_at.
P3: remove "Set tenant vertical" warning (page.tsx:155-160); real first name not email (page.tsx:89); Retry + 60s auto-refresh; friendly empty states; IST greeting.
Dup tile links (page.tsx:117,120); pill vs tile count mismatch (page.tsx:122).
