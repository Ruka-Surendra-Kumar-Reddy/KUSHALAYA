"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ElderProspect } from "@/lib/prospects";
import { areaContradictsPin, landingPageLabel, leadSourceLabel, splitLeadNotes } from "@/lib/lead-labels";

type FunnelRow = { month: string; NEW: number; CONTACTED: number; ASSESSMENT_BOOKED: number; CLIENT: number };
type Funnel = {
  steps: string[];
  months: FunnelRow[];
  totals: Omit<FunnelRow, "month">;
  sources: { source: string; count: number }[];
  excluded_closed?: number;
};

const LABELS: Record<string, string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  ASSESSMENT_BOOKED: "Assessment booked",
  CLIENT: "Client",
};

function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

/** Leads by the month they arrived: New → Contacted → Assessment booked → Client (FIX 107). */
export function LeadFunnel() {
  const [data, setData] = useState<Funnel | null>(null);
  const [withClosed, setWithClosed] = useState(false);
  useEffect(() => {
    api<Funnel>(`/api/v1/prospects/funnel?months=6${withClosed ? "&include_closed=true" : ""}`)
      .then(setData)
      .catch(() => setData(null));
  }, [withClosed]);
  if (!data) return null;
  const steps = data.steps as (keyof Omit<FunnelRow, "month">)[];
  return (
    <section className="card" aria-label="Lead funnel" style={{ marginBottom: "1rem" }}>
      <h3 style={{ marginTop: 0 }}>Lead funnel (last 6 months)</h3>
      <div style={{ overflowX: "auto" }}>
        {/* On phones each month is a small card (ks-shell.css, .ks-funnel). */}
        <table className="table ks-funnel">
          <thead>
            <tr>
              <th>Month</th>
              {steps.map((s) => (
                <th key={s}>{LABELS[s] || s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.months.map((r) => (
              <tr key={r.month}>
                <td className="ks-funnel-month">{monthLabel(r.month)}</td>
                {steps.map((s) => (
                  <td key={s} data-label={LABELS[s] || s}>{r[s]}</td>
                ))}
              </tr>
            ))}
            <tr className="is-total">
              <td className="ks-funnel-month">
                <strong>Total</strong>
              </td>
              {steps.map((s) => (
                <td key={s} data-label={LABELS[s] || s}>
                  <strong>{data.totals[s]}</strong>
                  {s !== "NEW" && data.totals.NEW ? (
                    <span className="muted"> ({Math.round((100 * data.totals[s]) / data.totals.NEW)}%)</span>
                  ) : null}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {data.excluded_closed || withClosed ? (
        <label className="muted ks-funnel-closed">
          <input type="checkbox" checked={withClosed} onChange={(e) => setWithClosed(e.target.checked)} />
          Include closed and archived leads{!withClosed && data.excluded_closed ? ` (${data.excluded_closed} left out)` : ""}
        </label>
      ) : null}
      {data.sources.length ? (
        <p className="muted" style={{ fontSize: "0.85rem", marginBottom: 0 }}>
          Where leads came from:{" "}
          {data.sources.map((s, i) => (
            <span key={s.source}>
              {i ? " · " : ""}
              {leadSourceLabel(s.source)} {s.count}
            </span>
          ))}
        </p>
      ) : null}
    </section>
  );
}

/** Website lead details on the selected prospect: source, referrer, PIN code, requested slot. */
export function LeadDetails({ p, withNotes = false }: { p: ElderProspect; withNotes?: boolean }) {
  const rows: [string, string][] = [];
  const notes = withNotes ? splitLeadNotes(p.notes) : { fields: [] as [string, string][], rest: "" };
  for (const [k, v] of notes.fields) {
    // A typed area that can't be where the PIN is (e.g. Hyderabad + a Jamshedpur PIN) is not shown as fact.
    if (k === "Area" && areaContradictsPin(v, p.pincode)) rows.push(["Area", `Area not set (typed “${v}”, PIN ${p.pincode})`]);
    else rows.push([k === "For" ? "For whom" : k, v]);
  }
  if (p.lead_source) rows.push(["Source", leadSourceLabel(p.lead_source)]);
  if (p.referred_by) rows.push(["Referred by", `${p.referred_by} (${p.referral_code})`]);
  if (p.utm_source || p.utm_campaign)
    rows.push(["Campaign", [p.utm_source, p.utm_medium, p.utm_campaign].filter(Boolean).join(" / ")]);
  if (p.referrer_url) rows.push(["Came from", p.referrer_url]);
  if (p.landing_page) rows.push(["First page seen", landingPageLabel(p.landing_page)]);
  if (p.pincode) rows.push(["PIN code", `${p.pincode} — ${p.area_served ? "in an area we serve" : "not in our service areas yet — check before booking"}`]);
  if (p.assessment_slot) {
    const fee = p.assessment_fee_paise ? ` · ₹${(p.assessment_fee_paise / 100).toLocaleString("en-IN")} ${p.assessment_paid ? "paid" : "not paid"}` : "";
    rows.push(["Asked for visit", p.assessment_slot + fee]);
  }
  if (!rows.length) return notes.rest ? <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{notes.rest}</p> : null;
  return (
    <div style={{ margin: "0.75rem 0" }}>
      <h4 style={{ margin: "0 0 0.35rem" }}>Lead</h4>
      <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.2rem 0.75rem", margin: 0, fontSize: "0.9rem" }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}>
            <dt className="muted">{k}</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{v}</dd>
          </div>
        ))}
      </dl>
      {notes.rest ? <p style={{ whiteSpace: "pre-wrap", margin: "0.5rem 0 0" }}>{notes.rest}</p> : null}
    </div>
  );
}
