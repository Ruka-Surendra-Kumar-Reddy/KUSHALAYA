"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { getApiUrl } from "@/lib/api";
import { openRazorpayCheckout } from "@/lib/livewell/razorpayCheckout";
import { publicBrandName } from "@/lib/public-brand";
import { apiErrorMessage, emailError, phoneError, pincodeError } from "@/lib/marketing/form-checks";
import { CALLBACK_PROMISE, captureLead, readLead, useSiteConfig, whatsAppHref, type LeadTouch } from "@/lib/marketing/site-config";

/**
 * Website enquiry form.
 *
 * Replaces the embedded Google Form, which was deleted at source and returned
 * "this file has been deleted" to every visitor. Posts straight to our own
 * endpoint, so an enquiry becomes a prospect the ops team already sees instead
 * of depending on a third-party document staying alive.
 */

export interface EnquiryExtras {
  services?: string[];
  visitFrequency?: string;
  products?: string[];
  area?: string;
  notes?: string;
}

type Sent = { status: "sent"; reference: string; areaMessage?: string; areaServed?: boolean; paid?: "paid" | "unpaid"; paymentMessage?: string };
type State = { status: "idle" | "sending" } | Sent | { status: "error"; message: string };

type Payment = { order_id: string; amount_minor: number; currency: string; provider: string; public_key: string };

/** Today + n days as YYYY-MM-DD in the visitor's own time zone. */
function dayPlus(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function EnquiryForm({
  kind,
  extras,
  submitLabel = "Send my enquiry",
  intro,
  blocked = false,
  blockedMessage,
}: {
  /** Where this came from — shows on the prospect record. */
  kind: "care-check" | "custom-plan" | "contact";
  /** Selections made elsewhere on the page, sent along with the contact details. */
  extras?: EnquiryExtras;
  submitLabel?: string;
  intro?: ReactNode;
  /** True while the page around the form isn't ready (e.g. nothing chosen in a custom plan). */
  blocked?: boolean;
  blockedMessage?: string;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [area, setArea] = useState("");
  const [notes, setNotes] = useState("");
  const [forWhom, setForWhom] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [state, setState] = useState<State>({ status: "idle" });
  const [pincode, setPincode] = useState("");
  const [pinCheck, setPinCheck] = useState<{ served: boolean; message: string } | null>(null);
  const [slotDate, setSlotDate] = useState("");
  const [slotWindow, setSlotWindow] = useState("morning");
  const [lead, setLead] = useState<LeadTouch>({});
  const site = useSiteConfig();
  const offersSlot = kind === "care-check";
  // Field errors show once the visitor leaves the field or tries to send.
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [tried, setTried] = useState(false);
  const latestPin = useRef("");
  const errors = { phone: phoneError(phone), email: emailError(email), pincode: pincodeError(pincode) };
  const show = (f: keyof typeof errors) => (tried || touched[f]) && errors[f];
  const blur = (f: string) => () => setTouched((t) => ({ ...t, [f]: true }));

  useEffect(() => {
    // The page shell records the visit's source too, but React runs this (child)
    // effect first, so on a first visit (every QR scan) it would read nothing.
    captureLead();
    setLead(readLead());
  }, []);

  async function checkPincode(value: string) {
    const pin = value.replace(/\D/g, "");
    latestPin.current = pin;
    if (pin.length !== 6 || pincodeError(pin)) {
      setPinCheck(null);
      return;
    }
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/home-safety/enquiries/pincode/${pin}`);
      const body = res.ok ? await res.json() : null;
      // A slower reply for an older PIN must not overwrite the current one.
      if (latestPin.current === pin) setPinCheck(body);
    } catch {
      if (latestPin.current === pin) setPinCheck(null);
    }
  }

  async function pay(reference: string, payment: Payment): Promise<"paid" | "unpaid"> {
    const outcome = await openRazorpayCheckout({
      keyId: payment.public_key,
      orderId: payment.order_id,
      amountMinor: payment.amount_minor,
      currency: payment.currency,
      name: publicBrandName(),
      description: "KushCare Discovery home assessment",
      prefill: { name, email: email || undefined, contact: phone || undefined },
    }).catch(() => ({ status: "failed" as const, message: "" }));
    if (outcome.status !== "paid") return "unpaid";
    const res = await fetch(`${getApiUrl()}/api/v1/home-safety/enquiries/${reference}/payment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        order_id: outcome.result.razorpay_order_id,
        payment_id: outcome.result.razorpay_payment_id,
        signature: outcome.result.razorpay_signature,
      }),
    }).catch(() => null);
    return res && res.ok ? "paid" : "unpaid";
  }

  const noWayToReply = !phone.trim() && !email.trim();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setTried(true);
    if (!name.trim() || noWayToReply || blocked) return;
    if (errors.phone || errors.email || errors.pincode) return;
    setState({ status: "sending" });
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/home-safety/enquiries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          phone: phone || null,
          email: email || null,
          area: area || extras?.area || null,
          services: extras?.services ?? null,
          visit_frequency: extras?.visitFrequency ?? null,
          products: extras?.products ?? null,
          notes: [notes, extras?.notes].filter(Boolean).join("\n\n") || null,
          kind,
          for_whom: forWhom || null,
          company: company || null,
          pincode: pincode || null,
          slot_date: offersSlot && slotDate ? slotDate : null,
          slot_window: offersSlot && slotDate ? slotWindow : null,
          // Read again at submit: the source (?src=qr, utm, referral) as recorded now.
          ...lead,
          ...readLead(),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(
          (detail && apiErrorMessage(detail.detail)) ||
            "Something went wrong. Please try again, or call us.",
        );
      }
      const body = await res.json();
      const sent: Sent = {
        status: "sent",
        reference: body.reference,
        areaMessage: body.area_message,
        areaServed: body.area_served,
      };
      if (typeof body.payment_message === "string" && body.payment_message) {
        // Online payment isn't available: the server says how to pay instead (e.g. at the visit).
        sent.paymentMessage = body.payment_message;
      } else if (body.payment && body.payment.order_id) {
        sent.paid = await pay(body.reference, body.payment as Payment);
      }
      setState(sent);
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Could not send. Please try again.",
      });
    }
  }

  if (state.status === "sent") {
    return (
      <div className="mk-form-done" role="status">
        <h3>Thank you — we have your details.</h3>
        <p>
          {CALLBACK_PROMISE}. Your reference is <strong>{state.reference}</strong> — keep it handy if you call.
        </p>
        {state.areaMessage ? <p>{state.areaMessage}</p> : null}
        {state.paymentMessage ? <p>{state.paymentMessage}</p> : null}
        {state.paid === "paid" ? <p>Your assessment fee is paid. We&rsquo;ll confirm the visit time when we call.</p> : null}
        {state.paid === "unpaid" ? (
          <p>The payment didn&rsquo;t go through. No problem — we&rsquo;ll sort it out when we call.</p>
        ) : null}
        <p>
          <a
            className="mk-btn mk-btn-green"
            href={whatsAppHref(site, `Hi, I just sent an enquiry (${state.reference}).`)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Message us on WhatsApp
          </a>
        </p>
      </div>
    );
  }

  return (
    <form className="mk-form" onSubmit={submit} noValidate>
      {intro}

      {lead.ref ? (
        <p className="mk-ref-note">
          A {publicBrandName()} family recommended us to you (code <strong>{lead.ref}</strong>). Thank you for
          trusting their word.
        </p>
      ) : null}

      {kind === "care-check" ? (
        <label className="mk-field">
          <span>Who is this for?</span>
          <select value={forWhom} onChange={(e) => setForWhom(e.target.value)}>
            <option value="">Choose…</option>
            <option value="Parent">My parent</option>
            <option value="Spouse">My spouse</option>
            <option value="Grandparent">My grandparent</option>
            <option value="Other relative">Another relative</option>
            <option value="Myself">Myself</option>
            <option value="Someone else">Someone else</option>
          </select>
        </label>
      ) : null}

      <div className="mk-form-row">
        <label className="mk-field">
          <span>
            Your name <em aria-hidden>*</em>
          </span>
          <input
            type="text"
            value={name}
            required
            autoComplete="name"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="mk-field">
          <span>Which area are they in?</span>
          <input
            type="text"
            value={area}
            placeholder="Area and city"
            onChange={(e) => setArea(e.target.value)}
          />
        </label>
      </div>

      <div className="mk-form-row">
        <label className="mk-field">
          <span>PIN code</span>
          <input
            type="text"
            inputMode="numeric"
            maxLength={7}
            value={pincode}
            placeholder="e.g. 560001"
            onChange={(e) => {
              setPincode(e.target.value);
              void checkPincode(e.target.value);
            }}
            onBlur={blur("pincode")}
            aria-invalid={show("pincode") ? true : undefined}
            aria-describedby={show("pincode") ? "mk-err-pin" : undefined}
          />
          {show("pincode") ? (
            <span className="mk-field-error" id="mk-err-pin">
              {errors.pincode}
            </span>
          ) : null}
          {pinCheck ? (
            <span className={`mk-area-note ${pinCheck.served ? "is-ok" : "is-check"}`} role="status">
              {pinCheck.message}
            </span>
          ) : null}
        </label>
        {offersSlot ? (
          <div className="mk-field">
            <span>Preferred call-back time (optional)</span>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input
                type="date"
                aria-label="Preferred day"
                min={dayPlus(1)}
                max={dayPlus(60)}
                value={slotDate}
                onChange={(e) => setSlotDate(e.target.value)}
              />
              <select aria-label="Time of day" value={slotWindow} onChange={(e) => setSlotWindow(e.target.value)}>
                {site.slot_windows.map((w) => (
                  <option key={w} value={w}>
                    {w[0].toUpperCase() + w.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <small className="mk-note">
              We confirm the KushCare Discovery visit time when we call.
              {site.assessment_is_paid ? " You can pay securely online after sending." : " The visit is free; nothing to pay."}
            </small>
          </div>
        ) : null}
      </div>

      <p className="mk-form-step">
        How should we reach you? <em>Give a phone number or an email &mdash; at least one.</em>
      </p>

      <div className="mk-form-row">
        <label className="mk-field">
          <span>Phone</span>
          <input
            type="tel"
            value={phone}
            autoComplete="tel"
            placeholder="98765 43210 or +44 …"
            onChange={(e) => setPhone(e.target.value)}
            onBlur={blur("phone")}
            aria-invalid={show("phone") ? true : undefined}
            aria-describedby={show("phone") ? "mk-err-phone" : undefined}
          />
          {show("phone") ? (
            <span className="mk-field-error" id="mk-err-phone">
              {errors.phone}
            </span>
          ) : null}
        </label>
        <label className="mk-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
            onBlur={blur("email")}
            aria-invalid={show("email") ? true : undefined}
            aria-describedby={show("email") ? "mk-err-email" : undefined}
          />
          {show("email") ? (
            <span className="mk-field-error" id="mk-err-email">
              {errors.email}
            </span>
          ) : null}
        </label>
      </div>

      <label className="mk-field">
        <span>Anything you&rsquo;d like us to know?</span>
        <textarea
          rows={4}
          value={notes}
          placeholder="Recent falls, mobility, medicines, the best time to call…"
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>

      {/* Honeypot: off-screen and hidden from assistive tech. Bots fill it in. */}
      <div className="mk-hp" aria-hidden="true">
        <label>
          Company
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        </label>
      </div>

      {state.status === "error" ? (
        <p className="mk-form-error" role="alert">
          {state.message}
        </p>
      ) : null}

      <div className="mk-form-actions">
        <button
          type="submit"
          className="mk-btn mk-btn-primary mk-btn-lg"
          disabled={state.status === "sending" || !name.trim() || noWayToReply || blocked}
        >
          {state.status === "sending" ? "Sending…" : submitLabel}
        </button>
        <p className="mk-note">
          {blocked
            ? blockedMessage || "Choose what you need above first."
            : noWayToReply
            ? "Add a phone number or email so we can reply."
            : `${CALLBACK_PROMISE}. We only use these details to contact you about care for your family.`}
        </p>
      </div>
    </form>
  );
}
