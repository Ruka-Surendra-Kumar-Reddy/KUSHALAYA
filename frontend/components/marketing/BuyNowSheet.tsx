"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { getApiUrl } from "@/lib/api";
import { SINGLE_VISIT, carePlan, inr } from "@/lib/care-plan-catalog";
import { openRazorpayCheckout } from "@/lib/livewell/razorpayCheckout";
import { TERMS_HREF } from "@/lib/marketing/family-contacts";
import { apiErrorMessage, emailError, phoneError, pincodeError } from "@/lib/marketing/form-checks";
import {
  PLAN_PURCHASES_PATH,
  TIME_OF_DAY,
  VISIT_NEEDS,
  VISIT_PLAN_ID,
  cleanCouponCode,
  earliestVisitDate,
  shownPrice,
  type CheckoutCycle,
  type PlanQuote,
  type VisitNeed,
} from "@/lib/marketing/plan-checkout";
import { readLead } from "@/lib/marketing/site-config";
import { publicBrandName } from "@/lib/public-brand";

type Payment = { order_id: string; amount_minor: number; currency: string; provider: string; public_key: string };
type Step =
  | { kind: "form" }
  | { kind: "paying" }
  | { kind: "paid"; reference: string }
  | { kind: "later"; reference: string; message: string }
  | { kind: "failed"; message: string };

/**
 * "Buy now" on a plan card: plan, Yearly / Monthly, contact details, optional coupon,
 * then Razorpay Checkout (UPI / card / netbanking). The server prices it again.
 * With planId "single-visit" (pay as you go) it sells one visit instead: what is
 * needed, an optional preferred date / time of day, no billing cycle.
 */
export function BuyNowSheet({
  planId,
  initialCycle,
  initialNeed,
  onClose,
}: {
  planId: string;
  initialCycle: CheckoutCycle;
  initialNeed?: VisitNeed | "";
  onClose: () => void;
}) {
  const visit = planId === VISIT_PLAN_ID;
  const plan = carePlan(planId);
  const title = visit ? SINGLE_VISIT.name : (plan?.name ?? "Care plan");
  const [cycle, setCycle] = useState<CheckoutCycle>(visit ? "once" : initialCycle);
  const [need, setNeed] = useState<VisitNeed | "">(initialNeed ?? "");
  const [needNote, setNeedNote] = useState("");
  const [prefDate, setPrefDate] = useState("");
  const [timeOfDay, setTimeOfDay] = useState("");
  const minDate = earliestVisitDate();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [area, setArea] = useState("");
  const [pincode, setPincode] = useState("");
  const [coupon, setCoupon] = useState("");
  const [quote, setQuote] = useState<PlanQuote | null>(null);
  const [couponMsg, setCouponMsg] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [terms, setTerms] = useState(false);
  const [honeypot, setHoneypot] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>({ kind: "form" });
  const panel = useRef<HTMLDivElement>(null);

  // Escape closes; the page behind does not scroll while the sheet is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && step.kind !== "paying") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose, step.kind]);

  async function applyCoupon(forCycle: CheckoutCycle = cycle) {
    const code = cleanCouponCode(coupon);
    setCouponMsg(null);
    if (!code) {
      setQuote(null);
      return;
    }
    setApplying(true);
    try {
      const res = await fetch(`${getApiUrl()}${PLAN_PURCHASES_PATH}/quote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, billing_cycle: forCycle, coupon_code: code }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setQuote(null);
        setCouponMsg(apiErrorMessage(body?.detail) || "That coupon can't be used.");
        return;
      }
      setQuote(body as PlanQuote);
      setCoupon(code);
    } catch {
      setCouponMsg("Couldn't check the coupon. Check your connection.");
    } finally {
      setApplying(false);
    }
  }

  function pickCycle(next: CheckoutCycle) {
    setCycle(next);
    if (quote) void applyCoupon(next);
  }

  async function pay(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const problem =
      (visit && !need && "Please tell us what you need.") ||
      (visit && need === "other" && !needNote.trim() && "Please add a short note about what you need.") ||
      (visit && prefDate && prefDate < minDate && "Please pick a date from tomorrow.") ||
      (!name.trim() && "Please tell us your name.") ||
      (!phone.trim() && "Please enter your mobile number.") ||
      phoneError(phone) ||
      (!email.trim() && "Please enter your email for the receipt.") ||
      emailError(email) ||
      pincodeError(pincode) ||
      (!terms && "Please accept the terms to continue.") ||
      null;
    if (problem) {
      setError(problem);
      return;
    }
    setStep({ kind: "paying" });
    try {
      const res = await fetch(`${getApiUrl()}${PLAN_PURCHASES_PATH}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id: planId,
          billing_cycle: cycle,
          name,
          phone,
          email,
          area: area || null,
          pincode: pincode || null,
          coupon_code: quote?.coupon_code || null,
          accept_terms: terms,
          company: honeypot,
          ...(visit
            ? { need, need_note: needNote.trim() || null, preferred_date: prefDate || null, time_of_day: timeOfDay || null }
            : {}),
          ...readLead(),
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStep({ kind: "form" });
        setError(apiErrorMessage(body?.detail) || "Something went wrong. Please try again.");
        return;
      }
      const reference = String(body.reference || "");
      const payment = body.payment as Payment | null;
      if (!payment || !payment.order_id) {
        setStep({ kind: "later", reference, message: String(body.payment_message || "We'll call you to complete it.") });
        return;
      }
      let result = { razorpay_order_id: payment.order_id, razorpay_payment_id: `pay_stub_${Date.now()}`, razorpay_signature: "stub" };
      if (payment.provider !== "stub") {
        // Local / test servers use the stub gateway (no window); the server refuses a stub on a live site.
        const outcome = await openRazorpayCheckout({
          keyId: payment.public_key,
          orderId: payment.order_id,
          amountMinor: payment.amount_minor,
          currency: payment.currency,
          name: publicBrandName(),
          description: visit
            ? `${title} — ${VISIT_NEEDS.find((n) => n.id === need)?.label ?? "visit"}`
            : `${title} (${cycle === "yearly" ? "yearly" : "monthly"})`,
          // Razorpay pre-fills the mobile reliably only with the country code (+91…).
          prefill: { name, email, contact: razorpayContact(phone) },
        });
        if (outcome.status === "dismissed") {
          setStep({ kind: "failed", message: "Payment was cancelled. Nothing was charged." });
          return;
        }
        if (outcome.status === "failed") {
          setStep({ kind: "failed", message: outcome.message });
          return;
        }
        result = outcome.result;
      }
      const v = await fetch(`${getApiUrl()}${PLAN_PURCHASES_PATH}/${encodeURIComponent(reference)}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_id: result.razorpay_order_id,
          payment_id: result.razorpay_payment_id,
          signature: result.razorpay_signature,
        }),
      });
      if (!v.ok) {
        // The webhook still settles a real payment; tell them we'll confirm.
        setStep({
          kind: "later",
          reference,
          message: "We couldn't confirm the payment yet. If money left your account, it is safe — we'll confirm by phone and email.",
        });
        return;
      }
      setStep({ kind: "paid", reference });
    } catch (err) {
      setStep({ kind: "failed", message: err instanceof Error ? err.message : "The payment did not go through." });
    }
  }

  const price = shownPrice(planId, cycle, quote);
  const cyclePrice = (c: CheckoutCycle) => shownPrice(planId, c, null)?.amountPaise ?? 0;

  return (
    <div className="mk-buy-backdrop" onClick={() => step.kind !== "paying" && onClose()}>
      <div
        className="mk-buy"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mk-buy-title"
        tabIndex={-1}
        ref={panel}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mk-buy-head">
          <div>
            <p className="mk-eyebrow">Buy now</p>
            <h2 id="mk-buy-title">{title}</h2>
          </div>
          <button type="button" className="mk-buy-x" aria-label="Close" onClick={onClose} disabled={step.kind === "paying"}>
            ×
          </button>
        </header>

        {step.kind === "paid" ? (
          <div className="mk-form-done" role="status">
            <h3>Thank you — payment received.</h3>
            <p>
              Your reference is <strong>{step.reference}</strong>. A receipt is on its way to {email}.
            </p>
            <p>
              {visit
                ? "Our care team will call you shortly to confirm the date and time of the visit."
                : "Your care manager will call you shortly to welcome you and plan the first visit."}
            </p>
            <button type="button" className="mk-btn mk-btn-primary" onClick={onClose}>
              Done
            </button>
          </div>
        ) : step.kind === "later" ? (
          <div className="mk-form-done" role="status">
            <h3>Thank you — we have your details.</h3>
            <p>{step.message}</p>
            {step.reference ? (
              <p>
                Your reference is <strong>{step.reference}</strong>.
              </p>
            ) : null}
            <button type="button" className="mk-btn mk-btn-primary" onClick={onClose}>
              Close
            </button>
          </div>
        ) : step.kind === "failed" ? (
          <div className="mk-buy-failed" role="alert">
            <h3>The payment didn&rsquo;t go through</h3>
            <p>{step.message}</p>
            <p>No problem — you can try again, or choose another way to pay (UPI, card or netbanking).</p>
            <div className="mk-form-actions">
              <button type="button" className="mk-btn mk-btn-primary" onClick={() => setStep({ kind: "form" })}>
                Try again
              </button>
              <button type="button" className="mk-btn mk-btn-outline" onClick={onClose}>
                Not now
              </button>
            </div>
          </div>
        ) : (
          <form className="mk-form" onSubmit={pay} noValidate>
            {visit ? null : (
            <div className="mk-period mk-buy-cycle" role="radiogroup" aria-label="Billing">
              {(["yearly", "monthly"] as const).map((c) => (
                <button
                  key={c}
                  type="button"
                  role="radio"
                  aria-checked={cycle === c}
                  className={cycle === c ? "mk-period-btn is-on" : "mk-period-btn"}
                  onClick={() => pickCycle(c)}
                >
                  {c === "yearly" ? "Yearly" : "Monthly"} · {inr(cyclePrice(c))}
                </button>
              ))}
            </div>
            )}

            {price ? (
              <div className="mk-buy-price" aria-live="polite">
                {price.discountPaise > 0 ? (
                  <>
                    <s>{inr(price.listPaise)}</s>
                    <strong>{inr(price.amountPaise)}</strong>
                    <span className="mk-buy-save">
                      {price.coupon} saves {inr(price.discountPaise)}
                    </span>
                  </>
                ) : (
                  <strong>{inr(price.amountPaise)}</strong>
                )}
                <span className="mk-buy-gst">
                  {visit
                    ? `${inr(SINGLE_VISIT.pricePaise)} visit + ${inr(SINGLE_VISIT.registrationPaise)} registration · ${SINGLE_VISIT.hours} hours, GST included`
                    : `${cycle === "yearly" ? "a year" : "a month"}, GST included`}
                </span>
              </div>
            ) : null}

            {visit ? (
              <>
                <label className="mk-field">
                  <span>
                    What do you need? <em aria-hidden>*</em>
                  </span>
                  <select value={need} onChange={(e) => setNeed(e.target.value as VisitNeed | "")}>
                    <option value="">Choose one</option>
                    {VISIT_NEEDS.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.label}
                      </option>
                    ))}
                  </select>
                </label>
                {need ? (
                  <label className="mk-field">
                    <span>
                      {need === "other" ? (
                        <>
                          Tell us briefly <em aria-hidden>*</em>
                        </>
                      ) : (
                        "Anything we should know? (optional)"
                      )}
                    </span>
                    <input type="text" value={needNote} maxLength={300} onChange={(e) => setNeedNote(e.target.value)} />
                  </label>
                ) : null}
                <div className="mk-form-row mk-buy-row">
                  <label className="mk-field">
                    <span>Preferred date (optional)</span>
                    <input type="date" value={prefDate} min={minDate} onChange={(e) => setPrefDate(e.target.value)} />
                  </label>
                  <label className="mk-field">
                    <span>Time of day (optional)</span>
                    <select value={timeOfDay} onChange={(e) => setTimeOfDay(e.target.value)}>
                      <option value="">Any time</option>
                      {TIME_OF_DAY.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </>
            ) : null}

            <div className="mk-form-row mk-buy-row">
              <label className="mk-field">
                <span>
                  Your name <em aria-hidden>*</em>
                </span>
                <input type="text" value={name} autoComplete="name" onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="mk-field">
                <span>
                  Mobile <em aria-hidden>*</em>
                </span>
                <input type="tel" value={phone} autoComplete="tel" inputMode="tel" onChange={(e) => setPhone(e.target.value)} />
              </label>
            </div>
            <label className="mk-field">
              <span>
                Email <em aria-hidden>*</em>
              </span>
              <input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} />
            </label>
            <div className="mk-form-row mk-buy-row">
              <label className="mk-field">
                <span>City (optional)</span>
                <input type="text" value={area} autoComplete="address-level2" onChange={(e) => setArea(e.target.value)} />
              </label>
              <label className="mk-field">
                <span>PIN code (optional)</span>
                <input
                  type="text"
                  value={pincode}
                  inputMode="numeric"
                  autoComplete="postal-code"
                  maxLength={7}
                  onChange={(e) => setPincode(e.target.value)}
                />
              </label>
            </div>
            <div className="mk-field">
              <span>Coupon code (optional)</span>
              <div className="mk-buy-coupon">
                <input
                  type="text"
                  value={coupon}
                  autoCapitalize="characters"
                  aria-label="Coupon code"
                  onChange={(e) => {
                    setCoupon(e.target.value);
                    if (quote) setQuote(null);
                    setCouponMsg(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void applyCoupon();
                    }
                  }}
                />
                <button type="button" className="mk-btn mk-btn-outline" onClick={() => void applyCoupon()} disabled={applying || !coupon.trim()}>
                  {applying ? "Checking…" : "Apply"}
                </button>
              </div>
              {couponMsg ? <p className="mk-buy-coupon-msg" role="alert">{couponMsg}</p> : null}
              {quote?.coupon_code ? <p className="mk-buy-coupon-ok">Coupon {quote.coupon_code} applied.</p> : null}
            </div>
            <input className="mk-hp" tabIndex={-1} autoComplete="off" aria-hidden value={honeypot} onChange={(e) => setHoneypot(e.target.value)} name="company" />
            <label className="mk-buy-terms">
              <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
              <span>
                I agree to the{" "}
                <a href={TERMS_HREF} target="_blank" rel="noopener noreferrer">
                  terms
                </a>
                . {visit ? "We confirm the visit time by phone." : "The plan starts once our team confirms it."}
              </span>
            </label>
            {error ? <p className="mk-form-error" role="alert">{error}</p> : null}
            <button type="submit" className="mk-btn mk-btn-primary mk-btn-lg" disabled={step.kind === "paying"}>
              {step.kind === "paying" ? "Opening payment…" : `Pay ${price ? inr(price.amountPaise) : ""}`}
            </button>
            <p className="mk-buy-note">Secure payment by Razorpay: UPI, cards or netbanking.</p>
          </form>
        )}
      </div>
    </div>
  );
}

/** "98765 43210" / "+91 98765-43210" / "0098765…" → "+919876543210" for Razorpay's contact field. */
function razorpayContact(raw: string): string {
  const d = raw.replace(/[^\d+]/g, "");
  if (d.startsWith("+")) return d;
  if (d.startsWith("00")) return "+" + d.slice(2);
  const digits = d.replace(/^0+/, "");
  return digits.length === 10 ? `+91${digits}` : digits.length === 12 && digits.startsWith("91") ? `+${digits}` : d;
}
