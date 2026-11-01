/**
 * Website "Buy now" on the care plans. The server (POST /home-safety/plan-purchases)
 * prices everything again — these helpers only drive what the sheet shows.
 * Money is integer paise.
 */
import { SINGLE_VISIT, planPricePaise, type BillingCycle } from "@/lib/care-plan-catalog";
import type { BillingPeriod } from "@/lib/marketing/pricing";

export const PLAN_PURCHASES_PATH = "/api/v1/home-safety/plan-purchases";

/** The plan cards say "annual"; the API says "yearly". */
export function cycleForPeriod(period: BillingPeriod): BillingCycle {
  return period === "monthly" ? "monthly" : "yearly";
}

/** Coupon codes as staff hand them out: trimmed, upper-case, letters/digits/-/_ only. */
export function cleanCouponCode(raw: string): string {
  return raw.trim().toUpperCase().replace(/[^A-Z0-9_-]/g, "").slice(0, 40);
}

/** Pay as you go: one Single priority visit, bought once (plan_id "single-visit"). */
export const VISIT_PLAN_ID = SINGLE_VISIT.id;
export type CheckoutCycle = BillingCycle | "once";

/** "What do you need?" — ids match the family service request types on the server. */
export const VISIT_NEEDS = [
  { id: "care_visit", label: "Caregiver / attendant visit" },
  { id: "physiotherapy", label: "Physiotherapy session" },
  { id: "discharge_help", label: "Hospital-discharge & recovery help" },
  { id: "safety_recheck", label: "Home safety re-check" },
  { id: "other", label: "Something else" },
] as const;
export type VisitNeed = (typeof VISIT_NEEDS)[number]["id"];

export const TIME_OF_DAY = [
  { id: "morning", label: "Morning" },
  { id: "afternoon", label: "Afternoon" },
  { id: "evening", label: "Evening" },
] as const;

/** The earliest preferred date (tomorrow, local) as YYYY-MM-DD for <input type="date" min>. */
export function earliestVisitDate(now: Date = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export type PlanQuote = {
  plan_id: string;
  plan_name: string;
  billing_cycle: CheckoutCycle;
  /** Single visit only: the visit and the one-time registration (they add up to list_paise). */
  visit_paise?: number;
  registration_paise?: number;
  list_paise: number;
  discount_paise: number;
  amount_paise: number;
  coupon_code: string | null;
};

/**
 * What to show as the price: the server's quote when it is for this plan + cycle,
 * else the catalog price (no coupon). Null for an unknown plan.
 */
export function shownPrice(
  planId: string,
  cycle: CheckoutCycle,
  quote: PlanQuote | null,
): { listPaise: number; discountPaise: number; amountPaise: number; coupon: string | null } | null {
  if (quote && quote.plan_id === planId && quote.billing_cycle === cycle) {
    return {
      listPaise: quote.list_paise,
      discountPaise: quote.discount_paise,
      amountPaise: quote.amount_paise,
      coupon: quote.coupon_code,
    };
  }
  const list =
    planId === VISIT_PLAN_ID
      ? cycle === "once"
        ? SINGLE_VISIT.pricePaise + SINGLE_VISIT.registrationPaise
        : null
      : cycle === "once"
        ? null
        : planPricePaise(planId, cycle);
  if (list === null) return null;
  return { listPaise: list, discountPaise: 0, amountPaise: list, coupon: null };
}
