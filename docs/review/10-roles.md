# Roles / permissions
CRITICAL: public POST /auth/register-elder-portal (auth.py:55, elder_portal_service.py:64-90) — anyone with client phone + agency creates a family login → full family data; also enumerates phones. → disable in prod / invite code or OTP.
HIGH: login-as-family any client in agency (elder_portal_service.py:146-171, elders.py:238) — needs team check.
HIGH: set_order_status lets manager move pending_approval → scheduled/completed (commerce.py:400-415). (+ coupon approval bypass commerce.py:356)
MED: caregiver_service get_caregiver no team check (caregivers.py:23/41/51); create_caregiver no manager_user_id; /caregivers POST allows managers while /team/caregivers admin-only.
MED: family-login / caregiver-portal-account creation any client in agency (elders.py:249, caregiver_portal.py:164).
MED: documents_service list/get/pending/verify no team check.
MED: incidents detail/ack/escalate/resolve/note no team check; summary badge agency-wide (incidents.py:104,134,143-212).
LOW: users list exposes all users incl. family emails to managers/viewers; invite allows ELDER_PORTAL without elder; reset family pw UI admin-only but backend allows manager; "Assessor" label for caregiver (lib/auth.ts:64).
UX P1: Users page status column, edit/deactivate/reactivate/change role (endpoints exist users.py:31-56); Viewers hidden; staff/caregiver password reset + forgot password; family logins via window.prompt plain text; can't deactivate family login.
P2: manager leaving → "reassign team to…"; manager team view; bulk assign clients.
P3: lowercase emails; last-admin guard.
