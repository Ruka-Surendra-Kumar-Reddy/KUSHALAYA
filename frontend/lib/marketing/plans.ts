/**
 * Care plans for the public site and the family app, built from the one source of
 * truth, lib/care-plan-catalog.ts (owner's company deck, 26 Oct 2026). Nothing here
 * holds its own price or visit count, so the site cannot drift from the catalog.
 *
 * Prices include GST. Every plan can be paid yearly or monthly; monthly costs
 * more on purpose ("₹9,900 a month if paid monthly").
 */
import {
  CARE_PLAN_CATALOG,
  EVERY_PLAN_INCLUDES,
  SINGLE_VISIT,
  inr,
  type CarePlanDef,
} from "@/lib/care-plan-catalog";

export interface CarePlan {
  id: CarePlanDef["id"];
  /** "KushAlaya Privilege". */
  name: string;
  /** "Privilege" — for tight spots such as the compare table. */
  shortName: string;
  /** One line: who this is for. */
  fit: string;
  visitsPerYear: number;
  /** "50 visits a year". */
  visitLabel: string;
  /** Yearly price in whole rupees. */
  annualInr: number;
  /** Monthly price in whole rupees. */
  monthlyInr: number;
  /** Shown as a tick list on the card. */
  includes: string[];
  /** The plan marked "Most popular". */
  highlight?: boolean;
}

export const CARE_PLANS: CarePlan[] = CARE_PLAN_CATALOG.map((p) => ({
  id: p.id,
  name: p.name,
  shortName: p.name.replace(/^KushAlaya\s+/, ""),
  fit: p.summary,
  visitsPerYear: p.visitsPerYear,
  visitLabel: `${p.visitsPerYear} visits a year`,
  annualInr: Math.round(p.annualPaise / 100),
  monthlyInr: Math.round((p.monthlyPaise ?? 0) / 100),
  includes: p.inclusions,
  highlight: p.popular || undefined,
}));

/** "₹9,900 a month if paid monthly". Never "effective". */
export function monthlyLine(plan: Pick<CarePlan, "monthlyInr">, money: (inr: number) => string = formatRupees): string {
  return `${money(plan.monthlyInr)} a month if paid monthly`;
}

/** What every annual plan includes (shown once, above the plan cards). */
export const EVERY_PLAN = EVERY_PLAN_INCLUDES;

export const MONTHLY_NOTE = "Prefer flexibility? Monthly billing available on every plan.";

function formatRupees(amount: number): string {
  return inr(amount * 100);
}

/** "Included" when the plan's own extras mention it, else "—". */
const extra = (re: RegExp) => (p: CarePlan) => (p.includes.some((line) => re.test(line)) ? "Included" : "—");

/** Rows for the plan comparison table, in display order (the price row is added by CarePlans). */
export const PLAN_COMPARISON: {
  label: string;
  value: (p: CarePlan) => string;
}[] = [
  { label: "Care-manager visits", value: (p) => p.visitLabel },
  { label: "Everything every annual plan includes", value: () => "Included" },
  { label: "SOS watch with family alerts", value: extra(/SOS watch/i) },
  { label: "Health kit (BP, glucose, pulse oximeter)", value: extra(/kit/i) },
  { label: "Weekly vitals tracking", value: extra(/^Weekly BP/i) },
];

export function planById(id: string): CarePlan | undefined {
  return CARE_PLANS.find((p) => p.id === id);
}

/** Lowest yearly price, for "plans from" lines. */
export const LOWEST_ANNUAL_INR = Math.min(...CARE_PLANS.map((p) => p.annualInr));

/** "Plans from ₹55,000 a year … Single priority visit — ₹3,400 + ₹100 registration …" */
/** "Single priority visit — ₹3,400 + ₹100 registration (4 hours, no subscription)". */
export const SINGLE_VISIT_LINE = `${SINGLE_VISIT.name} — ${inr(SINGLE_VISIT.pricePaise)} + ${inr(SINGLE_VISIT.registrationPaise)} registration (${SINGLE_VISIT.hours} hours, no subscription)`;

const monthlyPrices = CARE_PLANS.map((p) => p.monthlyInr).filter((n) => n > 0);

/** Answer-first cost line: "Care plans cost ₹55,000–₹1,60,000 a year, or ₹6,000–₹17,500 a month, GST included." */
export const PLAN_COST_ANSWER = `Care plans cost ${formatRupees(LOWEST_ANNUAL_INR)}–${formatRupees(Math.max(...CARE_PLANS.map((p) => p.annualInr)))} a year, or ${formatRupees(Math.min(...monthlyPrices))}–${formatRupees(Math.max(...monthlyPrices))} a month, GST included.`;

export const PLAN_PRICE_LINE = `Plans from ${formatRupees(LOWEST_ANNUAL_INR)} a year, GST included; monthly billing on every plan. ${SINGLE_VISIT_LINE}.`;

/**
 * Pay as you go — no subscription. Book a single visit only when it is needed and
 * pay for that visit alone. Shown beside the plans, not in the fine print.
 */
export const PAY_AS_YOU_GO = {
  eyebrow: "Flexible care",
  title: "Pay as you go care",
  body: "Not ready for a plan? Book a visit only when needed and pay for that visit — same trained team, same standard.",
  points: [
    { title: "No subscription", note: "No contract, no lock-in, no monthly fee" },
    { title: `${inr(SINGLE_VISIT.pricePaise)} a visit`, note: `+ ${inr(SINGLE_VISIT.registrationPaise)} registration · ${SINGLE_VISIT.hours} hours, GST included` },
    { title: "Same standard", note: "KushLife check and photo update every visit" },
  ],
  items: [
    SINGLE_VISIT_LINE,
    "Caregiver / attendant visits",
    "Physiotherapy sessions",
    "Hospital-discharge and recovery help",
    "Home safety re-checks",
  ],
  /** The need each item preselects in the Buy now sheet (null: the visit line itself). */
  itemNeeds: [null, "care_visit", "physiotherapy", "discharge_help", "safety_recheck"] as const,
  buyCta: "Buy now",
  cta: "Book a visit",
};
