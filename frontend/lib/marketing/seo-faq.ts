/**
 * /faq content. The home-page FAQs (content.ts FAQS) are reused by reference,
 * not copied; the rest are written here once.
 */
import { FAQS } from "./content";
import { PLAN_COST_ANSWER } from "./plans";
import { SEO_EMERGENCY_LINE, SEO_PHONES } from "./seo-common";

export type SeoFaq = { q: string; a: string };
export type SeoFaqGroup = { id: string; title: string; items: readonly SeoFaq[] };

const home = (i: number): SeoFaq => ({ q: FAQS[i].q, a: FAQS[i].a });

export const SEO_FAQ_GROUPS: readonly SeoFaqGroup[] = [
  {
    id: "getting-started",
    title: "Getting started",
    items: [
      home(6),
      {
        q: "What is KushCare Discovery?",
        a: "It is how every family starts. You fill in a short form about your parent and their home, we call you back to understand what you need, and then we arrange a home safety assessment.",
      },
      {
        q: "Is KushCare Discovery free?",
        a: "Yes. The form, the call back and the home safety assessment that follows are all free, with no obligation.",
      },
      {
        q: "Which cities do you cover?",
        a: "We work with families across India and arrange visits in your parent's city. Tell us the city in the KushCare Discovery form and we will confirm how we can help there.",
      },
      home(3),
    ],
  },
  {
    id: "assessment-ai",
    title: "Safety assessment & AI",
    items: [
      home(1),
      {
        q: "What does the KushAlaya Safety Score tell me?",
        a: "It is a score out of 100 from the assessment. It shows how safe the home is today and which fixes would make the biggest difference, so you can see progress as work is done.",
      },
      home(0),
      {
        q: "Do I have to buy the products you recommend?",
        a: "No. The report tells you what matters and why. You decide what to fix and when, and you see the price before anything is booked.",
      },
      {
        q: "Who fits grab bars, rails and other products?",
        a: "Installation is arranged by us through our partners and checked when done. You see the products and the price first.",
      },
    ],
  },
  {
    id: "visits-kushlife",
    title: "Visits & KushLife",
    items: [
      home(2),
      {
        q: "What happens on a caregiver visit?",
        a: "A caregiver spends time with your parent, runs the four KushLife checks, notes anything that has changed at home, and records the visit with a short note and photos for the family app.",
      },
      {
        q: "How will I hear about each visit?",
        a: "You get an update in the family app after every visit, plus regular summaries, so you see how your parent is doing over time and not only when something goes wrong.",
      },
      home(5),
    ],
  },
  {
    id: "prices-payments",
    title: "Prices & payments",
    items: [
      {
        q: "How much does it cost?",
        a: `${PLAN_COST_ANSWER} KushCare Discovery is free. The packages page lists every plan, and you see the price before anything is booked.`,
      },
      {
        q: "Are there hidden charges for products or installation?",
        a: "No. Products and installation are quoted separately and shown to you before any work is booked.",
      },
      {
        q: "How do I pay if I live outside India?",
        a: "Ask us during your callback and we will explain the payment options for your plan.",
      },
    ],
  },
  {
    id: "families-abroad",
    title: "Families abroad",
    items: [
      home(4),
      {
        q: "I live in the US or Canada. Can I call you?",
        a: `Yes. Call ${SEO_PHONES.usCanada.display} from the US or Canada, or ${SEO_PHONES.india.display} in India.`,
      },
      {
        q: "Can my siblings in different countries all see the updates?",
        a: "Yes. The family app can be shared with the family members you choose, so everyone sees the same visit notes and reports.",
      },
    ],
  },
  {
    id: "privacy-safety",
    title: "Privacy & safety",
    items: [
      {
        q: "Are you an emergency service?",
        a: `No. ${SEO_EMERGENCY_LINE} Our SOS wearable and alerts help the family know sooner; they do not replace emergency services.`,
      },
      {
        q: "What happens to the photos of my parents' home?",
        a: "Photos are used only to plan your home's safety work and are never shared or sold.",
      },
      {
        q: "Can my parents refuse a visit or a change?",
        a: "Yes, always. Visits are arranged with them, and they can say no to anything.",
      },
    ],
  },
];

export const SEO_FAQ_ALL: readonly SeoFaq[] = SEO_FAQ_GROUPS.flatMap((g) => g.items);
