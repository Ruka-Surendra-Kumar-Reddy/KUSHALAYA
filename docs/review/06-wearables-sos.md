# Wearables / SOS
Backend solid (dedupe, escalation, immediate family+staff alerts iot_ingest_service.py:168-186). UI weak.
P1: global sticky red SOS banner on every ops page + looping chime + browser Notification, poll 10s (AppShell.tsx:37 badge only, 60s); status "Acknowledged by Priya · 3 min ago" / "Unacknowledged — escalates in 2 min" (acknowledged_by never rendered); client phone tel:, address, Call family on alert row; notify family on acknowledge ("care team has seen the alert. Priya is handling it") (incident_service.py:593-613 sends nothing); family plain statuses; family "Mark resolved" → "We're OK — cancel SOS" + confirm.
P2: hide MAC/hub/mqtt behind expander, "From wearable band"; Level → "Escalation: Manager/Ops/Whole team"; band list battery %, last seen, online pill, sort problems first; "Band ID (printed on the back)"; "Send test alert" per band; confirm Escalate now.
P3: stale comment family alerts page:52; resolve note prompt; "Replace band" per row; relative times.
