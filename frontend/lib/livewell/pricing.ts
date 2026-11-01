import { DEFAULT_SAFEHOME_PRICING } from "./pricing-defaults";
import type { MarginType, RoundOffRule, SafeHomePricingConfig } from "./pricing-types";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

const STORAGE_KEY = "safehome_home_safety_pricing_v1";
const LEGACY_STORAGE_KEYS = ["eldercare_home_safety_pricing_v1"];

const VALID_MARGIN_TYPES = new Set<MarginType>(["percent", "fixed"]);
const VALID_ROUND_OFF = new Set<RoundOffRule>(["none", "nearest_50", "nearest_100"]);

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function normalizePricingConfig(raw: Partial<SafeHomePricingConfig>): SafeHomePricingConfig {
  const marginType = VALID_MARGIN_TYPES.has(raw.margin_type as MarginType)
    ? (raw.margin_type as MarginType)
    : DEFAULT_SAFEHOME_PRICING.margin_type;
  const roundOff = VALID_ROUND_OFF.has(raw.round_off_rule as RoundOffRule)
    ? (raw.round_off_rule as RoundOffRule)
    : DEFAULT_SAFEHOME_PRICING.round_off_rule;

  return {
    default_margin_percent: clamp(
      Number(raw.default_margin_percent) || DEFAULT_SAFEHOME_PRICING.default_margin_percent,
      0,
      100,
    ),
    min_margin_percent: clamp(
      Number(raw.min_margin_percent) || DEFAULT_SAFEHOME_PRICING.min_margin_percent,
      0,
      100,
    ),
    max_margin_percent: clamp(
      Number(raw.max_margin_percent) || DEFAULT_SAFEHOME_PRICING.max_margin_percent,
      0,
      100,
    ),
    margin_type: marginType,
    fixed_margin_inr: Math.max(0, Number(raw.fixed_margin_inr) || 0),
    travel_rate_per_km_inr: Math.max(0, Number(raw.travel_rate_per_km_inr) || 0),
    minimum_service_charge_inr: Math.max(0, Number(raw.minimum_service_charge_inr) || 0),
    labor_rate_per_hour_inr: Math.max(0, Number(raw.labor_rate_per_hour_inr) || 0),
    default_labor_hours_per_solution: Math.max(
      0,
      Number(raw.default_labor_hours_per_solution) ||
        DEFAULT_SAFEHOME_PRICING.default_labor_hours_per_solution,
    ),
    default_consumables_inr: Math.max(0, Number(raw.default_consumables_inr) || 0),
    default_miscellaneous_inr: Math.max(0, Number(raw.default_miscellaneous_inr) || 0),
    emergency_surcharge_percent: clamp(
      Number(raw.emergency_surcharge_percent) || 0,
      0,
      100,
    ),
    weekend_surcharge_percent: clamp(
      Number(raw.weekend_surcharge_percent) || 0,
      0,
      100,
    ),
    gst_percent: clamp(Number(raw.gst_percent) || DEFAULT_SAFEHOME_PRICING.gst_percent, 0, 100),
    round_off_rule: roundOff,
    default_travel_km: Math.max(0, Number(raw.default_travel_km) || 0),
    use_vendor_cost_for_margin: Boolean(raw.use_vendor_cost_for_margin),
  };
}

export function getLocalPricingConfig(): SafeHomePricingConfig {
  if (typeof window === "undefined") return DEFAULT_SAFEHOME_PRICING;
  try {
    const raw = readLocalStorageWithLegacy(STORAGE_KEY, LEGACY_STORAGE_KEYS);
    if (!raw) return DEFAULT_SAFEHOME_PRICING;
    return normalizePricingConfig(JSON.parse(raw) as SafeHomePricingConfig);
  } catch {
    return DEFAULT_SAFEHOME_PRICING;
  }
}

export function saveLocalPricingConfig(config: SafeHomePricingConfig): SafeHomePricingConfig {
  const normalized = normalizePricingConfig(config);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-pricing-updated"));
  }
  return normalized;
}

export function resetLocalPricingConfig(): SafeHomePricingConfig {
  removeLocalStorageKeys(STORAGE_KEY, ...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-pricing-updated"));
  }
  return DEFAULT_SAFEHOME_PRICING;
}
