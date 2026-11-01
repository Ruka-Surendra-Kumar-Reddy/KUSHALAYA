"use client";

/**
 * Client profile → Overview (opened from the Customer ID): summary tiles, the
 * customer's details with quick actions, care manager, visits used against the
 * plan, services the plan covers, and recent active / closed requests.
 * Data: the profile already loaded by the page, its visits, and /sales/customers/{id}/plans.
 */
import { useCallback, useEffect, useState } from "react";
import { carePlan, inr } from "@/lib/care-plan-catalog";
import { can } from "@/lib/roles";
import {
  CYCLE_LABEL,
  PLAN_STATUS_LABEL,
  customerCode,
  customerPlans,
  splitRequests,
  visitsIncluded,
  visitsUsed,
  type CustomerPlan,
  type RequestRow,
} from "@/lib/sales-pipeline";
import { AssignPlanDialog, dayLabel } from "@/components/ops/CustomerPlanParts";
import type { ClientProfile } from "@/lib/livewell/clientProfileApi";
import type { CareJob } from "@/lib/jobs";
import "@/components/ops/sales.css";

export type OverviewTab = "Details" | "Plan & payments" | "Visits & requests" | "SOS & alerts";

/** wa.me number: digits only, 10-digit Indian mobiles get 91. */
export function whatsappDigits(phone: string): string {
  const d = phone.replace(/\D/g, "");
  return d.length === 10 ? `91${d}` : d;
}

function RequestsTable({ title, rows, beneficiary }: { title: string; rows: RequestRow[]; beneficiary: string }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {rows.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <div className="cp-table-wrap">
          <table className="cp-table sp-table">
            <thead>
              <tr>
                <th>Request ID</th>
                <th>Beneficiary</th>
                <th>Date</th>
                <th>Service</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td>{r.id}</td>
                  <td>{beneficiary}</td>
                  <td>{dayLabel(r.date)}</td>
                  <td className="sp-wrap">{r.service}</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function CustomerOverview({
  data,
  jobs,
  onTab,
}: {
  data: ClientProfile;
  jobs: CareJob[];
  onTab: (t: OverviewTab) => void;
}) {
  const p = data.person;
  const name = `${p.first_name} ${p.last_name}`.trim();
  const edit = can("edit");
  const [plan, setPlan] = useState<CustomerPlan | null | undefined>(undefined);
  const [assigning, setAssigning] = useState(false);
  const load = useCallback(() => {
    customerPlans(p.id)
      .then((r) => setPlan(r.current))
      .catch(() => setPlan(null));
  }, [p.id]);
  useEffect(() => load(), [load]);

  const family = data.family.find((f) => f.is_primary) || data.family[0];
  const phone = (p.emergency_contact_phone || p.phone || "").trim();
  const def = plan ? carePlan(plan.plan_id) : undefined;
  const included = plan ? visitsIncluded(plan.plan_id, plan.billing_cycle) : 0;
  const used = visitsUsed(jobs, plan ?? null);
  const { active, closed } = splitRequests(data.service_requests, jobs);
  const openRequests = data.service_requests.filter((r) => ["requested", "confirmed"].includes(String(r.status || "requested"))).length;
  const watch = data.devices.length > 0;
  const canAssign = edit && plan !== undefined && (!plan || plan.status === "expired" || plan.status === "cancelled");

  return (
    <div className="sp-overview">
      <div className="sp-tiles" role="list">
        <button type="button" role="listitem" className="sp-tile" onClick={() => onTab("Plan & payments")}>
          <span className="sp-tile-label">Plan & payments</span>
          <strong>{plan ? inr(plan.amount_paise) : plan === null ? "No plan" : "…"}</strong>
          <span className="muted">
            {plan ? `${plan.payment_status === "paid" ? "Paid" : "Unpaid"} · ${PLAN_STATUS_LABEL[plan.status]}` : ""}
          </span>
        </button>
        <button type="button" role="listitem" className="sp-tile" onClick={() => onTab("Visits & requests")}>
          <span className="sp-tile-label">Visits used</span>
          <strong>{plan ? `${used} / ${included}` : "—"}</strong>
          <span className="muted">{plan ? "this plan period" : "No plan"}</span>
        </button>
        <button type="button" role="listitem" className="sp-tile" onClick={() => onTab("Visits & requests")}>
          <span className="sp-tile-label">Open requests</span>
          <strong>{openRequests}</strong>
          <span className="muted">from the family</span>
        </button>
        <button type="button" role="listitem" className="sp-tile" onClick={() => onTab("Details")}>
          <span className="sp-tile-label">Beneficiary</span>
          <strong className="sp-tile-name">{name}</strong>
          <span className="muted">Full details →</span>
        </button>
        <div role="listitem" className="sp-tile">
          <span className="sp-tile-label">Care manager</span>
          <strong className="sp-tile-name">{data.manager_name || "Not assigned"}</strong>
        </div>
      </div>

      <section className="card sp-cust">
        <div className="sp-cust-main">
          <h2>
            {customerCode(p.id)} · {family ? family.name : name}
          </h2>
          <dl className="sp-lead-facts">
            <div>
              <dt>Contact</dt>
              <dd>
                {family ? `${family.name}${family.relationship ? ` (${family.relationship})` : ""}` : p.emergency_contact_name || "—"}
                {family?.email ? <div className="muted">{family.email}</div> : null}
              </dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{phone || "—"}</dd>
            </div>
            <div>
              <dt>Address</dt>
              <dd>{p.address || "—"}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                {p.status ? p.status.charAt(0) + p.status.slice(1).toLowerCase() : "—"}
                {plan ? ` · plan ${PLAN_STATUS_LABEL[plan.status].toLowerCase()}` : ""}
              </dd>
            </div>
          </dl>
        </div>
        <div className="sp-cust-actions">
          {phone ? (
            <a className="secondary sp-btn" href={`tel:${phone.replace(/[^+\d]/g, "")}`}>
              Call
            </a>
          ) : null}
          {phone ? (
            <a className="secondary sp-btn" href={`https://wa.me/${whatsappDigits(phone)}`} target="_blank" rel="noopener noreferrer">
              WhatsApp
            </a>
          ) : null}
          {canAssign ? (
            <button type="button" onClick={() => setAssigning(true)}>
              Assign plan
            </button>
          ) : null}
          <button type="button" className="secondary" onClick={() => onTab("SOS & alerts")}>
            SOS watch: {watch ? "linked" : "not linked"}
          </button>
        </div>
      </section>

      <div className="cp-cols">
        <section className="card">
          <h2>Care manager</h2>
          <p>{data.manager_name || "No care manager yet."}</p>
          <button type="button" className="cp-linkbtn" onClick={() => onTab("Details")}>
            Care team and details →
          </button>
        </section>
        <section className="card">
          <h2>Visits utilized</h2>
          {plan ? (
            <>
              <p>
                <strong>{used}</strong> of {included} visits used · {Math.max(0, included - used)} left
              </p>
              <div className="sp-meter" role="meter" aria-valuemin={0} aria-valuemax={included} aria-valuenow={used} aria-label="Visits used">
                <span style={{ width: `${included ? Math.min(100, (used / included) * 100) : 0}%` }} />
              </div>
              <p className="muted">
                {plan.plan_name} · {CYCLE_LABEL[plan.billing_cycle]} · {dayLabel(plan.start_date)} to {dayLabel(plan.end_date)}
              </p>
            </>
          ) : (
            <p className="muted">No plan yet.</p>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Services covered</h2>
        {def ? (
          <ul className="sp-inclusions">
            {def.inclusions.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Assign a plan to see what it covers.</p>
        )}
      </section>

      <div className="cp-cols">
        <RequestsTable title="Recent active requests" rows={active} beneficiary={name} />
        <RequestsTable title="Recent closed requests" rows={closed} beneficiary={name} />
      </div>

      {assigning ? (
        <AssignPlanDialog
          elderId={p.id}
          name={name}
          onClose={() => setAssigning(false)}
          onDone={() => {
            setAssigning(false);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
