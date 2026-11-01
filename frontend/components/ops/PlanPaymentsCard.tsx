"use client";

/** Client profile → Plan & payments: current care plan, its history and amounts,
 *  with Assign plan / Authorize (admins) / Mark paid. */
import { useCallback, useEffect, useState } from "react";
import { inr } from "@/lib/care-plan-catalog";
import { can } from "@/lib/roles";
import { CYCLE_LABEL, couponNote, customerPlans, type CustomerPlan } from "@/lib/sales-pipeline";
import { AssignPlanDialog, PaymentDialog, dayLabel, payModeLabel } from "@/components/ops/CustomerPlanParts";
import { StatusPill } from "@/components/ops/CustomerPlansTable";

type Data = Awaited<ReturnType<typeof customerPlans>>;

export function PlanPaymentsCard({ elderId, name }: { elderId: number; name: string }) {
  const edit = can("edit");
  const admin = can("admin");
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [pay, setPay] = useState<{ plan: CustomerPlan; mode: "authorize" | "paid" } | null>(null);

  const load = useCallback(() => {
    customerPlans(elderId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the plan"));
  }, [elderId]);
  useEffect(() => load(), [load]);

  const cur = data?.current ?? null;
  const canAssign = edit && (!cur || cur.status === "expired" || cur.status === "cancelled");
  return (
    <section className="card sp-plan-card">
      <div className="sp-plan-head">
        <h2>Care plan {data ? <span className="muted">· {data.customer_id}</span> : null}</h2>
        {canAssign ? (
          <button type="button" onClick={() => setAssigning(true)}>
            {cur ? "Assign a new plan" : "Assign plan"}
          </button>
        ) : null}
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {message ? (
        <p className="sp-ok" role="status">
          {message}
        </p>
      ) : null}
      {data === null ? (
        <p className="muted">Loading…</p>
      ) : !cur ? (
        <p className="muted">No plan yet.</p>
      ) : (
        <>
          <dl className="sp-plan-now">
            <div>
              <dt>Plan</dt>
              <dd>
                <strong>{cur.plan_name}</strong> · {CYCLE_LABEL[cur.billing_cycle]}
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <StatusPill status={cur.status} />
              </dd>
            </div>
            <div>
              <dt>Dates</dt>
              <dd>
                {dayLabel(cur.start_date)} to {dayLabel(cur.end_date)}
              </dd>
            </div>
            <div>
              <dt>Amount</dt>
              <dd>
                {inr(cur.amount_paise)}
                {couponNote(cur)} · {cur.payment_status === "paid" ? `Paid (${payModeLabel(cur.payment_mode)})` : "Unpaid"}
              </dd>
            </div>
            {cur.authorized_by_name ? (
              <div>
                <dt>Authorized</dt>
                <dd>
                  {cur.authorized_by_name} · {dayLabel(cur.authorized_at)}
                </dd>
              </div>
            ) : null}
          </dl>
          {edit ? (
            <div className="sp-row-actions">
              {cur.status === "pending_approval" && admin ? (
                <button type="button" onClick={() => setPay({ plan: cur, mode: "authorize" })}>
                  Authorize
                </button>
              ) : null}
              {cur.status === "pending_approval" && !admin ? <span className="muted">Waiting for an admin to authorize.</span> : null}
              {cur.payment_status === "unpaid" && cur.status !== "cancelled" ? (
                <button type="button" className="secondary" onClick={() => setPay({ plan: cur, mode: "paid" })}>
                  Mark paid
                </button>
              ) : null}
            </div>
          ) : null}
          {data.plans.length > 1 ? (
            <>
              <h3 className="sp-sub">Plan history</h3>
              <div className="cp-table-wrap">
                <table className="cp-table sp-table">
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Billing</th>
                      <th>Start</th>
                      <th>End</th>
                      <th className="cp-num">Amount</th>
                      <th>Payment</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.plans.map((p) => (
                      <tr key={p.id}>
                        <td>{p.plan_name}</td>
                        <td>{CYCLE_LABEL[p.billing_cycle]}</td>
                        <td>{dayLabel(p.start_date)}</td>
                        <td>{dayLabel(p.end_date)}</td>
                        <td className="cp-num">
                          {inr(p.amount_paise)}
                          {p.coupon_code ? <small className="muted">{couponNote(p).replace(" · ", " ")}</small> : null}
                        </td>
                        <td>{p.payment_status === "paid" ? `Paid · ${payModeLabel(p.payment_mode)}` : "Unpaid"}</td>
                        <td>
                          <StatusPill status={p.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
          <p className="muted sp-totals">
            Plans total {inr(data.total_paise)} · paid {inr(data.paid_paise)}
          </p>
        </>
      )}
      {assigning ? (
        <AssignPlanDialog
          elderId={elderId}
          name={name}
          onClose={() => setAssigning(false)}
          onDone={(p) => {
            setAssigning(false);
            setMessage(`${p.plan_name} added. It is waiting for approval.`);
            load();
          }}
        />
      ) : null}
      {pay ? (
        <PaymentDialog
          plan={pay.plan}
          name={name}
          mode={pay.mode}
          onClose={() => setPay(null)}
          onDone={() => {
            setMessage(pay.mode === "authorize" ? "Plan authorized. It is now active." : "Marked paid.");
            setPay(null);
            load();
          }}
        />
      ) : null}
    </section>
  );
}
