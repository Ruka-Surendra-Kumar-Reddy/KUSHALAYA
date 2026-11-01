"use client";

import { withPublicBrand } from "@/lib/public-brand";

import { useCallback, useEffect, useRef, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyLetterList } from "@/components/livewell/family/FamilyKushLifeExtras";
import { FamilyContracts } from "@/components/contracts/FamilyContracts";
import {
  fetchFamilyDocumentTypes,
  fetchFamilyDocuments,
  uploadFamilyDocument,
  type FamilyDocument,
  type FamilyDocumentType,
} from "@/lib/livewell/familyApi";
import { getStoredAuth } from "@/lib/api";
import { familyDate } from "@/lib/livewell/familyTime";

/** Matches the server-side allowlist; keeps the picker from offering junk. */
const ACCEPT = ".pdf,.jpg,.jpeg,.png,.heic,.heif,.webp,.doc,.docx";

export default function FamilyDocumentsPage() {
  const [items, setItems] = useState<FamilyDocument[]>([]);
  const [types, setTypes] = useState<FamilyDocumentType[]>([]);
  const [docType, setDocType] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const [docs, docTypes] = await Promise.all([
        fetchFamilyDocuments(),
        fetchFamilyDocumentTypes(),
      ]);
      setItems(docs);
      setTypes(docTypes);
      setDocType((current) => current || docTypes[0]?.id || "");
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit() {
    setError("");
    setNotice("");
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    if (!docType) {
      setError("Pick a document type");
      return;
    }
    setBusy(true);
    try {
      await uploadFamilyDocument({ file, documentType: docType, note: note.trim() });
      setNotice("Uploaded. Your care team can now see this.");
      setFile(null);
      setNote("");
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function openDoc(doc: FamilyDocument) {
    try {
      const auth = getStoredAuth();
      const res = await fetch(doc.url, {
        headers: auth?.access_token
          ? { Authorization: `Bearer ${auth.access_token}` }
          : {},
      });
      if (!res.ok) throw new Error("Could not open document");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open");
    }
  }

  const typeLabel = (id: string) =>
    types.find((t) => t.id === id)?.label ?? id.replace(/^LW_/, "").replace(/_/g, " ");

  return (
    <FamilyShell title="Documents" subtitle="Care papers and records you share with the care team">
      <FamilyLetterList />
      <FamilyContracts />
      <FamilyError message={loadError} onRetry={() => void load()} what="your documents" />
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="muted">{notice}</p> : null}

      <section className="card home-safety-section">
        <h2>Upload a document</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Medical reports, prescriptions, insurance or ID. Your care team sees these on
          the client record.
        </p>
        <label className="home-safety-field">
          Type
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="home-safety-field">
          File
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label className="home-safety-field">
          Description (optional)
          <input
            type="text"
            value={note}
            maxLength={120}
            placeholder="e.g. Cardiology report, Mar 2026"
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <button type="button" disabled={busy} onClick={() => void submit()}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        <p className="muted" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
          PDF, photo or Word file, up to 10 MB.
        </p>
      </section>

      <section className="card home-safety-section">
        <h2>All documents</h2>
        <p className="muted home-safety-section-hint" style={{ marginTop: 0 }}>
          {withPublicBrand(
            "Papers your LiveWell360 team uploaded, plus anything you have shared.",
          )}
        </p>
        {items.length === 0 ? (
          <p className="muted">No documents yet.</p>
        ) : (
          <ul className="home-safety-family-doc-list">
            {items.map((d) => (
              <li key={d.id} className="card home-safety-family-doc-card">
                <div>
                  <strong>{d.title}</strong>
                  <p className="muted">
                    {typeLabel(d.document_type)}
                    {d.created_at
                      ? ` · ${familyDate(d.created_at)}`
                      : ""}
                    {d.uploaded_by_family ? " · shared by you" : ""}
                  </p>
                </div>
                <button type="button" className="secondary" onClick={() => openDoc(d)}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </FamilyShell>
  );
}
