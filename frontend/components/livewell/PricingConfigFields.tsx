"use client";

import type { MarginType, RoundOffRule, SafeHomePricingConfig } from "@/lib/livewell/pricing-types";

export interface PricingConfigFieldsProps {
  config: SafeHomePricingConfig;
  onPatch: (partial: Partial<SafeHomePricingConfig>) => void;
  disabled?: boolean;
}

/** Shared pricing form — margin, labor, travel, GST, surcharges (sheet 09_Pricing). */
export function PricingConfigFields({ config, onPatch, disabled = false }: PricingConfigFieldsProps) {
  return (
    <>
      <section className="card home-safety-solutions-section">
        <h2 style={{ marginTop: 0 }}>Margin</h2>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Margin type
            <select
              value={config.margin_type}
              disabled={disabled}
              onChange={(e) => onPatch({ margin_type: e.target.value as MarginType })}
            >
              <option value="percent">Percentage</option>
              <option value="fixed">Fixed amount (₹)</option>
            </select>
          </label>
          <label className="home-safety-field">
            Default margin %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled || config.margin_type === "fixed"}
              value={config.default_margin_percent}
              onChange={(e) => onPatch({ default_margin_percent: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Fixed margin ₹
            <input
              type="number"
              min={0}
              disabled={disabled || config.margin_type === "percent"}
              value={config.fixed_margin_inr}
              onChange={(e) => onPatch({ fixed_margin_inr: Number(e.target.value) })}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Min margin %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled}
              value={config.min_margin_percent}
              onChange={(e) => onPatch({ min_margin_percent: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Max margin %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled}
              value={config.max_margin_percent}
              onChange={(e) => onPatch({ max_margin_percent: Number(e.target.value) })}
            />
          </label>
        </div>
      </section>

      <section className="card home-safety-solutions-section">
        <h2 style={{ marginTop: 0 }}>Labor &amp; travel</h2>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Labor rate ₹/hour
            <input
              type="number"
              min={0}
              disabled={disabled}
              value={config.labor_rate_per_hour_inr}
              onChange={(e) => onPatch({ labor_rate_per_hour_inr: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Default hours per solution
            <input
              type="number"
              min={0}
              step={0.5}
              disabled={disabled}
              value={config.default_labor_hours_per_solution}
              onChange={(e) =>
                onPatch({ default_labor_hours_per_solution: Number(e.target.value) })
              }
            />
          </label>
          <label className="home-safety-field">
            Minimum service charge ₹
            <input
              type="number"
              min={0}
              disabled={disabled}
              value={config.minimum_service_charge_inr}
              onChange={(e) => onPatch({ minimum_service_charge_inr: Number(e.target.value) })}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Travel rate ₹/km
            <input
              type="number"
              min={0}
              disabled={disabled}
              value={config.travel_rate_per_km_inr}
              onChange={(e) => onPatch({ travel_rate_per_km_inr: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Default travel km
            <input
              type="number"
              min={0}
              step={0.1}
              disabled={disabled}
              value={config.default_travel_km}
              onChange={(e) => onPatch({ default_travel_km: Number(e.target.value) })}
            />
          </label>
        </div>
      </section>

      <section className="card home-safety-solutions-section">
        <h2 style={{ marginTop: 0 }}>Charges &amp; tax</h2>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Default consumables ₹
            <input
              type="number"
              min={0}
              disabled={disabled}
              value={config.default_consumables_inr}
              onChange={(e) => onPatch({ default_consumables_inr: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Default miscellaneous ₹
            <input
              type="number"
              min={0}
              disabled={disabled}
              value={config.default_miscellaneous_inr}
              onChange={(e) => onPatch({ default_miscellaneous_inr: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            GST %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled}
              value={config.gst_percent}
              onChange={(e) => onPatch({ gst_percent: Number(e.target.value) })}
            />
          </label>
        </div>
        <div className="home-safety-field-row">
          <label className="home-safety-field">
            Weekend surcharge %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled}
              value={config.weekend_surcharge_percent}
              onChange={(e) => onPatch({ weekend_surcharge_percent: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Emergency surcharge %
            <input
              type="number"
              min={0}
              max={100}
              disabled={disabled}
              value={config.emergency_surcharge_percent}
              onChange={(e) => onPatch({ emergency_surcharge_percent: Number(e.target.value) })}
            />
          </label>
          <label className="home-safety-field">
            Round-off rule
            <select
              value={config.round_off_rule}
              disabled={disabled}
              onChange={(e) => onPatch({ round_off_rule: e.target.value as RoundOffRule })}
            >
              <option value="none">None</option>
              <option value="nearest_50">Nearest ₹50</option>
              <option value="nearest_100">Nearest ₹100</option>
            </select>
          </label>
        </div>
      </section>

      <section className="card home-safety-solutions-section" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ marginTop: 0 }}>Margin basis</h2>
        <label className="home-safety-field home-safety-profile-checks">
          <span>
            Use vendor product cost for margin % (customer sell prices unchanged)
          </span>
          <input
            type="checkbox"
            disabled={disabled}
            checked={config.use_vendor_cost_for_margin}
            onChange={(e) => onPatch({ use_vendor_cost_for_margin: e.target.checked })}
          />
        </label>
        <p className="muted" style={{ marginBottom: 0 }}>
          When enabled, margin is calculated on preferred/lowest vendor cost + labor/travel.
          Product line items on the customer quote still use catalog sell prices.
        </p>
      </section>
    </>
  );
}
