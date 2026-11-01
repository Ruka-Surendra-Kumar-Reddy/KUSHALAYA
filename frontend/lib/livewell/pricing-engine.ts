import type { ImprovementPlan } from "./improvement-plan";
import type { ProductQuoteDraft } from "./product-recommendations";
import { catalogPriceIncludesInstallLabor } from "./catalog";
import { selectVendorOffer } from "./supplier-selection";
import type { SupplierDirectory, VendorSelectionContext } from "./supplier-types";
import type {
  QuoteInputs,
  SafeHomePricingConfig,
  SafeHomeQuote,
} from "./pricing-types";

export function parseInstallationHours(text: string | undefined): number | null {
  if (!text?.trim()) return null;
  const hourMatch = text.match(/([\d.]+)\s*(?:–|-)?\s*([\d.]+)?\s*(?:hours?|hrs?|h)\b/i);
  if (hourMatch) {
    const a = Number(hourMatch[1]);
    const b = hourMatch[2] != null ? Number(hourMatch[2]) : null;
    if (!Number.isNaN(a) && b != null && !Number.isNaN(b)) return (a + b) / 2;
    if (!Number.isNaN(a)) return a;
  }
  const nums = text.match(/[\d.]+/g);
  if (!nums?.length) return null;
  const values = nums.map(Number).filter((n) => !Number.isNaN(n));
  if (!values.length) return null;
  return values.reduce((sum, n) => sum + n, 0) / values.length;
}

export function estimateLaborHours(
  plan: ImprovementPlan,
  draft: ProductQuoteDraft,
  config: SafeHomePricingConfig,
): number {
  /** Solutions already covered by all-in installed catalog prices. */
  const coveredByInstalled = new Set<string>();
  for (const item of draft.items) {
    if (!catalogPriceIncludesInstallLabor(item.product)) continue;
    for (const id of item.solutionIds) coveredByInstalled.add(id);
  }

  const mappedSolutionIds = new Set(draft.items.flatMap((i) => i.solutionIds));
  let hours = 0;
  for (const entry of plan.entries) {
    if (!mappedSolutionIds.has(entry.solution.id)) continue;
    if (coveredByInstalled.has(entry.solution.id)) continue;
    const parsed = parseInstallationHours(entry.solution.installationTime);
    hours += parsed ?? config.default_labor_hours_per_solution;
  }
  return Math.round(hours * 100) / 100;
}

function roundToRule(amount: number, rule: SafeHomePricingConfig["round_off_rule"]): {
  rounded: number;
  adjustment: number;
} {
  if (rule === "none") return { rounded: Math.round(amount), adjustment: 0 };
  const step = rule === "nearest_50" ? 50 : 100;
  const rounded = Math.round(amount / step) * step;
  return { rounded, adjustment: rounded - amount };
}

function clampMarginPercent(config: SafeHomePricingConfig, override?: number): number {
  const base = override ?? config.default_margin_percent;
  return Math.min(config.max_margin_percent, Math.max(config.min_margin_percent, base));
}

export function computeVendorProductTotalInr(
  draft: ProductQuoteDraft,
  suppliers: SupplierDirectory,
  context: VendorSelectionContext = {},
): number {
  let total = 0;
  for (const item of draft.items) {
    const selected = selectVendorOffer(suppliers, item.product.id, {
      ...context,
      quantity: item.quantity,
    });
    if (selected) {
      total += selected.offer.supplier_cost_inr * item.quantity;
    }
  }
  return total;
}

export function buildSafeHomeQuote(
  draft: ProductQuoteDraft,
  plan: ImprovementPlan,
  config: SafeHomePricingConfig,
  inputs: QuoteInputs = {},
  options?: {
    suppliers?: SupplierDirectory;
    vendorContext?: VendorSelectionContext;
  },
): SafeHomeQuote | null {
  if (!draft.items.length) return null;

  const productTotalInr = draft.subtotalInr ?? 0;
  const vendorProductCostInr =
    options?.suppliers != null
      ? computeVendorProductTotalInr(
          draft,
          options.suppliers,
          options.vendorContext ?? {},
        )
      : null;
  const grossProductMarginInr =
    vendorProductCostInr != null ? productTotalInr - vendorProductCostInr : null;
  const laborHours =
    inputs.labor_hours ?? estimateLaborHours(plan, draft, config);
  const laborRatePerHourInr = config.labor_rate_per_hour_inr;
  let laborTotalInr = Math.round(laborHours * laborRatePerHourInr);

  const travelKm = inputs.travel_km ?? config.default_travel_km;
  const travelRatePerKmInr = config.travel_rate_per_km_inr;
  let travelTotalInr = Math.round(travelKm * travelRatePerKmInr);

  const serviceBeforeMin = laborTotalInr + travelTotalInr;
  let serviceMinimumApplied = false;
  if (laborHours > 0 && serviceBeforeMin < config.minimum_service_charge_inr) {
    const bump = config.minimum_service_charge_inr - serviceBeforeMin;
    laborTotalInr += bump;
    serviceMinimumApplied = true;
  }

  const consumablesInr = inputs.consumables_inr ?? config.default_consumables_inr;
  const miscellaneousInr = inputs.miscellaneous_inr ?? config.default_miscellaneous_inr;

  const productBaseForMargin =
    config.use_vendor_cost_for_margin && vendorProductCostInr != null
      ? vendorProductCostInr
      : productTotalInr;

  let costSubtotalInr =
    productBaseForMargin + laborTotalInr + travelTotalInr + consumablesInr + miscellaneousInr;

  let weekendSurchargeInr = 0;
  let emergencySurchargeInr = 0;
  if (inputs.apply_weekend_surcharge) {
    weekendSurchargeInr = Math.round(
      costSubtotalInr * (config.weekend_surcharge_percent / 100),
    );
    costSubtotalInr += weekendSurchargeInr;
  }
  if (inputs.apply_emergency_surcharge) {
    emergencySurchargeInr = Math.round(
      costSubtotalInr * (config.emergency_surcharge_percent / 100),
    );
    costSubtotalInr += emergencySurchargeInr;
  }

  const marginPercent = clampMarginPercent(config, inputs.margin_percent_override);
  const marginAmountInr =
    config.margin_type === "fixed"
      ? Math.round(config.fixed_margin_inr)
      : Math.round(costSubtotalInr * (marginPercent / 100));

  const customerServicesInr =
    productTotalInr + laborTotalInr + travelTotalInr + consumablesInr + miscellaneousInr;
  let customerPreMarginInr = customerServicesInr;
  if (inputs.apply_weekend_surcharge) {
    customerPreMarginInr += weekendSurchargeInr;
  }
  if (inputs.apply_emergency_surcharge) {
    customerPreMarginInr += emergencySurchargeInr;
  }

  const preTaxTotalInr = customerPreMarginInr + marginAmountInr;
  const gstAmountInr = Math.round(preTaxTotalInr * (config.gst_percent / 100));
  const totalBeforeRoundInr = preTaxTotalInr + gstAmountInr;
  const { rounded: grandTotalInr, adjustment: roundOffInr } = roundToRule(
    totalBeforeRoundInr,
    config.round_off_rule,
  );

  return {
    productTotalInr,
    laborHours,
    laborRatePerHourInr,
    laborTotalInr,
    travelKm,
    travelRatePerKmInr,
    travelTotalInr,
    consumablesInr,
    miscellaneousInr,
    serviceMinimumApplied,
    costSubtotalInr,
    weekendSurchargeInr,
    emergencySurchargeInr,
    marginType: config.margin_type,
    marginPercent,
    marginAmountInr,
    preTaxTotalInr,
    gstPercent: config.gst_percent,
    gstAmountInr,
    totalBeforeRoundInr,
    grandTotalInr,
    roundOffInr,
    vendorProductCostInr,
    grossProductMarginInr,
  };
}

function inr(n: number): string {
  return `₹${n.toLocaleString("en-IN")}`;
}

export function formatSafeHomeQuoteText(
  quote: SafeHomeQuote,
  draft: ProductQuoteDraft,
): string {
  const lines: string[] = [
    "CUSTOMER QUOTE ESTIMATE",
    "",
    `Products (${draft.pricedItemCount} priced): ${inr(quote.productTotalInr)}`,
    `Labor: ${quote.laborHours}h × ${inr(quote.laborRatePerHourInr)}/h = ${inr(quote.laborTotalInr)}`,
    `Travel: ${quote.travelKm} km × ${inr(quote.travelRatePerKmInr)}/km = ${inr(quote.travelTotalInr)}`,
    `Consumables: ${inr(quote.consumablesInr)}`,
  ];
  if (quote.miscellaneousInr > 0) {
    lines.push(`Other charges: ${inr(quote.miscellaneousInr)}`);
  }
  if (quote.serviceMinimumApplied) {
    lines.push("(Minimum service charge applied)");
  }
  if (quote.weekendSurchargeInr > 0) {
    lines.push(`Weekend surcharge: ${inr(quote.weekendSurchargeInr)}`);
  }
  if (quote.emergencySurchargeInr > 0) {
    lines.push(`Emergency surcharge: ${inr(quote.emergencySurchargeInr)}`);
  }
  lines.push(
    `Cost subtotal: ${inr(quote.costSubtotalInr)}`,
    `Margin (${quote.marginType === "fixed" ? "fixed" : `${quote.marginPercent}%`}): ${inr(quote.marginAmountInr)}`,
    `Pre-tax: ${inr(quote.preTaxTotalInr)}`,
    `GST (${quote.gstPercent}%): ${inr(quote.gstAmountInr)}`,
    `Before round-off: ${inr(quote.totalBeforeRoundInr)}`,
  );
  if (quote.roundOffInr !== 0) {
    lines.push(`Round-off: ${inr(quote.roundOffInr)}`);
  }
  lines.push(`GRAND TOTAL: ${inr(quote.grandTotalInr)}`);
  return lines.join("\n");
}
