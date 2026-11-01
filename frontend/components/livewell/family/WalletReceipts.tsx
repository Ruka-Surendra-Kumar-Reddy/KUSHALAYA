"use client";

import { useEffect, useState } from "react";
import { fetchFamilyReceipts, type FamilyReceipt } from "@/lib/livewell/familyApi";
import { familyDate } from "@/lib/livewell/familyTime";
import { LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";
import { inr, listFamilyInvoices } from "@/lib/business";

const STATUS_WORDS: Record<string, string> = {
  success: "Paid",
  pending: "Waiting for payment",
  failed: "Payment didn't go through",
};

const statusWords = (s: string) => STATUS_WORDS[s] || s.replace(/_/g, " ");
const day = (value: string | null) => (value ? familyDate(value) : "—");

const METHOD_WORDS: Record<string, string> = {
  razorpay: "Paid online (Razorpay)",
  wallet: "KushAlaya wallet",
  stub: "Paid online",
};
const methodWords = (m: string) => METHOD_WORDS[m.toLowerCase()] || m;

/** One ₹ format everywhere: "₹1,500", "₹1,500.50", "-₹500". */
const money = (paise: number) => inr(paise);

/** "Wallet Top-Up" and "Wallet top-up" compare equal. */
const norm = (t: string) => t.toLowerCase().replace(/[-\s]+/g, " ").trim();

/** "Wallet Top-Up" -> "Wallet top-up" (sentence case); other text is left alone. */
export function sentenceCase(t: string): string {
  const s = (t || "").trim();
  if (!/^[A-Z][a-z]+(?:[-‐‑ ][A-Z][a-z]+)+$/.test(s)) return s;
  return s.charAt(0) + s.slice(1).toLowerCase();
}

/** History and receipt titles in plain words: "Wallet Top-Up" -> "Money added to wallet". */
export function receiptTitle(t: string): string {
  if (/^\s*wallet[\s‐‑-]*top[\s‐‑-]*up\s*$/i.test(t || "")) return "Money added to wallet";
  return sentenceCase(t);
}

const TOPUP_NOTE = "GST not applicable on wallet top-up.";
const INVOICE_NOTE = "The invoice for this payment is under Invoices on the Wallet page.";

/** Wallet history: every top-up and payment, each with a printable receipt. */
export function WalletReceipts({ reloadKey = 0 }: { reloadKey?: number }) {
  const [receipts, setReceipts] = useState<FamilyReceipt[]>([]);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<FamilyReceipt | null>(null);
  // Service-request ids that have an invoice: only those receipts point to Invoices.
  const [invoiced, setInvoiced] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchFamilyReceipts()
      .then(setReceipts)
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load your history"));
    listFamilyInvoices()
      .then((rows) => setInvoiced(new Set(rows.map((r) => String(r.source_id)))))
      .catch(() => setInvoiced(new Set()));
  }, [reloadKey]);

  const noteFor = (r: FamilyReceipt): string | null => {
    if (r.kind === "recharge") return TOPUP_NOTE;
    if (r.service_request_id && invoiced.has(String(r.service_request_id))) return INVOICE_NOTE;
    return null;
  };

  if (open) {
    return (
      <section className="card fh-receipt" aria-label={`Receipt ${open.receipt_number}`}>
        <div className="fh-receipt-head">
          <div>
            <p className="fh-receipt-brand">{publicBrandName()}</p>
            <p className="muted">{LEGAL_ENTITY_NAME}</p>
          </div>
          <div className="fh-receipt-no">
            <span className="muted">Receipt</span>
            <strong>{open.receipt_number}</strong>
            <span className="muted">{day(open.date)}</span>
          </div>
        </div>
        <table className="fh-receipt-table">
          <tbody>
            <tr>
              <th>For</th>
              <td>{receiptTitle(open.description)}</td>
            </tr>
            {/* No "Type" row when it only repeats "For" ("Wallet top-up"). */}
            {open.kind_label && norm(open.kind_label) !== norm(open.description) ? (
              <tr>
                <th>Type</th>
                <td>{sentenceCase(open.kind_label)}</td>
              </tr>
            ) : null}
            {open.payment_method ? (
              <tr>
                <th>Paid via</th>
                <td>{methodWords(open.payment_method)}</td>
              </tr>
            ) : null}
            {open.payment_reference ? (
              <tr>
                <th>Reference</th>
                <td>{open.payment_reference}</td>
              </tr>
            ) : null}
            <tr>
              <th>Status</th>
              <td>{statusWords(open.status)}</td>
            </tr>
            <tr className="fh-receipt-total">
              <th>Amount</th>
              <td>{money(open.amount_minor)}</td>
            </tr>
            {open.balance_after_minor != null ? (
              <tr>
                <th>Wallet balance after</th>
                <td>{money(open.balance_after_minor)}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
        {noteFor(open) ? <p className="muted fh-receipt-foot">{noteFor(open)}</p> : null}
        <div className="fh-receipt-actions fh-no-print">
          <button type="button" className="primary" onClick={() => window.print()}>
            Print / save as PDF
          </button>
          <button type="button" className="secondary" onClick={() => setOpen(null)}>
            Back to history
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="card home-safety-section" id="history">
      <h2>History</h2>
      {error ? <p className="error-text">{error}</p> : null}
      {receipts.length === 0 ? (
        <p className="muted">No payments yet. Top-ups and payments will appear here.</p>
      ) : (
        <ul className="home-safety-family-report-list">
          {receipts.map((r) => (
            <li key={r.id} className="home-safety-family-report fh-receipt-row">
              <div className="home-safety-family-report-top">
                <strong>{receiptTitle(r.description)}</strong>
                <span
                  className={`home-safety-pill ${r.amount_minor < 0 ? "home-safety-pill-neutral" : "home-safety-pill-good"}`}
                >
                  {money(r.amount_minor)}
                </span>
              </div>
              <p className="muted home-safety-list-meta">
                {day(r.date)}
                {/* Skip the type when the description already says it ("Wallet top-up"). */}
                {r.kind_label && !norm(r.description).includes(norm(r.kind_label)) ? ` · ${r.kind_label}` : ""}
                {r.status !== "success" ? ` · ${statusWords(r.status)}` : ""}
              </p>
              <button type="button" className="secondary" onClick={() => setOpen(r)}>
                View receipt
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
