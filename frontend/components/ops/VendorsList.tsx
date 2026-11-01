"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { ContractsPanel } from "@/components/contracts/ContractsPanel";
import { SendContract } from "@/components/contracts/SendContract";
import { OpsModal } from "@/components/ops/OpsModal";
import { api } from "@/lib/api";
import { displayPhone } from "@/lib/display-format";
import { parseApiTime } from "@/lib/ist";
import "@/components/ops/clients.css";
import "@/components/ops/vendors.css";

/** Sales → Vendors. Services and fee bases come from GET /api/v1/vendors/options (one list, backend). */

type Option = { code: string; label: string };
export type Vendor = {
  id: number;
  company_name: string;
  address: string | null;
  owner_name: string | null;
  phone1: string;
  phone2: string | null;
  gstin: string | null;
  services: string[];
  services_other: string | null;
  fee_paise: number | null;
  fee_basis: string | null;
  last_payment_date: string | null;
  status: "active" | "inactive";
  notes: string | null;
  created_at: string | null;
};

const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

/** "1,500.5" → 150050 paise, without floating point. null when blank; NaN when not a number. */
export function rupeesToPaise(text: string): number | null {
  const s = text.replace(/[₹,\s]/g, "");
  if (!s) return null;
  const m = /^(\d+)(?:\.(\d{0,2}))?$/.exec(s);
  if (!m) return NaN;
  return Number(m[1]) * 100 + Number((m[2] || "").padEnd(2, "0"));
}

export function paiseToRupees(p: number | null): string {
  if (p === null || p === undefined) return "";
  const whole = Math.floor(p / 100);
  const frac = p % 100;
  return frac ? `${whole}.${String(frac).padStart(2, "0")}` : String(whole);
}

/** ₹1,500 / ₹1,500.50 in Indian grouping. */
export function formatPaise(p: number): string {
  const whole = Math.floor(p / 100).toLocaleString("en-IN");
  const frac = p % 100;
  return `₹${whole}${frac ? `.${String(frac).padStart(2, "0")}` : ""}`;
}

/** dd Mon yyyy. A plain date stays as is; a timestamp is shown in IST. */
export function formatDay(value: string | null): string {
  if (!value) return "";
  const plain = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const d = plain ? new Date(`${value}T00:00:00Z`) : parseApiTime(value);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: plain ? "UTC" : "Asia/Kolkata",
  }).format(d);
}

const EMPTY = {
  company_name: "",
  owner_name: "",
  address: "",
  phone1: "",
  phone2: "",
  gstin: "",
  services: [] as string[],
  services_other: "",
  fee: "",
  fee_basis: "per_visit",
  last_payment_date: "",
  status: "active",
  notes: "",
};
type Form = typeof EMPTY;

function toForm(v: Vendor): Form {
  return {
    company_name: v.company_name,
    owner_name: v.owner_name || "",
    address: v.address || "",
    phone1: v.phone1,
    phone2: v.phone2 || "",
    gstin: v.gstin || "",
    services: v.services,
    services_other: v.services_other || "",
    fee: paiseToRupees(v.fee_paise),
    fee_basis: v.fee_basis || "per_visit",
    last_payment_date: v.last_payment_date || "",
    status: v.status,
    notes: v.notes || "",
  };
}

export function VendorsList({ canEdit }: { canEdit: boolean }) {
  const [rows, setRows] = useState<Vendor[] | null>(null);
  const [services, setServices] = useState<Option[]>([]);
  const [bases, setBases] = useState<Option[]>([]);
  const [query, setQuery] = useState("");
  const [service, setService] = useState("");
  const [status, setStatus] = useState("active");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Vendor | "new" | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [contractFor, setContractFor] = useState<Vendor | null>(null);
  const [contractsKey, setContractsKey] = useState(0);

  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (query.trim()) p.set("q", query.trim());
    if (service) p.set("service", service);
    if (status) p.set("status", status);
    api<Vendor[]>(`/api/v1/vendors?${p}`)
      .then((r) => {
        setRows(r);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load vendors"));
  }, [query, service, status]);

  useEffect(() => {
    const t = window.setTimeout(load, 250);
    return () => window.clearTimeout(t);
  }, [load]);

  useEffect(() => {
    api<{ services: Option[]; fee_bases: Option[] }>("/api/v1/vendors/options")
      .then((o) => {
        setServices(o.services);
        setBases(o.fee_bases);
      })
      .catch(() => undefined);
  }, []);

  const label = (code: string, list: Option[]) => list.find((o) => o.code === code)?.label || code;

  function openForm(v: Vendor | "new") {
    setForm(v === "new" ? EMPTY : toForm(v));
    setFormError("");
    setEditing(v);
  }

  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const toggle = (code: string, on: boolean) =>
    setForm({ ...form, services: on ? [...form.services, code] : form.services.filter((s) => s !== code) });

  async function save(e: FormEvent) {
    e.preventDefault();
    const gstin = form.gstin.replace(/\s/g, "").toUpperCase();
    if (gstin && !GSTIN_RE.test(gstin)) return setFormError("GSTIN must be 15 characters, e.g. 36ABCDE1234F1Z5.");
    const fee = rupeesToPaise(form.fee);
    if (Number.isNaN(fee)) return setFormError("Enter the fee in rupees, e.g. 1500.");
    setSaving(true);
    setFormError("");
    const body = {
      company_name: form.company_name,
      owner_name: form.owner_name || null,
      address: form.address || null,
      phone1: form.phone1,
      phone2: form.phone2 || null,
      gstin: gstin || null,
      services: form.services,
      services_other: form.services.includes("other") ? form.services_other || null : null,
      fee_paise: fee,
      fee_basis: fee === null ? null : form.fee_basis,
      last_payment_date: form.last_payment_date || null,
      status: form.status,
      notes: form.notes || null,
    };
    try {
      if (editing === "new") {
        await api("/api/v1/vendors", { method: "POST", body: JSON.stringify(body) });
      } else if (editing) {
        await api(`/api/v1/vendors/${editing.id}`, { method: "PUT", body: JSON.stringify(body) });
      }
      setEditing(null);
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate() {
    if (!editing || editing === "new") return;
    setSaving(true);
    try {
      await api(`/api/v1/vendors/${editing.id}/deactivate`, { method: "POST" });
      setEditing(null);
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not deactivate");
    } finally {
      setSaving(false);
    }
  }

  const filtered = !!(query || service || status !== "active");
  const readOnly = !canEdit;

  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Vendors" />
        {canEdit ? (
          <div className="ks-head-actions">
            <Link className="secondary" href="/kushalaya/contracts?tab=templates" aria-label="Agreement templates" title="Edit the agreement text sent to vendors">
              <span className="ks-ha-icon" aria-hidden="true">✍</span>
              <span className="ks-ha-label">Agreement templates</span>
            </Link>
            <button type="button" onClick={() => openForm("new")} aria-label="Add vendor" title="Add vendor">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ Add vendor</span>
            </button>
          </div>
        ) : null}
      </div>

      <section className="vn card">
        {error ? <p className="error-text">{error}</p> : null}
        <div className="vn-bar">
          <input
            className="vn-search"
            type="search"
            aria-label="Search name, owner, phone or GSTIN"
            placeholder="Search name, owner, phone or GSTIN"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select aria-label="Service" value={service} onChange={(e) => setService(e.target.value)}>
            <option value="">All services</option>
            {services.map((s) => (
              <option key={s.code} value={s.code}>
                {s.label}
              </option>
            ))}
          </select>
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="">All</option>
          </select>
          <span className="vn-count" aria-live="polite">
            {rows ? `${rows.length} vendor${rows.length === 1 ? "" : "s"}` : ""}
          </span>
        </div>

        {rows === null ? (
          <p className="vn-empty">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="vn-empty">
            {filtered ? "No vendors match." : "No vendors yet."}
            {filtered ? (
              <button
                type="button"
                className="vn-clear"
                onClick={() => {
                  setQuery("");
                  setService("");
                  setStatus("active");
                }}
              >
                Clear filters
              </button>
            ) : null}
          </p>
        ) : (
          <div className="vn-list" role="list" aria-label="Vendors">
            <div className="vn-row vn-head" aria-hidden="true">
              <span>Vendor</span>
              <span>Phones</span>
              <span>Services</span>
              <span>Fees</span>
              <span>Last paid</span>
              <span>Added</span>
              <span>Status</span>
              <span />
            </div>
            {rows.map((v) => (
              <div
                key={v.id}
                role="listitem"
                className="vn-row"
                tabIndex={0}
                aria-label={`Open ${v.company_name}`}
                onClick={() => openForm(v)}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
                    e.preventDefault();
                    openForm(v);
                  }
                }}
              >
                <span className="vn-who">
                  <strong className="vn-name">{v.company_name}</strong>
                  <small>{v.owner_name || "—"}</small>
                </span>
                <span className="vn-phones">
                  <span>{displayPhone(v.phone1)}</span>
                  {v.phone2 ? <span>{displayPhone(v.phone2)}</span> : null}
                </span>
                <span className="vn-tags">
                  {v.services.length ? (
                    v.services.map((s) => (
                      <em key={s} className="vn-tag">
                        {s === "other" && v.services_other ? v.services_other : label(s, services)}
                      </em>
                    ))
                  ) : (
                    <span className="vn-dim">—</span>
                  )}
                </span>
                <span className="vn-fee">
                  {v.fee_paise !== null ? (
                    <>
                      <strong>{formatPaise(v.fee_paise)}</strong>
                      <small>{v.fee_basis ? label(v.fee_basis, bases).toLowerCase() : ""}</small>
                    </>
                  ) : (
                    <span className="vn-dim">—</span>
                  )}
                </span>
                <span className="vn-paid" data-label="Last paid">
                  {formatDay(v.last_payment_date) || <span className="vn-dim">—</span>}
                </span>
                <span className="vn-added" data-label="Added">
                  {formatDay(v.created_at)}
                </span>
                <span className="vn-state">
                  <span className={`vn-pill is-${v.status}`}>
                    {v.status === "active" ? "Active" : "Inactive"}
                  </span>
                </span>
                <span className="vn-act">
                  {canEdit ? (
                    <button type="button" className="secondary" tabIndex={-1} title={`Send an agreement to ${v.company_name} to sign`} onClick={(e) => (e.stopPropagation(), setContractFor(v))}>
                      Send agreement
                    </button>
                  ) : null}
                  <button type="button" tabIndex={-1} onClick={(e) => (e.stopPropagation(), openForm(v))}>
                    {canEdit ? "Edit" : "Open"}
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <OpsModal
        open={editing !== null}
        title={editing === "new" ? "New vendor" : readOnly ? "Vendor" : "Edit vendor"}
        onClose={() => setEditing(null)}
        wide
      >
        <form className="cl-form vn-form" onSubmit={save}>
          {formError ? <p className="ks-modal-error" role="alert">{formError}</p> : null}
          <fieldset disabled={readOnly || saving}>
            <div className="cl-grid">
              <label className="cl-wide">
                Company name *
                <input value={form.company_name} onChange={set("company_name")} required maxLength={200} />
              </label>
              <label>
                Owner name
                <input value={form.owner_name} onChange={set("owner_name")} maxLength={200} />
              </label>
              <label>
                GSTIN (optional)
                <input
                  value={form.gstin}
                  onChange={set("gstin")}
                  maxLength={15}
                  placeholder="36ABCDE1234F1Z5"
                  style={{ textTransform: "uppercase" }}
                />
              </label>
              <label>
                Phone 1 *
                <input type="tel" value={form.phone1} onChange={set("phone1")} required placeholder="+91…" />
              </label>
              <label>
                Phone 2
                <input type="tel" value={form.phone2} onChange={set("phone2")} />
              </label>
              <label className="cl-wide">
                Address
                <input value={form.address} onChange={set("address")} />
              </label>
            </div>

            <p className="cl-step">Services</p>
            <div className="vn-checks">
              {services.map((s) => (
                <label key={s.code} className="vn-check">
                  <input
                    type="checkbox"
                    checked={form.services.includes(s.code)}
                    onChange={(e) => toggle(s.code, e.target.checked)}
                  />
                  {s.label}
                </label>
              ))}
            </div>
            {form.services.includes("other") ? (
              <div className="cl-grid vn-other">
                <label className="cl-wide">
                  Other service
                  <input value={form.services_other} onChange={set("services_other")} maxLength={200} required />
                </label>
              </div>
            ) : null}

            <p className="cl-step">Fees and payment</p>
            <div className="cl-grid">
              <label>
                Fee (₹)
                <input inputMode="decimal" value={form.fee} onChange={set("fee")} placeholder="e.g. 1500" />
              </label>
              <label>
                Basis
                <select value={form.fee_basis} onChange={set("fee_basis")}>
                  {bases.map((b) => (
                    <option key={b.code} value={b.code}>
                      {b.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Last payment
                <input type="date" value={form.last_payment_date} onChange={set("last_payment_date")} />
              </label>
              <label>
                Status
                <select value={form.status} onChange={set("status")}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              <label className="cl-wide">
                Notes
                <textarea rows={2} value={form.notes} onChange={set("notes")} maxLength={4000} />
              </label>
            </div>
          </fieldset>
          {editing && editing !== "new" ? (
            <p className="muted cl-hint">Added {formatDay(editing.created_at)}</p>
          ) : null}
          {editing && editing !== "new" ? (
            <div className="vn-contracts">
              <ContractsPanel kind="vendor" vendorId={editing.id} partyName={editing.company_name} canEdit={canEdit} heading="Agreements" refreshKey={contractsKey} />
            </div>
          ) : null}
          <div className="cl-actions vn-actions">
            {canEdit && editing && editing !== "new" && editing.status === "active" ? (
              <button type="button" className="secondary vn-deact" disabled={saving} onClick={deactivate}>
                Deactivate
              </button>
            ) : null}
            <button type="button" className="secondary" disabled={saving} onClick={() => setEditing(null)}>
              {readOnly ? "Close" : "Cancel"}
            </button>
            {canEdit ? (
              <button type="submit" disabled={saving}>
                {saving ? "Saving…" : editing === "new" ? "Add vendor" : "Save"}
              </button>
            ) : null}
          </div>
        </form>
      </OpsModal>
      {contractFor ? (
        <SendContract
          party={{ kind: "vendor", vendorId: contractFor.id, partyName: contractFor.company_name }}
          onClose={() => setContractFor(null)}
          onDone={() => setContractsKey((n) => n + 1)}
        />
      ) : null}
    </>
  );
}
