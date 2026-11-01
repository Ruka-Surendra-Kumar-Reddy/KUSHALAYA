# Maps and directions — who sees what, and when

Two different things:

- **Directions** — a route from *your own phone* to the client's home. One button,
  "Directions", opens a choice of Google Maps, Apple Maps or Waze. It uses the
  client's saved home pin when there is one, otherwise the address. (If a visit has
  its own location, such as a hospital, it goes there instead.)
- **Live position** — where a caregiver is *right now*, shared only while they are on
  the way to a visit.

## Caregiver

- **Directions**: any time, on every visit card for today and upcoming visits
  (not on finished ones). Only their own visits.
- **Live position**: their phone shares its location from the moment they tap
  **On my way** until they **Check in**. Nothing is shared before or after. If they
  turn location off, the visit still works; the family just doesn't see the map.

## Care managers and admins (ops)

- **Directions**: to any client they can already see (their team; admins see all).
  Shown on the client page next to the address, on each open visit on Schedule,
  in the roster's repeating-visit card, and on emergency alert cards next to
  "Call client". No new data: the address was already on these pages.
- **Live position**: for their team's visits that are **on the way**, Schedule shows
  "12 min away · Map"; Map opens the caregiver's current position. After check-in
  nothing live is shown.

## Family

- **On-the-way map**: for their own parent only, while the caregiver is on the way
  ("Ravi is on the way — about 12 min away"). It disappears at check-in.
- **No directions**: families are never shown directions to their own home.

## For developers

- One component: `components/Directions.tsx` (styles in `components/live-visit.css`).
  Destination rule: `directionsTarget()` in `lib/live-location.ts`.
- The home pin comes from `elder_home` on jobs (`care_jobs.serialize`) and on alerts
  (`incident_service._elder_contact`), and `home_location` on the client profile.
  These are staff and own-caregiver endpoints only; family endpoints do not include it.
- Live position: `lib/live-location.ts` (`startLiveSharing`, `fetchFamilyLiveVisit`),
  ops badge `components/ops/OpsLiveBadge.tsx`.
