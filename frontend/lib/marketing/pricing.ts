/**
 * Billing periods for the public plans page. Prices come from the catalog
 * (lib/care-plan-catalog.ts), never derived here: paying monthly costs more than
 * the yearly price on purpose, and every plan offers both. No 6-month billing.
 */
import { planPricePaise } from "@/lib/care-plan-catalog";

export type BillingPeriod = "annual" | "monthly";

export const BILLING_PERIODS: BillingPeriod[] = ["annual", "monthly"];

export const PERIOD_LABEL: Record<BillingPeriod, string> = {
  annual: "Yearly",
  monthly: "Monthly",
};

/** Suffix shown after the amount, e.g. "₹9,900 / month". */
export const PERIOD_SUFFIX: Record<BillingPeriod, string> = {
  annual: "/ year",
  monthly: "/ month",
};

/** Whole rupees billed for one period, or null when the plan isn't offered that way. */
export function priceForPeriod(planId: string, period: BillingPeriod): number | null {
  const paise = planPricePaise(planId, period === "annual" ? "yearly" : "monthly");
  return paise === null ? null : Math.round(paise / 100);
}

/** "₹1,200" — Indian digit grouping, no decimals. */
export function formatInr(amount: number): string {
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * Rough rupees per US dollar for the "$ USD" view on the plans page. Display
 * only: every plan is billed in rupees, and the page says so. Update now and
 * then; it is not a live rate.
 */
export const USD_INR_RATE = 88;

/** "≈ $136" for a rupee amount (rounded to whole dollars). */
export function formatUsdApprox(amountInr: number): string {
  return `≈ $${Math.round(amountInr / USD_INR_RATE).toLocaleString("en-US")}`;
}
