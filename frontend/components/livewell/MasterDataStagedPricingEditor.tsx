"use client";

import { useEffect, useState } from "react";
import { PricingConfigFields } from "@/components/livewell/PricingConfigFields";
import { DEFAULT_SAFEHOME_PRICING } from "@/lib/livewell/pricing-defaults";
import { normalizePricingConfig } from "@/lib/livewell/pricing";
import {
  saveStagedImportPricing,
  type MasterDataImportResult,
} from "@/lib/livewell/masterDataApi";
import type { SafeHomePricingConfig } from "@/lib/livewell/pricing-types";

interface MasterDataStagedPricingEditorProps {
  pending: MasterDataImportResult;
  busy: boolean;
  onSaved: (result: MasterDataImportResult) => void;
  onError: (message: string) => void;
}

export function MasterDataStagedPricingEditor({
  pending,
  busy,
  onSaved,
  onError,
}: MasterDataStagedPricingEditorProps) {
  const [config, setConfig] = useState<SafeHomePricingConfig>(
    pending.staged_pricing ?? DEFAULT_SAFEHOME_PRICING,
  );
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setConfig(pending.staged_pricing ?? DEFAULT_SAFEHOME_PRICING);
    setDirty(false);
  }, [pending.version_id, pending.staged_pricing]);

  function patch(partial: Partial<SafeHomePricingConfig>) {
    setDirty(true);
    setConfig((prev) => normalizePricingConfig({ ...prev, ...partial }));
  }

  async function handleSave() {
    setSaving(true);
    onError("");
    try {
      const result = await saveStagedImportPricing(pending.version_id, config);
      setConfig(result.staged_pricing ?? config);
      setDirty(false);
      onSaved(result);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const sourceLabel = pending.pricing_from_workbook
    ? "Loaded from sheet 09_Pricing in this workbook"
    : "Not in this workbook — showing current live rates (save to include on approve)";

  return (
    <section className="card home-safety-section" style={{ marginTop: "1.25rem" }}>
      <h2 style={{ marginTop: 0 }}>Pricing (sheet 09_Pricing)</h2>
      <p className="muted" style={{ fontSize: "0.9rem" }}>
        {sourceLabel}. Margin, labor, travel, GST, and surcharges apply to customer quotes on
        assessment review.
      </p>
      <div
        className="home-safety-sync-hint"
        style={{
          padding: "0.65rem 0.85rem",
          marginBottom: "1rem",
          fontSize: "0.88rem",
          borderLeft: "4px solid var(--color-primary, #2563eb)",
        }}
      >
        <strong>Version control:</strong> After you edit pricing here, click{" "}
        <strong>Save staged pricing</strong>, then <strong>Approve import</strong>. To keep the
        spreadsheet in sync, use <strong>Export current workbook</strong> and commit{" "}
        <code>Kushalaya_Configuration.xlsx</code> to git. Edits saved only on the{" "}
        <a href="/kushalaya/pricing">Pricing</a> page bypass import history until exported.
      </div>

      {pending.pricing_edited_in_staging && !dirty ? (
        <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
          Staged pricing saved — will apply when you approve this import.
        </p>
      ) : null}

      <div className="home-safety-rubric-admin actions" style={{ marginBottom: "1rem" }}>
        <button
          type="button"
          className="primary"
          disabled={busy || saving || !dirty}
          onClick={() => void handleSave()}
        >
          {saving ? "Saving…" : "Save staged pricing"}
        </button>
      </div>

      <PricingConfigFields config={config} onPatch={patch} disabled={busy || saving} />
    </section>
  );
}
