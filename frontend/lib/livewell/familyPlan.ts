/**
 * Plan numbers for families: a believable projected score and one total price range.
 */
import { findingNeed } from "./familyFindings";

/**
 * Score after the open fixes: the current score plus the points the open plan
 * items add (capped below 100). null when it can't be worked out honestly; the
 * page then says "Score goes up as fixes are done".
 */
export function projectedScore(
  current: number | null | undefined,
  items: { score_gain?: number | null; status?: string | null }[] | null | undefined,
): number | null {
  if (current == null || !Number.isFinite(current)) return null;
  const gain = (items || [])
    .filter((i) => (i.status || "").toLowerCase() !== "done")
    .reduce((sum, i) => sum + Math.max(0, Number(i.score_gain) || 0), 0);
  if (gain <= 0) return null;
  return Math.min(Math.round(current + gain), 95);
}

/** "₹3,000–₹25,000" / "₹4,000" / "Rs 3000 - 5000" -> [min, max] in rupees; null when no number. */
export function parseRupeeRange(text: string | null | undefined): [number, number] | null {
  const nums = (text || "")
    .replace(/,/g, "")
    .match(/\d+(?:\.\d+)?/g)
    ?.map(Number)
    .filter((n) => Number.isFinite(n) && n > 0);
  if (!nums || !nums.length) return null;
  return [Math.min(...nums.slice(0, 2)), Math.max(...nums.slice(0, 2))];
}

const inr = (n: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);

/** One total range over the open items' indicative costs: "₹7,000–₹65,000"; null when none are priced. */
export function totalCostRange(
  items: { estimated_cost?: string | null; status?: string | null }[] | null | undefined,
): string | null {
  let lo = 0;
  let hi = 0;
  let any = false;
  for (const i of items || []) {
    if ((i.status || "").toLowerCase() === "done") continue;
    const r = parseRupeeRange(i.estimated_cost);
    if (!r) continue;
    any = true;
    lo += r[0];
    hi += r[1];
  }
  if (!any) return null;
  return lo === hi ? inr(lo) : `${inr(lo)}–${inr(hi)}`;
}

export type NeedOption = { product_id: number; price_with_gst_paise: number | null };

/**
 * One total for the fixes, the same on /safety and /plan: per need, the
 * cheapest priced option (options under one need are alternatives), summed.
 * Money stays in paise. `unpriced` counts needs with no priced option.
 */
export function fixesTotal<T extends NeedOption>(
  needs: Map<string, T[]>,
  priceOf: (o: T) => number | null = (o) => o.price_with_gst_paise,
): { paise: number; priced: number; unpriced: number } {
  let paise = 0;
  let priced = 0;
  let unpriced = 0;
  for (const options of needs.values()) {
    const prices = options.map(priceOf).filter((p): p is number => !!p && p > 0);
    if (prices.length) {
      paise += Math.min(...prices);
      priced += 1;
    } else unpriced += 1;
  }
  return { paise, priced, unpriced };
}

/** Suggestions grouped by the need they fix ("No toilet grab bar"), in order. */
export function groupByNeed<T extends { name: string; reasons: string[] }>(items: T[]): Map<string, T[]> {
  const needs = new Map<string, T[]>();
  for (const i of items) {
    const need = i.reasons[0] ? findingNeed(i.reasons[0]) : i.name;
    needs.set(need, [...(needs.get(need) ?? []), i]);
  }
  return needs;
}
