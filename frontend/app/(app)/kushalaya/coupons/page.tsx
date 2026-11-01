"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/PageHeader";
import { formatIST } from "@/lib/ist";
import { Flash } from "@/components/Flash";
import { OpsModal } from "@/components/ops/OpsModal";
import { listCoupons, rupees, saveCoupon, type Coupon } from "@/lib/commerce";
import "@/components/ops/commerce.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

const EMPTY = { code: "", kind: "percent" as Coupon["kind"], value: "", expires: "", maxUses: "", note: "" };

/** yyyy-mm-dd in the browser's time, for the date input. */
function dateValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Coupons: admin creates codes; managers apply them on a client's order. */
export default function CouponsPage() {
  const isAdmin = isAdminUser();
  const router = useRouter();
  useEffect(() => {
    // Admin-only page (business/global data); the API refuses non-admins too.
    if (!isAdmin) router.replace("/unauthorized");
  }, [isAdmin, router]);
  const [coupons, setCoupons] = useState<Coupon[] | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | "form" | null>(null);
  // The form opens from "+ New coupon" (or Edit); the list comes first.
  const [formOpen, setFormOpen] = useState(false);

  const load = () => listCoupons().then(setCoupons);

  useEffect(() => {
    if (!isAdmin) return;
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [isAdmin]);

  function edit(c: Coupon) {
    setError("");
    setMessage("");
    setEditingId(c.id);
    setFormOpen(true);
    setForm({
      code: c.code,
      kind: c.kind,
      value: String(c.value / 100),
      expires: dateValue(c.expires_at),
      maxUses: c.max_uses ? String(c.max_uses) : "",
      note: c.note || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function stopEditing() {
    setEditingId(null);
    setForm(EMPTY);
    setFormOpen(false);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    const v = Number(form.value || 0);
    if (!Number.isFinite(v) || v <= 0) return setError("Enter a discount above zero.");
    if (form.kind === "percent" && v > 100) return setError("A % coupon can be at most 100%.");
    if (form.maxUses && (!Number.isInteger(Number(form.maxUses)) || Number(form.maxUses) < 1))
      return setError("Times it can be used must be a whole number, 1 or more — or leave it empty for no limit.");
    setBusy("form");
    try {
      // Both kinds are stored ×100: % as basis points, ₹ as paise.
      const body = {
        kind: form.kind,
        value: Math.round(v * 100),
        expires_at: form.expires ? new Date(`${form.expires}T23:59:59`).toISOString() : null,
        max_uses: form.maxUses ? Number(form.maxUses) : null,
        note: form.note,
      };
      if (editingId) {
        await saveCoupon(editingId, body);
        setMessage(`Coupon ${form.code} saved.`);
      } else {
        await saveCoupon(null, { ...body, code: form.code });
        setMessage(`Coupon ${form.code.toUpperCase()} created.`);
      }
      stopEditing();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the coupon");
    } finally {
      setBusy(null);
    }
  }

  async function toggle(c: Coupon) {
    setError("");
    setBusy(c.id);
    try {
      await saveCoupon(c.id, { active: !c.active });
      setMessage(`${c.code} is ${c.active ? "off" : "on"}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the coupon");
    } finally {
      setBusy(null);
    }
  }

  const label = (c: Coupon) => (c.kind === "percent" ? `${c.value / 100}% off` : `${rupees(c.value)} off`);

  if (!isAdmin) return null;
  return (
    <div className="ks-frame">
      <div className="ks-head-row">
        <PageHeader title="Coupons" subtitle="Discount codes staff add to a client's order" />
        {isAdmin ? (
          <div className="ks-head-actions">
            <button
              type="button"
              onClick={() => {
                setError("");
                setMessage("");
                setFormOpen(true);
              }}
              aria-label="New coupon"
              title="New coupon"
            >
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ New coupon</span>
            </button>
          </div>
        ) : null}
      </div>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      <OpsModal open={isAdmin && formOpen} title={editingId ? `Edit coupon ${form.code}` : "New coupon"} onClose={stopEditing}>
          <form className="cm-form" onSubmit={submit}>
            {error ? <p className="ks-modal-error cm-wide" role="alert">{error}</p> : null}
            <label>
              Code
              <input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                placeholder="e.g. FESTIVE10"
                pattern="[A-Za-z0-9\-]{1,40}"
                title="Letters, numbers and dashes"
                disabled={editingId !== null}
                required
              />
            </label>
            <label>
              Type
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as Coupon["kind"] })}>
                <option value="percent">% off</option>
                <option value="amount">₹ off</option>
              </select>
            </label>
            <label>
              {form.kind === "percent" ? "Discount (%)" : "Discount (₹)"}
              <input
                type="number"
                min={0}
                max={form.kind === "percent" ? 100 : undefined}
                step={form.kind === "percent" ? "0.5" : "1"}
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                required
              />
            </label>
            <label>
              Expires on
              <input type="date" value={form.expires} onChange={(e) => setForm({ ...form, expires: e.target.value })} />
            </label>
            <label>
              Times it can be used
              <input type="number" min={1} value={form.maxUses} onChange={(e) => setForm({ ...form, maxUses: e.target.value })} placeholder="No limit" />
            </label>
            <label className="cm-wide">
              Note
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="e.g. Diwali offer for new families" />
            </label>
            <div className="cm-actions">
              <button type="button" className="secondary" onClick={stopEditing}>
                Cancel
              </button>
              <button type="submit" disabled={busy === "form"}>
                {busy === "form" ? "Saving…" : editingId ? "Save coupon" : "Create coupon"}
              </button>
            </div>
          </form>
      </OpsModal>

      <div className="card cm-cp-card">
        {coupons === null ? (
          <p className="muted">Loading…</p>
        ) : coupons.length === 0 ? (
          <p className="muted">No coupons yet.{isAdmin ? " Use + New coupon, e.g. DIWALI10 for 10% off." : " An admin creates them."}</p>
        ) : (
          <table className="table cm-table cm-cp-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Status</th>
                <th>Discount</th>
                <th>Used</th>
                <th>Expires</th>
                <th>Note</th>
                {isAdmin ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {coupons.map((c) => (
                <tr key={c.id} className={c.active ? "" : "is-off"}>
                  <td className="cm-cp-code">
                    <strong className="cm-code">{c.code}</strong>
                  </td>
                  <td className="cm-cp-statuscell">
                    <span className={`cm-cp-status${c.active ? " is-on" : ""}`}>{c.active ? "Active" : "Off"}</span>
                  </td>
                  <td data-label="Discount">{label(c)}</td>
                  <td data-label="Used">
                    {c.used_count}
                    {c.max_uses ? ` of ${c.max_uses}` : ""}
                  </td>
                  <td data-label="Expires">{c.expires_at ? formatIST(c.expires_at, { dateOnly: true }) : "Never"}</td>
                  <td data-label="Note" className="cm-cp-note">{c.note || "—"}</td>
                  {isAdmin ? (
                    <td className="cm-cp-act">
                      <button type="button" className="secondary" onClick={() => edit(c)} aria-label={`Edit ${c.code}`}>
                        Edit
                      </button>
                      <button type="button" className="secondary" disabled={busy === c.id} onClick={() => void toggle(c)} aria-label={`${c.active ? "Turn off" : "Turn on"} ${c.code}`}>
                        {c.active ? "Turn off" : "Turn on"}
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
