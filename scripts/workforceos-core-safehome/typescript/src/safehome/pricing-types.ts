/** SafeHome pricing config — shared shape (sheet 09_Pricing). */

export type SafeHomeMarginType = "percent" | "fixed";
export type SafeHomeRoundOffRule = "none" | "nearest_50" | "nearest_100";

export interface SafeHomePricingConfig {
  default_margin_percent: number;
  min_margin_percent: number;
  max_margin_percent: number;
  margin_type: SafeHomeMarginType;
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
  round_off_rule: SafeHomeRoundOffRule;
  default_travel_km: number;
  use_vendor_cost_for_margin: boolean;
}
