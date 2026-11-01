"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Flash } from "@/components/Flash";
import { formatIST } from "@/lib/ist";
import { currentMonthIST, downloadExport, downloadInvoicePdf, inr, listInvoices, type Invoice } from "@/lib/business";
import { PageHeader } from "@/components/PageHeader";
import { PA_ICONS } from "@/components/ops/PageActions";
import "@/components/ops/business.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

/** Invoices and credit notes, issued automatically when a family pays or is refunded. */
export default function InvoicesPage() {
  const isAdmin = isAdminUser();
  const router = useRouter();
  useEffect(() => {
    // Admin-only page (business/global data); the API refuses non-admins too.
    if (!isAdmin) router.replace("/unauthorized");
  }, [isAdmin, router]);
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const [registered, setRegistered] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"" | Invoice["kind"]>("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isAdmin) return;
    listInvoices()
      .then((r) => {
        setRows(r.invoices);
        setRegistered(r.gst_registered);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [isAdmin]);

  async function exportRegister() {
    setBusy(true);
    try {
      await downloadExport("gst-register", currentMonthIST());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function download(inv: Invoice) {
    try {
      await downloadInvoicePdf(inv);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  }

  const q = query.trim().toLowerCase();
  const shown = (rows || []).filter(
    (r) =>
      (!kind || r.kind === kind) &&
      (!q || r.number.toLowerCase().includes(q) || (r.customer_name || "").toLowerCase().includes(q)),
  );

  if (!isAdmin) return null;
  return (
    <div className="ks-frame">
      <div className="ks-head-row">
        <PageHeader title="Invoices" subtitle="Made when a family pays; credit notes for refunds" />
        <div className="ks-head-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void exportRegister()}
            aria-label="Download this month's GST register (CSV)"
            title="Download this month's GST register (CSV)"
          >
            <span className="ks-ha-icon" aria-hidden="true">↓</span>
            <span className="ks-ha-label">{busy ? "Preparing…" : "Download CSV"}</span>
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
      {rows && rows.length > 0 ? (
        <div className="od-filter" role="search">
          <label>
            <span className="sr-only">Search invoices</span>
            <input aria-label="Search by number or client"
              type="search"
              placeholder="Search by number or client"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>
            <span className="sr-only">Show</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as "" | Invoice["kind"])}>
              <option value="">All invoices and credit notes</option>
              <option value="invoice">Invoices only</option>
              <option value="credit_note">Credit notes only</option>
            </select>
          </label>
        </div>
      ) : null}
      <Flash error={error} message="" onClear={() => setError("")} />
      {!registered && (
        <p className="card od-banner" role="note">
          <strong>No GSTIN yet</strong> — these are bills of supply / receipts without GST.
          {isAdmin ? <> <Link href="/settings/business" className="ks-link">Add the GSTIN</Link> to issue GST tax invoices.</> : " Ask an admin to add it."}
        </p>
      )}
      <div className="card od-table-wrap">
        {rows === null ? (
          <p className="muted">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="muted">No invoices yet. The first one appears when a family pays.</p>
        ) : shown.length === 0 ? (
          <p className="muted">Nothing matches. Clear the search or show all.</p>
        ) : (
          <table className="table od-inv-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Number</th>
                <th>Type</th>
                <th>Client</th>
                <th className="od-num">GST</th>
                <th className="od-num">Total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                // Credit notes show as minus in both GST and Total, whatever sign the API sends.
                const signed = (p: number) => (r.kind === "credit_note" ? -Math.abs(p) : p);
                return (
                  <tr key={r.id} className={r.kind === "credit_note" ? "is-credit" : ""}>
                    <td data-label="Date">{r.issued_at ? formatIST(r.issued_at, { dateOnly: true }) : "—"}</td>
                    <td data-label="Number" className="od-inv-no"><strong>{r.number}</strong></td>
                    <td data-label="Type">
                      {r.title}
                      {r.original_number ? <small className="muted"> against {r.original_number}</small> : null}
                    </td>
                    <td data-label="Client">
                      <Link href={`/kushalaya/customers/${r.elder_id}`}>{r.customer_name}</Link>
                    </td>
                    <td data-label="GST" className="od-num">{inr(signed(r.cgst_paise + r.sgst_paise + r.igst_paise))}</td>
                    <td data-label="Total" className="od-num">{inr(signed(r.total_paise))}</td>
                    <td className="od-inv-pdf">
                      <button type="button" className="secondary" onClick={() => download(r)}>PDF</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
