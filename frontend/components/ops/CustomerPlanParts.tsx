"use client";

/** Shared pieces for care plans: the plan + cycle + start date picker, and the
 *  Assign / Authorize / Mark paid dialogs (Customers table, client profile, Operations board). */
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { inr, planPricePaise, type BillingCycle } from "@/lib/care-plan-catalog";
import {
  CYCLE_LABEL,
  PAYMENT_MODES,
  assignPlan,
  authorizePlan,
  couponNote,
  cyclesFor,
  isoDay,
  markPlanPaid,
  planCatalogOptions,
  planEndDate,
  planPrice,
  type CustomerPlan,
  type PlanPrice,
} from "@/lib/sales-pipeline";
import "@/components/ops/sales.css";

export type PlanPick = { plan_id: string; billing_cycle: BillingCycle | ""; start_date: string; coupon_code?: string };

export const emptyPick = (): PlanPick => ({ plan_id: "", billing_cycle: "", start_date: isoDay(new Date()), coupon_code: "" });

/** The coupon to send with a plan, or null (the server checks it again). */
export const pickCoupon = (p: PlanPick): string | null => (p.coupon_code || "").trim().toUpperCase() || null;

/** "12 Oct 2026" from yyyy-mm-dd. */
export function dayLabel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function PlanFields({ value, onChange }: { value: PlanPick; onChange: (v: PlanPick) => void }) {
  const cycles = value.plan_id ? cyclesFor(value.plan_id) : [];
  const amount =
    value.plan_id && value.billing_cycle ? planPricePaise(value.plan_id, value.billing_cycle) : null;
  const [quote, setQuote] = useState<PlanPrice | null>(null);
  const [couponMsg, setCouponMsg] = useState("");
  const code = pickCoupon(value);
  const priced =
    quote && code && quote.coupon_code === code && quote.plan_id === value.plan_id && quote.billing_cycle === value.billing_cycle
      ? quote
      : null;
  async function checkCoupon() {
    setCouponMsg("");
    setQuote(null);
    if (!code || !value.plan_id || !value.billing_cycle) return setCouponMsg("Choose the plan and billing first.");
    try {
      setQuote(await planPrice({ plan_id: value.plan_id, billing_cycle: value.billing_cycle, coupon_code: code }));
    } catch (err) {
      setCouponMsg(err instanceof Error ? err.message : "That coupon can't be used.");
    }
  }
  return (
    <div className="sp-plan-fields">
      <label>
        Plan
        <select
          value={value.plan_id}
          required
          onChange={(e) => {
            const id = e.target.value;
            const ok = cyclesFor(id);
            // A plan with one cycle gets it picked; otherwise keep a still-valid choice.
            const cycle = ok.length === 1 ? ok[0]! : ok.includes(value.billing_cycle as BillingCycle) ? value.billing_cycle : "";
            onChange({ ...value, plan_id: id, billing_cycle: cycle });
          }}
        >
          <option value="">Choose…</option>
          {planCatalogOptions().map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="sp-cycle" disabled={!value.plan_id}>
        <legend>Billing</legend>
        {(["yearly", "monthly"] as const).map((c) => (
          <label key={c} className={cycles.includes(c) ? "" : "is-off"}>
            <input
              type="radio"
              name="sp-cycle"
              value={c}
              checked={value.billing_cycle === c}
              disabled={!cycles.includes(c)}
              onChange={() => onChange({ ...value, billing_cycle: c })}
            />
            {CYCLE_LABEL[c]}
            {value.plan_id && !cycles.includes(c) ? <span className="muted"> (not offered)</span> : null}
          </label>
        ))}
      </fieldset>
      <label>
        Start date
        <input type="date" value={value.start_date} required onChange={(e) => onChange({ ...value, start_date: e.target.value })} />
      </label>
      <label>
        Coupon code (optional)
        <span className="sp-coupon">
          <input
            type="text"
            value={value.coupon_code || ""}
            placeholder="e.g. PAYNOW5"
            maxLength={40}
            onChange={(e) => {
              setCouponMsg("");
              onChange({ ...value, coupon_code: e.target.value.toUpperCase() });
            }}
          />
          <button type="button" className="secondary" disabled={!code} onClick={() => void checkCoupon()}>
            Check
          </button>
        </span>
      </label>
      {couponMsg ? (
        <p className="error-text" role="alert">
          {couponMsg}
        </p>
      ) : null}
      {amount != null && value.billing_cycle && value.start_date ? (
        <p className="sp-plan-sum" role="status">
          {priced ? (
            <>
              <s>{inr(priced.list_paise)}</s> {inr(priced.amount_paise)} ({priced.coupon_code} −{inr(priced.discount_paise)})
            </>
          ) : (
            inr(amount)
          )}{" "}
          {value.billing_cycle === "yearly" ? "a year" : "a month"} · ends {dayLabel(planEndDate(value.start_date, value.billing_cycle))} ·
          starts as Pending approval, unpaid
        </p>
      ) : null}
    </div>
  );
}

/** Backdrop + dialog form; Escape or a click outside closes it. */
export function SpDialog({
  title,
  onClose,
  onSubmit,
  children,
  busy,
  error,
  submitLabel,
}: {
  title: string;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
  busy: boolean;
  error: string;
  submitLabel: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, busy]);
  return (
    <div className="home-safety-showcase-modal-backdrop" role="presentation" onClick={() => !busy && onClose()}>
      <form
        className="home-safety-showcase-modal card ct-dialog sp-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onSubmit={onSubmit}
      >
        <h2>{title}</h2>
        {children}
        {error ? (
          <p className="error-text" role="alert">
            {error}
          </p>
        ) : null}
        <div className="sp-dialog-actions">
          <button type="button" className="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" disabled={busy}>
            {busy ? "Saving…" : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}

const errText = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback);

export function AssignPlanDialog({
  elderId,
  name,
  onClose,
  onDone,
}: {
  elderId: number;
  name: string;
  onClose: () => void;
  onDone: (p: CustomerPlan) => void;
}) {
  const [pick, setPick] = useState<PlanPick>(emptyPick);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!pick.plan_id || !pick.billing_cycle) return setError("Choose a plan and Yearly or Monthly.");
    setBusy(true);
    setError("");
    try {
      onDone(
        await assignPlan(elderId, {
          plan_id: pick.plan_id,
          billing_cycle: pick.billing_cycle,
          start_date: pick.start_date,
          coupon_code: pickCoupon(pick),
        }),
      );
    } catch (err) {
      setError(errText(err, "Could not save the plan"));
      setBusy(false);
    }
  }
  return (
    <SpDialog title={`Assign a plan · ${name}`} onClose={onClose} onSubmit={submit} busy={busy} error={error} submitLabel="Assign plan">
      <PlanFields value={pick} onChange={setPick} />
    </SpDialog>
  );
}

/** Authorize (pending → active) or Mark paid. Both record how they paid. */
export function PaymentDialog({
  plan,
  name,
  mode,
  onClose,
  onDone,
}: {
  plan: CustomerPlan;
  name: string;
  mode: "authorize" | "paid";
  onClose: () => void;
  onDone: (p: CustomerPlan) => void;
}) {
  const [payMode, setPayMode] = useState(plan.payment_mode || "");
  const [paid, setPaid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!payMode) return setError("Choose how they paid.");
    setBusy(true);
    setError("");
    try {
      onDone(mode === "authorize" ? await authorizePlan(plan.id, { payment_mode: payMode, paid }) : await markPlanPaid(plan.id, payMode));
    } catch (err) {
      setError(errText(err, "Could not save"));
      setBusy(false);
    }
  }
  return (
    <SpDialog
      title={`${mode === "authorize" ? "Authorize plan" : "Mark paid"} · ${name}`}
      onClose={onClose}
      onSubmit={submit}
      busy={busy}
      error={error}
      submitLabel={mode === "authorize" ? "Authorize" : "Mark paid"}
    >
      <p className="muted sp-dialog-lead">
        {plan.plan_name} · {CYCLE_LABEL[plan.billing_cycle]} · {inr(plan.amount_paise)}{couponNote(plan)} · {dayLabel(plan.start_date)} to {dayLabel(plan.end_date)}
      </p>
      <label>
        Payment mode
        <select value={payMode} onChange={(e) => setPayMode(e.target.value)} required>
          <option value="">Choose…</option>
          {PAYMENT_MODES.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {mode === "authorize" ? (
        <fieldset className="sp-cycle">
          <legend>Payment</legend>
          <label>
            <input type="radio" name="sp-paid" checked={!paid} onChange={() => setPaid(false)} /> Unpaid
          </label>
          <label>
            <input type="radio" name="sp-paid" checked={paid} onChange={() => setPaid(true)} /> Paid
          </label>
        </fieldset>
      ) : null}
      {mode === "authorize" ? <p className="muted sp-dialog-lead">The plan becomes Active.</p> : null}
    </SpDialog>
  );
}

export function payModeLabel(mode: string | null): string {
  return PAYMENT_MODES.find(([k]) => k === mode)?.[1] ?? (mode || "—");
}
