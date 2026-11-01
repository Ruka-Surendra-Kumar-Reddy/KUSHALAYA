"use client";

import { FormEvent, useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import {
  fetchFamilyCircle,
  fetchFamilyElders,
  inviteFamilyCircleMember,
  removeFamilyCircleMember,
  type FamilyCircleMember,
} from "@/lib/livewell/familyApi";

export default function FamilyCirclePage() {
  const [members, setMembers] = useState<FamilyCircleMember[]>([]);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    email: "",
    phone: "",
    first_name: "",
    last_name: "",
    portal_relationship: "son",
  });

  const [senior, setSenior] = useState<{ id: number | null; name: string }>({ id: null, name: "" });

  async function load() {
    setMembers(await fetchFamilyCircle());
    const list = await fetchFamilyElders().catch(() => null);
    if (list) {
      const active = list.elders.find((e) => e.id === list.active_elder_id) || list.elders.find((e) => e.is_active);
      setSenior({ id: active?.id ?? list.active_elder_id ?? null, name: active?.name || list.senior_name || "" });
    }
  }
  const seniorName = senior.name || "your senior";

  function retry() {
    setLoadError("");
    load().catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    retry();
  }, []);

  const iAmPrimary = members.some((m) => m.is_you && m.is_primary);

  async function onRemove(m: FamilyCircleMember) {
    if (!window.confirm(`Remove ${m.first_name} ${m.last_name} (${m.email}) from ${seniorName}'s circle?`)) return;
    setError("");
    setMessage("");
    try {
      await removeFamilyCircleMember(m.id);
      setMessage(`Removed ${m.email} from ${seniorName}'s circle.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove");
    }
  }

  async function onInvite(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await inviteFamilyCircleMember({ ...form, elder_id: senior.id });
      setMessage(`Invited ${form.email}. They will get an email${form.phone ? " and a WhatsApp message" : ""} with a link to set their own password.`);
      setForm({
        email: "",
        phone: "",
        first_name: "",
        last_name: "",
        portal_relationship: "son",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <FamilyShell title="Family members" subtitle="People in the family who can see these updates">
      <FamilyError message={loadError} onRetry={retry} what="family members" />
      {error ? <p className="error-text">{error}</p> : null}
      {message ? <p className="home-safety-family-success">{message}</p> : null}

      <section className="home-safety-family-p0-section">
        <h2 className="home-safety-family-p0-heading">Members</h2>
        <ul className="home-safety-family-circle-list">
          {members.map((m) => (
            <li key={m.id} className="card home-safety-family-circle-card">
              <strong>
                {m.first_name} {m.last_name}
                {m.is_you ? " (you)" : ""}
                {m.is_primary ? (
                  <span className="home-safety-pill home-safety-pill-good fh-circle-primary">Primary</span>
                ) : null}
              </strong>
              <p className="muted">
                {m.email} · {m.portal_relationship}
              </p>
              {iAmPrimary && !m.is_you ? (
                <button type="button" className="secondary fh-circle-remove" onClick={() => void onRemove(m)}>
                  Remove
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      {!iAmPrimary ? (
        <p className="muted">Only the primary family member can add or remove people.</p>
      ) : (
      <section className="card home-safety-section">
        <h2>Invite someone</h2>
        <p className="muted home-safety-section-hint">
          Creates a family login for {seniorName} only. They receive a link to set their own password; nothing to share
          privately (WhatsApp / call).
        </p>
        <form className="home-safety-family-invite-form" onSubmit={(e) => void onInvite(e)}>
          <div className="home-safety-field-row">
            <label className="home-safety-field">
              First name
              <input
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                required
              />
            </label>
            <label className="home-safety-field">
              Last name
              <input
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                required
              />
            </label>
          </div>
          <label className="home-safety-field">
            Email
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </label>
          <label className="home-safety-field">
            Mobile number (optional, for the WhatsApp link)
            <input
              type="tel"
              inputMode="tel"
              placeholder="+91 98765 43210"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </label>
          <label className="home-safety-field">
            Relationship
            <select
              value={form.portal_relationship}
              onChange={(e) => setForm({ ...form, portal_relationship: e.target.value })}
            >
              <option value="son">Son</option>
              <option value="daughter">Daughter</option>
              <option value="spouse">Spouse</option>
              <option value="family">Family</option>
              <option value="nri">NRI / abroad</option>
              <option value="self">Self</option>
            </select>
          </label>
          <button type="submit" className="primary" disabled={saving}>
            {saving ? "Adding…" : "Add family member"}
          </button>
        </form>
      </section>
      )}
    </FamilyShell>
  );
}
