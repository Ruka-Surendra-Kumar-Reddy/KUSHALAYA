"use client";

import { useEffect, useState } from "react";
import { dateTimeIST } from "@/lib/ist";
import { Flash } from "@/components/Flash";
import { MasterDataStagedPricingEditor } from "@/components/livewell/MasterDataStagedPricingEditor";
import {
  MASTER_IMPORT_STAGED_EVENT,
  MASTER_PENDING_STORAGE_KEY,
  MasterDataSyncBanner,
} from "@/components/livewell/MasterDataSyncBanner";
import {
  approveMasterImport,
  exportMasterWorkbook,
  fetchMasterDataCurrentSummary,
  fetchMasterDataSyncStatus,
  formatMasterDataSummary,
  importMasterWorkbook,
  listMasterVersions,
  refreshHomeSafetyCaches,
  rollbackMasterVersion,
  seedMasterDefaults,
  type MasterDataConfigSummary,
  type MasterDataImportResult,
  type MasterDataSyncStatus,
  type MasterDataVersionSummary,
} from "@/lib/livewell/masterDataApi";

function readStashedPending(): MasterDataImportResult | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(MASTER_PENDING_STORAGE_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(MASTER_PENDING_STORAGE_KEY);
    return JSON.parse(raw) as MasterDataImportResult;
  } catch {
    return null;
  }
}

export function MasterDataAdminEditor() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [comments, setComments] = useState("");
  const [pending, setPending] = useState<MasterDataImportResult | null>(null);
  const [versions, setVersions] = useState<MasterDataVersionSummary[]>([]);
  const [currentSummary, setCurrentSummary] = useState<MasterDataConfigSummary | null>(null);
  const [sync, setSync] = useState<MasterDataSyncStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);

  async function refreshMasterDataState() {
    const [nextVersions, summary, nextSync] = await Promise.all([
      listMasterVersions(),
      fetchMasterDataCurrentSummary().catch(() => null),
      fetchMasterDataSyncStatus().catch(() => null),
    ]);
    setVersions(nextVersions);
    setCurrentSummary(summary);
    setSync(nextSync);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("home-safety-master-sync-updated"));
    }
  }

  useEffect(() => {
    void refreshMasterDataState().catch(() => setVersions([]));
    const stashed = readStashedPending();
    if (stashed) {
      setPending(stashed);
      if (stashed.errors?.length) {
        setError(`Import rejected — ${stashed.errors.length} error(s). Fix the workbook and re-upload.`);
      } else {
        setMessage(
          `Staged version ${stashed.version_id}. Review warnings/diff below, then Approve.`,
        );
      }
    }
    function onStaged(ev: Event) {
      const result = (ev as CustomEvent<MasterDataImportResult>).detail;
      if (!result) return;
      setPending(result);
      setError(
        result.errors?.length
          ? `Import rejected — ${result.errors.length} error(s). Fix the workbook and re-upload.`
          : "",
      );
      setMessage(
        result.errors?.length
          ? ""
          : `Staged version ${result.version_id}. Review warnings/diff below, then Approve.`,
      );
      try {
        sessionStorage.removeItem(MASTER_PENDING_STORAGE_KEY);
      } catch {
        /* ignore */
      }
    }
    window.addEventListener(MASTER_IMPORT_STAGED_EVENT, onStaged);
    return () => window.removeEventListener(MASTER_IMPORT_STAGED_EVENT, onStaged);
  }, []);

  async function handleImport(file: File) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await importMasterWorkbook(file, comments);
      setPending(result);
      if (result.errors.length) {
        setError(`Import rejected — ${result.errors.length} error(s). Fix the workbook and re-upload.`);
      } else {
        setMessage(
          `Staged version ${result.version_id}. Review warnings/diff below, then Approve.`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setPending(null);
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!pending?.version_id || pending.errors.length) return;

    const preview = pending.catalog_photo_preview;
    if (preview?.would_lose_photos) {
      const ok = window.confirm(
        `This import would reduce showcase/catalog photos from ${preview.products_with_photos_before} to ${preview.products_with_photos_after} product(s) with linked images.\n\n` +
          "Recommended: cancel, roll back if needed, Export current workbook (includes ImageDocumentIDs), edit other sheets, re-import.\n\n" +
          "Approve anyway and accept photo link loss?",
      );
      if (!ok) return;
    }

    setBusy(true);
    setError("");
    try {
      const result = await approveMasterImport(pending.version_id, {
        confirmCatalogPhotoLoss: preview?.would_lose_photos ?? false,
      });
      await refreshHomeSafetyCaches();
      setMessage(
        `Approved ${result.version_id} — UploadId ${result.upload_id || result.version_id}. Applied: ${result.applied.join(", ") || "none"}. Local caches refreshed.`,
      );
      setPending(null);
      setComments("");
      await refreshMasterDataState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSeedDefaults() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await seedMasterDefaults();
      setPending(result);
      if (result.errors.length) {
        setError(`Factory workbook rejected — ${result.errors.length} error(s).`);
      } else {
        setMessage(
          `Staged factory spreadsheet as ${result.version_id}. Review diff, then Approve to load into the database.`,
        );
      }
      await refreshMasterDataState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stage factory workbook failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    setError("");
    try {
      await exportMasterWorkbook();
      setMessage(
        "Downloaded Kushalaya_Configuration.xlsx (includes 00_Meta UploadId). " +
          "If you edited config in the app, re-upload this file and Approve to clear the dirty alert.",
      );
      await refreshMasterDataState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  async function handleRollback(version: MasterDataVersionSummary) {
    const versionId = version.version_id;
    if (!versionId) return;

    const applied = version.applied?.length ? version.applied.join(", ") : "config";
    const approvedAt = version.approved_at
      ? dateTimeIST(version.approved_at)
      : "that import";

    const ok = window.confirm(
      `Roll back to the config snapshot from BEFORE import ${versionId}?\n\n` +
        `Approved: ${approvedAt}\n` +
        `Applied entities: ${applied}\n\n` +
        `This restores rubric, solutions, catalog, pricing, suppliers, and AI config as they were before that import — ` +
        `including catalog product photos (image links). Spreadsheet changes from that import will be undone.\n\n` +
        `That import and any newer imports will be removed from import history.\n\n` +
        `Photo files stay in tenant document storage; rollback restores the image_ids on each product.`,
    );
    if (!ok) return;

    setRollingBackId(versionId);
    setError("");
    setMessage("");
    try {
      const result = await rollbackMasterVersion(versionId);
      await refreshHomeSafetyCaches();
      await refreshMasterDataState();
      const summaryText = result.summary ? formatMasterDataSummary(result.summary) : "";
      const removed =
        result.versions_removed && result.versions_removed > 0
          ? ` Removed ${result.versions_removed} import(s) from history.`
          : "";
      setMessage(
        `Rolled back to the snapshot from before ${result.version_id}.` +
          removed +
          (summaryText ? ` Live config now: ${summaryText}.` : ""),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rollback failed");
    } finally {
      setRollingBackId(null);
    }
  }

  return (
    <div className="home-safety-master-data-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <MasterDataSyncBanner />

      <p className="muted">
        Configurations stay empty until you <strong>Upload</strong> (or stage the factory file) and{" "}
        <strong>Approve</strong>. The app then runs from the database. Edits in Catalog / Rubric /
        Pricing mark the tenant <strong>dirty</strong> vs the last UploadId — export the workbook,
        save it as your source of truth, then re-upload and Approve. Sheet <code>00_Meta</code> stores
        the UploadId on every export.
      </p>

      <details className="card home-safety-section" style={{ marginBottom: "1rem", padding: "0.75rem 1rem" }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>
          Catalog product photos (not in the spreadsheet)
        </summary>
        <ul className="muted" style={{ margin: "0.75rem 0 0", paddingLeft: "1.25rem", fontSize: "0.9rem" }}>
          <li>
            <strong>Files</strong> — uploaded JPEG/PNG stored as tenant documents (
            <code>HOME_SAFETY_CATALOG_IMAGE</code>) in blob storage (S3 or local, per deploy).
          </li>
          <li>
            <strong>Links</strong> — each product&apos;s <code>image_ids</code> in{" "}
            <code>workflow_config.home_safety_catalog</code> points at those document IDs.
          </li>
          <li>
            <strong>Upload</strong> — Catalog → expand a product → photos and vendor/cost (Preferred
            from sheet 08). Changing vendor marks dirty — Export + commit the xlsx, then Approve.
          </li>
          <li>
            <strong>Spreadsheet column</strong> — <code>ImageDocumentIDs</code> on sheet{" "}
            <code>05_Products</code> (comma-separated document IDs). Filled on{" "}
            <strong>Export current workbook</strong>; import restores links when ProductIDs match.
          </li>
          <li>
            <strong>After import</strong> — empty ImageDocumentIDs merges existing links for matching
            ProductIDs. Approve is blocked if linked photo count would drop (unless you confirm).
          </li>
          <li>
            If photos disappeared, use <strong>Rollback</strong> below (files usually remain on the
            server).
          </li>
        </ul>
      </details>

      {currentSummary ? (
        <section
          className="card home-safety-section"
          style={{ marginBottom: "1rem", borderLeft: "4px solid var(--color-primary, #2563eb)" }}
        >
          <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>Live config (what the app uses now)</h2>
          <p style={{ margin: 0 }}>{formatMasterDataSummary(currentSummary)}</p>
          <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
            {sync?.upload_id ? (
              <>
                Baseline UploadId: <code>{sync.upload_id}</code>
                {sync.exported_at ? ` · last export ${dateTimeIST(sync.exported_at)}` : ""}
              </>
            ) : (
              "No approved spreadsheet upload yet."
            )}
          </p>
        </section>
      ) : null}

      <div className="home-safety-rubric-admin actions" style={{ marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <button type="button" className="secondary" onClick={() => void handleExport()}>
          Export current workbook
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={() => void handleSeedDefaults()}>
          Stage factory spreadsheet
        </button>
        <label className="home-safety-field" style={{ margin: 0 }}>
          Comments (optional)
          <input
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            placeholder="e.g. Q2 catalog refresh"
          />
        </label>
        <label className="primary" style={{ display: "inline-block", cursor: "pointer" }}>
          {busy ? "Working…" : "Upload workbook"}
          <input
            type="file"
            accept=".xlsx,.xlsm"
            style={{ display: "none" }}
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImport(file);
              e.target.value = "";
            }}
          />
        </label>
        {pending && !pending.errors.length ? (
          <button type="button" className="primary" disabled={busy} onClick={() => void handleApprove()}>
            Approve import
          </button>
        ) : null}
      </div>

      {pending ? (
        <section className="card home-safety-section">
          <h2 style={{ marginTop: 0 }}>Staged import — {pending.version_id}</h2>
          <p className="muted">Status: <strong>{pending.status}</strong></p>
          <p className="muted">
            Sheets: {pending.sheets_found.join(", ") || "—"}
            {" · "}
            Entities: {pending.entities.join(", ") || "—"}
          </p>

          {pending.catalog_photo_preview?.would_lose_photos ? (
            <div
              className="home-safety-master-warnings"
              style={{ padding: "0.75rem", marginBottom: "1rem", borderRadius: "6px" }}
            >
              <strong>Showcase photos at risk</strong>
              <p style={{ margin: "0.35rem 0 0" }}>
                Linked catalog photos: {pending.catalog_photo_preview.products_with_photos_before} →{" "}
                {pending.catalog_photo_preview.products_with_photos_after} after approve. Export
                current workbook first, or confirm on Approve.
              </p>
            </div>
          ) : pending.catalog_photo_preview ? (
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Catalog photos preserved: {pending.catalog_photo_preview.products_with_photos_after}{" "}
              product(s) with linked images after merge.
            </p>
          ) : null}

          {pending.errors.length > 0 && (
            <div>
              <h3>Errors</h3>
              <ul className="home-safety-master-errors">
                {pending.errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {pending.warnings.length > 0 && (
            <div>
              <h3>Warnings</h3>
              <ul className="home-safety-master-warnings">
                {pending.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {!pending.errors.length ? (
            <MasterDataStagedPricingEditor
              pending={pending}
              busy={busy}
              onSaved={(result) => {
                setPending(result);
                setMessage(`Staged pricing saved for ${result.version_id}. Review diff, then Approve.`);
              }}
              onError={setError}
            />
          ) : null}

          <h3>Diff preview</h3>
          <pre className="home-safety-master-diff">{JSON.stringify(pending.diff, null, 2)}</pre>
          {pending.field_diff &&
          typeof pending.field_diff === "object" &&
          Array.isArray((pending.field_diff as { changes?: unknown }).changes) &&
          ((pending.field_diff as { changes: unknown[] }).changes?.length ?? 0) > 0 ? (
            <>
              <h3>Field changes (projected after approve)</h3>
              <ul className="home-safety-master-warnings">
                {(
                  pending.field_diff as {
                    changes: { entity: string; id: string; field: string; change_type: string }[];
                    change_count?: number;
                    truncated?: boolean;
                  }
                ).changes
                  .slice(0, 40)
                  .map((c, i) => (
                    <li key={`${c.entity}-${c.id}-${c.field}-${i}`}>
                      [{c.change_type}] {c.entity} {c.id}
                      {c.field !== "*" ? `.${c.field}` : ""}
                    </li>
                  ))}
              </ul>
              {(pending.field_diff as { truncated?: boolean; change_count?: number }).truncated ? (
                <p className="muted">
                  Showing first 40 of {(pending.field_diff as { change_count?: number }).change_count}{" "}
                  changes.
                </p>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}

      {versions.length > 0 && (
        <section className="card home-safety-section" style={{ marginTop: "1.25rem" }}>
          <h2 style={{ marginTop: 0 }}>Import history</h2>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            Each row is a past <strong>Approve</strong>. The snapshot column is config{" "}
            <em>before</em> that import — what rollback restores.{" "}
            <strong>Rollback</strong> on a row restores that snapshot, then removes that import and
            any newer imports from this list. Check <strong>Live config</strong> above for what is
            active now.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Approved</th>
                <th>Before import (snapshot)</th>
                <th>Applied</th>
                <th>Comments</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr
                  key={v.version_id ?? v.approved_at ?? ""}
                  style={v.matches_current ? { background: "rgba(37, 99, 235, 0.06)" } : undefined}
                >
                  <td>
                    <code>{v.version_id}</code>
                    {v.is_latest_import ? (
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--color-muted, #64748b)",
                          marginTop: "0.2rem",
                        }}
                      >
                        Latest import
                      </div>
                    ) : null}
                    {v.matches_current ? (
                      <div style={{ fontSize: "0.75rem", color: "var(--color-primary, #2563eb)", marginTop: "0.2rem" }}>
                        Same as live config
                      </div>
                    ) : null}
                  </td>
                  <td>{v.approved_at ? dateTimeIST(v.approved_at) : "—"}</td>
                  <td className="muted" style={{ fontSize: "0.85rem" }}>
                    {v.snapshot_summary
                      ? formatMasterDataSummary(v.snapshot_summary)
                      : "—"}
                  </td>
                  <td>{v.applied?.join(", ") || "—"}</td>
                  <td>{v.comments || "—"}</td>
                  <td>
                    {v.version_id ? (
                      <button
                        type="button"
                        className="secondary danger"
                        disabled={busy || rollingBackId !== null}
                        onClick={() => void handleRollback(v)}
                        title="Restore config from before this import was approved"
                      >
                        {rollingBackId === v.version_id ? "Rolling back…" : "Rollback"}
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
