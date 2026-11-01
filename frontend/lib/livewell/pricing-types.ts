/** SafeHome 360™ tenant pricing configuration (Phase C). */

export type MarginType = "percent" | "fixed";
export type RoundOffRule = "none" | "nearest_50" | "nearest_100";

export interface SafeHomePricingConfig {
  default_margin_percent: number;
  min_margin_percent: number;
  max_margin_percent: number;
  margin_type: MarginType;
  fixed_margin_inr: number;
  travel_rate_per_km_inr: number;
  minimum_service_charge_inr: number;
  labor_rate_per_hour_inr: number;
  default_labor_hours_per_solution: number;
  default_consumables_inr: number;
  default_miscellaneous_inr: number;
  emergency_surcharge_percent: number;
  weekend_surcharge_percent: number;
  gst_percent: number;
  round_off_rule: RoundOffRule;
  default_travel_km: number;
  /** When true, margin % applies to vendor product cost + services (sell prices unchanged on quote). */
  use_vendor_cost_for_margin: boolean;
}

/** Optional assessor overrides on the review quote. */
export interface QuoteInputs {
  travel_km?: number;
  labor_hours?: number;
  consumables_inr?: number;
  miscellaneous_inr?: number;
  apply_weekend_surcharge?: boolean;
  apply_emergency_surcharge?: boolean;
  margin_percent_override?: number;
}

export interface SafeHomeQuote {
  productTotalInr: number;
  laborHours: number;
  laborRatePerHourInr: number;
  laborTotalInr: number;
  travelKm: number;
  travelRatePerKmInr: number;
  travelTotalInr: number;
  consumablesInr: number;
  miscellaneousInr: number;
  serviceMinimumApplied: boolean;
  costSubtotalInr: number;
  weekendSurchargeInr: number;
  emergencySurchargeInr: number;
  marginType: MarginType;
  marginPercent: number;
  marginAmountInr: number;
  preTaxTotalInr: number;
  gstPercent: number;
  gstAmountInr: number;
  totalBeforeRoundInr: number;
  grandTotalInr: number;
  roundOffInr: number;
  /** Sum of selected vendor costs × qty (internal). */
  vendorProductCostInr: number | null;
  /** Sell product total minus vendor cost total (internal). */
  grossProductMarginInr: number | null;
}
