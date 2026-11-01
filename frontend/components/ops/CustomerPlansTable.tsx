"use client";

/** Customers → Plans table: Customer ID, name, plan, billing, dates, amount, paid,
 *  status, care manager; search, status filter, CSV download, and the
 *  "Pending approval" queue with Authorize (admins) and Mark paid. */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { inr } from "@/lib/care-plan-catalog";
import { can } from "@/lib/roles";
import {
  CYCLE_LABEL,
  PLAN_STATUS_LABEL,
  customerMatchesStatus,
  customersCsv,
  downloadCsv,
  filterCustomers,
  isoDay,
  listCustomers,
  sourceLabel,
  type CustomerPlan,
  type CustomerRow,
  type PendingPlan,
} from "@/lib/sales-pipeline";
import { AssignPlanDialog, PaymentDialog, dayLabel } from "@/components/ops/CustomerPlanParts";

const STATUS_FILTERS = [
  ["all", "All"],
  ["pending_approval", "Pending approval"],
  ["active", "Active"],
  ["expired", "Expired"],
  ["cancelled", "Cancelled"],
  ["none", "No plan"],
  ["unpaid", "Unpaid"],
  ["ending30", "Ending in 30 days"],
] as const;

type Pay = { plan: CustomerPlan; name: string; mode: "authorize" | "paid" };

export function StatusPill({ status }: { status: CustomerRow["status"] }) {
  return <span className={`sp-pill is-${status}`}>{PLAN_STATUS_LABEL[status]}</span>;
}

export function CustomerPlansTable({ onMessage, viewSwitch }: { onMessage: (m: string) => void; viewSwitch?: React.ReactNode }) {
  const edit = can("edit");
  const admin = can("admin");
  const [data, setData] = useState<{ customers: CustomerRow[]; pending: PendingPlan[] } | null>(null);
  const [error, setError] = useState("");
  const [status, setStatusState] = useState("all");
  // ?status=pending_approval etc. (Dashboard tiles), kept in the URL as it changes.
  useEffect(() => {
    const st = new URLSearchParams(window.location.search).get("status");
    if (st && STATUS_FILTERS.some(([k]) => k === st)) setStatusState(st);
  }, []);
  const setStatus = useCallback((st: string) => {
    setStatusState(st);
    const url = new URL(window.location.href);
    if (st === "all") url.searchParams.delete("status");
    else url.searchParams.set("status", st);
    window.history.replaceState(window.history.state, "", url.toString());
  }, []);
  const [query, setQuery] = useState("");
  const [assign, setAssign] = useState<CustomerRow | null>(null);
  const [pay, setPay] = useState<Pay | null>(null);

  const load = useCallback(() => {
    listCustomers()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load customers"));
  }, []);
  useEffect(() => load(), [load]);

  const shown = useMemo(() => filterCustomers(data?.customers ?? [], status, query), [data, status, query]);
  const today = isoDay(new Date());
  const count = (s: string) => (data?.customers ?? []).filter((r) => customerMatchesStatus(r, s, today)).length;

  return (
    <section className="sp-customers">
      {error ? <p className="error-text">{error}</p> : null}

      {data && data.pending.length ? (
        <div className="card sp-pending" aria-label="Plans pending approval">
          <h2>Pending approval ({data.pending.length})</h2>
          <div className="cp-table-wrap">
            <table className="cp-table sp-table">
              <thead>
                <tr>
                  <th>Customer ID</th>
                  <th>Customer</th>
                  <th>Plan</th>
                  <th>Start</th>
                  <th>End</th>
                  <th className="cp-num">Amount</th>
                  <th>Payment</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.pending.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link className="ks-link" href={`/kushalaya/customers/${p.elder_id}`}>
                        {p.customer_id}
                      </Link>
                    </td>
                    <td>
                      <Link className="ks-link" href={`/kushalaya/customers/${p.elder_id}?tab=details`}>
                        {p.name}
                      </Link>
                    </td>
                    <td>
                      {p.plan_name} · {CYCLE_LABEL[p.billing_cycle]}
                    </td>
                    <td>{dayLabel(p.start_date)}</td>
                    <td>{dayLabel(p.end_date)}</td>
                    <td className="cp-num">{inr(p.amount_paise)}</td>
                    <td>{p.payment_status === "paid" ? "Paid" : "Unpaid"}</td>
                    <td className="sp-row-actions">
                      {admin ? (
                        <button type="button" onClick={() => setPay({ plan: p, name: p.name, mode: "authorize" })}>
                          Authorize
                        </button>
                      ) : (
                        <span className="muted">Waiting for an admin</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="cl-bar sp-bar">
        <input
          aria-label="Search customer ID, name, phone or plan"
          type="search"
          placeholder="Search customer ID, name, phone or plan"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="sp-inline">
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUS_FILTERS.map(([k, label]) => (
              <option key={k} value={k}>
                {label}
                {data ? ` (${count(k)})` : ""}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="secondary"
          disabled={!shown.length}
          onClick={() => downloadCsv(`kushalaya-customers-${isoDay(new Date())}.csv`, customersCsv(shown))}
        >
          Download CSV
        </button>
        {viewSwitch ? <div className="sp-bar-end">{viewSwitch}</div> : null}
      </div>

      {data === null ? (
        <p className="muted">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="muted">No matching customers.</p>
      ) : (
        <div className="cp-table-wrap">
          <table className="cp-table sp-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Contact</th>
                <th>Plan</th>
                <th>Period</th>
                <th>Payment</th>
                <th>Status</th>
                <th>Care manager</th>
                {edit ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const p = r.plan;
                return (
                  <tr key={r.elder_id}>
                    {/* Related details share a cell so the table fits without sideways scrolling. */}
                    <td>
                      <Link className="ks-link sp-cell-main" href={`/kushalaya/customers/${r.elder_id}?tab=details`}>
                        {r.name}
                      </Link>
                      <span className="sp-cell-sub">
                        <Link className="ks-link" href={`/kushalaya/customers/${r.elder_id}`}>
                          {r.customer_id}
                        </Link>
                        {r.device_linked ? <span className="sp-tag">SOS watch</span> : null}
                      </span>
                    </td>
                    <td>
                      <span className="sp-cell-main">{r.phone || "—"}</span>
                      <span className="sp-cell-sub">
                        {[r.city, r.referred_by ? `via ${sourceLabel(r.referred_by)}` : ""].filter(Boolean).join(" · ") || " "}
                      </span>
                    </td>
                    <td>
                      {p ? (
                        <>
                          <span className="sp-cell-main">{p.plan_name.replace(/^KushAlaya /, "")}</span>
                          <span className="sp-cell-sub">{CYCLE_LABEL[p.billing_cycle]}</span>
                        </>
                      ) : (
                        <span className="muted">No plan yet</span>
                      )}
                    </td>
                    <td>
                      {p ? (
                        <>
                          <span className="sp-cell-main">{dayLabel(p.start_date)}</span>
                          <span className="sp-cell-sub">to {dayLabel(p.end_date)}</span>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {p ? (
                        <>
                          <span className="sp-cell-main">{inr(p.amount_paise)}</span>
                          <span className={`sp-pill is-${p.payment_status}`}>{p.payment_status === "paid" ? "Paid" : "Unpaid"}</span>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{p ? <StatusPill status={r.status} /> : <span className="muted">—</span>}</td>
                    <td>{r.care_manager || <span className="muted">Not assigned</span>}</td>
                    {edit ? (
                      <td className="sp-row-actions">
                        {!p || p.status === "expired" || p.status === "cancelled" ? (
                          <button type="button" className="secondary" onClick={() => setAssign(r)}>
                            Assign plan
                          </button>
                        ) : null}
                        {p && p.status === "pending_approval" && admin ? (
                          <button type="button" onClick={() => setPay({ plan: p, name: r.name, mode: "authorize" })}>
                            Authorize
                          </button>
                        ) : null}
                        {p && p.payment_status === "unpaid" && p.status !== "cancelled" ? (
                          <button type="button" className="secondary" onClick={() => setPay({ plan: p, name: r.name, mode: "paid" })}>
                            Mark paid
                          </button>
                        ) : null}
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {assign ? (
        <AssignPlanDialog
          elderId={assign.elder_id}
          name={assign.name}
          onClose={() => setAssign(null)}
          onDone={(p) => {
            setAssign(null);
            onMessage(`${p.plan_name} added for ${assign.name}. It is waiting for approval.`);
            load();
          }}
        />
      ) : null}
      {pay ? (
        <PaymentDialog
          plan={pay.plan}
          name={pay.name}
          mode={pay.mode}
          onClose={() => setPay(null)}
          onDone={(p) => {
            setPay(null);
            onMessage(pay.mode === "authorize" ? `${pay.name}: ${p.plan_name} is now active.` : `${pay.name}: marked paid.`);
            load();
          }}
        />
      ) : null}
    </section>
  );
}
