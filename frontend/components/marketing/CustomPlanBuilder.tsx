"use client";

import { useMemo, useState } from "react";

import { SAFETY_PRODUCTS } from "@/lib/marketing/products";
import { CALLBACK_PROMISE } from "@/lib/marketing/site-config";
import { EnquiryForm } from "./EnquiryForm";

/**
 * Custom plan enquiry.
 *
 * Families who don't fit a standard membership pick the care they actually want
 * — services, visit frequency, and any products — and send it in for a written
 * offer. The selections are composed into a structured message so whoever picks
 * it up can price it without a follow-up call to ask what was meant.
 *
 * Today this hands off over WhatsApp, the channel already used everywhere else
 * on this site. `buildEnquirySummary` returns the same structured payload a
 * future POST endpoint would take, so wiring it to the quote system later is a
 * change of transport, not of logic.
 */

const SERVICE_OPTIONS = [
  { id: "assessment", label: "Home safety assessment" },
  { id: "nursing", label: "Nursing visits" },
  { id: "physio", label: "Physiotherapy" },
  { id: "companion", label: "Companion visits" },
  { id: "medication", label: "Medication management" },
  { id: "doctor", label: "Doctor consultation" },
  { id: "emergency", label: "Emergency response / SOS" },
  { id: "attendant", label: "Full-time attendant" },
] as const;

const VISIT_OPTIONS = [
  { value: "none", label: "No regular visits" },
  { value: "1_month", label: "1 a month" },
  { value: "2_month", label: "2 a month" },
  { value: "weekly", label: "Weekly" },
  { value: "2_week", label: "Twice a week" },
  { value: "daily", label: "Daily" },
] as const;

export interface CustomPlanEnquiry {
  services: string[];
  visitFrequency: string;
  products: string[];
  city: string;
  notes: string;
}

/** Plain-text summary of the enquiry — also the future API payload. */
export function buildEnquirySummary(enquiry: CustomPlanEnquiry): string {
  const lines = ["Custom plan request", ""];
  lines.push(
    `Services: ${enquiry.services.length ? enquiry.services.join(", ") : "not specified"}`,
  );
  lines.push(`Visits: ${enquiry.visitFrequency || "not specified"}`);
  if (enquiry.products.length) lines.push(`Products: ${enquiry.products.join(", ")}`);
  if (enquiry.city) lines.push(`Area: ${enquiry.city}`);
  if (enquiry.notes) lines.push(`Notes: ${enquiry.notes}`);
  return lines.join("\n");
}

export function CustomPlanBuilder() {
  const [services, setServices] = useState<string[]>([]);
  const [visits, setVisits] = useState<string>("");
  const [chosenProducts, setChosenProducts] = useState<string[]>([]);
  const [notes, setNotes] = useState("");

  // The real products we fit, not catalog rows — same list as the section above.
  const productChoices = useMemo(() => SAFETY_PRODUCTS.map((p) => p.name), []);

  const enquiry: CustomPlanEnquiry = {
    services: services.map(
      (id) => SERVICE_OPTIONS.find((s) => s.id === id)?.label ?? id,
    ),
    visitFrequency: VISIT_OPTIONS.find((v) => v.value === visits)?.label ?? "",
    products: chosenProducts,
    city: "",
    notes,
  };

  const nothingChosen = services.length === 0 && !visits && chosenProducts.length === 0;
  function toggle(list: string[], set: (v: string[]) => void, value: string) {
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  return (
    <section className="mk-band" aria-labelledby="fm-custom-title" id="custom-plan">
      <div className="mk-wrap">
        <p className="mk-eyebrow">Custom plan</p>
        <h2 id="fm-custom-title">Build the plan your family actually needs</h2>
        <p className="mk-sub" style={{ marginBottom: "1.5rem" }}>
          Not every family fits a standard membership. Choose the care you want and send it
          across — we&rsquo;ll come back with a written offer and a clear price.
        </p>

        <div className="mk-custom-grid">
          <fieldset className="mk-fieldset">
            <legend>Which services do you need?</legend>
            <div className="mk-chip-set">
              {SERVICE_OPTIONS.map((s) => (
                <label
                  key={s.id}
                  className={services.includes(s.id) ? "mk-chip is-on" : "mk-chip"}
                >
                  <input
                    type="checkbox"
                    checked={services.includes(s.id)}
                    onChange={() => toggle(services, setServices, s.id)}
                  />
                  {s.label}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="mk-fieldset">
            <legend>How often should someone visit?</legend>
            <div className="mk-chip-set">
              {VISIT_OPTIONS.map((v) => (
                <label
                  key={v.value}
                  className={visits === v.value ? "mk-chip is-on" : "mk-chip"}
                >
                  <input
                    type="radio"
                    name="fm-visits"
                    checked={visits === v.value}
                    onChange={() => setVisits(v.value)}
                  />
                  {v.label}
                </label>
              ))}
            </div>
          </fieldset>

          {productChoices.length ? (
            <fieldset className="mk-fieldset">
              <legend>Any safety products you already have in mind?</legend>
              <div className="mk-chip-set">
                {productChoices.map((name) => (
                  <label
                    key={name}
                    className={chosenProducts.includes(name) ? "mk-chip is-on" : "mk-chip"}
                  >
                    <input
                      type="checkbox"
                      checked={chosenProducts.includes(name)}
                      onChange={() => toggle(chosenProducts, setChosenProducts, name)}
                    />
                    {name}
                  </label>
                ))}
              </div>
              <p className="mk-note">
                Optional — the assessment will recommend what the home actually needs.
              </p>
            </fieldset>
          ) : null}

          <div className="mk-field">
            <label className="mk-fieldset-label" htmlFor="fm-custom-notes">
              Anything else we should know?
            </label>
            <textarea
              id="fm-custom-notes"
              rows={3}
              value={notes}
              placeholder="Mobility, recent falls, who to contact, timing that suits you…"
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <div className="mk-form-card">
          <EnquiryForm
            kind="custom-plan"
            blocked={nothingChosen}
            blockedMessage="Pick at least one service, a visit frequency or a product above first."
            submitLabel="Send my custom plan"
            extras={{
              services: enquiry.services,
              visitFrequency: enquiry.visitFrequency,
              products: enquiry.products,
              notes: enquiry.notes,
            }}
            intro={
              <p className="mk-sub" style={{ marginTop: 0 }}>
                Leave your phone number or email. {CALLBACK_PROMISE} to talk through the plan you
                picked above, then send a written quote.
              </p>
            }
          />
        </div>
      </div>
    </section>
  );
}
