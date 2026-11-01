"use client";

import Link from "next/link";
import { PA_ICONS } from "@/components/ops/PageActions";
import { PageHeader } from "@/components/PageHeader";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Flash } from "@/components/Flash";
import { currentMonthIST, downloadExport, getOwnerDashboard, inr, type OwnerDashboard } from "@/lib/business";
import "@/components/ops/business.css";
import { isAdmin as isAdminUser } from "@/lib/roles";
import { AiUsageCard } from "@/components/ops/AiUsageCard";
import { BackupWarning } from "@/components/ops/BackupStatusBadge";
import { plural } from "@/lib/run-sheet";

const STATUS_WORDS: Record<string, string> = {
  pending_approval: "Waiting for approval",
  approved: "Approved",
  quoted: "Sent to family",
  family_accepted: "Paid, to book",
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

/** "DELIVERED" / "in_progress" → "Delivered" / "In progress" for statuses not in the list above. */
function plainStatus(s: string): string {
  const t = s.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** "2026-10" → "October 2026". */
function monthWords(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  if (!y || !m) return ym;
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

/** The last 24 months, newest first, as "YYYY-MM" (the native month box shows "October, 2026"). */
function recentMonths(latest: string, count = 24, earliest?: string | null): string[] {
  const [y, m] = latest.split("-").map(Number);
  const out: string[] = [];
  for (let i = 0; i < count && y && m; i++) {
    const d = new Date(y, m - 1 - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (earliest && key < earliest) break;
    out.push(key);
  }
  return out.length ? out : [latest];
}

const pct = (v: number | null) => (v == null ? "—" : `${v}%`);

/** Owner dashboard (admins): money, visits, safety and clients for one IST month. */
export default function OwnerDashboardPage() {
  const router = useRouter();
  const isAdmin = isAdminUser();
  const [month, setMonth] = useState(currentMonthIST());
  const [data, setData] = useState<OwnerDashboard | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!isAdmin) {
      router.replace("/unauthorized");
      return;
    }
    setData(null);
    getOwnerDashboard(month)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [month, isAdmin, router]);

  async function exportCsv(kind: string) {
    setBusy(kind);
    try {
      await downloadExport(kind, month);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setBusy("");
    }
  }

  if (!isAdmin) return null;
  const d = data;

  return (
    <div className="ks-frame">
      <div className="ks-head-row">
        <PageHeader title="Owner dashboard" subtitle="How the business did this month" />
        <div className="ks-head-actions">
          <button
            type="button"
            className="secondary"
            onClick={() => router.push("/kushalaya/invoices")}
            aria-label="Invoices"
            title="Invoices"
          >
            <span className="ks-ha-icon" aria-hidden="true">{PA_ICONS.invoice}</span>
            <span className="ks-ha-label">Invoices</span>
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => router.push("/settings/business")}
            aria-label="Business details"
            title="Business details"
          >
            <span className="ks-ha-icon" aria-hidden="true">{PA_ICONS.building}</span>
            <span className="ks-ha-label">Business details</span>
          </button>
        </div>
      </div>
      <BackupWarning />
      <div className="od-filter-row">
        <label className="od-month">
          Month
          <select value={month} onChange={(e) => setMonth(e.target.value)}>
            {recentMonths(currentMonthIST(), 24, data?.first_month).map((m) => (
              <option key={m} value={m}>
                {monthWords(m)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Flash error={error} message="" onClear={() => setError("")} />

      {d && !d.gst_registered && (
        <p className="card od-banner" role="note">
          <strong>No GSTIN yet.</strong> Payments get a “Bill of supply / receipt” without GST.{" "}
          <Link href="/settings/business" className="ks-link">Add the GSTIN</Link> to issue GST tax invoices.
        </p>
      )}

      {!d ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <div className="od-grid">
            <section className="card od-card">
              <h2>Cash collected</h2>
              <span className="od-big">{inr(d.cash.this_month_paise)}</span>
              <p className="od-sub">Last month {inr(d.cash.last_month_paise)} · wallet top-ups</p>
              <p className="od-sub">Invoiced (less credit notes) {inr(d.cash.billed_paise)}</p>
            </section>
            <section className="card od-card">
              <h2>Outstanding dues</h2>
              <span className="od-big">{inr(d.dues.total_paise)}</span>
              <ul className="od-rows">
                {d.dues.aging.map((a) => (
                  <li key={a.bucket}>
                    <span>{a.bucket} days ({a.count})</span>
                    <span>{inr(a.amount_paise)}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card od-card">
              <h2>Orders this month</h2>
              {d.pipeline.length === 0 ? (
                <p className="od-sub">No orders yet.</p>
              ) : (
                <ul className="od-rows">
                  {d.pipeline.map((p) => (
                    <li key={p.status}>
                      <span>{STATUS_WORDS[p.status] || plainStatus(p.status)} ({p.count})</span>
                      <span>{inr(p.amount_paise)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="card od-card">
              <h2>Gross margin</h2>
              <span className="od-big">{d.margin.margin_bp == null ? "—" : `${(d.margin.margin_bp / 100).toFixed(1)}%`}</span>
              <p className="od-sub">
                {inr(d.margin.margin_paise)} on {inr(d.margin.revenue_paise)} · {d.margin.orders} paid orders, before GST
              </p>
            </section>
            <section className="card od-card">
              <h2>Visits</h2>
              <span className="od-big">{d.visits.done} / {d.visits.planned}</span>
              <p className="od-sub">done of planned · {d.visits.missed} missed · {d.visits.cancelled} cancelled</p>
            </section>
            <section className="card od-card">
              <h2>SOS acknowledge time</h2>
              <span className="od-big">{d.sos.median_ack_minutes == null ? "—" : `${d.sos.median_ack_minutes} min`}</span>
              <p className="od-sub">median · {d.sos.acknowledged} of {plural(d.sos.alerts, "alert")} acknowledged</p>
            </section>
            <section className="card od-card">
              <h2>Reassessment compliance</h2>
              <span className="od-big">{pct(d.reassessment.percent)}</span>
              <p className="od-sub">{d.reassessment.in_date} of {d.reassessment.active_clients} active clients assessed in the last 6 months</p>
            </section>
            <section className="card od-card">
              <h2>Staff utilisation</h2>
              <span className="od-big">{pct(d.utilisation.percent)}</span>
              <p className="od-sub">
                {d.utilisation.visit_hours} visit hours of {d.utilisation.available_hours} available · {plural(d.utilisation.caregivers, "caregiver")}
              </p>
            </section>
            <section className="card od-card">
              <h2>Clients</h2>
              <span className="od-big">{d.clients.active} active</span>
              <p className="od-sub">
                {d.clients.new} new · {d.clients.churned} left this month
              </p>
            </section>
            <section className="card od-card">
              <h2>Family satisfaction</h2>
              {d.satisfaction.available ? (
                <>
                  <span className="od-big">
                    {d.satisfaction.average_rating == null ? "—" : `${d.satisfaction.average_rating} / 5`}
                  </span>
                  <p className="od-sub">
                    {plural(d.satisfaction.ratings, "visit rating")} · {plural(d.satisfaction.nps_responses, "reply", "replies")}
                  </p>
                  <p className="od-sub">
                    Family recommend score:{" "}
                    {d.satisfaction.nps == null
                      ? "no answers yet"
                      : `${d.satisfaction.nps} (how many families would recommend us, minus those who would not; above 30 is good)`}
                  </p>
                </>
              ) : (
                <p className="od-sub">{d.satisfaction.message}</p>
              )}
            </section>
            <AiUsageCard />
          </div>

          <section className="card">
            <h2>Monthly exports</h2>
            <p className="muted">CSV files for {monthWords(d.month)}. Open in Excel or send to your accountant.</p>
            <div className="od-exports">
              {d.exports.map((x) => (
                <button key={x.key} type="button" className="secondary" disabled={!!busy} onClick={() => exportCsv(x.key)}>
                  {busy === x.key ? "Preparing…" : x.label}
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
