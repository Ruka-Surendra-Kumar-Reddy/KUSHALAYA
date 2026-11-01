"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  fetchMasterDataSyncStatus,
  importMasterWorkbook,
  type MasterDataFieldChange,
  type MasterDataImportResult,
  type MasterDataSyncStatus,
} from "@/lib/livewell/masterDataApi";

export const MASTER_PENDING_STORAGE_KEY = "livewell-master-data-pending";
export const MASTER_IMPORT_STAGED_EVENT = "home-safety-master-import-staged";

function formatChange(change: MasterDataFieldChange): string {
  const loc = change.field === "*" ? change.id : `${change.id}.${change.field}`;
  if (change.change_type === "added") return `+ ${change.entity} ${loc}`;
  if (change.change_type === "removed") return `− ${change.entity} ${loc}`;
  return `~ ${change.entity} ${loc}`;
}

function stashPending(result: MasterDataImportResult) {
  try {
    sessionStorage.setItem(MASTER_PENDING_STORAGE_KEY, JSON.stringify(result));
  } catch {
    /* ignore quota / private mode */
  }
  window.dispatchEvent(
    new CustomEvent(MASTER_IMPORT_STAGED_EVENT, { detail: result }),
  );
}

export function MasterDataSyncBanner({ compact = false }: { compact?: boolean }) {
  const [sync, setSync] = useState<MasterDataSyncStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const pathname = usePathname();
  const router = useRouter();
  const onMasterDataPage = pathname?.startsWith("/kushalaya/master-data") ?? false;

  const refresh = useCallback(() => {
    void fetchMasterDataSyncStatus()
      .then(setSync)
      .catch(() => setSync(null));
  }, []);

  useEffect(() => {
    refresh();
    const onUpdate = () => refresh();
    window.addEventListener("home-safety-master-sync-updated", onUpdate);
    window.addEventListener("home-safety-rubric-updated", onUpdate);
    window.addEventListener("home-safety-suppliers-updated", onUpdate);
    return () => {
      window.removeEventListener("home-safety-master-sync-updated", onUpdate);
      window.removeEventListener("home-safety-rubric-updated", onUpdate);
      window.removeEventListener("home-safety-suppliers-updated", onUpdate);
    };
  }, [refresh]);

  async function handleFile(file: File) {
    setBusy(true);
    setError("");
    try {
      const result = await importMasterWorkbook(file);
      stashPending(result);
      if (!onMasterDataPage) {
        router.push("/kushalaya/master-data");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (!sync) return null;
  if (!sync.requires_upload && !sync.dirty) {
    if (compact) return null;
    return (
      <div
        className="home-safety-master-sync-banner in-sync"
        style={{
          padding: "0.65rem 0.85rem",
          marginBottom: "1rem",
          borderRadius: 8,
          background: "#eef8f4",
          border: "1px solid #b7e0d0",
          fontSize: "0.9rem",
        }}
      >
        <strong>Spreadsheet sync:</strong> {sync.message}
        {sync.upload_id ? (
          <span className="muted"> · UploadId <code>{sync.upload_id}</code></span>
        ) : null}
      </div>
    );
  }

  const tone = sync.requires_upload
    ? { bg: "#fff8e8", border: "#f0d48a", title: "Master data not loaded" }
    : { bg: "#fff4f0", border: "#f0c2b4", title: "Spreadsheet out of date" };

  const changes = sync.drift?.changes?.slice(0, compact ? 5 : 25) ?? [];

  return (
    <div
      className="home-safety-master-sync-banner"
      style={{
        padding: "0.75rem 0.9rem",
        marginBottom: "1rem",
        borderRadius: 8,
        background: tone.bg,
        border: `1px solid ${tone.border}`,
        fontSize: "0.9rem",
      }}
    >
      <strong>{tone.title}</strong>
      <p style={{ margin: "0.35rem 0 0.5rem" }}>{sync.message}</p>
      {sync.upload_id ? (
        <p className="muted" style={{ margin: "0 0 0.5rem", fontSize: "0.85rem" }}>
          Baseline UploadId: <code>{sync.upload_id}</code>
          {sync.dirty && sync.drift?.change_count
            ? ` · ${sync.drift.change_count} field change(s)`
            : null}
        </p>
      ) : null}
      {changes.length > 0 ? (
        <ul style={{ margin: "0 0 0.5rem", paddingLeft: "1.2rem" }}>
          {changes.map((c, i) => (
            <li key={`${c.entity}-${c.id}-${c.field}-${i}`}>{formatChange(c)}</li>
          ))}
        </ul>
      ) : null}
      {error ? (
        <p style={{ margin: "0 0 0.5rem", color: "var(--color-danger, #b91c1c)" }}>{error}</p>
      ) : null}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", alignItems: "center" }}>
        <label
          className="primary"
          style={{
            display: "inline-block",
            cursor: busy ? "wait" : "pointer",
            opacity: busy ? 0.7 : 1,
            margin: 0,
          }}
        >
          {busy ? "Uploading…" : "Upload workbook"}
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm"
            style={{ display: "none" }}
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
            }}
          />
        </label>
        {!onMasterDataPage ? (
          <Link href="/kushalaya/master-data">Open Master Data to Approve</Link>
        ) : (
          <span className="muted">Then review the staged import below and Approve.</span>
        )}
        {!sync.requires_upload ? (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Tip: Export first if you still need to capture in-app edits.
          </span>
        ) : null}
      </div>
    </div>
  );
}
