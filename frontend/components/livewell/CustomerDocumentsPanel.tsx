"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import {
  CUSTOMER_DOC_TEMPLATES,
  PACKET_LABELS,
  type CustomerDocFormCode,
  type CustomerDocPacket,
} from "@/lib/livewell/customerDocumentTemplates";
import {
  listSignedDocsForAssessment,
  signedDocFileUrl,
  uploadSignedDoc,
  type SignedDocRecord,
} from "@/lib/livewell/signedDocs";
import { resolveElderIdForProspect } from "@/lib/livewell/photos";
import { stripAssessmentIdSuffix } from "@/lib/livewell/assessmentDisplay";

const PACKETS: CustomerDocPacket[] = [
  "enrollment",
  "assessment",
  "installation",
  "completion",
];

export function CustomerDocumentsPanel({
  assessment,
}: {
  assessment: HomeSafetyAssessment;
}) {
  const [docs, setDocs] = useState<SignedDocRecord[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [formCode, setFormCode] = useState<CustomerDocFormCode>("LW_HOME_ASSESSMENT_CONSENT");
  const [notes, setNotes] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try {
      const rows = await listSignedDocsForAssessment(assessment.id);
      setDocs(rows);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load signed documents");
    }
  }, [assessment.id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onUpload(file: File | null) {
    if (!file) return;
    setBusyCode(formCode);
    setError("");
    setMessage("");
    try {
      let elderId = assessment.elderId;
      if (!elderId && assessment.prospectId) {
        elderId = await resolveElderIdForProspect(assessment.prospectId);
      }
      if (!assessment.prospectId && !elderId) {
        throw new Error(
          "Link this assessment to a prospect or elder before uploading signed documents.",
        );
      }
      await uploadSignedDoc({
        file,
        formCode,
        assessmentId: assessment.id,
        prospectId: assessment.prospectId,
        elderId,
        notes: notes.trim() || undefined,
      });
      setNotes("");
      setMessage(`Uploaded signed ${formCode.replace(/_/g, " ").toLowerCase()}.`);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusyCode(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const uploadedCodes = new Set(docs.map((d) => d.form_code));

  return (
    <section className="card home-safety-section home-safety-signed-docs">
      <h2>Customer documents</h2>
      <p className="muted">
        Print the paper pack with customer details filled in, collect wet signatures, then upload
        scans or photos of the signed pages.
      </p>
      <div className="home-safety-signed-docs-actions">
        {/* Full page load — soft Next Link / client router can fail under PWA / stale bundles. */}
        <a
          href={`/kushalaya/assess/${encodeURIComponent(assessment.id)}/documents`}
          className="primary home-safety-signed-docs-print-link"
          onClick={(e) => {
            e.preventDefault();
            window.location.assign(
              `/kushalaya/assess/${encodeURIComponent(assessment.id)}/documents`,
            );
          }}
        >
          Print / view pack
        </a>
        <a
          href={`/kushalaya/assess/${encodeURIComponent(assessment.id)}/documents?form=LW_EMERGENCY_INFO_SHEET`}
          className="home-safety-signed-docs-print-link"
          onClick={(e) => {
            e.preventDefault();
            window.location.assign(
              `/kushalaya/assess/${encodeURIComponent(assessment.id)}/documents?form=LW_EMERGENCY_INFO_SHEET`,
            );
          }}
        >
          Print Emergency Information Sheet
        </a>
      </div>
      <p className="muted">
        The Emergency Information Sheet is included with Safety Assessment (catalog EMG-001).
        Complete intake contacts + medical fields, print, post in the home, then upload a photo
        below.
      </p>

      {error ? <p className="error-text">{error}</p> : null}
      {message ? <p className="success">{message}</p> : null}

      <h3>Upload wet-signed scan or photo</h3>
      <div className="home-safety-signed-docs-upload grid-2">
        <div>
          <label htmlFor="signed-doc-type">Document type</label>
          <select
            id="signed-doc-type"
            value={formCode}
            onChange={(e) => setFormCode(e.target.value as CustomerDocFormCode)}
          >
            {PACKETS.map((packet) => (
              <optgroup key={packet} label={PACKET_LABELS[packet]}>
                {CUSTOMER_DOC_TEMPLATES.filter((t) => t.packet === packet).map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.title}
                    {uploadedCodes.has(t.code) ? " ✓" : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="signed-doc-notes">Notes (optional)</label>
          <input
            id="signed-doc-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. pages 1–2, left blank emergency phone"
          />
        </div>
        <div className="home-safety-signed-docs-file">
          <label htmlFor="signed-doc-file">PDF or photo (JPEG/PNG)</label>
          <input
            id="signed-doc-file"
            ref={inputRef}
            type="file"
            accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png"
            capture="environment"
            disabled={Boolean(busyCode)}
            onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
          />
          {busyCode ? <p className="muted">Uploading…</p> : null}
        </div>
      </div>

      <h3>Uploaded for this assessment</h3>
      {docs.length === 0 ? (
        <p className="muted">No signed documents uploaded yet.</p>
      ) : (
        <ul className="home-safety-signed-docs-list">
          {docs.map((d) => (
            <li key={d.id}>
              <strong>{stripAssessmentIdSuffix(d.document_name)}</strong>
              <span className="muted">
                {" "}
                · {d.signature_status || "captured"} · {d.uploaded_at?.slice(0, 10) || "—"}
              </span>
              <a
                href={signedDocFileUrl(d.id)}
                target="_blank"
                rel="noreferrer"
                className="home-safety-signed-docs-view"
              >
                View
              </a>
            </li>
          ))}
        </ul>
      )}

      <p className="muted home-safety-signed-docs-legal">
        Templates are Hyderabad pilot drafts ({docs[0]?.template_version || "2026.07-HYD"}). Have
        Indian counsel review before production use.
      </p>
    </section>
  );
}
