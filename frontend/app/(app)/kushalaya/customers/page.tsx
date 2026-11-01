"use client";

import { FormEvent, useEffect, useState } from "react";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import { api, getStoredAuth } from "@/lib/api";
import { can } from "@/lib/roles";
import { canManageUsers } from "@/lib/auth";
import "@/components/ops/clients.css";
import { CustomersList } from "@/components/ops/CustomersList";
import { OpsModal } from "@/components/ops/OpsModal";

type Manager = { id: number; first_name: string; last_name: string };

const EMPTY = {
  first_name: "",
  last_name: "",
  phone: "",
  address: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  medical_conditions: "",
  manager_user_id: "",
  fam_name: "",
  fam_email: "",
  fam_password: "",
  fam_relationship: "son",
};

/** Customers: one aligned list; "+ Add customer" opens the new-client form. */
export default function ClientsPage() {
  const role = getStoredAuth()?.role || "";
  const isAdmin = canManageUsers(role);
  const edit = can("edit", role);
  const [reloadKey, setReloadKey] = useState(0);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (isAdmin) api<Manager[]>("/api/v1/team/managers").then(setManagers).catch(() => undefined);
  }, [isAdmin]);

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });


  async function add(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await api<{ first_name: string }>("/api/v1/team/clients", {
        method: "POST",
        body: JSON.stringify({
          first_name: form.first_name,
          last_name: form.last_name,
          phone: form.phone || null,
          address: form.address || null,
          emergency_contact_name: form.emergency_contact_name || null,
          emergency_contact_phone: form.emergency_contact_phone || null,
          medical_conditions: form.medical_conditions || null,
          manager_user_id: form.manager_user_id ? Number(form.manager_user_id) : null,
          family: form.fam_email
            ? { name: form.fam_name, email: form.fam_email, password: form.fam_password, relationship: form.fam_relationship }
            : null,
        }),
      });
      setMessage(
        form.fam_email
          ? `${created.first_name} added. The family signs in at family.kushalaya.com with ${form.fam_email.toLowerCase()} and the password you set.`
          : `${created.first_name} added.`,
      );
      setForm(EMPTY);
      setAdding(false);
      setReloadKey((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the client");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Customers" />
        {edit ? (
          <div className="ks-head-actions">
            <button type="button" onClick={() => setAdding(true)} aria-label="Add customer" title="Add customer">
              <span className="ks-ha-icon" aria-hidden="true">+</span>
              <span className="ks-ha-label">+ Add customer</span>
            </button>
          </div>
        ) : null}
      </div>
      <Flash error={adding ? "" : error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      <CustomersList reloadKey={reloadKey} />

      <OpsModal open={adding} title="New customer" onClose={() => setAdding(false)} wide>
        <form className="cl-form" onSubmit={add}>
          {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}
          <p className="cl-step">1 · The person we care for</p>
          <div className="cl-grid">
            <label>
              First name
              <input value={form.first_name} onChange={set("first_name")} required />
            </label>
            <label>
              Last name
              <input value={form.last_name} onChange={set("last_name")} />
            </label>
            <label>
              Phone
              <input type="tel" value={form.phone} onChange={set("phone")} placeholder="+91…" />
            </label>
            <label className="cl-wide">
              Home address
              <input value={form.address} onChange={set("address")} />
            </label>
            <label>
              Emergency contact
              <input value={form.emergency_contact_name} onChange={set("emergency_contact_name")} />
            </label>
            <label>
              Emergency phone (gets SMS / WhatsApp updates)
              <input type="tel" value={form.emergency_contact_phone} onChange={set("emergency_contact_phone")} />
            </label>
            <label className="cl-wide">
              Health notes
              <input value={form.medical_conditions} onChange={set("medical_conditions")} placeholder="Conditions, allergies, mobility aid" />
            </label>
            {isAdmin ? (
              <label>
                Manager
                <select value={form.manager_user_id} onChange={set("manager_user_id")}>
                  <option value="">Choose…</option>
                  {managers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.first_name} {m.last_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>

          <p className="cl-step">2 · Family sign-in (family.kushalaya.com)</p>
          <div className="cl-grid">
            <label>
              Family member&apos;s name
              <input value={form.fam_name} onChange={set("fam_name")} placeholder="e.g. Ravi Rao" />
            </label>
            <label>
              Relationship
              <select value={form.fam_relationship} onChange={set("fam_relationship")}>
                <option value="son">Son</option>
                <option value="daughter">Daughter</option>
                <option value="spouse">Spouse</option>
                <option value="family">Other family</option>
              </select>
            </label>
            <label>
              Email — this is their username
              <input type="email" value={form.fam_email} onChange={set("fam_email")} />
            </label>
            <label>
              Password (at least 8 characters)
              <input
                type="text"
                value={form.fam_password}
                onChange={set("fam_password")}
                minLength={form.fam_email ? 8 : undefined}
                required={!!form.fam_email}
              />
            </label>
          </div>
          <p className="muted cl-hint">You can skip the family sign-in and add it later from the client’s Family card.</p>
          <div className="cl-actions">
            <button type="button" className="secondary" disabled={saving} onClick={() => setAdding(false)}>
              Cancel
            </button>
            <button type="submit" disabled={saving}>
              {saving ? "Adding…" : "Add customer"}
            </button>
          </div>
        </form>
      </OpsModal>
    </>
  );
}
