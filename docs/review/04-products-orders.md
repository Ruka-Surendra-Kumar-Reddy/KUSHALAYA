# Products / coupons / orders
BUG P1: approval bypass — commerce.py:356 `manual = ... and not coupon_code` → manager discount >10% skips approval when a coupon is entered; also only checks role==CARE_MANAGER (:358). Same in ClientOrders.tsx:162.
BUG P1: set_order_status (commerce.py:401-416) allows any transition (reopen cancelled). Add allowed transitions.
P1: "Send quote to family" + quoted/family_accepted status; family portal shows lines, GST, total.
P2: "Original price" → "Our cost (₹)", "Selling price" → "Price (before GST)", "₹X + GST" in picker/suggestions; "Our margin" internal-only; install scheduling: datetime-local + caregiver picker instead of window.prompt (ClientOrders.tsx:192-207 no error handling); Reject on approvals, Cancel/Reschedule scheduled orders; "+ New product" + edit drawer (name/category/description; backend supports).
P3: product cards <720px; coupon edit + subtitle "Staff enter the code in New order on a client's page"; coupons.tsx:35 dead ternary, toggle no error handling; ProductQuoteDraftPanel.tsx:424 "SafeHome quote" brand leak; "Not linked" not "—".
