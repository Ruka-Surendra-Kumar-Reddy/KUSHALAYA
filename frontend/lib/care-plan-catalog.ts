/**
 * KushAlaya care plans — the one source of truth on the frontend (owner's pricing
 * sheet, 27 Oct 2026). Same data as backend/app/livewell/care_plan_catalog.py.
 * Prices include GST and are integer paise. Paying monthly costs more than the
 * annual price on purpose; monthly billing is offered on every plan.
 */
export type BillingCycle = "yearly" | "monthly";

export type CarePlanDef = {
  id: "assurance" | "total-care" | "privilege" | "signature";
  name: string;
  tag: string;
  annualPaise: number;
  /** Monthly price (paise); null would mean annual-only billing. */
  monthlyPaise: number | null;
  visitsPerYear: number;
  summary: string;
  popular?: boolean;
  inclusions: string[];
};

export const CARE_PLAN_CATALOG: CarePlanDef[] = [
  {
    id: "assurance",
    name: "KushAlaya Assurance",
    tag: "Annual plan",
    annualPaise: 5_500_000,
    monthlyPaise: 600_000,
    visitsPerYear: 8,
    summary: "Ideal for emergency support only",
    inclusions: [
      "8 care-manager visits a year",
    ],
  },
  {
    id: "total-care",
    name: "KushAlaya Total Care",
    tag: "Annual plan",
    annualPaise: 9_500_000,
    monthlyPaise: 990_000,
    visitsPerYear: 30,
    summary: "Baseline protection",
    inclusions: [
      "30 care-manager visits a year",
    ],
  },
  {
    id: "privilege",
    name: "KushAlaya Privilege",
    tag: "Most popular",
    annualPaise: 12_500_000,
    monthlyPaise: 1_350_000,
    visitsPerYear: 50,
    summary: "Ongoing partnership",
    popular: true,
    inclusions: [
      "50 care-manager visits a year (about 1 a week)",
      "Complimentary SOS watch with family alerts",
    ],
  },
  {
    id: "signature",
    name: "KushAlaya Signature",
    tag: "Premium",
    annualPaise: 16_000_000,
    monthlyPaise: 1_750_000,
    visitsPerYear: 70,
    summary: "Ultra high-touch",
    inclusions: [
      "70 care-manager visits a year",
      "Complimentary SOS watch with family alerts",
      "Privilege kit: BP monitor, glucose meter, pulse oximeter",
      "Weekly BP, glucose, pulse and SpO2 tracking",
    ],
  },
];

/** What every annual plan includes; each plan's inclusions are only what differs. */
export const EVERY_PLAN_INCLUDES: string[] = [
  "Care-manager visits — the number depends on the plan",
  "Emergency visits always free — never counted against your visits",
  "Emergency coordination",
  "Free KushAlaya assessment with any annual plan",
  "Family portal: visit reports with photos, message your care manager, rapid family alerts, live care-manager location, WhatsApp digest",
  "Doctor and errand accompaniment",
  "Utilities, groceries and repairs coordination",
  "Partner services coordinated by us: home caregivers, physiotherapy, nursing and recovery support",
  "Personalised recommendations and request follow-ups",
  "Digital health and service records",
  "Regular family care summaries",
];

/** Pay as you go (no subscription): a 4-hour priority visit plus a one-time registration. */
export const SINGLE_VISIT = {
  id: "single-visit",
  name: "Single priority visit",
  pricePaise: 340_000,
  registrationPaise: 10_000,
  hours: 4,
} as const;
/** KushCare Discovery home assessment: free (owner, 27 Oct 2026). The ₹100 registration is only for SINGLE_VISIT. */
export const HOME_ASSESSMENT = { id: "home-assessment", name: "KushCare Discovery home assessment", pricePaise: 0 } as const;

export function carePlan(id: string): CarePlanDef | undefined {
  return CARE_PLAN_CATALOG.find((p) => p.id === id);
}

/** Price for one billing period, or null when that cycle isn't offered. */
export function planPricePaise(id: string, cycle: BillingCycle): number | null {
  const p = carePlan(id);
  if (!p) return null;
  return cycle === "yearly" ? p.annualPaise : p.monthlyPaise;
}

/** "₹1,25,000" — whole rupees, Indian grouping. */
export function inr(paise: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);
}
