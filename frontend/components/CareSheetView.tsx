"use client";

import { allergyState } from "@/lib/allergies";
import type { ClientSheet } from "@/lib/clientCare";
import "./care-sheet.css";

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function contact(name: string, phone: string) {
  return [name, phone].filter(Boolean).join(" · ");
}

/**
 * The one-page client sheet, read-only. Used by staff (print), the caregiver app on visit day
 * and the family portal. Keys and access show only when the API sent them (never to family).
 */
export function CareSheetView({ sheet, showContacts = true }: { sheet: ClientSheet; showContacts?: boolean }) {
  return (
    <div className="csv">
      {allergyState(sheet.allergies).kind === "listed" ? (
        <p className="csv-allergy" role="note">
          <strong>Allergies:</strong> {sheet.allergies}
        </p>
      ) : (
        <p className="csv-allergy is-none">
          <strong>Allergies:</strong> {allergyState(sheet.allergies).text}
        </p>
      )}

      <h3>Medicines</h3>
      {sheet.medicines.length ? (
        <table className="csv-meds">
          <thead>
            <tr>
              <th>Medicine</th>
              <th>Dose</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {sheet.medicines.map((m, i) => (
              <tr key={`${m.name}-${i}`}>
                <td>{m.name}</td>
                <td>{m.dose}</td>
                <td>{m.times}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="csv-muted">No medicines recorded</p>
      )}

      <dl className="csv-grid">
        <Row label="Conditions" value={sheet.conditions} />
        <Row label="Walking and mobility" value={sheet.mobility} />
        <Row label="Risks to watch" value={sheet.risks} />
        <Row label="Language" value={sheet.language} />
        <Row label="Doctor" value={contact(sheet.doctor_name, sheet.doctor_phone)} />
        <Row label="Hospital" value={contact(sheet.hospital_name, sheet.hospital_phone)} />
        {showContacts ? (
          <Row label="Emergency contact" value={contact(sheet.emergency_contact_name, sheet.emergency_contact_phone)} />
        ) : null}
        <Row label="Family preferences" value={sheet.family_preferences} />
        {sheet.keys_access !== undefined ? (
          <Row label="Keys and access (staff only)" value={sheet.keys_access || "Not recorded"} />
        ) : null}
      </dl>

      {sheet.open_risks?.length ? (
        <>
          <h3>Risk register</h3>
          <ul className="csv-risks">
            {sheet.open_risks.map((r, i) => (
              <li key={i} className={`is-${r.level}`}>
                <strong>{r.risk}</strong>
                {r.mitigation ? <span> — {r.mitigation}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
