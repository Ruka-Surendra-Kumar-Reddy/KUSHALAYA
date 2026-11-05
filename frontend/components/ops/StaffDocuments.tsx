"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { OpsModal } from "@/components/ops/OpsModal";
import { api, downloadFileBlob, postFormData } from "@/lib/api";
import { parseApiTime } from "@/lib/ist";

type Doc = {
  id: number;
  doc_type: string;
  file_name: string;
  uploaded_by: string;
  created_at: string | null;
};

const DOC_TYPES: { code: string; label: string }[] = [
  { code: "offer_letter", label: "Offer letter (signed)" },
  { code: "relieving_letter", label: "Relieving letter" },
  { code: "id_proof", label: "ID proof" },
  { code: "other", label: "Other" },
];

/** Optional HR papers for one team member. Admins only; the API enforces that too. */
export function StaffDocuments({
  person,
  onClose,
}: {
  person: { type: "staff" | "caregiver"; id: number; name: string };
  onClose: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [docType, setDocType] = useState(DOC_TYPES[0].code);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/api/v1/staff-documents/${person.type}/${person.id}`;

  const load = useCallback(() => {
    api<Doc[]>(path)
      .then(setDocs)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load documents"));
  }, [path]);

  useEffect(load, [load]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function upload(file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("doc_type", docType);
    form.append("file", file);
    void run(async () => {
      await postFormData(path, form);
      load();
    });
    if (input.current) input.current.value = "";
  }

  function view(d: Doc) {
    // Open the tab inside the click, or the browser blocks it as a popup.
    const tab = window.open("", "_blank");
    void run(async () => {
      try {
        const url = URL.createObjectURL(await downloadFileBlob(`/api/v1/staff-documents/file/${d.id}`));
        if (tab) tab.location.href = url;
        window.setTimeout(() => URL.revokeObjectURL(url), 300_000);
      } catch (e) {
        tab?.close();
        throw e;
      }
    });
  }

  function download(d: Doc) {
    void run(async () => {
      const url = URL.createObjectURL(await downloadFileBlob(`/api/v1/staff-documents/file/${d.id}`));
      const link = document.createElement("a");
      link.href = url;
      link.download = d.file_name;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    });
  }

  function remove(d: Doc) {
    if (!window.confirm(`Remove ${d.file_name}?`)) return;
    void run(async () => {
      await api(`/api/v1/staff-documents/file/${d.id}`, { method: "DELETE" });
      load();
    });
  }

  return (
    <OpsModal open title={`Documents · ${person.name}`} onClose={onClose}>
      <p className="muted tm-docs-note">Optional. Only admins can see these. PDF, JPG or PNG, 10 MB at most.</p>
      <div className="tm-docs-add">
        <select aria-label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)}>
          {DOC_TYPES.map((t) => (
            <option key={t.code} value={t.code}>
              {t.label}
            </option>
          ))}
        </select>
        <button type="button" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Working…" : "Upload"}
        </button>
        <input
          ref={input}
          type="file"
          hidden
          accept="application/pdf,image/jpeg,image/png"
          onChange={(e) => upload(e.target.files?.[0])}
        />
      </div>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {docs === null ? (
        <p className="muted">Loading…</p>
      ) : docs.length === 0 ? (
        <p className="muted">No documents yet.</p>
      ) : (
        <ul className="tm-docs">
          {docs.map((d) => (
            <li key={d.id}>
              <span className="tm-docs-info">
                <strong>{DOC_TYPES.find((t) => t.code === d.doc_type)?.label || d.doc_type}</strong>
                <span className="tm-docs-name">{d.file_name}</span>
                <span className="muted">
                  {d.created_at
                    ? parseApiTime(d.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
                    : ""}
                  {d.uploaded_by ? ` · ${d.uploaded_by}` : ""}
                </span>
              </span>
              <span className="tm-docs-acts">
                <button type="button" className="secondary" disabled={busy} onClick={() => view(d)}>
                  View
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => download(d)}>
                  Download
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => remove(d)}>
                  Remove
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </OpsModal>
  );
}
