"use client";

import { allergyState } from "@/lib/allergies";
import { FormEvent, useState } from "react";
import { updateClientDetails, type ClientDetails, type ClientPerson } from "@/lib/livewell/clientProfileApi";
import { can } from "@/lib/roles";

const GENDERS: Record<string, string> = { male: "Male", female: "Female", other: "Other", m: "Male", f: "Female" };

function dob(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="cp-field">
      <span>{label}</span>
      <strong className={value?.trim() && value.trim() !== "Not recorded" ? "" : "cp-none"}>{value?.trim() || "Not recorded"}</strong>
    </div>
  );
}

const KEYS = [
  "phone",
  "address",
  "date_of_birth",
  "gender",
  "emergency_contact_name",
  "emergency_contact_phone",
  "medical_conditions",
  "allergies",
  "mobility_status",
] as const;
type Key = (typeof KEYS)[number];

function draftOf(p: ClientPerson): Record<Key, string> {
  const out = {} as Record<Key, string>;
  for (const k of KEYS) out[k] = k === "date_of_birth" ? (p.date_of_birth || "").slice(0, 10) : (p[k] ?? "");
  const g = out.gender.trim().toLowerCase();
  out.gender = g === "m" ? "male" : g === "f" ? "female" : g;
  return out;
}

/** Overview: Personal + Health cards, with an inline "Edit details" form (PUT /elders/{id}). */
export function ClientEditForm({
  person,
  carePlan,
  careStatus,
  onSaved,
}: {
  person: ClientPerson;
  carePlan?: string | null;
  careStatus?: string | null;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const canEdit = can("edit");
  const [draft, setDraft] = useState(() => draftOf(person));
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  const set = (k: Key) => (e: { target: { value: string } }) => setDraft({ ...draft, [k]: e.target.value });

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    // Only what changed: an unchanged address is not geocoded again.
    const before = draftOf(person);
    const payload: ClientDetails = {};
    for (const k of KEYS) {
      const v = draft[k].trim();
      if (v !== before[k].trim()) (payload as Record<string, string | null>)[k] = v || null;
    }
    if (!Object.keys(payload).length) {
      setEditing(false);
      setBusy(false);
      return;
    }
    try {
      await updateClientDetails(person.id, payload);
      setNote({ ok: true, text: "Details saved." });
      setEditing(false);
      onSaved();
    } catch (err) {
      setNote({ ok: false, text: err instanceof Error ? err.message : "Could not save the details" });
    } finally {
      setBusy(false);
    }
  }

  const status = [careStatus, person.care_level ? `Care level: ${person.care_level}` : ""].filter(Boolean).join(" · ");

  if (editing) {
    return (
      <form className="card cp-edit" onSubmit={save}>
        <h2>Edit details</h2>
        <div className="cp-edit-grid">
          <label>
            Phone
            <input type="tel" value={draft.phone} onChange={set("phone")} />
          </label>
          <label>
            Date of birth
            <input type="date" value={draft.date_of_birth} onChange={set("date_of_birth")} />
          </label>
          <label>
            Gender
            <select value={draft.gender} onChange={set("gender")}>
              <option value="">Not recorded</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="cp-edit-wide">
            Address
            <input value={draft.address} onChange={set("address")} />
          </label>
          <label>
            Emergency contact name
            <input value={draft.emergency_contact_name} onChange={set("emergency_contact_name")} />
          </label>
          <label>
            Emergency contact phone
            <input type="tel" value={draft.emergency_contact_phone} onChange={set("emergency_contact_phone")} />
          </label>
          <label className="cp-edit-wide">
            Conditions and health notes
            <textarea rows={2} value={draft.medical_conditions} onChange={set("medical_conditions")} />
          </label>
          <label>
            Allergies
            <input value={draft.allergies} onChange={set("allergies")} />
          </label>
          <label>
            Mobility
            <input value={draft.mobility_status} onChange={set("mobility_status")} placeholder="e.g. Walks with a stick" />
          </label>
        </div>
        <div className="cp-edit-actions">
          <button type="submit" className="primary" disabled={busy}>
            {busy ? "Saving…" : "Save details"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => {
              setDraft(draftOf(person));
              setEditing(false);
              setNote(null);
            }}
          >
            Cancel
          </button>
        </div>
        {note ? <p className={note.ok ? "cp-ok" : "error-text"}>{note.text}</p> : null}
      </form>
    );
  }

  return (
    <>
      <section className="card">
        <div className="cp-card-head">
          <h2>Personal</h2>
          {canEdit ? (
          <button
            type="button"
            className="cp-linkbtn"
            onClick={() => {
              setDraft(draftOf(person));
              setEditing(true);
              setNote(null);
            }}
          >
            Edit details
          </button>
          ) : null}
        </div>
        <div className="cp-fields">
          <Field label="Phone" value={person.phone} />
          <Field label="Date of birth" value={person.date_of_birth ? dob(person.date_of_birth) : null} />
          <Field label="Gender" value={person.gender ? GENDERS[person.gender.toLowerCase()] ?? person.gender : null} />
          <Field label="Address" value={person.address} />
          <Field label="Emergency contact" value={person.emergency_contact_name} />
          <Field label="Emergency phone" value={person.emergency_contact_phone} />
        </div>
        {note ? <p className={note.ok ? "cp-ok" : "error-text"}>{note.text}</p> : null}
      </section>
      <section className="card">
        <h2>Health and care</h2>
        <div className="cp-fields">
          <Field label="Conditions" value={person.medical_conditions} />
          <Field label="Allergies" value={allergyState(person.allergies).text} />
          <Field label="Mobility" value={person.mobility_status} />
          <Field label="Care plan" value={carePlan} />
          <Field label="Care status" value={status} />
        </div>
      </section>
    </>
  );
}
