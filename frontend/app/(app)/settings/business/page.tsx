"use client";

import { BackLink } from "@/components/ops/PageActions";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Flash } from "@/components/Flash";
import { getBusinessDetails, saveBusinessDetails, type BusinessDetails } from "@/lib/business";
import { listProducts } from "@/lib/commerce";
import "@/components/ops/notifications.css";
import "@/components/ops/business.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

/** Settings → Business details: what goes on every invoice (admins). */
export default function BusinessDetailsPage() {
  const router = useRouter();
  const isAdmin = isAdminUser();
  const [form, setForm] = useState<BusinessDetails | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isAdmin) {
      router.replace("/unauthorized");
      return;
    }
    getBusinessDetails()
      .then(setForm)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    listProducts(true)
      .then((ps) => setCategories(Array.from(new Set(ps.map((p) => p.category).filter(Boolean))).sort()))
      .catch(() => setCategories([]));
  }, [isAdmin, router]);

  const set = (patch: Partial<BusinessDetails>) => form && setForm({ ...form, ...patch });

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setError("");
    try {
      const { states: _s, state_name: _n, gst_registered: _g, ...body } = form;
      setForm(await saveBusinessDetails(body));
      setMessage("Business details saved. New invoices use them; old ones keep what they were issued with.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) return null;

  return (
    <div className="ks-frame">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Business details</h1>
        <p className="muted">Printed on every invoice and credit note. Invoices are made automatically when a family pays.</p>
      </header>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      {!form ? (
        <p className="muted">Loading…</p>
      ) : (
        <form className="card" onSubmit={submit}>
          {!form.gst_registered && (
            <p className="card od-banner" role="note">
              <strong>Add your GSTIN.</strong> Until then, payments get a “Bill of supply / receipt” with no GST breakdown.
            </p>
          )}
          {/* Hints sit under their input so every label and box lines up. */}
          <div className="od-form is-top">
            <label>
              Legal name
              <input value={form.legal_name} onChange={(e) => set({ legal_name: e.target.value })} required />
            </label>
            <label>
              Trade name
              <input value={form.trade_name} onChange={(e) => set({ trade_name: e.target.value })} />
              <small>Optional, shown in brackets</small>
            </label>
            <label>
              GSTIN
              <input
                value={form.gstin}
                maxLength={15}
                placeholder="36ABCDE1234F1Z5"
                onChange={(e) => set({ gstin: e.target.value.toUpperCase() })}
              />
              <small>15 characters; the state is taken from it</small>
            </label>
            <label>
              State
              <select
                value={form.state_code}
                disabled={!!form.gstin}
                onChange={(e) => set({ state_code: e.target.value })}
              >
                {form.states.map((s) => (
                  <option key={s.code} value={s.code}>{s.name} ({s.code})</option>
                ))}
              </select>
            </label>
            <label className="od-wide">
              Registered address
              <textarea rows={2} value={form.address} onChange={(e) => set({ address: e.target.value })} />
            </label>
            <label>
              Email on invoices
              <input type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} />
            </label>
            <label>
              Phone on invoices
              <input value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
            </label>
            <label>
              Invoice prefix
              <input
                value={form.invoice_prefix}
                maxLength={5}
                onChange={(e) => set({ invoice_prefix: e.target.value.toUpperCase() })}
              />
              <small>Up to 5 letters, e.g. KUS → KUS2627/00001</small>
            </label>
            <label>
              Default SAC / HSN
              <input value={form.default_sac} onChange={(e) => set({ default_sac: e.target.value })} />
              {/* Same as DEFAULT_SAC in backend gst_invoices.py; the hint goes once the owner sets a real code. */}
              {(form.default_sac || "").trim() === "9993" || !(form.default_sac || "").trim() ? (
                <small>9993 is a placeholder — confirm with your accountant</small>
              ) : null}
            </label>
          </div>
          {categories.length > 0 && (
            <>
              <h2>HSN / SAC by product category</h2>
              <p className="muted">Leave blank to use the default.</p>
              <div className="od-form">
                {categories.map((cat) => (
                  <label key={cat}>
                    {cat}
                    <input
                      value={form.hsn_by_category[cat] || ""}
                      placeholder={form.default_sac}
                      onChange={(e) => set({ hsn_by_category: { ...form.hsn_by_category, [cat]: e.target.value } })}
                    />
                  </label>
                ))}
              </div>
            </>
          )}
          <p>
            <button type="submit" className="primary" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </p>
        </form>
      )}
    </div>
  );
}
