"use client";

import { useEffect, useState } from "react";
import { downloadInvoicePdf, inr, listFamilyInvoices, type Invoice } from "@/lib/business";
import { familyDate } from "@/lib/livewell/familyTime";

/** Invoices and credit notes for what the family paid (only their own). */
export function FamilyInvoices({ reloadKey = 0 }: { reloadKey?: number }) {
  const [rows, setRows] = useState<Invoice[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listFamilyInvoices()
      .then(setRows)
      .catch(() => setRows([]));
  }, [reloadKey]);

  async function download(inv: Invoice) {
    try {
      await downloadInvoicePdf(inv, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  }

  return (
    <section className="card home-safety-section" id="invoices">
      <h2>Invoices</h2>
      {error ? <p className="error-text">{error}</p> : null}
      {rows.length === 0 ? <p className="muted">No invoices yet.</p> : null}
      <ul className="home-safety-family-report-list">
        {rows.map((r) => (
          <li key={r.id} className="home-safety-family-report fh-receipt-row">
            <div className="home-safety-family-report-top">
              <strong>{r.title} {r.number}</strong>
              <span className="home-safety-pill home-safety-pill-neutral">
                {r.kind === "credit_note" ? "−" : ""}{inr(r.total_paise)}
              </span>
            </div>
            <p className="muted home-safety-list-meta">
              {r.issued_at ? familyDate(r.issued_at) : ""}
              {r.original_number ? ` · refund against ${r.original_number}` : ""}
            </p>
            <button type="button" className="secondary" onClick={() => download(r)}>
              Download PDF
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
