/**
 * Copy for the public site, in one place.
 *
 * Everything a non-engineer might want to change — headlines, steps, service
 * cards, testimonials, FAQ, the numbers in the trust strip — lives here as
 * plain data. Components render it; they do not carry copy of their own.
 *
 * Brand token: write `LiveWell360` where the product name appears and it is
 * rewritten to the configured brand at render time (see lib/public-brand.ts).
 * No city names: the service is described by what it does, not where.
 */

import { withPublicBrand } from "@/lib/public-brand";
import { PLAN_COST_ANSWER, SINGLE_VISIT_LINE } from "./plans";

const b = withPublicBrand;

export const HERO = {
  eyebrow: "Elder care across India",
  title: "Elder care at home for your parents,",
  accent: " anywhere in India.",
  lede: b(
    "KushAlaya provides elder care at home across India: a home safety assessment to prevent falls, then regular care-manager visits with a KushLife check — safe, steady, settled, connected. Families in India or abroad follow every visit in the family app.",
  ),
  primary: "Start KushCare Discovery",
  secondary: "WhatsApp us",
  micro: "We call you back within 2 hours · One accountable team · BLS & CPR-trained caregivers",
} as const;

/**
 * The trust strip states facts about the service, never invented traction.
 * Live counts from the API are shown only once they pass `LIVE_STAT_MINIMUM`
 * (see useLiveStats) — a public "0 families" helps nobody.
 */
export const PROMISES = [
  { value: "100", label: b("Point LiveWell360 Safety Score for every home"), icon: "clipboard" },
  { value: "4", label: "KushLife checks on every visit", icon: "heart" },
  { value: "8–70", label: "Care-manager visits a year", icon: "users" },
  { value: "1 tap", label: "SOS watch alerts the care manager", icon: "bell" },
] as const;

export const LIVE_STAT_MINIMUM = 25;

export const WHY = {
  eyebrow: "Why families call us",
  title: "Most elders want to stay home. Families need a partner who listens.",
  paras: [
    "Slippery bathrooms, dim corridors, steep stairs, medicines, hospital visits and repairs can turn urgent overnight — especially when you live far away.",
    "Home safety, trusted professionals and family updates in one calm, accountable service — always putting the person at home first.",
  ],
  image: "/marketing/why-families.webp",
  imageAlt: "An elderly man steadying himself on a wall in a dim hallway of his flat in the evening",
} as const;

export const STEPS = [
  {
    n: "01",
    title: "Assess",
    short: "A scored home visit",
    body: b("A respectful home visit — bathrooms, bedrooms, stairs, lighting, daily risks — with your parent at the centre. You get a LiveWell360 Safety Score out of 100."),
    image: "/marketing/how-01-assess.webp",
    alt: "A care manager checking the height of a bathroom grab bar while an elderly man watches from the doorway",
  },
  {
    n: "02",
    title: "Recommend",
    short: "A plan you decide together",
    body: "A clear report with priorities and options to decide together — products and plans only where they fit.",
    image: "/marketing/how-02-recommend.webp",
    alt: "A care manager going through a printed report with an elderly woman and her son at the dining table",
  },
  {
    n: "03",
    title: "Improve",
    short: "Verified installers, photos after",
    body: "Verified partners make the approved changes, with photos and completion notes — no black box.",
    image: "/marketing/how-03-improve.webp",
    alt: "An installer fitting a stainless steel grab bar in a bathroom while an elderly woman watches with a cup of tea",
  },
  {
    n: "04",
    title: "Support",
    short: "KushLife on every visit",
    body: "Regular KushLife visits, physiotherapy, medicines, hospital coordination and steady family updates.",
    image: "/marketing/how-04-support.webp",
    alt: "A care manager taking the blood pressure of a smiling elderly man in his armchair",
  },
] as const;

export const KUSHLIFE_SAMPLE = {
  eyebrow: "In the family portal",
  title: "Lakshmi's KushLife trend",
  points: [46, 48, 50, 49, 53, 54, 57, 58],
  note: "50 is her personal normal. Higher means better than usual.",
  checks: [
    { title: "Safe", ok: true, note: "Grab bars checked · night light working" },
    { title: "Steady", ok: true, note: "Walked to the park, no unsteadiness" },
    { title: "Settled", ok: true, note: "Sleeping well · meals regular" },
    { title: "Connected", ok: true, note: "“Tell my son the physio helps.”" },
  ],
} as const;

export const SERVICES = [
  {
    id: "assessment",
    title: "Home safety assessment",
    body: "We assess the home and the elder together and show you what to fix first, plus an AI room check from your photos — reviewed by your care manager — with a preview of the room made safer.",
    icon: "home",
    link: { label: "See it before we fit it", href: "/safe-homes#ai" },
  },
  {
    id: "bath-bed",
    title: "Bathroom & bedroom safety",
    body: "Grab bars, anti-slip surfaces, night lighting and transfer support where mornings and nights feel most vulnerable.",
    icon: "bath",
  },
  {
    id: "physio",
    title: "Physiotherapy at home",
    body: "Strength, balance and confidence — a home exercise plan and supervised sessions that keep someone on their feet.",
    icon: "walk",
  },
  {
    id: "medicines",
    title: "Medicines & wellness",
    body: "Reminders, monthly checks or fully managed medicines, with blood pressure, weight, sleep and appetite tracked on visits.",
    icon: "pill",
  },
  {
    id: "sos",
    title: "SOS & emergency readiness",
    body: "An SOS watch alerts the care manager first, who checks and then tells the family. Immobility warnings and emergency contacts on file.",
    icon: "bell",
  },
  {
    id: "caregivers",
    title: "Trained caregivers at home",
    body: "Caregivers we train ourselves — all BLS and CPR trained — guided by a care manager.",
    icon: "users",
  },
] as const;

export const ABROAD = {
  eyebrow: "For families abroad",
  title: "Your trusted local eyes, hands and updates",
  body: "You can’t attend every appointment or check every repair. We’re your dependable team on the ground — and we keep you informed.",
  points: [
    "Clear updates after every visit",
    "Photos and completion reports",
    "Care-manager visits on every plan",
    "Video calls planned around your time zone",
    "Visibility into wellbeing without intrusion",
  ],
  image: "/marketing/abroad.webp",
  imageAlt: "A daughter abroad reading a care update with photos of her mother on her laptop",
} as const;

/**
 * These quotes are illustrative, written to show the kind of feedback we
 * expect — they are NOT from real customers. While this is true the site
 * labels them as samples. Replace them with real, consented quotes and set
 * this to false; publishing invented reviews as genuine is not allowed.
 */
/**
 * Sample report (what a family receives after the assessment). Illustrative
 * only: no real client. Shown in place of testimonials until real reviews.
 */
export const SAMPLE_REPORT = {
  client: "Sample home · 2BHK, ground floor",
  score: 64,
  scoreLabel: "Needs attention",
  rooms: [
    { room: "Bathroom", score: 48, note: "Wet floor, no grab bar by the toilet" },
    { room: "Bedroom", score: 62, note: "No light between bed and bathroom" },
    { room: "Stairs & entry", score: 70, note: "One loose step edge" },
    { room: "Kitchen", score: 78, note: "Daily items stored too high" },
  ],
  fixes: [
    "Anti-slip bathroom flooring",
    "Grab bars at toilet and shower",
    "Motion-sensor night lights",
    "Step-edge strips on entry stairs",
  ],
  after: 86,
} as const;

export const TESTIMONIALS_ARE_SAMPLES = true;

export const TESTIMONIALS = [
  {
    initials: "RK",
    text: "I’m in Dubai, and I still know how Amma’s day went before I sit down for dinner.",
    who: "Ravi K.",
    role: "Son · Dubai",
  },
  {
    initials: "SP",
    text: b("Thank you, LiveWell360 team. Appa’s grab bars and night lights were in within a week of the assessment."),
    who: "Suresh P.",
    role: "Son · Singapore",
  },
  {
    initials: "MS",
    text: "The visit report with photos is the first thing I open every Thursday morning.",
    who: "Meena S.",
    role: "Daughter · Bengaluru",
  },
  {
    initials: "LN",
    text: "Our care manager treats Atha like her own mother. We feel we are right there with her.",
    who: "Lakshmi N.",
    role: "Daughter-in-law · Chennai",
  },
  {
    initials: "AK",
    text: "One tap on SOS and Meera called us back within minutes. That is real peace of mind.",
    who: "Arun & Kavya",
    role: "Grandchildren",
  },
  {
    initials: "PR",
    text: b("Every WhatsApp digest ends my day with a smile. Grateful to the whole LiveWell360 team."),
    who: "Priyanka R.",
    role: "Daughter · London",
  },
] as const;

export const FAQS = [
  {
    q: "How does the AI room check work? Is the preview exactly what you will install?",
    a: "Send a photo of a room. Our AI spots common risks — a missing grab bar, a slippery floor, a loose rug — and shows the room with the right products fitted. Your care manager checks every finding; the preview is an illustration, confirmed at the visit. Photos are used only for your plan, never shared or sold.",
  },
  {
    q: b("What is a LiveWell360 assessment?"),
    a: b("A professional home visit covering bathroom, bedroom, stairs, lighting, mobility and daily safety. You receive a report with a LiveWell360 Safety Score out of 100 and prioritised recommendations with clear next steps. The assessment is free."),
  },
  {
    q: "What is KushLife?",
    a: "Our promise for every visit after the assessment: four short checks — Safe, Steady, Settled, Connected — recorded in the family portal with photos and a note, so you see the trend and not just the incident.",
  },
  {
    q: "Will you rush or override my parents’ wishes?",
    a: b("No. We started LiveWell360 with the utmost respect for elders. We explain options in plain language, protect dignity, and never treat ageing as a project to complete against someone’s will."),
  },
  {
    q: "Can families abroad use the service?",
    a: "Yes. Families in another city or country get the same portal, photos and reports, care-manager visits, and video calls planned around their time zone.",
  },
  {
    q: "Do you offer wearable SOS and fall alerts?",
    a: "Yes. The Privilege and Signature plans include a complimentary SOS watch with family alerts in the family portal. Possible-fall sensing is experimental and not medical-grade.",
  },
  {
    q: "How much do plans cost?",
    a: `${PLAN_COST_ANSWER} Paying monthly costs a little more than paying yearly. ${SINGLE_VISIT_LINE}.`,
  },
  {
    q: "How do I book?",
    a: "Tap Book an assessment and tell us about your parent in a short, free KushCare Discovery form, or message the founder directly. We confirm a visit window that respects your household’s routine.",
  },
] as const;

export const PARTNER_TEASER = {
  eyebrow: "Trusted Partner Network",
  title: "Verified partners behind every improvement",
  body: b("Suppliers and installers join for assessment-led work and LiveWell360 co-branded trust — not cold leads or paid listings."),
  image: "/marketing/partners.webp",
  imageAlt: "A physiotherapist, an installer and a care manager talking with an elderly couple in a living room",
} as const;

export const FINAL_CTA = {
  title: "Ready for a calmer next step?",
  body: "Tell us about your parents in a short form, or call the founder directly. We show up with respect — for your parents’ dignity and your family’s trust.",
} as const;
