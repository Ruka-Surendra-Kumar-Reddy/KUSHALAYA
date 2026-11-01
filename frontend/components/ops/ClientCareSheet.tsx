"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CareSheetView } from "@/components/CareSheetView";
import { shortDate, type ClientSheet, type Medicine } from "@/lib/clientCare";
import "@/components/care-sheet.css";
import { can } from "@/lib/roles";

type TextKey =
  | "allergies"
  | "conditions"
  | "mobility"
  | "risks"
  | "keys_access"
  | "language"
  | "doctor_name"
  | "doctor_phone"
  | "hospital_name"
  | "hospital_phone"
  | "family_preferences";

const FIELDS: { key: TextKey; label: string; hint: string; long?: boolean }[] = [
  { key: "allergies", label: "Allergies", hint: "Medicines, foods — shown in red at the top", long: true },
  { key: "conditions", label: "Conditions", hint: "Diabetes, BP, knee replacement 2024…", long: true },
  { key: "mobility", label: "Walking and mobility", hint: "Walker indoors, needs a hand on stairs", long: true },
  { key: "risks", label: "Risks to watch", hint: "Falls at night, forgets the stove", long: true },
  { key: "keys_access", label: "Keys and access (staff only)", hint: "Key safe code, watchman name, spare key — never shown to family", long: true },
  { key: "language", label: "Language", hint: "Telugu, some English" },
  { key: "doctor_name", label: "Doctor", hint: "Dr name, clinic" },
  { key: "doctor_phone", label: "Doctor phone", hint: "+91 …" },
  { key: "hospital_name", label: "Hospital", hint: "Preferred hospital" },
  { key: "hospital_phone", label: "Hospital phone", hint: "+91 …" },
  { key: "family_preferences", label: "Family preferences", hint: "Call son before 9 pm; no visits during puja", long: true },
];

const BLANK: Medicine = { name: "", dose: "", times: "" };

/** Staff: the one-page client sheet — edit, print. */
export function ClientCareSheet({ elderId }: { elderId: number }) {
  const url = `/api/v1/home-safety/clients/${elderId}/sheet`;
  const [sheet, setSheet] = useState<ClientSheet | null>(null);
  const [form, setForm] = useState<ClientSheet | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api<ClientSheet>(url).then(setSheet).catch((e: Error) => setError(e.message));
  }, [url]);
  useEffect(() => load(), [load]);

  function print() {
    document.body.classList.add("csv-printing");
    const done = () => {
      document.body.classList.remove("csv-printing");
      window.removeEventListener("afterprint", done);
    };
    window.addEventListener("afterprint", done);
    window.print();
  }

  async function save() {
    if (!form) return;
    setSaving(true);
    setError("");
    try {
      const body: Record<string, unknown> = { medicines: form.medicines.filter((m) => m.name.trim()) };
      for (const f of FIELDS) body[f.key] = form[f.key] ?? "";
      const next = await api<ClientSheet>(url, { method: "PUT", body: JSON.stringify(body) });
      setSheet(next);
      setForm(null);
    } catch (e) {
      setError((e as Error).message || "Could not save");
    } finally {
      setSaving(false);
    }
  }

  function setMed(i: number, patch: Partial<Medicine>) {
    if (!form) return;
    const meds = form.medicines.map((m, j) => (j === i ? { ...m, ...patch } : m));
    setForm({ ...form, medicines: meds });
  }

  if (!sheet) return error ? <p className="cc-err">{error}</p> : null;

  return (
    <section className="card csv-print" id="sheet">
      <div className="csv-print-head">
        <h1 style={{ margin: 0 }}>{sheet.elder_name}</h1>
        <p style={{ margin: "2pt 0 6pt" }}>
          {[sheet.address, sheet.phone].filter(Boolean).join(" · ")}
          {sheet.updated_at ? ` · Sheet updated ${shortDate(sheet.updated_at)}` : ""}
        </p>
      </div>
      <div className="cc-head no-print">
        <h2>Client sheet</h2>
        <span className="cc-small">
          {sheet.updated_at
            ? `Updated ${shortDate(sheet.updated_at)}${sheet.updated_by ? ` by ${sheet.updated_by}` : ""}`
            : FIELDS.some((f) => String(sheet[f.key] ?? "").trim())
              ? "Filled in from the client record"
              : "Not filled in yet"}
        </span>
        <div className="cc-actions">
          {form ? (
            <>
              <button type="button" className="secondary" onClick={() => setForm(null)} disabled={saving}>
                Cancel
              </button>
              <button type="button" onClick={() => void save()} disabled={saving}>
                {saving ? "Saving…" : "Save sheet"}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="secondary" onClick={print}>
                Print
              </button>
              {can("edit") ? (
                <button
                  type="button"
                  onClick={() => setForm({ ...sheet, medicines: sheet.medicines.length ? sheet.medicines : [BLANK] })}
                >
                  Edit
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
      {error ? <p className="cc-err no-print">{error}</p> : null}

      {form ? (
        <div className="cc-form no-print">
          <div className="cc-wide">
            <strong>Medicines</strong>
            {form.medicines.map((m, i) => (
              <div className="cc-med" key={i}>
                <label>
                  <span className="cc-med-l">Medicine</span>
                  <input aria-label="Medicine" placeholder="Medicine" value={m.name} onChange={(e) => setMed(i, { name: e.target.value })} />
                </label>
                <label>
                  <span className="cc-med-l">Dose</span>
                  <input aria-label="Dose" placeholder="Dose (500 mg)" value={m.dose} onChange={(e) => setMed(i, { dose: e.target.value })} />
                </label>
                <label>
                  <span className="cc-med-l">When</span>
                  <input aria-label="When" placeholder="When (morning, night)" value={m.times} onChange={(e) => setMed(i, { times: e.target.value })} />
                </label>
                <button
                  type="button"
                  className="cc-med-remove"
                  aria-label={`Remove ${m.name || "medicine"}`}
                  onClick={() => setForm({ ...form, medicines: form.medicines.filter((_, j) => j !== i) })}
                >
                  Remove
                </button>
              </div>
            ))}
            <button type="button" className="secondary" onClick={() => setForm({ ...form, medicines: [...form.medicines, BLANK] })}>
              + Add medicine
            </button>
          </div>
          {FIELDS.map((f) => (
            <label key={f.key} className={f.long ? "cc-wide" : undefined}>
              {f.label}
              {f.long ? (
                <textarea rows={2} placeholder={f.hint} value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
              ) : (
                <input placeholder={f.hint} value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
              )}
            </label>
          ))}
        </div>
      ) : (
        <CareSheetView sheet={sheet} />
      )}
    </section>
  );
}
