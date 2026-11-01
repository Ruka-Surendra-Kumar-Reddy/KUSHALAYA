"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  downloadDocumentBlob,
  getStoredAuth,
  uploadDocument,
} from "@/lib/api";
import { canVerifyDocuments } from "@/lib/auth";
import { useBranding } from "@/components/BrandingProvider";
import {
  demandEntityLabel,
  supplyEntityLabel,
} from "@/lib/terminology";
import { Flash } from "@/components/Flash";
import { TranslatedPageHeader } from "@/components/TranslatedPageHeader";
import type { Caregiver, DocumentRow, Elder } from "@/lib/types";

function DocumentsContent() {
  const auth = getStoredAuth();
  const branding = useBranding();
  const demandLabel = demandEntityLabel(branding.vertical, branding.market);
  const supplyLabel = supplyEntityLabel(branding.vertical, branding.market);
  const searchParams = useSearchParams();
  const [clients, setClients] = useState<Elder[]>([]);
  const [workers, setWorkers] = useState<Caregiver[]>([]);
  const [entityType, setEntityType] = useState(
    searchParams.get("entity") === "caregiver" ? "caregiver" : "elder",
  );
  const [entityId, setEntityId] = useState<number | "">(
    searchParams.get("id") ? parseInt(searchParams.get("id")!, 10) : "",
  );
  const [docType, setDocType] = useState("PHOTO");
  const [file, setFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [pending, setPending] = useState<DocumentRow[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.all([
      api<Elder[]>("/api/v1/elders").then(setClients).catch(() => setClients([])),
      api<Caregiver[]>("/api/v1/caregivers")
        .then(setWorkers)
        .catch(() => setWorkers([])),
    ]).catch(() => {});
    if (canVerifyDocuments(auth?.role || "")) {
      api<DocumentRow[]>("/api/v1/documents/pending")
        .then(setPending)
        .catch(() => setPending([]));
    }
  }, [auth?.role]);

  async function loadDocs() {
    if (!entityId) return;
    setDocuments(
      await api<DocumentRow[]>(
        `/api/v1/documents/entity/${entityType}/${entityId}`,
      ),
    );
  }

  useEffect(() => {
    if (entityId) loadDocs().catch((e) => setError(String(e)));
  }, [entityType, entityId]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file || !entityId) return;
    const fd = new FormData();
    fd.append("entity_type", entityType);
    fd.append("entity_id", String(entityId));
    fd.append("document_type", docType);
    fd.append("file", file);
    try {
      await uploadDocument(fd);
      setMessage("Uploaded");
      setFile(null);
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function verify(id: number, status: "APPROVED" | "REJECTED") {
    let rejection_reason: string | undefined;
    if (status === "REJECTED") {
      const reason = prompt("Rejection reason:");
      if (!reason) return;
      rejection_reason = reason;
    }
    await api(`/api/v1/documents/${id}/verify`, {
      method: "POST",
      body: JSON.stringify({ status, rejection_reason }),
    });
    setMessage(`Document ${status.toLowerCase()}`);
    await loadDocs();
    setPending(await api<DocumentRow[]>("/api/v1/documents/pending"));
  }

  async function viewDoc(id: number) {
    const blob = await downloadDocumentBlob(id);
    window.open(URL.createObjectURL(blob), "_blank");
  }

  const entities: { id: number; first_name: string; last_name: string }[] =
    entityType === "caregiver" ? workers : clients;

  return (
    <>
      <TranslatedPageHeader pageKey="documents" />
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h2>Upload</h2>
        <form onSubmit={onUpload} className="grid-2">
          <div>
            <label>Record type</label>
            <select
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                setEntityId("");
              }}
            >
              <option value="elder">{demandLabel}</option>
              <option value="caregiver">{supplyLabel}</option>
            </select>
          </div>
          <div>
            <label>Person</label>
            <select
              value={entityId}
              onChange={(e) =>
                setEntityId(e.target.value ? parseInt(e.target.value, 10) : "")
              }
              required
            >
              <option value="">Select…</option>
              {entities.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.first_name} {row.last_name} (#{row.id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Document type</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="PHOTO">Photo</option>
              <option value="AADHAAR">Aadhaar</option>
              <option value="PAN">PAN</option>
              <option value="CERTIFICATE">Certificate</option>
              <option value="POLICE_VERIFICATION">Police verification</option>
            </select>
          </div>
          <div>
            <label>File</label>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="submit">Upload</button>
          </div>
        </form>
        {entities.length === 0 && (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            No {entityType === "elder" ? demandLabel.toLowerCase() : supplyLabel.toLowerCase()}{" "}
            records yet. Convert a prospect in Pipeline first.
          </p>
        )}
      </div>
      {canVerifyDocuments(auth?.role || "") && pending.length > 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Pending queue ({pending.length})</h2>
          <table className="table">
            <tbody>
              {pending.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.entity_type} #{d.entity_id} — {d.document_type}
                  </td>
                  <td>{d.file_name}</td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => verify(d.id, "APPROVED")}
                    >
                      Approve
                    </button>{" "}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => verify(d.id, "REJECTED")}
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="card">
        <h2>Documents</h2>
        {documents.length === 0 ? (
          <p className="muted">No documents</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>File</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id}>
                  <td>{d.document_type}</td>
                  <td>{d.file_name}</td>
                  <td>{d.verification_status}</td>
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => viewDoc(d.id)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default function DocumentsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <DocumentsContent />
    </Suspense>
  );
}
