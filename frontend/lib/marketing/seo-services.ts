/**
 * /services/<slug> pages. One entry per service; the page template is
 * components/marketing/SeoPages.tsx. Facts only: no statistics, no response
 * times, no local offices.
 */
import { SEO_EMERGENCY_LINE, SEO_PHONES, SEO_PRICE_LINE, type SeoSection } from "./seo-common";

export type SeoService = {
  slug: string;
  /** <title>, 60 chars max. */
  metaTitle: string;
  /** Meta description, 155 chars max. */
  metaDescription: string;
  /** schema.org serviceType. */
  serviceType: string;
  /** Short name for link lists. */
  label: string;
  eyebrow: string;
  title: string;
  accent: string;
  lede: string;
  image: string;
  imageAlt: string;
  sections: readonly SeoSection[];
  /** Related existing pages. */
  related: readonly { href: string; label: string }[];
};

export const SEO_SERVICES: readonly SeoService[] = [
  {
    slug: "home-safety-assessment",
    metaTitle: "Home Safety Assessment for Elderly Parents | KushAlaya",
    metaDescription:
      "A room-by-room home safety assessment for ageing parents anywhere in India, with a KushAlaya Safety Score and a clear, priced plan of fixes.",
    serviceType: "Home safety assessment for older adults",
    label: "Home safety assessment",
    eyebrow: "Home safety assessment",
    title: "Home safety assessment for elderly parents",
    accent: " — before a fall happens.",
    lede: "A home safety assessment for elderly parents looks at the home and the elder together: bathrooms, floors, stairs, lighting and wiring, and how your parent actually moves, bathes and climbs stairs. A KushAlaya care manager visits, talks with your parents and gives you a Safety Score out of 100 with a fix-first list.",
    image: "/marketing/how-01-assess.webp",
    imageAlt: "A KushAlaya visitor checking a room in an older couple's home",
    sections: [
      {
        title: "Why a home safety assessment matters",
        paras: [
          "Most homes were set up when the people living in them were younger. Over the years small things become real risks: a bathroom floor that stays wet, a step with no rail, a dark passage to the toilet at night, a rug that slides. Your parents may have stopped noticing them, and from far away you cannot see them at all.",
          "An assessment looks at the home with fresh eyes and turns a vague worry into a short, practical list. It is the first step of every KushAlaya plan, because we would rather fix the right things than sell the wrong ones.",
        ],
      },
      {
        title: "What we check",
        paras: ["The visit covers the places where falls and accidents usually happen, and how your parents actually move through the day."],
        bullets: [
          "Bathroom and toilet: floor grip, support near the toilet and shower, water on the floor",
          "Bedroom: bed height, the path to the toilet at night, light switches within reach",
          "Stairs, steps and thresholds: rails, edges, uneven levels",
          "Lighting: dark corners, night lights, glare",
          "Kitchen and daily routines: reaching, bending, gas and appliances",
          "Mobility, and how your parent feels about living at home",
        ],
      },
      {
        title: "Your KushAlaya Safety Score and report",
        paras: [
          "After the visit you get a report with a KushAlaya Safety Score out of 100 and prioritised recommendations: what is urgent, what can wait, and what each fix costs. You see the price before anything is booked, and you decide what to do.",
          "As fixes are done, the score is updated so you can see the home getting safer.",
        ],
      },
      {
        title: "AI room check and room preview",
        paras: [
          "You can also send a photo of a room. Our AI points out common risks such as a missing grab bar or a slippery floor, and a care manager reviews every finding before it reaches you. The AI room preview shows the room with recommended products fitted; it is an illustration, and the final products and positions are confirmed at the visit.",
        ],
      },
      {
        title: "How to book",
        paras: [
          "Start with a free KushCare Discovery: a short form about your parent and their home. We call you back, understand what you need, and arrange the assessment visit in your parent's city.",
          SEO_PRICE_LINE,
        ],
      },
    ],
    related: [
      { href: "/kushcare-discovery", label: "Start KushCare Discovery" },
      { href: "/safe-homes", label: "Safe homes: products and fixes" },
      { href: "/safe-homes#ai", label: "AI room check" },
      { href: "/packages", label: "Plans and prices" },
    ],
  },
  {
    slug: "elder-care-visits",
    metaTitle: "Elder Care Visits at Home with KushLife | KushAlaya",
    metaDescription:
      "Regular caregiver visits for ageing parents at home in India. Four KushLife checks every visit and an update for the family after each one.",
    serviceType: "In-home elder care visits",
    label: "Elder care visits",
    eyebrow: "Elder care visits",
    title: "Elder care visits at home",
    accent: " that keep the family close.",
    lede: "Elder care visits bring a trained KushAlaya care manager to your parents' home on a set schedule, from 8 to 70 visits a year. Every visit runs four KushLife checks — safe, steady, settled, connected — and sends the family a short update with photos.",
    image: "/marketing/kushlife-visit.webp",
    imageAlt: "A caregiver chatting with an older woman at home",
    sections: [
      {
        title: "Company, care and a trained eye",
        paras: [
          "Many parents are fine most days, but nobody is looking in regularly. A caregiver visit gives them company and gives you a reliable picture of how they are. The caregiver also notices the small changes that often come before a fall or an illness: a new bruise, a missed meal, a room that has become cluttered.",
          "Visits are arranged with your parents, at times that suit their routine. They can say no to anything.",
        ],
      },
      {
        title: "The four KushLife checks",
        paras: ["Every visit after the assessment includes four short checks, recorded the same way each time so you see the trend and not just the incident."],
        bullets: [
          "Safe: the home is still free of new hazards",
          "Steady: how your parent is moving, standing and walking",
          "Settled: mood, sleep, appetite and how the day is going",
          "Connected: contact with family and friends, and anything they want you to know",
        ],
      },
      {
        title: "Updates in the family app",
        paras: [
          "After each visit you get a short note and photos in the family app, along with regular summaries. Brothers and sisters in different cities or countries see the same information, so nobody has to pass messages along.",
        ],
      },
      {
        title: "SOS wearable and emergencies",
        paras: [
          "The Privilege and Signature plans include a complimentary SOS watch linked to the family app. It helps the family know sooner when something is wrong.",
          SEO_EMERGENCY_LINE,
        ],
      },
      {
        title: "Getting started",
        paras: [
          "Visits start after a home safety assessment, so the caregiver knows the home and what to look out for. Begin with KushCare Discovery and we will call you back.",
          SEO_PRICE_LINE,
        ],
      },
    ],
    related: [
      { href: "/kushlife", label: "About KushLife checks" },
      { href: "/packages", label: "Plans and prices" },
      { href: "/kushcare-discovery", label: "Start KushCare Discovery" },
      { href: "/contact", label: "Talk to us" },
    ],
  },
  {
    slug: "care-for-nri-families",
    metaTitle: "Care for Parents in India from Abroad | KushAlaya",
    metaDescription:
      "Living abroad while your parents age in India? KushAlaya checks their home, fixes risks, visits regularly and keeps you updated in your time zone.",
    serviceType: "Elder care coordination for families living abroad",
    label: "Care for NRI families",
    eyebrow: "For families abroad",
    title: "Care for parents in India",
    accent: " while you live abroad.",
    lede: "KushAlaya cares for parents in India while their children live abroad. We check the home for fall risks, fix them, visit regularly and coordinate in an emergency. You see every visit, photo and report in the family app, in your own time zone.",
    image: "/marketing/abroad.webp",
    imageAlt: "A family abroad on a video call with their parents in India",
    sections: [
      {
        title: "The distance problem",
        paras: [
          "When you live abroad, you hear about your parents in short phone calls. They often say everything is fine, because they do not want you to worry. You may only find out about the loose step or the slip in the bathroom after it has happened.",
          "KushAlaya gives you a trusted set of eyes in your parents' home, and a record you can check whenever you want.",
        ],
      },
      {
        title: "What we do for you",
        paras: ["One team handles the home, the visits and the updates:"],
        bullets: [
          "A home safety assessment with a KushAlaya Safety Score and a priced list of fixes",
          "Safety products and installation arranged by us, checked when done",
          "Regular caregiver visits with four KushLife checks every time",
          "Updates in the family app after every visit, shared with the family members you choose",
          "A complimentary SOS watch on the Privilege and Signature plans",
        ],
      },
      {
        title: "Talk to us in your time zone",
        paras: [
          `Calls with your care manager are planned around your time zone. From the US or Canada, call ${SEO_PHONES.usCanada.display}. In India, call ${SEO_PHONES.india.display}. Or fill in the KushCare Discovery form and we will call you back.`,
        ],
      },
      {
        title: "What we are not",
        paras: [
          `We are not a hospital, a nursing agency or an emergency service. ${SEO_EMERGENCY_LINE}`,
          "We make the home safer, visit regularly and keep the family informed, so problems are caught early.",
        ],
      },
      {
        title: "Plans and payments",
        paras: [
          `${SEO_PRICE_LINE} You see the price before anything is booked, and we explain payment options for families abroad during your callback.`,
        ],
      },
    ],
    related: [
      { href: "/kushcare-discovery", label: "Start KushCare Discovery" },
      { href: "/packages", label: "Plans and prices" },
      { href: "/kushlife", label: "KushLife checks" },
      { href: "/about", label: "About us" },
    ],
  },
  {
    slug: "fall-prevention-products",
    metaTitle: "Fall Prevention Products & Installation | KushAlaya",
    metaDescription:
      "Grab bars, rails, anti-slip work and night lighting for older parents' homes in India, chosen after a safety assessment and fitted for you.",
    serviceType: "Fall prevention products and installation",
    label: "Fall prevention products",
    eyebrow: "Fall prevention products",
    title: "Fall prevention products for the elderly,",
    accent: " fitted properly.",
    lede: "Fall prevention products for elderly parents are grab bars, handrails, anti-slip floors, night lights and SOS watches. KushAlaya chooses them after a home safety assessment and our own team installs them, so each fix sits exactly where your parents need it.",
    image: "/marketing/how-03-improve.webp",
    imageAlt: "A grab bar and rail being fitted in an older parent's home",
    sections: [
      {
        title: "Start with the home, not the catalogue",
        paras: [
          "A grab bar in the wrong place does little. We recommend products only after a home safety assessment, so each one answers a real risk in your parents' home and fits how they move.",
          "Your parents stay in charge: nothing is fitted without their agreement, and we explain each change in plain language.",
        ],
      },
      {
        title: "What we typically recommend",
        paras: ["The exact list depends on the home. Common fixes include:"],
        bullets: [
          "Grab bars near the toilet and in the shower",
          "Anti-slip treatment or mats for bathroom and wet-area floors",
          "Hand rails on stairs and steps, and support at thresholds",
          "Night lights and motion lighting on the path to the toilet",
          "Shower chairs and raised toilet seats where useful",
          "A complimentary SOS watch on the Privilege and Signature plans",
        ],
      },
      {
        title: "See it before it is fitted",
        paras: [
          "The AI room preview shows a room with the recommended products in place, so you and your parents can picture the change. It is an illustration; the final products and positions are confirmed at the visit.",
        ],
      },
      {
        title: "Installation, checked",
        paras: [
          "We arrange installation through our partners and check the work when it is done. You see the products and the price before anything is booked, and your Safety Score is updated afterwards.",
        ],
      },
      {
        title: "How to begin",
        paras: [
          "Fill in the KushCare Discovery form. We call you back and arrange the assessment that shows which fixes your parents' home really needs.",
        ],
      },
    ],
    related: [
      { href: "/safe-homes", label: "Safe homes" },
      { href: "/safe-homes#ai", label: "AI room check and preview" },
      { href: "/kushcare-discovery", label: "Start KushCare Discovery" },
      { href: "/packages", label: "Plans and prices" },
    ],
  },
];

export function seoServiceBySlug(slug: string): SeoService | undefined {
  return SEO_SERVICES.find((s) => s.slug === slug);
}
